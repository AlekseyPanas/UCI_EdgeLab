from __future__ import annotations
from threading import Thread, Lock, Condition
from typing import Callable, Any
from abc import abstractmethod

#####################################################
# ------------            BASE          ----------- #
#####################################################


class ResponseAccumulator:
    @abstractmethod
    def response_handler(self, src_pid: str, *args, **kwargs):
        """When response comes in, it gets called here"""

    @abstractmethod
    def wait_for(self) -> Any:
        """Once enough replies are accumulated, reply"""


class Link:
    def __init__(self):
        self._on_receive: Callable[[dict], None] = lambda x: x

    @abstractmethod
    def reliably_send(self, payload: dict):
        """"""

    def add_on_receive(self, on_receive: Callable[[dict], None]):
        self._on_receive = on_receive


class Router:
    def __init__(self):
        self.__routes: dict[str, Link] = dict()
        self.__req_handlers: dict[str, Callable[[str, Any, ...], None]] = dict()
        self.__accumulators: dict[int, tuple[ResponseAccumulator, set[str], set[str]]] = dict()

        self.__latest_broadcast_id = 0
        self.__broadcast_id_lock = Lock()

    def __get_next_broadcast_id(self):
        self.__broadcast_id_lock.acquire()
        self.__latest_broadcast_id += 1
        broadcast_id = self.__latest_broadcast_id
        self.__broadcast_id_lock.release()
        return broadcast_id

    def get_links(self) -> dict[str, Link]:
        return self.__routes

    def send_req(self, target_pids: list[str], message_type: str, params: dict, accum: ResponseAccumulator | None = None):
        """
        Broadcast a request to one or more processes and optionally specify a response accumulator to collect
        replies
        """
        broadcast_id = self.__get_next_broadcast_id()
        if accum is not None:
            self.__accumulators[broadcast_id] = accum, set(target_pids), set()
        for pid in target_pids:
            self.__routes[pid].reliably_send({"message_type": message_type, "broadcast_id": broadcast_id, "params": params})

    def send_res(self, target_pid: str, broadcast_id: int, params: dict):
        """
        Reply to the request with the given broadcast_id from the given target_pid process
        """
        self.__routes[target_pid].reliably_send({"broadcast_id": broadcast_id, "params": params})

    def register_link(self, target_pid: str, link: Link):
        assert target_pid not in self.__routes
        self.__routes[target_pid] = link
        link.add_on_receive(lambda payload: self.__on_receive(target_pid, payload))

    def __on_receive(self, source_pid: str, payload: dict):
        # Req message
        if "message_type" in payload:
            if payload["message_type"] in self.__req_handlers:
                self.__req_handlers[payload["message_type"]](source_pid, payload["broadcast_id"], **payload["params"])

        # Res message
        else:
            if payload["broadcast_id"] in self.__accumulators:
                accum_tup = self.__accumulators[payload["broadcast_id"]]
                accum_tup[2].add(source_pid)
                accum_tup[0].response_handler(source_pid, **payload["params"])

                if accum_tup[2] == accum_tup[1]:
                    self.__accumulators.pop(payload["broadcast_id"])

    def add_handler(self, message_type: str, on_recv: Callable[[str, Any, ...], None]):
        self.__req_handlers[message_type] = on_recv

#####################################################
# ------------      IMPLEMENTATIONS     ----------- #
#####################################################


class LocalLink(Link):
    def __init__(self):
        super().__init__()
        self.__other_link = None

    def set_target_link(self, other_link: LocalLink):
        self.__other_link = other_link

    def reliably_send(self, payload: dict):
        if self.__other_link is None:
            raise Exception("Link not connected!!")
        Thread(target=self.__other_link._on_receive(payload)).start()


class CountXAcksResponseAccumulator(ResponseAccumulator):
    """
    Wait for an integer number of replies to come in and return those replies in a dictionary by pid
    """
    def __init__(self, num_acks: int):
        self.__num_acks = num_acks
        self.__replies = dict()
        self.__lock = Lock()
        self.__cond = Condition(self.__lock)
        self.__is_done = False

    def response_handler(self, src_pid: str, **kwargs):
        self.__lock.acquire()
        self.__replies[src_pid] = kwargs
        if len(self.__replies) >= self.__num_acks:
            self.__is_done = True
            self.__cond.notify_all()
        self.__lock.release()

    def wait_for(self) -> Any:
        self.__lock.acquire()
        if not self.__is_done:
            self.__cond.wait()
        temp = self.__replies
        self.__lock.release()
        return temp


class CountSpecificAcksResponseAccumulator(ResponseAccumulator):
    """
    Wait for a specified set of PIDs to reply
    """
    def __init__(self, expected_pids: set[str]):
        self.__expected_pids = expected_pids
        self.__replies = dict()
        self.__lock = Lock()
        self.__cond = Condition(self.__lock)
        self.__is_done = False

    def response_handler(self, src_pid: str, **kwargs):
        self.__lock.acquire()
        self.__replies[src_pid] = kwargs
        if self.__expected_pids.issubset(set(self.__replies.keys())):
            self.__is_done = True
            self.__cond.notify_all()
        self.__lock.release()

    def wait_for(self) -> Any:
        self.__lock.acquire()
        if not self.__is_done:
            self.__cond.wait()
        temp = self.__replies
        self.__lock.release()
        return temp
