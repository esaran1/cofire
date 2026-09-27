"""Run a pipeline stage under the watchdog.

Each stage runs as a fresh child process (the `spawn` model: nothing is
inherited from a forked interpreter) with `OMP_NUM_THREADS` set explicitly.
The watchdog samples the child's CPU. A stage idling below 1% for five minutes
is the OpenMP deadlock this project has hit before; it is killed and resumed,
which is safe because every stage skips work it has already checkpointed. No
stage may run past 60 minutes.

    python -m cofire.ship.runner <label> -- <command...>
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

IDLE_CPU = 1.0
IDLE_SECONDS = 300
STAGE_SECONDS = 3600
POLL = 15
MAX_RESUMES = 3


def _cpu(pid: int) -> float:
    """CPU percent of the process and its children."""
    out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,%cpu="], capture_output=True, text=True).stdout
    rows = [line.split() for line in out.splitlines() if line.strip()]
    kids = {pid}
    grew = True
    while grew:
        grew = False
        for p, pp, _ in rows:
            if int(pp) in kids and int(p) not in kids:
                kids.add(int(p))
                grew = True
    return sum(float(c) for p, _, c in rows if int(p) in kids)


def run(label: str, cmd: list[str], threads: int = 4) -> int:
    env = {**os.environ, "OMP_NUM_THREADS": str(threads), "MKL_NUM_THREADS": str(threads)}
    start = time.monotonic()
    for attempt in range(MAX_RESUMES + 1):
        proc = subprocess.Popen(cmd, env=env, start_new_session=True)
        idle_since: float | None = None
        while proc.poll() is None:
            time.sleep(POLL)
            if time.monotonic() - start > STAGE_SECONDS:
                os.killpg(proc.pid, signal.SIGKILL)
                print(f"[watchdog] {label}: over {STAGE_SECONDS // 60} min, killed; split this stage", flush=True)
                return 124
            if _cpu(proc.pid) < IDLE_CPU:
                idle_since = idle_since or time.monotonic()
                if time.monotonic() - idle_since > IDLE_SECONDS:
                    os.killpg(proc.pid, signal.SIGKILL)
                    print(f"[watchdog] {label}: idle at 0% CPU for 5 min, killed; resuming", flush=True)
                    break
            else:
                idle_since = None
        else:
            rc = proc.returncode
            print(f"[watchdog] {label}: exit {rc} after {time.monotonic() - start:.0f}s "
                  f"(attempt {attempt + 1})", flush=True)
            return rc
    print(f"[watchdog] {label}: gave up after {MAX_RESUMES} resumes", flush=True)
    return 125


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--" not in args or args.index("--") != 1:
        raise SystemExit(__doc__)
    sys.exit(run(args[0], args[2:]))
