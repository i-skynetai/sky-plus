"""Put the package on the path and keep the suite from touching anything outside a temp folder."""
import atexit
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_scratch = tempfile.TemporaryDirectory(prefix="skynet-tests-")


def _cleanup():
    os.chdir(tempfile.gettempdir())     # Windows will not remove the folder the process stands in
    _scratch.cleanup()


atexit.register(_cleanup)
os.environ.setdefault("SKYNET_RUN_LOG", os.path.join(_scratch.name, "runs.jsonl"))
os.environ.setdefault("SKYNET_CONFIG_SEARCH", "0")
os.environ.pop("SKYNET_CONFIG", None)
for _key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AZURE_API_KEY", "GEMINI_API_KEY", "OTEL_EXPORTER_OTLP_ENDPOINT",
             "SKYNET_LOG_KEY"):
    os.environ.pop(_key, None)          # a test that needs one sets it explicitly
os.chdir(_scratch.name)      # as if run from an empty folder: no skynet.yaml of the repo's own leaks in
