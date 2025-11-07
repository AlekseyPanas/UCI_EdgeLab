from __future__ import annotations
from threading import Thread
from typing import Callable, Any
from abc import abstractmethod

#####################################################
# ------------            BASE          ----------- #
#####################################################


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
        self.__handlers: dict[str, Callable[[str, Any, ...], None]] = dict()

    def get_links(self) -> dict[str, Link]:
        return self.__routes

    def __on_receive(self, source_pid: str, payload: dict):
        if payload["message_type"] in self.__handlers:
            self.__handlers[payload["message_type"]](source_pid, **payload["params"])

    def register_link(self, target_pid: str, link: Link):
        assert target_pid not in self.__routes
        self.__routes[target_pid] = link
        link.add_on_receive(lambda payload: self.__on_receive(target_pid, payload))

    def send(self, target_pids: list[str], message_type: str, params: dict):
        for pid in target_pids:
            self.__routes[pid].reliably_send({"message_type": message_type, "params": params})

    def add_handler(self, message_type: str, on_recv: Callable[[str, Any, ...], None]):
        self.__handlers[message_type] = on_recv

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
