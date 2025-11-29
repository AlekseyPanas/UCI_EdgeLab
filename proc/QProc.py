from proc.proc import Process
from router.router import Router
from typing import Any
from threading import Lock, Condition
from abc import abstractmethod


class ChoiceEngine:
    @abstractmethod
    def get_choices(self, D: Any) -> tuple[Any, Any]:
        """Given a choice set D defined in the manner expected by this engine, return a set of choices given
        current context state and return relevant perception context when making the choice"""

    @abstractmethod
    def add_context(self, src_pid: str, context: Any):
        """In the manner defined by this engine, a process provides some context. This context can be choice-specific,
        or choice-independent, as this engine allows"""

    @abstractmethod
    def compute_intersection(self, choice_sets: set[Any]) -> Any:
        """Given a set of sets of choices, compute their intersection"""

    @abstractmethod
    def largest_intersecting_subset(self, choice_sets: set[Any]) -> list[tuple[Any, set[Any]]]:
        """Given a set of sets of choices, compute the largest subset of choice sets which has a non-zero intersection,
        or multiple if there is a tie"""

    @abstractmethod
    def is_choice_set_empty(self, choices: Any):
        """Determine if the given set of choices is empty"""

    @abstractmethod
    def is_subset(self, choices: Any, of_choices: Any):
        """Return if choices is a subset of of_choices"""


class QProc(Process):
    M_GET_CHOICES = "GCH"
    M_GET_CHOICES_RES = "GCH_res"
    M_COMMIT = "CM"
    M_INIT_PER_EXC = "IPEX"
    M_INIT_PER_EXC_RES = "IPEX_res"
    M_PER_EXC = "PEX"
    M_PER_EXC_RES = "PEX_res"

    def __init__(self, pid: str, router: Router, pids: list[str], leader_pid: str, choice_engine: ChoiceEngine):
        super().__init__(pid, router)
        self._engine = choice_engine
        self._D = None
        self._leader_pid = leader_pid
        self._pids = pids
        self._N = len(self._pids)
        self._is_leader = self._pid == leader_pid

        self._D_lock = Lock()
        self._D_cond = Condition(self._D_lock)

        self._choices_reply_set = set()
        self._waiting_choices = False
        self._waiting_choices_lock = Lock()
        self._waiting_choices_cond = Condition(self._waiting_choices_lock)
        self._replied_choices = set()

        self._perception_exchange_init_ack_set = set()
        self._waiting_perception_init_exchange = False
        self._waiting_perception_init_exchange_lock = Lock()
        self._waiting_perception_init_exchange_cond = Condition(self._waiting_perception_init_exchange_lock)

        self._perception_exchange_ack_set = set()
        self._waiting_perception_exchange = False
        self._waiting_perception_exchange_lock = Lock()
        self._waiting_perception_exchange_cond = Condition(self._waiting_perception_exchange_lock)

        self._final_choices = None
        self._final_choices_lock = Lock()
        self._final_choices_cond = Condition(self._final_choices_lock)

        self._latest_choices = None
        self._latest_choices_context = None

    def _initialize_handlers(self):
        self.get_router().add_handler(QProc.M_GET_CHOICES, self._get_choices_req_handler)
        self.get_router().add_handler(QProc.M_GET_CHOICES_RES, self._get_choices_res_handler)
        self.get_router().add_handler(QProc.M_COMMIT, self._commit_handler)
        self.get_router().add_handler(QProc.M_INIT_PER_EXC, self._init_perception_exchange_handler)
        self.get_router().add_handler(QProc.M_INIT_PER_EXC_RES, self._init_perception_exchange_res_handler)
        self.get_router().add_handler(QProc.M_PER_EXC, self._perception_exchange_handler)
        self.get_router().add_handler(QProc.M_PER_EXC_RES, self._perception_exchange_res_handler)

    def _wait_for_D(self):
        self._D_lock.acquire()
        self._D_cond.wait()
        self._D_lock.release()

    def _broadcast_get_choices(self):
        while True:
            input("Press ENTER to start next round...")

            if self._is_leader:
                # Ask everyone to return their choices and wait for replies
                self._waiting_choices_lock.acquire()
                self._waiting_choices = True
                self.get_router().send(self._pids, QProc.M_GET_CHOICES, dict())
                self._waiting_choices_cond.wait()
                self._waiting_choices_lock.release()

                # Compute the intersection of everyone's choices
                common_choices = self._engine.compute_intersection(self._replied_choices)

                # Commit if intersection is not empty
                if not self._engine.is_choice_set_empty(common_choices):
                    self.get_router().send(self._pids, QProc.M_COMMIT, {"choices": common_choices})
                    break

                # Otherwise for each set
                # TODO: Issue here if proc receives multiple requests to share, fix it by unioning all proc sets
                else:
                    for common2, _ in self._engine.largest_intersecting_subset(self._replied_choices):
                        self._waiting_perception_init_exchange = True
                        self._waiting_perception_init_exchange_lock.acquire()
                        self.get_router().send(self._pids, QProc.M_INIT_PER_EXC, {"choices": common2})
                        self._waiting_perception_init_exchange_cond.wait()
                        self._waiting_perception_init_exchange_lock.release()

    def _get_choices_req_handler(self, src_pid: str):
        self._wait_for_D()

        self._latest_choices, self._latest_choices_context = self._engine.get_choices(self._D)
        self.get_router().send([src_pid], QProc.M_GET_CHOICES_RES, {"choices": self._latest_choices})

    def _commit_handler(self, src_pid: str, choices: Any):
        self._final_choices_lock.acquire()
        self._final_choices = choices
        self._final_choices_cond.notify_all()
        self._final_choices_lock.release()

    def _init_perception_exchange_handler(self, src_pid: str, choices: Any):
        if self._engine.is_subset(choices, self._latest_choices):
            self._waiting_perception_exchange_lock.acquire()
            self._waiting_perception_exchange = True
            self.get_router().send(self._pids, QProc.M_PER_EXC, {"context": self._latest_choices_context})
            self._waiting_perception_exchange_cond.wait()
            self._waiting_perception_exchange_lock.release()
        self.get_router().send([src_pid], QProc.M_INIT_PER_EXC_RES, dict())

    def _perception_exchange_handler(self, src_pid: str, context: Any):
        self._engine.add_context(src_pid, context)
        self.get_router().send([src_pid], QProc.M_PER_EXC_RES, dict())

    def _perception_exchange_res_handler(self, src_pid: str):
        self._waiting_perception_exchange_lock.acquire()
        self._perception_exchange_ack_set.add(src_pid)
        if self._waiting_perception_exchange and len(self._perception_exchange_ack_set) == len(self._pids):
            self._waiting_perception_exchange = False
            self._perception_exchange_ack_set = set()
            self._waiting_perception_exchange_cond.notify_all()
        self._waiting_perception_exchange_lock.release()

    def _init_perception_exchange_res_handler(self, src_pid: str):
        self._waiting_perception_init_exchange_lock.acquire()
        self._perception_exchange_init_ack_set.add(src_pid)
        if self._waiting_perception_init_exchange and len(self._perception_exchange_init_ack_set) == len(self._pids):
            self._waiting_perception_init_exchange = False
            self._perception_exchange_init_ack_set = set()
            self._waiting_perception_init_exchange_cond.notify_all()
        self._waiting_perception_init_exchange_lock.release()

    def _get_choices_res_handler(self, src_pid: str, choices: Any):
        self._waiting_choices_lock.acquire()
        self._choices_reply_set.add(src_pid)
        self._replied_choices.add(choices)
        if len(self._choices_reply_set) == len(self._pids) and self._waiting_choices:
            self._choices_reply_set = set()
            self._waiting_choices = False
            self._waiting_choices_cond.notify_all()
        self._waiting_choices_lock.release()

    """============== PUBLIC =============="""
    def inject_D(self, D: Any):
        self._D = D

        self._D_lock.acquire()
        self._D_cond.notify_all()
        self._D_lock.release()

    def await_final_choices(self) -> Any:
        self._final_choices_lock.acquire()
        if self._final_choices is not None:
            temp = self._final_choices
        else:
            self._final_choices_cond.wait()
            temp = self._final_choices
        self._final_choices_lock.release()
        return temp
