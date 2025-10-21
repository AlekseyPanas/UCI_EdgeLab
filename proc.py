from abc import abstractmethod
import socket
from typing import Callable
import msgpack

# TODO: Add link


class Network:
    @abstractmethod
    def send(self, target_pids: list[str], message_type: str, payload: dict):
        pass

    @abstractmethod
    def add_handler(self, message_type: str, on_recv: Callable[[str, dict], None]):
        pass


class LocalNetwork(Network):
    def __init__(self):
        pass

    def send(self, target_pids: list[str], message_type: str, payload: dict):
        pass

    def add_handler(self, message_type: str, on_recv: Callable[[str, dict], None]):
        pass


class Process:
    def __init__(self, pid: str, pids: list[str], leader_pid: str):
        self.__pid = pid
        self.__pids = pids
        self.__leader_pid = leader_pid
        self.__is_leader = pid == leader_pid
        self.__n = len(self.__pids)

    def
