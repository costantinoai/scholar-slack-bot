#!/usr/bin/env python3
"""Simple web interface to manage authors and cached publications.

This module exposes a small Flask application that allows users to:

* Add or remove Google Scholar authors from ``src/authors.db``.
* Refresh cached publications for individual authors or for all of them.
* Inspect the cached publications in a searchable table.
* Clear cached publications.
* Trigger the project's unit tests from the browser.

The implementation intentionally reuses existing backend helpers such as
``add_new_author_to_json`` and ``fetch_pubs_dictionary`` so the GUI acts as a
lightweight layer over the established workflow.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from subprocess import run
from types import SimpleNamespace
from typing import Iterable

from flask import Flask, redirect, render_template_string, request, url_for

from fetch_scholar import fetch_pubs_dictionary
from helper_funcs import add_new_author_to_json, get_authors_json

# Paths to the SQLite databases used by the application.  Keeping them as
# constants makes the locations easy to update and re-use throughout the file.
AUTHORS_DB = Path("./src/authors.db")
PUBLICATIONS_DB = Path("./src/publications.db")

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
        conn.execute(query, params or [])
        conn.commit()
    finally:
        conn.close()


def _remove_author(author_id: str) -> None:
    """Remove an author and associated cached publications.

    Args:
        author_id: Google Scholar identifier of the author to remove.
    """

    # Delete the author from the authors database
    conn = sqlite3.connect(AUTHORS_DB)
    try:
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
    return render_template_string(TEMPLATE, authors=authors, test_output=None)


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


@app.get("/publications")
def publications():
    """Display cached publications in a searchable table."""

    conn = sqlite3.connect(PUBLICATIONS_DB)
    try:
        cursor = conn.execute(
            """
            SELECT a.name, p.title, p.year, p.url, p.citations
            FROM publications p
            JOIN authors a ON a.id = p.author_id
            ORDER BY a.name, p.year DESC
            """
        )
        rows = cursor.fetchall()
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

    result = run(["pytest", "-q"], capture_output=True, text=True)
    authors = get_authors_json(str(AUTHORS_DB))
    return render_template_string(
        TEMPLATE, authors=authors, test_output=result.stdout + result.stderr
    )


# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

TEMPLATE = """
<!doctype html>
<title>Scholar Slack Bot GUI</title>
<h1>Author Manager</h1>

<h2>Add Author</h2>
<form method="post" action="{{ url_for('add_author') }}">
  <input type="text" name="scholar_id" placeholder="Google Scholar ID" required>
  <input type="submit" value="Add">
</form>

<h2>Bulk Add Authors</h2>
<form method="post" action="{{ url_for('add_bulk') }}">
  <textarea name="scholar_ids" rows="4" cols="40" placeholder="One ID per line"></textarea><br>
  <input type="submit" value="Add IDs">
</form>

<h2>Current Authors</h2>
<table border="1" cellpadding="4" cellspacing="0">
  <tr><th>Name</th><th>ID</th><th>Actions</th></tr>
  {% for a in authors %}
  <tr>
    <td>{{ a.name }}</td>
    <td>{{ a.id }}</td>
    <td>
      <form style="display:inline" method="post" action="{{ url_for('refresh_author', author_id=a.id) }}">
        <button type="submit">Refresh</button>
      </form>
      <form style="display:inline" method="post" action="{{ url_for('clear_author_cache', author_id=a.id) }}">
        <button type="submit">Clear Cache</button>
      </form>
      <form style="display:inline" method="post" action="{{ url_for('remove_author', author_id=a.id) }}">
        <button type="submit">Remove</button>
      </form>
      <a href="{{ url_for('publications') }}">View Pubs</a>
    </td>
  </tr>
  {% endfor %}
</table>

<form method="post" action="{{ url_for('refresh_all') }}">
  <button type="submit">Refresh All</button>
</form>
<form method="post" action="{{ url_for('clear_cache') }}">
  <button type="submit">Clear All Cache</button>
</form>

<h2>Run Tests</h2>
<form method="post" action="{{ url_for('run_tests') }}">
  <button type="submit">pytest</button>
</form>
{% if test_output %}
  <h3>Test Output</h3>
  <pre>{{ test_output }}</pre>
{% endif %}
"""


PUB_TEMPLATE = """
<!doctype html>
<title>Cached Publications</title>
<h1>Cached Publications</h1>
<input type="text" id="filter" onkeyup="filterTable()" placeholder="Filter...">
<table id="pubs" border="1" cellpadding="4" cellspacing="0">
  <thead>
    <tr><th>Author</th><th>Title</th><th>Year</th><th>Citations</th></tr>
  </thead>
  <tbody>
    {% for pub in publications %}
    <tr>
      <td>{{ pub.name }}</td>
      <td><a href="{{ pub.url }}" target="_blank">{{ pub.title }}</a></td>
      <td>{{ pub.year }}</td>
      <td>{{ pub.citations }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<script>
function filterTable() {
  const filter = document.getElementById('filter').value.toLowerCase();
  const rows = document.querySelectorAll('#pubs tbody tr');
  rows.forEach(r => {
    r.style.display = r.innerText.toLowerCase().includes(filter) ? '' : 'none';
  });
}
</script>
"""


if __name__ == "__main__":
    # Running the Flask development server makes the interface available at
    # http://localhost:5000.  In production environments a proper WSGI server
    # should be used instead.
    app.run(debug=True)
