"""Offline guarantee: third-party telemetry is off before any AI library is loaded."""

from __future__ import annotations

import os
import subprocess
import sys


def test_onnxruntime_telemetry_is_disabled_before_import() -> None:
    import app  # noqa: F401

    assert os.environ["ORT_DISABLE_TELEMETRY"] == "1"


def test_fresh_process_sets_the_switch_before_onnxruntime_loads() -> None:
    code = ("import os, sys; os.environ.pop('ORT_DISABLE_TELEMETRY', None); "
            "import app.ai.runtime; "
            "assert 'onnxruntime' in sys.modules and os.environ['ORT_DISABLE_TELEMETRY'] == '1'")
    env = {k: v for k, v in os.environ.items() if k != "ORT_DISABLE_TELEMETRY"}
    subprocess.run([sys.executable, "-c", code], check=True, env=env, cwd=os.getcwd())
