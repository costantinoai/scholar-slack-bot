import types
import sys

dummy = types.ModuleType('scholarly')
dummy.scholarly = None
sys.modules.setdefault('scholarly', dummy)

from scholar_slack_bot.fetch_scholar import save_updated_cache, load_cache


def test_cache_roundtrip(tmp_path):
    args = types.SimpleNamespace(update_cache=False)
    pubs = [{"bib": {"title": "A"}, "num_citations": 1}]
    save_updated_cache(pubs, [], "TEST", tmp_path, args)
    loaded = load_cache("TEST", tmp_path)
    assert loaded[0]["bib"]["title"] == "A"
