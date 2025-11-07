from router.router import Router, LocalLink
from proc.proc import Process


def create_fully_connected_local_procs(proc_class, pids: list[str], additional_params: list[dict] = None) -> dict[str, Process]:
    """
    Generate processes fully connected by local links given the process class, pids, and parameters. Takes care of
    creating the routers, links, and link connections
    """

    if additional_params is None:
        additional_params = [dict() for _ in pids]

    assert len(pids) == len(additional_params)

    procs = {}

    # Configure each process with a router and outgoing links for every process
    for i in range(len(pids)):
        pid = pids[i]
        params = additional_params[i]
        router = Router()
        for target_pid in pids:
            router.register_link(target_pid, LocalLink())
        procs[pid] = proc_class(pid, router, **params)

    # Link each process' links to corresponding other local link
    for proc in procs.values():
        links1 = proc.get_router().get_links()
        for target_pid in links1:
            local_link: LocalLink = links1[target_pid]
            local_link.set_target_link(procs[target_pid].get_router().get_links()[proc.get_pid()])

    return procs
