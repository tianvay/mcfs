"""systemd access for the Minecraft unit.

All calls use fixed argument lists (no shell). Start/stop/restart of the
Minecraft unit and starting the two update helper units are permitted for the
portal user by a polkit rule (deploy/50-mcportal.rules) - nothing else.
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass

ALLOWED_VERBS = ("start", "stop", "restart")


@dataclass
class UnitState:
    active_state: str        # active | inactive | activating | deactivating | failed
    sub_state: str
    main_pid: int
    started_at: float | None  # ExecMainStartTimestamp (unix)


def _ts(value: str) -> float | None:
    # --timestamp=unix yields "@1789905929"; empty or "n/a" when unset
    if value.startswith("@"):
        try:
            return float(value[1:])
        except ValueError:
            return None
    return None


def show(unit: str) -> UnitState:
    out = subprocess.run(
        ["systemctl", "show", unit, "--timestamp=unix",
         "-p", "ActiveState", "-p", "SubState", "-p", "MainPID", "-p", "ExecMainStartTimestamp"],
        capture_output=True, text=True, timeout=10, check=True,
    ).stdout
    props = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    return UnitState(
        active_state=props.get("ActiveState", "unknown"),
        sub_state=props.get("SubState", "unknown"),
        main_pid=int(props.get("MainPID", "0") or 0),
        started_at=_ts(props.get("ExecMainStartTimestamp", "")),
    )


HELPER_UNITS = ("mcportal-update-apply.service", "mcportal-update-rollback.service")


def run_helper(unit: str, timeout: float = 1200) -> tuple[bool, str]:
    """Start one of the fixed oneshot helper units and wait until it has finished."""
    if unit not in HELPER_UNITS:
        raise ValueError(f"unit not allowed: {unit}")
    since = f"@{int(time.time()) - 1}"
    try:
        res = subprocess.run(["systemctl", "--no-ask-password", "start", unit],
                             capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"{unit} hat nach {timeout:.0f}s nicht geantwortet"
    log = subprocess.run(["journalctl", "-u", unit, "--since", since, "-n", "15", "-o", "cat", "--no-pager", "-q"],
                         capture_output=True, text=True, timeout=10).stdout.strip()
    return res.returncode == 0, log or (res.stderr or res.stdout).strip()


def control(unit: str, verb: str, timeout: float = 120) -> tuple[bool, str]:
    if verb not in ALLOWED_VERBS:
        raise ValueError(f"verb not allowed: {verb}")
    try:
        res = subprocess.run(
            ["systemctl", "--no-ask-password", verb, unit],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"systemctl {verb} timed out after {timeout:.0f}s"
    return res.returncode == 0, (res.stderr or res.stdout).strip()
