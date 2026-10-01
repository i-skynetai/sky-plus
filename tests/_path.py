"""Put the package on the path and keep the suite from touching anything outside a temp folder."""
import atexit, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_scratch = tempfile.TemporaryDirectory(prefix="skynet-tests-")
atexit.register(_scratch.cleanup)
os.environ.setdefault("SKYNET_RUN_LOG", os.path.join(_scratch.name, "runs.jsonl"))
os.environ.setdefault("SKYNET_CONFIG_SEARCH", "0")
os.environ.pop("SKYNET_CONFIG", None)
os.chdir(_scratch.name)      # as if run from an empty folder: no skynet.yaml of the repo's own leaks in
