import sys
from unittest.mock import patch

from scholar_slack_bot.cli import initialize_args


def test_initialize_args_defaults():
    """Running without CLI arguments uses defaults and does not enable test mode."""
    with patch.object(sys, "argv", ["cli.py"]):
        args = initialize_args()
    assert args.test_message is False
    assert args.add_scholar_id is None
    assert args.update_cache is False
