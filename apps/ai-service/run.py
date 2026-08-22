"""ExamShield AI service launcher.

Ensures only ONE server instance runs at a time via a PID lock file.
"""
from __future__ import annotations

import atexit
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_LOCK_FILE = Path(__file__).resolve().parent / ".server.lock"


def _acquire_lock() -> None:
    """Prevent multiple server instances from running simultaneously."""
    if _LOCK_FILE.exists():
        try:
            old_pid = int(_LOCK_FILE.read_text().strip())
        except (ValueError, OSError):
            old_pid = 0
        # Check if the old process is still alive
        if old_pid and _is_process_alive(old_pid):
            print(
                f"ERROR: Another ExamShield AI server is already running (PID {old_pid}).\n"
                f"Lock file: {_LOCK_FILE}\n"
                f"To force-start, delete the lock file and kill the old process:\n"
                f"  del {_LOCK_FILE}\n"
                f"  taskkill /F /PID {old_pid}",
                file=sys.stderr,
            )
            sys.exit(1)
        # Stale lock — old process is dead, remove it
        try:
            _LOCK_FILE.unlink()
        except OSError:
            pass

    # Write our PID
    _LOCK_FILE.write_text(str(os.getpid()))


def _release_lock() -> None:
    """Remove the lock file on clean exit."""
    try:
        _LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _is_process_alive(pid: int) -> bool:
    """Check if a process with the given PID exists (Windows + cross-platform)."""
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


atexit.register(_release_lock)

if __name__ == "__main__":
    _acquire_lock()
    try:
        from examshield_ai.service import main
        main()
    finally:
        _release_lock()
