"""KiraPick (formerly Snorlu AI Culling) — offline, non-destructive photo culling."""

__version__ = "2.2.0"

# Offline guarantee: ONNX Runtime >= 1.31 starts a Microsoft "1DS" telemetry client as soon as it is
# imported (HTTPS to mobile.events.data.microsoft.com + a local event store), before any API call
# could switch it off. This variable, read at import time, disables both. It is set here, the first
# module of the app, so it is in place before anything imports onnxruntime. Verified in the dev
# container: without it every run tried to connect; with it, no attempt and no store is written.
import os as _os

_os.environ["ORT_DISABLE_TELEMETRY"] = "1"
