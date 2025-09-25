"""Global pytest configuration for the Neuroca memory system.

The module primarily ensures the ``src`` tree is importable regardless of how the
repository is cloned. When mutation testing is active the ``mutmut`` CLI toggles the
``MUTANT_UNDER_TEST`` environment variable to verify that the suite detects injected
failures. We optionally log the flag when ``MUTMUT_DEBUG`` is enabled to help diagnose
mutmut runner issues without polluting the workspace during normal test execution.
"""

import os
import sys
from pathlib import Path
from typing import Set

import pytest

# Add the src directory to the Python path so imports can work correctly
# without needing to add the 'src.' prefix to every import
project_root = Path(__file__).parent.parent
src_dir = project_root / 'src'

# Make the 'neuroca' package directly importable
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Rest of conftest.py would go here (global fixtures, etc.)
mutant_flag = os.environ.get("MUTANT_UNDER_TEST")
debug_mutmut = os.environ.get("MUTMUT_DEBUG", "").lower() in {"1", "true", "yes"}
_logged_mutmut_flags: Set[str] = set()


def _maybe_log_mutmut_flag(flag: str | None) -> None:
    """Record mutmut state transitions when debug logging is enabled."""

    if not (flag and debug_mutmut) or flag in _logged_mutmut_flags:
        return

    try:
        with open("mutmut_env.log", "a", encoding="utf-8") as env_log:
            env_log.write(f"{flag}\n")
    except OSError:
        return

    _logged_mutmut_flags.add(flag)


_maybe_log_mutmut_flag(mutant_flag)


@pytest.fixture(autouse=True)
def _mutmut_forced_failure_guard() -> None:
    """Force pytest to fail when mutmut requests a sentinel failure run."""

    flag = os.environ.get("MUTANT_UNDER_TEST")
    _maybe_log_mutmut_flag(flag)
    if flag == "fail":
        pytest.fail("mutmut forced failure sentinel")
