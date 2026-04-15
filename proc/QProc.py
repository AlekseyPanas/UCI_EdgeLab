from proc.proc import Process
from router.router import Router, CountXAcksResponseAccumulator, ResponseAccumulator, CountSpecificAcksResponseAccumulator
from typing import Any
from threading import Lock, Condition
from abc import abstractmethod
import ollama
import itertools
import os


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

    def __init__(self, pid: str, router: Router, leader_pid: str, choice_engine: ChoiceEngine):
        super().__init__(pid, router)
        self._engine = choice_engine
        self._leader_pid = leader_pid
        self._pids = list(self._router.get_links().keys())
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
            # input("Press ENTER to start next round...")
            rnd += 1
            self.debug(f"Starting round {rnd}")

            if self._is_leader:
                # Ask everyone to return their choices and wait for replies
                await_all = CountXAcksResponseAccumulator(self._N)
                self.get_router().send_req(self._pids, QProc.M_GET_CHOICES, dict(), await_all)
                self.debug(f"Broadcasted M_GET_CHOICES request, waiting for replies from all...")
                pid_to_choices_dict = await_all.wait_for()
                pid_to_choices_dict = {pid: pid_to_choices_dict[pid]["choices"] for pid in pid_to_choices_dict}

                # Compute the intersection of everyone's choices
                common_choices = self._engine.compute_intersection(set(pid_to_choices_dict.values()))
                self.debug(f"Got replies! {pid_to_choices_dict}")
                self.debug(f"Computed intersection! {common_choices}")

                # Commit if intersection is not empty
                if not self._engine.is_choice_set_empty(common_choices):
                    self.debug(f"Sending commit to all... {common_choices}")
                    self.get_router().send_req(self._pids, QProc.M_COMMIT, {"choices": common_choices})
                    break
                # TODO: Fix this, currently naively terminates with an empty choice set after 5 rounds
                elif rnd >= 5:
                    self.debug(f"No consensus reached after 5 rounds, committing empty set {common_choices}")
                    self.get_router().send_req(self._pids, QProc.M_COMMIT, {"choices": common_choices})
                    break

                # Otherwise find largest subsets of choice replies which intersect (multiple if tied), union them,
                # and ask all relevant procs to share their perceptions with everyone else. Wait for them to share their
                # perceptions. Then proceed to next round
                else:
                    self.debug(f"No consensus, sending M_INIT_PER_EXC to exchange perceptions...")
                    await_all = CountXAcksResponseAccumulator(len(self._pids))
                    self.get_router().send_req(self._pids, QProc.M_INIT_PER_EXC, dict(), await_all)
                    await_all.wait_for()
                    self.debug(f"Perception exchange complete!")

    def _get_choices_req_handler(self, src_pid: str, broadcast_id: int):
        self._latest_choices, self._latest_choices_context = self._engine.get_choices()
        self.debug(f"Computed choices {self._latest_choices} with context {self._latest_choices_context}, replying...")
        self.get_router().send_res(src_pid, broadcast_id, {"choices": self._latest_choices})

    def _commit_handler(self, src_pid: str, broadcast_id: int, choices: Any):
        # We are done! Save the final decided choice set and notify anyone waiting
        self._final_choices_lock.acquire()
        self._final_choices = choices
        self._final_choices_cond.notify_all()
        self._final_choices_lock.release()
        self.debug(f"Commited {choices}!")

    def _init_perception_exchange_handler(self, src_pid: str, broadcast_id: int):
        # Send my perception to everyone except myself, wait for ACKs, then ACK to leader that I'm done sharing perception
        self.debug(f"Broadcasting own perception context: {self._latest_choices_context}, choices: {self._latest_choices}")
        await_all = CountXAcksResponseAccumulator(self._N - 1)
        self.get_router().send_req(self._other_pids, QProc.M_PER_EXC, {"context": self._latest_choices_context, "choices": self._latest_choices}, await_all)
        await_all.wait_for()
        self.debug(f"Everyone ACKed my perception broadcast! Replying to leader...")
        self.get_router().send_res(src_pid, broadcast_id, dict())

    def _perception_exchange_handler(self, src_pid: str, broadcast_id: int, context: Any, choices: Any):
        # Add the provided context to my choice engine and ACK the context sender
        self._engine.add_context(src_pid, context, choices)
        self.debug(f"Context {context} from {src_pid} added, replying to perception exchange...")
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


class PreferenceOrderEngine(ChoiceEngine):
    """
    Everyone ranks choices from 0 to len(choices). Context is this ranking. Choice is the lowest sum of rankings
    across accumulated contexts. This engine is meant to converge in the non-byzantine setting at worst in the second
    round, making it good for testing the surrounding code
    """
    def __init__(self, D: frozenset[str], preference_order: list[str], own_pid: str):
        self.__D = D
        self.__preference_orders: dict[str, list[str]] = dict()
        self.__preference_orders[own_pid] = preference_order
        self.__own_pid = own_pid

    def get_choices(self) -> tuple[frozenset[str], list[str]]:
        summed_orders = dict()
        for pid in self.__preference_orders:
            for i in range(len(self.__preference_orders[pid])):
                choice_val = self.__preference_orders[pid][i]
                if choice_val not in summed_orders:
                    summed_orders[choice_val] = 0
                summed_orders[choice_val] += i
        min_choice_sum = min(summed_orders.values())
        choices = [c for c in summed_orders if summed_orders[c] == min_choice_sum]
        print(f"get_choices computation: SUMMED_ORDERS: {summed_orders}, PREFERENCE_ORDERS: {self.__preference_orders}, CHOICES: {choices}")
        return frozenset(choices), self.__preference_orders[self.__own_pid]

    def add_context(self, src_pid: str, context: list[str], choices: frozenset[str]):
        self.__preference_orders[src_pid] = context

    def compute_intersection(self, choice_sets: set[frozenset[str]]) -> frozenset[str]:
        choice_sets_list = list(choice_sets)
        cur_choice_set = choice_sets_list[0]
        for i in range(1, len(choice_sets_list)):
            cur_choice_set = cur_choice_set.intersection(choice_sets_list[i])
        return cur_choice_set

    def largest_intersecting_subsets(self, choice_sets: list[frozenset[str]]) -> list[tuple[frozenset[str], set[int]]]:
        pass

    def is_choice_set_empty(self, choices: frozenset[str]):
        return len(choices) == 0

    def is_subset(self, choices: frozenset[str], of_choices: frozenset[str]):
        return of_choices.issubset(choices)


class DiscreteLLMContextEngine(ChoiceEngine):
    """This engine assumes D is a discrete set of choices, and that LLMs are used to evaluate Q values
    using association and sensory concepts as described in the research doc"""
    PROMPT_PATH = os.path.join(os.getcwd(), "z_prompts/QProcDiscreteLLMContextEngine")

    def __init__(self, D: frozenset[str], self_description: str, public_self_description: str):
        self.__D = D
        self.__self_description = self_description
        self.__public_self_description = public_self_description
        with open(self.PROMPT_PATH, "r") as file:
            self.__prompt = file.read()
        self.__contexts = dict()

    def get_choices(self) -> tuple[Any, Any]:

        context = {"choice_specific": {}, "self_description": self.__self_description}

    def add_context(self, src_pid: str, context: dict[str, str], choices: set[str]):
        if src_pid in self.__contexts:
            self.__contexts[src_pid] += context

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



