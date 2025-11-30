import math

from experiments_tests.local_util import create_fully_connected_local_procs
from router.router import Router, LocalLink
from proc.hello_proc import HelloProcess
from proc.constrained_consensus_proc import ConstrainedConsensusProc
from proc.QProc import QProc, DiscreteLLMContextEngine
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from threading import Thread, Lock, Condition
from visualization.interval_visualizer import IntervalVisualizer
from util.util import do_intervals_intersect
import time


def hello_test():
    """
    Test that router and local link code works by broadcasting messages and replies
    """

    # Configure each process with a router and outgoing links for every process
    PIDS = ["0", "1", "3"]
    PROCS = create_fully_connected_local_procs(HelloProcess, PIDS)

    for proc in PROCS.values():
        proc: HelloProcess
        proc.say_hello_to_all(f"Sup bro, this is yo homie {proc.get_pid()}")


def constrained_test():
    PIDS = ["0", "1", "2"]
    PROCS: dict[str, ConstrainedConsensusProc] = create_fully_connected_local_procs(ConstrainedConsensusProc, PIDS, [{"pids": PIDS, "leader_pid": "0"}] * len(PIDS))

    tz = ZoneInfo("America/Los_Angeles")
    now = datetime.now(tz=tz)

    def h(hours: float) -> timedelta:
        return timedelta(hours=hours)

    # helper to make tuple ranges relative to 'now'
    def range_h(start_h: float, end_h: float):
        return now + h(start_h), now + h(end_h)

    proc0_blocks = [
        range_h(0, 2),
        range_h(3, 6),  # 3–6h from now
        range_h(8, 10),  # 8–10h
        range_h(13, 15),  # 13–15h
        range_h(20, 22),  # 20–22h
        range_h(26, 30),  # 1+ day-ish block for stress
    ]

    proc1_blocks = [
        range_h(0, 2),
        range_h(4, 7),  # overlaps with proc0 3–6
        range_h(9, 11),  # overlaps with proc0 8–10 slightly
        range_h(12, 14),  # near proc0 13–15
        range_h(18, 20),  # evening block
        range_h(28, 31),  # later multi-hour block
    ]

    proc2_blocks = [
        range_h(0, 2),
        range_h(2, 5),  # starts earlier, overlaps many
        range_h(7, 9),  # gaps around 6–7 and 9–10
        range_h(11, 13),  # sits before proc1's 12–14
        range_h(16, 18),  # mid-evening
        range_h(24, 27),  # ~next-day block
    ]

    def dates_to_unix(dates: list[tuple[datetime, datetime]]):
        return [(d[0].timestamp(), d[1].timestamp()) for d in dates]

    count = 0
    outputs = dict()
    lock = Lock()
    cond = Condition(lock)

    c0 = dates_to_unix(proc0_blocks)
    c1 = dates_to_unix(proc1_blocks)
    c2 = dates_to_unix(proc2_blocks)

    def execute(pid, constraints):
        nonlocal count
        v = PROCS[pid].agree_on_value(constraints)
        lock.acquire()
        outputs[pid] = v
        count += 1
        if count >= len(PIDS):
            cond.notify_all()
        lock.release()

    Thread(target=execute, args=["0", c0]).start()
    Thread(target=execute, args=["1", c1]).start()
    Thread(target=execute, args=["2", c2]).start()

    lock.acquire()
    cond.wait()
    lock.release()

    print(f"Returned values: {outputs}")
    # Checks if all values in list are approximately equal (consensus)
    vals = list(outputs.values())
    for i in range(len(outputs) - 1):
        assert math.isclose(vals[i][0], vals[i+1][0])
        assert math.isclose(vals[i][1], vals[i+1][1])

    vis = IntervalVisualizer(c0 + c1 + c2 + [(vals[0][0], vals[0][1], (0, 0, 255))] + [(-math.inf, time.time(), (0, 150, 0))])
    vis.run()


def qproc_engine_test():
    engine = DiscreteLLMContextEngine()
    print(engine.largest_intersecting_subsets([frozenset({"1", "2"}), frozenset({"2", "3"}), frozenset({"4"})]))


if __name__ == "__main__":
    qproc_engine_test()
