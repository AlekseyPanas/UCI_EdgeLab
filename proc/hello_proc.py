"""
This is a dummy process to ensure link connections are working and messages successfully broadcast to all
processes as needed
"""
from typing import Any

from proc.proc import Process
from router.router import ResponseAccumulator, CountXAcksResponseAccumulator


class HelloProcess(Process):
    M_SAY_HELLO = "hello"

    def _initialize_handlers(self):
        self._router.add_handler("hello", self.__hello_handler)

    def __hello_handler(self, src_pid: str, broadcast_id: int, msg: str):
        self.debug(f"Received 'Hello, {msg}' from {src_pid} with broadcast_id {broadcast_id}. Replying...")
        self._router.send_res(src_pid, broadcast_id, {"msg": "Hello back at ya!"})

    """ ======================== PUBLIC =========================== """
    def say_hello_to_all(self, msg: str):
        self.debug("Sending hello to all!")
        count_all = CountXAcksResponseAccumulator(len(self._other_pids))
        self._router.send_req(self._other_pids, HelloProcess.M_SAY_HELLO, {"msg": msg}, count_all)
        replies = count_all.wait_for()
        for pid in replies:
            self.debug(f"{pid} replied with {replies[pid]}")
