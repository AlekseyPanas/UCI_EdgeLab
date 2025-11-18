"""
Assumptions:
- Async model
- Non-byzantine
    - TODO: Incorporate byzantine? (e.g process rejecting all requests just for fun)
- No failures
    - TODO: Include failures
- Fixed topology
    - TODO: Add reconfig (changing topology)
- All processes aware of topology
    - TODO: Add topology discovery and agreement
- Fixed leader
    - TODO: Remove fixed leader
- Fixed constraints
    - TODO: Add constraint modification at runtime
            - SLN: Local rejection of value if does not satisfy local constraints
- No relaxable constraints
    - TODO: Add relaxable constraints
- All constraints provided immediately (stateless)
    - TODO: Incorporate state to learn the user
- Constraints provided in mathematical form
    - TODO: Incorporate LLMs
- CSP related to choosing one compact time future interval of 2 hours long among constraints which block occupied intervals (unix timestamp used)
    - TODO: Extend time CSP to include movable blocked intervals and free time limitations (e.g I'd
        like to go to the gym for 3 hours this week, weekends Im free only 2 hours each day, etc)
    - TODO: Extend CSP to work with infinitely repeating constraints (e.g must be during daytime)
    - TODO: Extend CSP to specify a custom interval (what happens if processes disagree?)
    - TODO: Extend CSP to any value type

- TODO: Adding reward function to value (e.g among all satisfied values, the earlier it is, the higher the reward. Maximize reward)

Every process outputs:
- same v (consensus)
- v satisfies all constraints (csp)

Implementation details:
- Paxos consensus layer
- Constraints sent to leader immediately
- Leader waits for all processes to send constraints
- Leader solves CSP locally and proposes a valid value
- Done

TODO: Additional ping ponging comes from
    TODO: Compromise as a function of others (Ill only relax if others do)
    TODO: Dont know weaker constraints ahead of time
    TODO: Ping pong to debate who will relax

    TODO: Size of transfer and privacy
Heatmap of venn diagrams (i.e each point in decision space for each process has a score of how desirable it is +
    second heatmap is a compromise layer (weights)

Normalization of penalties across LLMs is pairwise communication, i.e who should relax
"""
import datetime

from proc.proc import Process
from router.router import Router
from threading import Lock, Condition
import time


class ConstrainedConsensusProc(Process):
    MSG_CONSTRAINTS = "constraints"
    MSG_PROPOSE = "propose"

    def __init__(self, pid: str, router: Router, pids: list[str], leader_pid: str):
        super().__init__(pid, router)
        self._all_pids = pids
        self._leader_pid = leader_pid
        self._is_leader = self._pid == leader_pid
        self._n = len(self._all_pids)

        self.__constraints = set()
        self.__desired_interval = 0.5 * 60 * 60
        self.__received_pids = set()

        self.__lock = Lock()
        self.__condition = Condition(self.__lock)
        self.__v = None

        self.__proposed_lock = Lock()
        self.__proposed = False

    def _initialize_handlers(self):
        self._router.add_handler(self.MSG_CONSTRAINTS, self.__constraints_handler)
        self._router.add_handler(self.MSG_PROPOSE, self.__propose_handler)

    def __constraints_handler(self, src_pid: str, constraints: list[float, float]):
        for c in constraints:
            self.__constraints.add(c)
        self.__received_pids.add(src_pid)
        self.debug(f"Received constraints {constraints} from {src_pid}")

        self.__proposed_lock.acquire()
        if len(self.__received_pids) == self._n and not self.__proposed:
            self.__proposed = True
            self.debug(f"All constraints received! Solving CSP and broadcasting proposal...")
            self._router.send(self._all_pids, self.MSG_PROPOSE, {"time_range_val": self.__solve_csp()})
        self.__proposed_lock.release()

    def __propose_handler(self, src_pid: str, time_range_val: tuple[float, float]):
        self.debug(f"Received proposal from {src_pid} with value {time_range_val}")
        self.__v = time_range_val
        self.__lock.acquire()
        self.__condition.notify_all()
        self.__lock.release()

    def __solve_csp(self) -> tuple[float, float]:
        cur_time = time.time()
        srt_constraints = self.__constraints

        while True:
            srt_constraints = sorted(srt_constraints)

            if len(srt_constraints) == 0 or (srt_constraints[0][0] - cur_time) >= self.__desired_interval:
                result = (cur_time, cur_time + self.__desired_interval)
                self.debug(f"Solved CSP with value {result}")
                return result

            cur_time = srt_constraints[0][1] + 0.01
            while True:
                if len(srt_constraints) and srt_constraints[0][1] <= cur_time:
                    srt_constraints.pop(0)
                else:
                    break

    """ ======================== PUBLIC =========================== """

    def agree_on_value(self, constraints: list[float, float]):
        self.debug(f"Received client request with {constraints}, sending to Leader {self._leader_pid}")
        self._router.send([self._leader_pid], self.MSG_CONSTRAINTS, {"constraints": constraints})

        self.debug(f"Waiting for value...")
        if self.__v is None:
            self.__lock.acquire()
            self.__condition.wait()
            self.__lock.release()
        self.debug(f"Returning value {self.__v}")

        return self.__v
