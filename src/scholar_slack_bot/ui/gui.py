#!/usr/bin/env python3
"""Simple web interface to manage authors and cached publications.

This module exposes a small Flask application that allows users to:

* Add or remove Google Scholar authors from ``data/authors.db``.
* Refresh cached publications for individual authors or for all of them.
* Inspect the cached publications in a searchable table.
* Clear cached publications.
* Trigger the project's unit tests from the browser.

The implementation intentionally reuses existing backend helpers such as
``add_new_author_to_json`` and ``fetch_pubs_dictionary`` so the GUI acts as a
lightweight layer over the established workflow.
"""

from __future__ import annotations

import configparser
import json
import sqlite3
from pathlib import Path
from subprocess import run
from types import SimpleNamespace
from typing import Iterable

from flask import Flask, redirect, render_template_string, request, url_for

from ..scholar.fetch import fetch_pubs_dictionary
from ..utils.helpers import add_new_author_to_json, get_authors_json


# ---------------------------------------------------------------------------
# Persistent settings
# ---------------------------------------------------------------------------

# ``data/settings.json`` stores user-tunable paths and API options.  Resolve the
# project root relative to this file so the application can be launched from any
# working directory without breaking path references.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SETTINGS_FILE = PROJECT_ROOT / "data" / "settings.json"


def _load_settings() -> dict:
    """Load settings from :data:`SETTINGS_FILE` or return defaults.

    Returns:
        dict: Mapping of setting names to values.  The defaults match the
        original project paths so the GUI works out of the box.
    """

    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)

    # Defaults used when the settings file is missing.  They mirror the values
    # previously hard coded into the application.
    return {
        "authors_db": "./data/authors.db",
        "publications_db": "./data/publications.db",
        "slack_config_path": "./data/slack.config",
        "api_call_delay": "1.0",
    }


def _save_settings() -> None:
    """Persist the in-memory settings to :data:`SETTINGS_FILE`."""

    with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2)


# Settings are loaded at import time and used to configure database locations.
settings = _load_settings()
# Interpret database paths relative to the project root so they resolve
# consistently regardless of the launch directory.
AUTHORS_DB = (PROJECT_ROOT / settings["authors_db"]).resolve()
PUBLICATIONS_DB = (PROJECT_ROOT / settings["publications_db"]).resolve()


def _load_slack_config() -> dict:
    """Return Slack configuration values from the file on disk.

    The Slack config uses an INI format with a single ``[slack]`` section.  The
    function reads the file pointed to by ``settings['slack_config_path']`` and
    returns a mapping of key/value pairs.  Missing files or options yield empty
    strings so the web form can still render editable fields.
    """

    cfg = configparser.ConfigParser()
    cfg_path = (PROJECT_ROOT / settings["slack_config_path"]).resolve()
    if cfg_path.exists():
        cfg.read(cfg_path, encoding="utf-8")
    section = cfg["slack"] if cfg.has_section("slack") else {}
    defaults = {"api_token": "", "channel_name": "", "workspace": ""}
    return {key: section.get(key, "") for key in defaults}


def _save_slack_config() -> None:
    """Persist current :data:`slack_settings` to the configured file."""

    cfg = configparser.ConfigParser()
    cfg["slack"] = slack_settings
    cfg_path = (PROJECT_ROOT / settings["slack_config_path"]).resolve()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg_path, "w", encoding="utf-8") as fh:
        cfg.write(fh)


# Slack settings are loaded alongside the general project settings so the form
# can expose API tokens and channel names for editing.
slack_settings = _load_slack_config()

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _run_sql(query: str, params: Iterable | None = None) -> None:
    """Execute a write-only SQL statement on the publications database.

    The helper keeps repetitive connection boilerplate out of the route handlers
    and ensures the connection is always properly closed.

    Args:
        query: SQL statement to execute.
        params: Parameters for the SQL statement, if any.
    """

    conn = sqlite3.connect(PUBLICATIONS_DB)
    try:
        # Ensure the publications table exists before running the user query.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS publications (
                author_id TEXT,
                title TEXT,
                year INTEGER,
                url TEXT,
                citations INTEGER,
                PRIMARY KEY (author_id, title)
            )
            """
        )
        conn.execute(query, params or [])
        conn.commit()
    finally:
        conn.close()


def _remove_author(author_id: str) -> None:
    """Remove an author and associated cached publications.

    Args:
        author_id: Google Scholar identifier of the author to remove.
    """

    # Delete the author from the authors database, creating the table on demand
    # so the GUI works on a fresh repository without manual initialization.
    conn = sqlite3.connect(AUTHORS_DB)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS authors (
                name TEXT,
                id TEXT PRIMARY KEY
            )
            """
        )
        conn.execute("DELETE FROM authors WHERE id=?", (author_id,))
        conn.commit()
    finally:
        conn.close()

    # Purge any cached publications for the author
    _run_sql("DELETE FROM publications WHERE author_id=?", (author_id,))


def _clear_cache(author_id: str | None = None) -> None:
    """Clear cached publications.

    Args:
        author_id: When provided, only cache for the given author is removed.
            Otherwise the entire cache table is cleared.
    """

    if author_id:
        _run_sql("DELETE FROM publications WHERE author_id=?", (author_id,))
    else:
        _run_sql("DELETE FROM publications")


def _refresh(authors: list[tuple[str, str]]) -> None:
    """Fetch and cache publications for the given authors.

    Args:
        authors: List of ``(name, id)`` tuples representing authors.
    """

    # ``fetch_pubs_dictionary`` expects an argparse-style namespace.  Only the
    # flags used by the underlying functions are provided here.
    args = SimpleNamespace(update_cache=False, test_fetching=False)
    fetch_pubs_dictionary(authors, args)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    """Render the main page with author management tools."""

    authors = get_authors_json(str(AUTHORS_DB))
    # Convert settings dict into an object so templates can access fields using
    # dot notation (``settings.authors_db`` etc.).
    settings_ns = SimpleNamespace(**settings)
    slack_ns = SimpleNamespace(**slack_settings)
    return render_template_string(
        TEMPLATE,
        authors=authors,
        test_output=None,
        settings=settings_ns,
        slack=slack_ns,
    )


@app.post("/add-author")
def add_author():
    """Add a single author based on the submitted Scholar ID."""

    scholar_id = request.form.get("scholar_id", "").strip()
    if scholar_id:
        add_new_author_to_json(str(AUTHORS_DB), scholar_id)
    return redirect(url_for("index"))


@app.post("/add-bulk")
def add_bulk():
    """Add multiple authors supplied in a textarea, one per line."""

    ids_text = request.form.get("scholar_ids", "")
    for line in ids_text.splitlines():
        scholar_id = line.strip()
        if scholar_id:
            add_new_author_to_json(str(AUTHORS_DB), scholar_id)
    return redirect(url_for("index"))


@app.post("/remove/<author_id>")
def remove_author(author_id: str):
    """Remove an author and their cached publications."""

    _remove_author(author_id)
    return redirect(url_for("index"))


@app.post("/refresh/<author_id>")
def refresh_author(author_id: str):
    """Fetch latest publications for a specific author."""

    authors = get_authors_json(str(AUTHORS_DB))
    to_refresh = [(a["name"], a["id"]) for a in authors if a["id"] == author_id]
    if to_refresh:
        _refresh(to_refresh)
    return redirect(url_for("index"))


@app.post("/refresh-all")
def refresh_all():
    """Fetch publications for all authors."""

    authors = get_authors_json(str(AUTHORS_DB))
    tuples = [(a["name"], a["id"]) for a in authors]
    if tuples:
        _refresh(tuples)
    return redirect(url_for("index"))


@app.post("/clear-cache")
def clear_cache():
    """Remove every cached publication."""

    _clear_cache()
    return redirect(url_for("index"))


@app.post("/clear-cache/<author_id>")
def clear_author_cache(author_id: str):
    """Clear cached publications for a specific author."""

    _clear_cache(author_id)
    return redirect(url_for("index"))


@app.post("/update-settings")
def update_settings():
    """Persist user-supplied configuration from the settings form."""

    # Update each known setting from the submitted form values.
    for key in settings:
        if key in request.form:
            settings[key] = request.form[key].strip()

    # Slack-related settings are prefixed with ``slack_`` to avoid colliding
    # with the general project settings above.  Strip the prefix and update the
    # in-memory mapping before persisting the file to disk.
    for key in list(slack_settings):
        form_key = f"slack_{key}"
        if form_key in request.form:
            slack_settings[key] = request.form[form_key].strip()

    _save_settings()
    _save_slack_config()

    # Refresh global paths so subsequent requests use the new values.
    global AUTHORS_DB, PUBLICATIONS_DB
    AUTHORS_DB = Path(settings["authors_db"])
    PUBLICATIONS_DB = Path(settings["publications_db"])

    return redirect(url_for("index"))


@app.get("/publications")
def publications():
    """Display cached publications in a searchable table."""

    author_id = request.args.get("author_id")
    conn = sqlite3.connect(PUBLICATIONS_DB)
    try:
        # Ensure the ``publications`` table exists; a fresh database file will
        # otherwise raise ``OperationalError`` when the user tries to view
        # cached entries before any have been inserted.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS publications (
                author_id TEXT,
                title TEXT,
                year INTEGER,
                url TEXT,
                citations INTEGER,
                PRIMARY KEY (author_id, title)
            )
            """
        )

        # Attach the authors database so names can be joined to cached entries
        # in the display query below.
        conn.execute(f"ATTACH DATABASE '{AUTHORS_DB}' AS auth")

        # Build the base query pulling publication details along with the
        # associated author's name.  Parameters are collected separately to
        # protect against SQL injection and keep the query readable.
        sql = (
            "SELECT a.name, p.title, p.year, p.url, p.citations "
            "FROM publications p JOIN auth.authors a ON a.id = p.author_id"
        )
        params: list[str] = []
        if author_id:
            sql += " WHERE a.id=?"
            params.append(author_id)
        sql += " ORDER BY a.name, p.year DESC"
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    pubs = [
        {
            "name": name,
            "title": title,
            "year": year,
            "url": url,
            "citations": citations,
        }
        for name, title, year, url, citations in rows
    ]
    return render_template_string(PUB_TEMPLATE, publications=pubs)


@app.post("/run-tests")
def run_tests():
    """Execute ``pytest`` and display the output on the main page."""

    result = run(["pytest", "-vv"], capture_output=True, text=True)
    authors = get_authors_json(str(AUTHORS_DB))
    settings_ns = SimpleNamespace(**settings)
    slack_ns = SimpleNamespace(**slack_settings)
    return render_template_string(
        TEMPLATE,
        authors=authors,
        test_output=result.stdout + result.stderr,
        settings=settings_ns,
        slack=slack_ns,
    )


# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

TEMPLATE = """
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Scholar Slack Bot</title>
  <link href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css\" rel=\"stylesheet\">
  <script src=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js\"></script>
</head>
<body class=\"container py-4\">
  <h1 class=\"mb-4\">Scholar Slack Bot</h1>

  {% if test_output %}
  <div class=\"alert alert-info\"><pre class=\"mb-0\">{{ test_output }}</pre></div>
  {% endif %}

  <div class=\"row g-4\">
    <div class=\"col-md-6\">
      <div class=\"card h-100\">
        <div class=\"card-header\">Add Author</div>
        <div class=\"card-body\">
          <form class=\"row gy-2\" method=\"post\" action=\"{{ url_for('add_author') }}\">
            <div class=\"col-12\">
              <input type=\"text\" name=\"scholar_id\" class=\"form-control\" placeholder=\"Google Scholar ID\" required>
            </div>
            <div class=\"col-12\">
              <button class=\"btn btn-primary\" type=\"submit\" data-bs-toggle=\"tooltip\" title=\"Add a single author by ID\">Add</button>
            </div>
          </form>
          <hr>
          <form method=\"post\" action=\"{{ url_for('add_bulk') }}\">
            <div class=\"mb-2\">
              <textarea name=\"scholar_ids\" class=\"form-control\" rows=\"4\" placeholder=\"One ID per line\"></textarea>
            </div>
            <button class=\"btn btn-primary\" type=\"submit\" data-bs-toggle=\"tooltip\" title=\"Add multiple authors at once\">Add Bulk</button>
          </form>
        </div>
      </div>
    </div>

    <div class=\"col-md-6\">
      <!-- Button toggles visibility of the settings panel.  Keeping the panel collapsed by default keeps the interface uncluttered while still allowing advanced configuration edits when needed. -->
      <button class=\"btn btn-outline-secondary mb-2\" type=\"button\" data-bs-toggle=\"collapse\" data-bs-target=\"#settings-panel\" aria-expanded=\"false\" aria-controls=\"settings-panel\">Edit Configs</button>
      <div id=\"settings-panel\" class=\"collapse\">
        <div class=\"card h-100\">
          <div class=\"card-header\">Settings</div>
          <div class=\"card-body\">
            <form method=\"post\" action=\"{{ url_for('update_settings') }}\">
              <div class=\"mb-2\">
                <label class=\"form-label\">Authors DB</label>
                <input type=\"text\" class=\"form-control\" name=\"authors_db\" value=\"{{ settings.authors_db }}\" data-bs-toggle=\"tooltip\" title=\"Path to authors.db\">
              </div>
              <div class=\"mb-2\">
                <label class=\"form-label\">Publications DB</label>
                <input type=\"text\" class=\"form-control\" name=\"publications_db\" value=\"{{ settings.publications_db }}\" data-bs-toggle=\"tooltip\" title=\"Path to publications.db\">
              </div>
              <div class=\"mb-2\">
                <label class=\"form-label\">Slack Config Path</label>
                <input type=\"text\" class=\"form-control\" name=\"slack_config_path\" value=\"{{ settings.slack_config_path }}\" data-bs-toggle=\"tooltip\" title=\"Location of slack.config\">
              </div>
              <div class=\"mb-2\">
                <label class=\"form-label\">API Call Delay (s)</label>
                <input type=\"text\" class=\"form-control\" name=\"api_call_delay\" value=\"{{ settings.api_call_delay }}\" data-bs-toggle=\"tooltip\" title=\"Throttle between API calls\">
              </div>
              <hr>
              <h5>Slack Config</h5>
              {% for key, value in slack.__dict__.items() %}
              <div class=\"mb-2\">
                <label class=\"form-label\">{{ key.replace('_', ' ').title() }}</label>
                <input type=\"text\" class=\"form-control\" name=\"slack_{{ key }}\" value=\"{{ value }}\" data-bs-toggle=\"tooltip\" title=\"Slack {{ key.replace('_', ' ') }}\">
              </div>
              {% endfor %}
              <button class=\"btn btn-success\" type=\"submit\">Save Settings</button>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class=\"mt-4\">
    <div class=\"d-flex justify-content-between align-items-center\">
      <h2>Current Authors</h2>
      <div>
        <form class=\"d-inline\" method=\"post\" action=\"{{ url_for('refresh_all') }}\" onsubmit=\"return confirm('Refresh publications for all authors?')\">
          <button class=\"btn btn-outline-primary\" type=\"submit\" data-bs-toggle=\"tooltip\" title=\"Fetch publications for every author\">Refresh All</button>
        </form>
        <form class=\"d-inline\" method=\"post\" action=\"{{ url_for('clear_cache') }}\" onsubmit=\"return confirm('Clear all cached publications?')\">
          <button class=\"btn btn-outline-danger\" type=\"submit\" data-bs-toggle=\"tooltip\" title=\"Delete all cached publications\">Clear Cache</button>
        </form>
      </div>
    </div>
    <div class=\"table-responsive\">
      <table class=\"table table-striped\">
        <thead><tr><th>Name</th><th>ID</th><th>Actions</th></tr></thead>
        <tbody>
        {% for a in authors %}
          <tr>
            <td>{{ a.name }}</td>
            <td>{{ a.id }}</td>
            <td>
              <form class=\"d-inline\" method=\"post\" action=\"{{ url_for('refresh_author', author_id=a.id) }}\" onsubmit=\"return confirm('Refresh publications for {{ a.name }}?')\">
                <button class=\"btn btn-sm btn-outline-primary\" type=\"submit\" data-bs-toggle=\"tooltip\" title=\"Update publications for this author\">Refresh</button>
              </form>
              <form class=\"d-inline\" method=\"post\" action=\"{{ url_for('clear_author_cache', author_id=a.id) }}\" onsubmit=\"return confirm('Remove cached publications for {{ a.name }}?')\">
                <button class=\"btn btn-sm btn-outline-warning\" type=\"submit\" data-bs-toggle=\"tooltip\" title=\"Clear cached publications for this author\">Clear</button>
              </form>
              <form class=\"d-inline\" method=\"post\" action=\"{{ url_for('remove_author', author_id=a.id) }}\" onsubmit=\"return confirm('Remove {{ a.name }} from authors?')\">
                <button class=\"btn btn-sm btn-outline-danger\" type=\"submit\" data-bs-toggle=\"tooltip\" title=\"Remove author from database\">Remove</button>
              </form>
              <a class=\"btn btn-sm btn-outline-secondary\" href=\"{{ url_for('publications', author_id=a.id) }}\" data-bs-toggle=\"tooltip\" title=\"View cached publications\">View Pubs</a>
            </td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
  </div>

  <div class=\"mt-4\">
    <h2>Run Tests</h2>
    <form method=\"post\" action=\"{{ url_for('run_tests') }}\" onsubmit=\"return confirm('This may take a while. Run tests?')\">
      <button class=\"btn btn-secondary\">pytest</button>
    </form>
  </div>

  <script>
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(t => new bootstrap.Tooltip(t));
  </script>
</body>
</html>
"""


PUB_TEMPLATE = """
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Cached Publications</title>
  <link href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css\" rel=\"stylesheet\">
  <script src=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js\"></script>
</head>
<body class=\"container py-4\">
  <h1>Cached Publications</h1>
  <input class=\"form-control mb-3\" type=\"text\" id=\"filter\" onkeyup=\"filterTable()\" placeholder=\"Filter...\">
  <div class=\"table-responsive\">
    <table id=\"pubs\" class=\"table table-striped\">
      <thead>
        <tr><th>Author</th><th>Title</th><th>Year</th><th>Citations</th></tr>
      </thead>
      <tbody>
        {% for pub in publications %}
        <tr>
          <td>{{ pub.name }}</td>
          <td><a href=\"{{ pub.url }}\" target=\"_blank\">{{ pub.title }}</a></td>
          <td>{{ pub.year }}</td>
          <td>{{ pub.citations }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
<script>
function filterTable(){
  const filter=document.getElementById('filter').value.toLowerCase();
  document.querySelectorAll('#pubs tbody tr').forEach(r=>{
    r.style.display=r.innerText.toLowerCase().includes(filter)?'':'none';
  });
}
const tooltipTriggerList=[].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
tooltipTriggerList.map(t=>new bootstrap.Tooltip(t));
</script>
</body>
</html>
"""


if __name__ == "__main__":
    # Running the Flask development server makes the interface available at
    # http://localhost:5000.  In production environments a proper WSGI server
    # should be used instead.
    app.run(debug=True)
