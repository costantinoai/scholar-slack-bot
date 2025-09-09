#!/usr/bin/env python3
"""Simple web interface to manage authors and cached publications.

This module exposes a small Flask application that allows users to:

* Add or remove Google Scholar authors from ``src/authors.db``.
* Refresh cached publications for individual authors or for all of them.
* Inspect the cached publications in a searchable table.
* Clear cached publications.
* Edit project settings and Slack credentials.
* Trigger unit tests or the full Slack workflows from the browser.

The implementation intentionally reuses existing backend helpers such as
``add_new_author_to_json`` and ``fetch_pubs_dictionary`` so the GUI acts as a
lightweight layer over the established workflow.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from subprocess import PIPE, STDOUT, Popen, TimeoutExpired
from types import SimpleNamespace
from typing import Iterable

import requests
from flask import Flask, Response, redirect, render_template_string, request, url_for
from configparser import ConfigParser

from fetch_scholar import fetch_pubs_dictionary
from helper_funcs import add_new_author_to_json, get_authors_json


# ---------------------------------------------------------------------------
# Persistent settings
# ---------------------------------------------------------------------------

# ``settings.json`` stores user-tunable paths and API options.  The helper
# functions below load and save this file so changes made in the web interface
# are preserved across restarts.
SETTINGS_FILE = Path("settings.json")


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
        "authors_db": "./src/authors.db",
        "publications_db": "./src/publications.db",
        "slack_config_path": "./src/slack.config",
        "api_call_delay": "1.0",
    }


def _save_settings() -> None:
    """Persist the in-memory settings to :data:`SETTINGS_FILE`."""

    with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2)


# Settings are loaded at import time and used to configure database locations.
settings = _load_settings()
AUTHORS_DB = Path(settings["authors_db"])
PUBLICATIONS_DB = Path(settings["publications_db"])
SLACK_CONFIG_PATH = Path(settings["slack_config_path"])

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Slack configuration helpers
# ---------------------------------------------------------------------------


def _load_slack_config() -> dict:
    """Return Slack credentials from ``slack.config`` or defaults.

    Returns:
        dict: ``api_token`` and ``channel_name`` keys with possibly empty
        values if the configuration file is missing.
    """

    parser = ConfigParser()
    if SLACK_CONFIG_PATH.exists():
        parser.read(SLACK_CONFIG_PATH)

    return {
        "api_token": parser.get("slack", "api_token", fallback=""),
        "channel_name": parser.get("slack", "channel_name", fallback=""),
    }


def _save_slack_config(conf: dict) -> None:
    """Persist Slack credentials to the configured path.

    Args:
        conf: Mapping containing ``api_token`` and ``channel_name`` fields.
    """

    parser = ConfigParser()
    parser["slack"] = conf
    with open(SLACK_CONFIG_PATH, "w", encoding="utf-8") as fh:
        parser.write(fh)


def _get_workspace_name(token: str) -> str | None:
    """Query the Slack API for the human-readable workspace name.

    The function returns ``None`` when the token is missing or the request
    fails so callers can fall back to a generic placeholder.

    Args:
        token: Slack API token used for authentication.

    Returns:
        Optional workspace name.
    """

    if not token:
        return None

    try:
        response = requests.post(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        data = response.json()
        if data.get("ok"):
            return data.get("team")
    except Exception:
        # Network errors or malformed responses are ignored to keep the UI
        # responsive even when Slack is unreachable.
        pass
    return None


# ---------------------------------------------------------------------------
# Background process management
# ---------------------------------------------------------------------------

# ``CURRENT_PROCESS`` holds the handle of the subprocess currently running as a
# workflow or test.  Only one process is allowed at a time so the interface can
# expose a single stream of output.
CURRENT_PROCESS: Popen[str] | None = None


def _start_process(cmd: list[str]) -> None:
    """Launch ``cmd`` in the background and capture its output.

    Any previously running process is terminated first to avoid overlapping
    subprocesses.

    Args:
        cmd: Sequence forming the command to execute.
    """

    _stop_current_process()
    global CURRENT_PROCESS
    CURRENT_PROCESS = Popen(cmd, stdout=PIPE, stderr=STDOUT, text=True, bufsize=1)


def _stop_current_process() -> None:
    """Terminate the active background process if it exists."""

    global CURRENT_PROCESS
    if CURRENT_PROCESS and CURRENT_PROCESS.poll() is None:
        CURRENT_PROCESS.terminate()
        try:
            CURRENT_PROCESS.wait(2)
        except TimeoutExpired:
            CURRENT_PROCESS.kill()
    CURRENT_PROCESS = None


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
    # Convert settings and Slack configuration into objects so templates can
    # access fields using dot notation (``settings.authors_db`` etc.).
    settings_ns = SimpleNamespace(**settings)
    slack_conf = _load_slack_config()
    workspace = _get_workspace_name(slack_conf["api_token"])
    slack_ns = SimpleNamespace(workspace=workspace, **slack_conf)
    return render_template_string(
        TEMPLATE,
        authors=authors,
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

    _save_settings()

    # Refresh global paths so subsequent requests use the new values.
    global AUTHORS_DB, PUBLICATIONS_DB, SLACK_CONFIG_PATH
    AUTHORS_DB = Path(settings["authors_db"])
    PUBLICATIONS_DB = Path(settings["publications_db"])
    SLACK_CONFIG_PATH = Path(settings["slack_config_path"])

    return redirect(url_for("index"))


@app.post("/update-slack")
def update_slack():
    """Persist Slack API token and channel name from the settings form."""

    conf = {
        "api_token": request.form.get("api_token", "").strip(),
        "channel_name": request.form.get("channel_name", "").strip(),
    }
    _save_slack_config(conf)
    return redirect(url_for("index"))


@app.get("/publications")
def publications():
    """Display cached publications in a searchable table."""

    author_id = request.args.get("author_id")
    conn = sqlite3.connect(PUBLICATIONS_DB)
    try:
        # Attach the authors database so names can be joined to cached entries.
        conn.execute(f"ATTACH DATABASE '{AUTHORS_DB}' AS auth")
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


@app.post("/send-test")
def send_test_message():
    """Start a subprocess to send a Slack test message."""

    _start_process(
        [
            "python",
            "-u",
            "main.py",
            "--test_message",
            "--authors_path",
            settings["authors_db"],
            "--slack_config_path",
            settings["slack_config_path"],
        ]
    )
    return ("", 204)


@app.post("/run-workflow")
def run_workflow():
    """Start a subprocess to run the full fetch-and-send workflow."""

    _start_process(
        [
            "python",
            "-u",
            "main.py",
            "--authors_path",
            settings["authors_db"],
            "--slack_config_path",
            settings["slack_config_path"],
        ]
    )
    return ("", 204)


@app.post("/run-tests")
def run_tests():
    """Start a subprocess to execute ``pytest``."""

    _start_process(["pytest", "-vv", "-s"])
    return ("", 204)


@app.get("/stream")
def stream_output():
    """Stream stdout from the running subprocess as server-sent events."""

    if CURRENT_PROCESS is None:
        return Response("data: no process\n\n", mimetype="text/event-stream")

    def generate():
        while True:
            line = CURRENT_PROCESS.stdout.readline()
            if line:
                yield f"data: {line.rstrip()}\n\n"
            elif CURRENT_PROCESS.poll() is not None:
                break
        code = CURRENT_PROCESS.poll()
        yield f"data: [exit {code}]\n\n"
        yield "data: __COMPLETE__\n\n"
        _stop_current_process()

    return Response(generate(), mimetype="text/event-stream")


@app.post("/stop")
def stop_process():
    """Terminate the running subprocess, if any."""

    _stop_current_process()
    return ("", 204)


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

  <div id=\"output-container\" class=\"alert alert-info\" style=\"display:none;\"><pre id=\"output\" class=\"mb-0\"></pre></div>

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
            <button class=\"btn btn-success\" type=\"submit\">Save Settings</button>
          </form>
          <hr>
          <form method=\"post\" action=\"{{ url_for('update_slack') }}\">
            <div class=\"mb-2\">
              <label class=\"form-label\">Slack API Token</label>
              <input type=\"text\" class=\"form-control\" name=\"api_token\" value=\"{{ slack.api_token }}\" data-bs-toggle=\"tooltip\" title=\"Bot token used for Slack API\">
            </div>
            <div class=\"mb-2\">
              <label class=\"form-label\">Slack Channel Name</label>
              <input type=\"text\" class=\"form-control\" name=\"channel_name\" value=\"{{ slack.channel_name }}\" data-bs-toggle=\"tooltip\" title=\"Destination channel for messages\">
            </div>
            <button class=\"btn btn-warning\" type=\"submit\">Save Slack Config</button>
          </form>
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
    <h2>Workflows</h2>
    <p>Target: <strong>{{ slack.channel_name or 'unknown channel' }}</strong>{% if slack.workspace %} in <strong>{{ slack.workspace }}</strong>{% else %} in <strong>unknown workspace</strong>{% endif %}</p>
    <button class=\"btn btn-outline-secondary\" onclick=\"startProcess('{{ url_for('send_test_message') }}', 'Send test message to {{ slack.channel_name }} in {{ slack.workspace or 'unknown workspace' }}?')\">Send Test Message</button>
    <button class=\"btn btn-outline-success mt-2\" onclick=\"startProcess('{{ url_for('run_workflow') }}', 'Run workflow and send messages to {{ slack.channel_name }} in {{ slack.workspace or 'unknown workspace' }}?')\">Run Workflow</button>
    <button id=\"stop-btn\" class=\"btn btn-danger mt-2\" style=\"display:none;\" onclick=\"stopProcess()\">Stop</button>
  </div>

    <div class=\"mt-4\">
      <h2>Run Tests</h2>
      <button class=\"btn btn-secondary\" onclick=\"startProcess('{{ url_for('run_tests') }}', 'This may take a while. Run tests?')\">pytest</button>
    </div>

  <script>
  let evtSource;

  function startProcess(url, confirmText){
    if (confirmText && !confirm(confirmText)) return;
    document.getElementById('output').textContent = '';
    document.getElementById('output-container').style.display = 'block';
    fetch(url, {method: 'POST'});
    if (evtSource) evtSource.close();
    evtSource = new EventSource('/stream');
    document.getElementById('stop-btn').style.display = 'inline-block';
    evtSource.onmessage = function(e){
      if (e.data === '__COMPLETE__'){
        evtSource.close();
        document.getElementById('stop-btn').style.display = 'none';
      } else {
        const out = document.getElementById('output');
        out.textContent += e.data + '\n';
        out.scrollTop = out.scrollHeight;
      }
    };
  }

  function stopProcess(){
    fetch('/stop', {method: 'POST'});
    if (evtSource) evtSource.close();
    document.getElementById('stop-btn').style.display = 'none';
  }

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
