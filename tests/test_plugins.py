"""Token-free tests for the plugin system.

This module intentionally contains no API tokens or real integrations.
It validates:
- Dataclasses: Publication, Author
- Plugin registry behavior using a dummy, in-memory plugin
- Config loader read/write using temporary files
"""

from __future__ import annotations

import pytest
from pathlib import Path
import tempfile
import configparser

from plugins.base import (
    MessagingPlugin,
    Publication,
    Author,
)
from plugins.registry import PluginRegistry, get_global_registry, reset_global_registry
from plugins.config import PluginConfigLoader


class DummyPlugin(MessagingPlugin):
    """A minimal plugin used for safe, token-free tests."""

    def _validate_config(self) -> None:
        # Accept any config; no required keys/tokens
        return None

    def send_message(self, message: str, target: str) -> bool:
        return True

    def format_publications(self, publications: list[Publication]) -> str:
        return "\n".join(p.title for p in publications) if publications else ""

    def format_authors(self, authors: list[Author]) -> str:
        return ", ".join(a.name for a in authors) if authors else ""

    def format_test_message(self, message: str = "Test") -> str:
        return f"TEST: {message}"

    def test_connection(self) -> bool:
        return True

    def get_config_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    @property
    def name(self) -> str:
        return "dummy"

    @property
    def display_name(self) -> str:
        return "Dummy"

    @property
    def version(self) -> str:
        return "0.0.1"

    @property
    def description(self) -> str:
        return "Token-free dummy plugin for tests"


# Fixtures

@pytest.fixture
def sample_publications():
    return [
        Publication(
            title="Neural Networks for NLP",
            authors="Smith, J., Doe, A.",
            year="2024",
            abstract="A novel approach to NLP...",
            pub_url="https://example.com/paper1",
            journal="Nature",
            citations=42,
        ),
        Publication(
            title="Deep Learning in Vision",
            authors="Johnson, B., Lee, C., Wang, D., Brown, E., Davis, F.",
            year="2024",
            abstract="Computer vision using DL...",
            pub_url="https://example.com/paper2",
            journal="IEEE Trans.",
            citations=15,
        ),
    ]


@pytest.fixture
def sample_authors():
    return [
        Author(name="John Doe", scholar_id="abc123xyz"),
        Author(name="Jane Smith", scholar_id="xyz789abc"),
    ]


@pytest.fixture
def registry():
    return PluginRegistry()


# Dataclasses

def test_publication_creation():
    pub = Publication(
        title="Test Paper",
        authors="Author A, Author B",
        year="2024",
        abstract="This is a test abstract",
        pub_url="https://example.com/paper",
        journal="Test Journal",
        citations=10,
    )
    assert pub.title == "Test Paper"
    assert pub.citations == 10


def test_author_creation():
    author = Author(name="Test Author", scholar_id="test123")
    assert author.name == "Test Author"
    assert author.scholar_id == "test123"


# PluginRegistry (dummy plugin only)

def test_registry_initialization(registry):
    assert len(registry.list_plugins()) == 0


def test_register_plugin(registry):
    registry.register(DummyPlugin)
    assert "dummy" in registry.list_plugins()


def test_register_invalid_plugin(registry):
    class NotAPlugin:
        pass

    with pytest.raises(TypeError, match="must inherit from MessagingPlugin"):
        registry.register(NotAPlugin)  # type: ignore[arg-type]


def test_register_duplicate_plugin(registry):
    registry.register(DummyPlugin)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(DummyPlugin)


def test_unregister_plugin(registry):
    registry.register(DummyPlugin)
    registry.unregister("dummy")
    assert "dummy" not in registry.list_plugins()


def test_unregister_nonexistent_plugin(registry):
    with pytest.raises(KeyError):
        registry.unregister("nonexistent")


def test_get_plugin_class(registry):
    registry.register(DummyPlugin)
    plugin_class = registry.get_plugin_class("dummy")
    assert plugin_class == DummyPlugin


def test_get_nonexistent_plugin_class(registry):
    with pytest.raises(KeyError, match="not found"):
        registry.get_plugin_class("nonexistent")


def test_create_instance(registry):
    registry.register(DummyPlugin)
    plugin = registry.create_instance("dummy", {})
    assert isinstance(plugin, DummyPlugin)
    assert plugin.name == "dummy"


def test_create_instance_with_cache(registry):
    registry.register(DummyPlugin)
    p1 = registry.create_instance("dummy", {}, cache=True)
    p2 = registry.create_instance("dummy", {}, cache=True)
    assert p1 is p2


def test_create_instance_without_cache(registry):
    registry.register(DummyPlugin)
    p1 = registry.create_instance("dummy", {}, cache=False)
    p2 = registry.create_instance("dummy", {}, cache=False)
    assert p1 is not p2


def test_get_plugin_info(registry):
    registry.register(DummyPlugin)
    info = registry.get_plugin_info("dummy")
    assert info["name"] == "dummy"
    assert info["display_name"] == "Dummy"
    assert info["version"] == "0.0.1"


def test_get_all_plugins_info(registry):
    registry.register(DummyPlugin)
    all_info = registry.get_all_plugins_info()
    assert len(all_info) == 1
    assert all_info[0]["name"] == "dummy"


def test_clear_cache(registry):
    registry.register(DummyPlugin)
    p1 = registry.create_instance("dummy", {}, cache=True)
    registry.clear_cache()
    p2 = registry.create_instance("dummy", {}, cache=True)
    assert p1 is not p2


def test_global_registry():
    reset_global_registry()
    reg1 = get_global_registry()
    reg2 = get_global_registry()
    assert reg1 is reg2


# PluginConfigLoader (no tokens)

def test_load_from_ini():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".config", delete=False) as f:
        config = configparser.ConfigParser()
        config["slack"] = {
            "channel_name": "general",
        }
        config.write(f)
        temp_path = f.name

    try:
        loader = PluginConfigLoader()
        result = loader.load_from_ini(temp_path, "slack")
        assert result["channel_name"] == "general"
    finally:
        Path(temp_path).unlink()


def test_load_from_ini_missing_file():
    loader = PluginConfigLoader()
    with pytest.raises(FileNotFoundError):
        loader.load_from_ini("/nonexistent/file.config", "slack")


def test_load_from_ini_missing_section():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".config", delete=False) as f:
        config = configparser.ConfigParser()
        config["other"] = {"key": "value"}
        config.write(f)
        temp_path = f.name

    try:
        loader = PluginConfigLoader()
        with pytest.raises(KeyError, match="Section 'slack' not found"):
            loader.load_from_ini(temp_path, "slack")
    finally:
        Path(temp_path).unlink()


def test_save_to_ini():
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.config"

        loader = PluginConfigLoader()
        config = {"channel": "general"}
        loader.save_to_ini(config, str(file_path), "slack")

        assert file_path.exists()
        loaded = loader.load_from_ini(str(file_path), "slack")
        assert loaded["channel"] == "general"


def test_load_from_json():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        import json

        json.dump({"channel": "general"}, f)
        temp_path = f.name

    try:
        loader = PluginConfigLoader()
        result = loader.load_from_json(temp_path)
        assert result["channel"] == "general"
    finally:
        Path(temp_path).unlink()


def test_save_to_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.json"

        loader = PluginConfigLoader()
        config = {"channel": "general"}
        loader.save_to_json(config, str(file_path))

        assert file_path.exists()
        loaded = loader.load_from_json(str(file_path))
        assert loaded["channel"] == "general"


def test_end_to_end_dummy_plugin_usage():
    registry = PluginRegistry()
    registry.register(DummyPlugin)

    plugin = registry.create_instance("dummy", {})

    pub = Publication(
        title="Test Paper",
        authors="Author A",
        year="2024",
        abstract="Abstract",
        pub_url="https://example.com",
        journal="Journal",
    )
    message = plugin.format_publications([pub])

    assert "Test Paper" in message
    assert isinstance(message, str)

