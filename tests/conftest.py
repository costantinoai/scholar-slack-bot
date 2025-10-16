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


def pytest_ignore_collect(collection_path, path, config):
    """Ignore source files during test collection.

    Pytest should only collect from the tests/ directory, not from source
    files that happen to have functions starting with 'test_'.
    """
    # Get the string path
    str_path = str(collection_path)

    # Ignore everything outside tests/ directory
    if "/tests/" not in str_path and not str_path.endswith("/tests"):
        # Only ignore .py files that are not in tests/
        if str_path.endswith(".py"):
            return True

    return False
