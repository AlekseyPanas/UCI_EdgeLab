from __future__ import annotations
from abc import abstractmethod
import inspect
from router.router import Router
from threading import Lock

PRINT_LOCK = Lock()


class Process:
    def __init__(self, pid: str, router: Router):
        self._pid = pid
        self._router = router
        self._other_pids = list(self._router.get_links().keys())

        self._initialize_handlers()

    @abstractmethod
    def _initialize_handlers(self):
        pass

    def get_pid(self) -> str:
        return self._pid

    def get_router(self) -> Router:
        return self._router

    def debug(self, msg: str):
        PRINT_LOCK.acquire()
        print(f"[{self._pid}][{inspect.stack()[1][3]}] {msg}")
        PRINT_LOCK.release()
