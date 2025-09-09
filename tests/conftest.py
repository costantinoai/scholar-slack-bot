import sys
from types import ModuleType
from pathlib import Path

# Stub external modules not needed for tests
scholarly_stub = ModuleType("scholarly")
scholarly_stub.scholarly = object()
sys.modules.setdefault("scholarly", scholarly_stub)

# Ensure project root is on sys.path for module imports
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
