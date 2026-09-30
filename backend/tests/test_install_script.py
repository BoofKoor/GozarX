"""The installer's re-run paths (``install.sh``), exercised by ``install_rerun.sh``.

A re-run used to drop every ``.env`` key the installer does not manage (the site's Google
verification token among them), blank a working admin password hash for the length of the build,
and leave nginx on its old config. The shell script sources the installer with docker and curl
stubbed and every path pointed at a temp dir, so it never touches the repo or a real stack.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("install_rerun.sh")


@pytest.mark.skipif(
    not (shutil.which("bash") and shutil.which("openssl")), reason="needs bash + openssl"
)
def test_installer_rerun_keeps_env_keys_and_the_password_and_restarts_nginx() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, timeout=120, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
