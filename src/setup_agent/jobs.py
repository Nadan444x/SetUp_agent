"""Detached background install jobs — fire and forget.

install_background spawns each install as a DETACHED Windows process (`setup-agent runjob <id>`),
so the installs keep running even after the CLI exits.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from .safety import _env_with_brew

JOBS_DIR = Path.home() / ".setup-agent" / "jobs"
LOGS_DIR = Path.home() / ".setup-agent" / "logs"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class Job:
    id: str
    label: str
    argv: list[str]
    status: str = "running"          # running | done | failed
    kind: str = "winget"
    token: str = ""
    pid: int | None = None
    returncode: int | None = None
    started_at: str = field(default_factory=_now)
    ended_at: str = ""
    log_path: str = ""

    def is_active(self) -> bool:
        return self.status == "running"


def _alive(pid: int | None) -> bool:
    if not pid:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True
    return True


def job_running(job: Job) -> bool:
    return job.status == "running" and _alive(job.pid)


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _persist(job: Job) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    path = _job_path(job.id)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(asdict(job), indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load_job(job_id: str) -> Job | None:
    try:
        return Job(**json.loads(_job_path(job_id).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def _notify(title: str, message: str) -> None:
    from .notify import notify
    notify(title, message)


class JobManager:
    def __init__(self) -> None:
        self._spawned: list[str] = []
        self._reported: set[str] = set()

    def active_tokens(self) -> set[str]:
        out: set[str] = set()
        for jid in self._spawned:
            j = load_job(jid)
            if j and job_running(j) and j.token:
                out.add(f"{j.kind}:{j.token}")
        for d in load_persisted_jobs():
            if d.get("status") == "running" and d.get("token") and _alive(d.get("pid")):
                out.add(f"{d.get('kind')}:{d.get('token')}")
        return out

    def spawn_detached(self, label: str, argv: list[str], kind: str = "winget", token: str = "") -> Job:
        from .state import profile_path

        job = Job(id=uuid.uuid4().hex[:8], label=label, argv=list(argv), kind=kind, token=token)
        job.log_path = str(LOGS_DIR / f"{job.id}.log")
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        _persist(job)
        self._spawned.append(job.id)

        env = _env_with_brew()
        env["SETUP_AGENT_PROFILE"] = str(profile_path())

        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)

        proc = subprocess.Popen(
            [sys.executable, "-m", "setup_agent.cli", "runjob", job.id],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=creationflags, env=env,
        )
        job.pid = proc.pid
        _persist(job)
        return job

    def active(self) -> list[Job]:
        return [j for jid in self._spawned if (j := load_job(jid)) and job_running(j)]

    def newly_finished(self) -> list[Job]:
        out = []
        for jid in self._spawned:
            if jid in self._reported:
                continue
            j = load_job(jid)
            if j and not j.is_active():
                self._reported.add(jid)
                out.append(j)
        return out

    def all_spawned(self) -> list[Job]:
        return [j for jid in self._spawned if (j := load_job(jid))]


JOBS = JobManager()


def run_job(job_id: str) -> int:
    """The DETACHED runner, invoked as `setup-agent runjob <id>`."""
    from .state import record_change

    job = load_job(job_id)
    if job is None:
        return 1
    try:
        with open(job.log_path, "w", encoding="utf-8") as log:
            proc = subprocess.run(
                job.argv, stdout=log, stderr=subprocess.STDOUT, text=True,
                env=_env_with_brew(), timeout=3600,
            )
        job.returncode = proc.returncode
    except subprocess.TimeoutExpired:
        job.returncode = 124
    except OSError as exc:
        job.returncode = 1
        try:
            Path(job.log_path).write_text(f"could not start: {exc}\n", encoding="utf-8")
        except OSError:
            pass

    job.ended_at = _now()
    job.status = "done" if job.returncode == 0 else "failed"
    _persist(job)

    label = job.token or job.label
    if job.status == "done":
        if job.token:
            section = "Applications & Packages (Winget)"
            pretty = job.token.split(".")[-1] if "." in job.token else job.token
            item = f"{pretty} (`{job.token}`)"
            try:
                record_change(section, item, f"installed package `{job.token}` (background)")
            except Exception:
                pass
        _notify("SetUp Agent", f"{label} installed ✓")
    else:
        _notify("SetUp Agent", f"{label} failed — see setup-agent jobs")
    return job.returncode or 0


def load_persisted_jobs() -> list[dict]:
    jobs: list[dict] = []
    if not JOBS_DIR.is_dir():
        return jobs
    for path in sorted(JOBS_DIR.glob("*.json")):
        try:
            jobs.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return jobs
