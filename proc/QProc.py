from proc.proc import Process
from router.router import Router, CountXAcksResponseAccumulator, ResponseAccumulator, CountSpecificAcksResponseAccumulator
from typing import Any
from threading import Lock, Condition
from abc import abstractmethod
import ollama
import itertools


class ChoiceEngine:
    @abstractmethod
    def get_choices(self) -> tuple[Any, Any]:
        """From the internally injected choice set D defined in the manner expected by this engine, return a set of choices given
        current context state and return relevant perception context when making the choice"""

    @abstractmethod
    def add_context(self, src_pid: str, context: Any, choices: Any):
        """In the manner defined by this engine, a process provides some context. This context can be choice-specific,
        or choice-independent, as this engine allows. This context comes as a way for src_pid to convince this
        process that their choice is better. This includes the choices this process made during this round,
        regardless of what the context applies to"""

    # TODO: Consider having leader share which groups of choices were largely chosen, and the quorum. This is useful context for making local decisions

    @abstractmethod
    def compute_intersection(self, choice_sets: set[Any]) -> Any:
        """Given a set of sets of choices, compute their intersection"""

    @abstractmethod
    def largest_intersecting_subsets(self, choice_sets: list[Any]) -> list[tuple[Any, set[int]]]:
        """Given a list of choice sets, compute the largest subset of choice sets which has a non-zero intersection,
        or multiple if there is a tie. Return tuples of (intersection, set of indexes specifying subset)"""

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
        self._leader_pid = leader_pid
        self._pids = pids
        self._N = len(self._pids)
        self._is_leader = self._pid == leader_pid

        self._final_choices = None
        self._final_choices_lock = Lock()
        self._final_choices_cond = Condition(self._final_choices_lock)

        self._latest_choices = None
        self._latest_choices_context = None

    def _initialize_handlers(self):
        self.get_router().add_handler(QProc.M_GET_CHOICES, self._get_choices_req_handler)
        self.get_router().add_handler(QProc.M_COMMIT, self._commit_handler)
        self.get_router().add_handler(QProc.M_INIT_PER_EXC, self._init_perception_exchange_handler)
        self.get_router().add_handler(QProc.M_PER_EXC, self._perception_exchange_handler)

    def _broadcast_get_choices(self):
        rnd = 0
        while True:
            input("Press ENTER to start next round...")
            rnd += 1

            if self._is_leader:
                # Ask everyone to return their choices and wait for replies
                await_all = CountXAcksResponseAccumulator(self._N)
                self.get_router().send_req(self._pids, QProc.M_GET_CHOICES, dict(), await_all)
                pid_to_choices_dict = await_all.wait_for()
                pid_to_choices_dict = {pid: pid_to_choices_dict[pid]["choices"] for pid in pid_to_choices_dict}

                # Compute the intersection of everyone's choices
                common_choices = self._engine.compute_intersection(set(pid_to_choices_dict.values()))

                # Commit if intersection is not empty
                if not self._engine.is_choice_set_empty(common_choices):
                    self.get_router().send_req(self._pids, QProc.M_COMMIT, {"choices": common_choices})
                    break
                # TODO: Fix this, currently naively terminates with an empty choice set after 5 rounds
                elif rnd >= 5:
                    self.get_router().send_req(self._pids, QProc.M_COMMIT, {"choices": common_choices})
                    break

                # Otherwise find largest subsets of choice replies which intersect (multiple if tied), union them,
                # and ask all relevant procs to share their perceptions with everyone else. Wait for them to share their
                # perceptions. Then proceed to next round
                else:
                    pids = list(pid_to_choices_dict.keys())
                    choices_set = [pid_to_choices_dict[p] for p in pids]
                    relevant_pids = {pids[i] for _, idxs in self._engine.largest_intersecting_subsets(choices_set) for i in idxs}
                    await_relevant = CountSpecificAcksResponseAccumulator(relevant_pids)
                    self.get_router().send_req(list(relevant_pids), QProc.M_INIT_PER_EXC, dict(), await_relevant)
                    await_relevant.wait_for()

    def _get_choices_req_handler(self, src_pid: str, broadcast_id: int):
        self._latest_choices, self._latest_choices_context = self._engine.get_choices()
        self.get_router().send_res(src_pid, broadcast_id, {"choices": self._latest_choices})

    def _commit_handler(self, src_pid: str, choices: Any):
        # We are done! Save the final decided choice set and notify anyone waiting
        self._final_choices_lock.acquire()
        self._final_choices = choices
        self._final_choices_cond.notify_all()
        self._final_choices_lock.release()

    def _init_perception_exchange_handler(self, src_pid: str, broadcast_id: int):
        # Send my perception to everyone except myself, wait for ACKs, then ACK to leader that I'm done sharing perception
        await_all = CountXAcksResponseAccumulator(self._N - 1)
        self.get_router().send_req(self._other_pids, QProc.M_PER_EXC, {"context": self._latest_choices_context, "choices": self._latest_choices}, await_all)
        await_all.wait_for()
        self.get_router().send_res(src_pid, broadcast_id, dict())

    def _perception_exchange_handler(self, src_pid: str, broadcast_id: int, context: Any, choices: Any):
        # Add the provided context to my choice engine and ACK the context sender
        self._engine.add_context(src_pid, context, choices)
        self.get_router().send_res(src_pid, broadcast_id, dict())

    """============== PUBLIC =============="""
    def start(self):
        if self._is_leader:
            self._broadcast_get_choices()

    def await_final_choices(self) -> Any:
        self._final_choices_lock.acquire()
        if self._final_choices is not None:
            temp = self._final_choices
        else:
            self._final_choices_cond.wait()
            temp = self._final_choices
        self._final_choices_lock.release()
        return temp


class DiscreteLLMContextEngine(ChoiceEngine):
    """This engine assumes D is a discrete set of choices, and that LLMs are used to evaluate Q values
    using association and sensory concepts as described in the research doc"""

    def __init__(self, D: frozenset[str], self_description: str):
        self.__D = D
        self.__self_description = self_description

    def get_choices(self) -> tuple[Any, Any]:

        context = {"choice_specific": {}, "self_description": self.__self_description}

    def add_context(self, src_pid: str, context: Any, choices: set[str]):
        pass

    def compute_intersection(self, choice_sets: set[frozenset[str]]) -> set[str]:
        choice_sets = list(choice_sets)
        accum = choice_sets[0]
        for i in range(1, len(choice_sets)):
            accum = accum.intersection(choice_sets[i])
        return accum

    def largest_intersecting_subsets(self, choice_sets: list[frozenset[str]]) -> list[tuple[set[str], set[int]]]:
        done = False
        output = []
        for i in range(len(choice_sets), 0, -1):
            # Every combination of size i
            for comb in itertools.combinations(range(len(choice_sets)), i):
                comb_choice_set = {choice_sets[j] for j in comb}
                common = self.compute_intersection(comb_choice_set)
                if not self.is_choice_set_empty(common):
                    done = True
                    output.append((common, set(comb)))
            if done:
                break
        return output

    def is_choice_set_empty(self, choices: set[str]):
        return len(choices) == 0

    def is_subset(self, choices: set[str], of_choices: set[str]):
        return choices.issubset(of_choices)



