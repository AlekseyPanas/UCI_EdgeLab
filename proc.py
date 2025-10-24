from abc import abstractmethod
import socket
from typing import Callable
import msgpack
from threading import Thread


class Link:
    def __init__(self):
        self._on_receive = lambda x: x

    @abstractmethod
    def reliably_send(self, payload: dict):
        """"""

    def add_on_receive(self, on_receive: Callable[[dict], None]):
        self._on_receive = on_receive


class LocalLink(Link):
    def __init__(self, other_link: Link):
        super().__init__()
        self.__other_link = other_link

    def reliably_send(self, payload: dict):
        thread = Thread(target=self.__other_link.)


class Router:
    def __init__(self):
        self.__routes: dict[str, Link] = dict()
        self.__handlers: dict[str, Callable[[str, dict], None]] = dict()

    def __on_receive(self, source_pid: str, payload: dict):
        if payload["message_type"] in self.__handlers:
            self.__handlers[payload["message_type"]](source_pid, payload["params"])

    def register_link(self, pid: str, link: Link):
        assert pid not in self.__routes
        self.__routes[pid] = link
        link.add_on_receive(lambda payload: self.__on_receive(pid, payload))

    @abstractmethod
    def send(self, target_pids: list[str], message_type: str, params: dict):
        for pid in target_pids:
            self.__routes[pid].reliably_send({"message_type": message_type, "params": params})

    @abstractmethod
    def add_handler(self, message_type: str, on_recv: Callable[[str, dict], None]):
        self.__handlers[message_type] = on_recv



class Process:
    def __init__(self, pid: str, pids: list[str], leader_pid: str):
        self.__pid = pid
        self.__pids = pids
        self.__leader_pid = leader_pid
        self.__is_leader = pid == leader_pid
        self.__n = len(self.__pids)

    def
