import sys
from unittest.mock import patch

from main import initialize_args


def test_initialize_args_defaults():
    """Running without CLI arguments uses defaults and does not enable test mode."""
    with patch.object(sys, "argv", ["main.py", "fetch"]):
        args = initialize_args()
    assert args.test_message is False
    assert args.add_scholar_id is None
    assert args.update_cache is False


def test_initialize_args_test_fetch():
    """`test-fetch` subcommand requires a scholar ID and disables messaging."""
    with patch.object(sys, "argv", ["main.py", "test-fetch", "ABC123"]):
        args = initialize_args()
    assert args.scholar_id == "ABC123"
    assert args.test_message is False


def test_initialize_args_test_run_limit():
    """`test-run` accepts a limit on the number of authors."""
    with patch.object(sys, "argv", ["main.py", "test-run", "--limit", "5"]):
        args = initialize_args()
    assert args.limit == 5
    assert args.test_message is True
