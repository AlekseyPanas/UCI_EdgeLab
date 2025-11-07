"""
This is a dummy process to ensure link connections are working and messages successfully broadcast to all
processes as needed
"""
from proc.proc import Process


class HelloProcess(Process):
    def _initialize_handlers(self):
        self._router.add_handler("hello", self.__hello_handler)

    def __hello_handler(self, src_pid: str, msg: str):
        self.debug(f"Received 'Hello, {msg}' from {src_pid}")
        if "back" not in msg:
            self.debug("Sending reply...")
            self._router.send([src_pid], "hello", {"msg": f"Hello back to ya from {self._pid}!"})

    """ ======================== PUBLIC =========================== """
    def say_hello_to_all(self, msg: str):
        self.debug("Sending hello to all!")
        self._router.send(self._other_pids, "hello", {"msg": msg})
