"""Web UI routes for the Scholar Slack Bot dashboard.

This module provides the web interface routes that render HTML templates
using Jinja2. These routes serve the dashboard UI and use HTMX for
dynamic content updates.
"""

import logging
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3

from src.api.deps import get_authors_db, get_publications_db

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(tags=["web"])

# Initialize templates
templates = Jinja2Templates(directory="src/web/templates")


def _resolve_base_template(request: Request) -> str:
    """Choose which base template to use for this request.

    We support a simple query parameter toggle `?theme=material` to switch the
    UI to a Material Design flavored base. The default theme remains the
    Tailwind-based layout (`base.html`). A cookie `ui_theme=material` is also
    honored if present.
    """
    try:
        theme = (request.query_params.get("theme") or "").lower().strip()
        if not theme:
            theme = (request.cookies.get("ui_theme") or "").lower().strip()
        if theme in {"material", "md", "material3"}:
            return "base_material.html"
    except Exception:
        pass
    return "base.html"


# ============================================================================
# Page Routes (Full HTML pages)
# ============================================================================

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the main dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request, "base_template": _resolve_base_template(request)})


@router.get("/authors", response_class=HTMLResponse)
async def authors_page(request: Request):
    """Render the authors management page."""
    return templates.TemplateResponse("authors.html", {"request": request, "base_template": _resolve_base_template(request)})


@router.get("/publications", response_class=HTMLResponse)
async def publications_page(request: Request):
    """Render the publications browser page."""
    return templates.TemplateResponse("publications.html", {"request": request, "base_template": _resolve_base_template(request)})


@router.get("/plugins", response_class=HTMLResponse)
async def plugins_page(request: Request):
    """Render the plugins configuration page."""
    return templates.TemplateResponse("plugins.html", {"request": request, "base_template": _resolve_base_template(request)})


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Render the application settings page."""
    return templates.TemplateResponse("settings.html", {"request": request, "base_template": _resolve_base_template(request)})


@router.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    """Render the statistics page.

    This full page uses Chart.js to visualize:
    - Publications by year (all years or last 10)
    - Top journals (by publications)
    - Top keywords/topics extracted from titles/abstracts
    - Top authors by h-index and by citations
    It consumes the `/api/v1/publications/stats` endpoint.
    """
    return templates.TemplateResponse("stats.html", {"request": request, "base_template": _resolve_base_template(request)})


@router.get("/author/{author_id}", response_class=HTMLResponse)
async def author_detail_page(request: Request, author_id: str):
    """Render author detail view with sortable publications table."""
    return templates.TemplateResponse("author_detail.html", {"request": request, "author_id": author_id, "base_template": _resolve_base_template(request)})


# ============================================================================
# HTMX Partial Routes (HTML fragments for dynamic updates)
# ============================================================================

@router.get("/web/stats", response_class=HTMLResponse)
async def get_stats_cards(
    request: Request,
    authors_db: sqlite3.Connection = Depends(get_authors_db),
    pubs_db: sqlite3.Connection = Depends(get_publications_db)
):
    """Get statistics cards HTML fragment."""
    try:
        # Get counts
        cursor = authors_db.execute("SELECT COUNT(*) as count FROM authors")
        total_authors = cursor.fetchone()["count"]

        cursor = pubs_db.execute("SELECT COUNT(*) as count FROM publications")
        total_pubs = cursor.fetchone()["count"]

        cursor = pubs_db.execute("SELECT SUM(citations) as total FROM publications")
        total_citations = cursor.fetchone()["total"] or 0

        # Count recent publications (this year)
        cursor = pubs_db.execute(
            "SELECT COUNT(*) as count FROM publications WHERE year = strftime('%Y', 'now')"
        )
        recent_pubs = cursor.fetchone()["count"]

        html = f"""
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <!-- Total Authors -->
            <div class="bg-white rounded-lg shadow p-6">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm font-medium text-gray-600">Total Authors</p>
                        <p class="text-3xl font-bold text-gray-900 mt-2">{total_authors}</p>
                    </div>
                    <div class="p-3 bg-blue-100 rounded-full">
                        <svg class="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/>
                        </svg>
                    </div>
                </div>
            </div>

            <!-- Total Publications -->
            <div class="bg-white rounded-lg shadow p-6">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm font-medium text-gray-600">Total Publications</p>
                        <p class="text-3xl font-bold text-gray-900 mt-2">{total_pubs}</p>
                    </div>
                    <div class="p-3 bg-green-100 rounded-full">
                        <svg class="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
                        </svg>
                    </div>
                </div>
            </div>

            <!-- New This Year -->
            <div class="bg-white rounded-lg shadow p-6">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm font-medium text-gray-600">New This Year</p>
                        <p class="text-3xl font-bold text-gray-900 mt-2">{recent_pubs}</p>
                    </div>
                    <div class="p-3 bg-purple-100 rounded-full">
                        <svg class="w-8 h-8 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>
                        </svg>
                    </div>
                </div>
            </div>

            <!-- Total Citations -->
            <div class="bg-white rounded-lg shadow p-6">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm font-medium text-gray-600">Total Citations</p>
                        <p class="text-3xl font-bold text-gray-900 mt-2">{int(total_citations)}</p>
                    </div>
                    <div class="p-3 bg-yellow-100 rounded-full">
                        <svg class="w-8 h-8 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/>
                        </svg>
                    </div>
                </div>
            </div>
        </div>
        """
        return HTMLResponse(content=html)

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return HTMLResponse(content="<div>Error loading statistics</div>", status_code=500)


@router.get("/web/recent-publications", response_class=HTMLResponse)
async def get_recent_publications(
    request: Request,
    limit: int = 5,
    pubs_db: sqlite3.Connection = Depends(get_publications_db)
):
    """Get recent publications HTML fragment."""
    try:
        cursor = pubs_db.execute(
            """SELECT author_id, title, year, citations, url
               FROM publications
               ORDER BY year DESC, citations DESC
               LIMIT ?""",
            (limit,)
        )
        publications = cursor.fetchall()

        if not publications:
            return HTMLResponse(content='<div class="px-6 py-4 text-gray-500">No publications found</div>')

        html_parts = []
        for pub in publications:
            pub_dict = dict(pub)
            html_parts.append(f"""
            <div class="px-6 py-4 hover:bg-gray-50 transition-colors">
                <h4 class="font-medium text-gray-900 mb-1">{pub_dict['title']}</h4>
                <div class="flex items-center text-sm text-gray-600 space-x-4">
                    <span>{pub_dict['year'] or 'N/A'}</span>
                    <span>•</span>
                    <span>{pub_dict['citations'] or 0} citations</span>
                    {f'<a href="{pub_dict["url"]}" target="_blank" class="text-blue-600 hover:text-blue-800">View →</a>' if pub_dict.get('url') else ''}
                </div>
            </div>
            """)

        return HTMLResponse(content="\n".join(html_parts))

    except Exception as e:
        logger.error(f"Error getting recent publications: {e}")
        return HTMLResponse(content='<div class="px-6 py-4 text-red-500">Error loading publications</div>', status_code=500)


@router.get("/web/authors-list", response_class=HTMLResponse)
async def get_authors_list(
    request: Request,
    authors_db: sqlite3.Connection = Depends(get_authors_db),
    pubs_db: sqlite3.Connection = Depends(get_publications_db)
):
    """Get authors list HTML fragment."""
    try:
        # Try to include optional columns when available for contextual labeling
        try:
            cursor = authors_db.execute("SELECT name, id, openalex_id FROM authors ORDER BY name")
            authors = cursor.fetchall()
            include_openalex = True
        except Exception:
            cursor = authors_db.execute("SELECT name, id FROM authors ORDER BY name")
            authors = cursor.fetchall()
            include_openalex = False

        if not authors:
            return HTMLResponse(content="""
                <div class="bg-white rounded-lg shadow p-8 text-center">
                    <svg class="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/>
                    </svg>
                    <h3 class="text-lg font-medium text-gray-900 mb-2">No authors yet</h3>
                    <p class="text-gray-600 mb-4">Start by adding your first author to monitor</p>
                    <button onclick="showAddAuthorModal()" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                        Add Your First Author
                    </button>
                </div>
            """)

        html_parts = []
        for author in authors:
            author_dict = dict(author)
            author_id = author_dict['id']
            author_name = author_dict['name']
            openalex_val = author_dict.get('openalex_id') if include_openalex else None
            id_label = 'OpenAlex ID' if openalex_val else 'Scholar ID'

            # Get publication count
            pub_cursor = pubs_db.execute(
                "SELECT COUNT(*) as count FROM publications WHERE author_id = ?",
                (author_id,)
            )
            pub_count = pub_cursor.fetchone()["count"]

            # Total citations
            cit_row = pubs_db.execute(
                "SELECT COALESCE(SUM(citations), 0) as total FROM publications WHERE author_id = ?",
                (author_id,)
            ).fetchone()
            total_citations = int(cit_row["total"]) if cit_row is not None else 0

            # h-index
            h = 0
            try:
                cits = pubs_db.execute(
                    "SELECT citations FROM publications WHERE author_id = ? ORDER BY citations DESC",
                    (author_id,)
                ).fetchall()
                sorted_cits = [int((row["citations"] or 0)) for row in cits]
                for i, c in enumerate(sorted_cits, start=1):
                    if c >= i:
                        h = i
                    else:
                        break
            except Exception:
                h = 0

            html_parts.append(f"""
            <div class="bg-white rounded-lg shadow hover:shadow-lg transition-shadow"
                 data-author-name="{author_name}"
                 data-pub-count="{pub_count}"
                 data-total-citations="{total_citations}"
                 data-h-index="{h}">
                <div class="p-6">
                    <div class="flex items-start justify-between">
                        <div class="flex-1">
                            <div class="flex items-center space-x-3">
                                <div class="w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-600 rounded-full flex items-center justify-center text-white font-bold text-lg">
                                    {author_name[0].upper()}
                                </div>
                                <div>
                                    <h3 class="text-lg font-semibold text-gray-900">{author_name}</h3>
                                    <p class="text-sm text-gray-500">{id_label}: {author_id}</p>
                                </div>
                            </div>

                            <div class="mt-4 flex items-center space-x-6">
                                <div class="flex items-center text-sm text-gray-600">
                                    <svg class="w-5 h-5 mr-2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
                                    </svg>
                                    <span class="font-medium">{pub_count}</span> publications
                                </div>
                                <div class="flex items-center text-sm text-gray-600">
                                    <svg class="w-5 h-5 mr-2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17v-6a2 2 0 012-2h2a2 2 0 012 2v6m-6 4h6"/>
                                    </svg>
                                    <span class="font-medium">{total_citations}</span> citations
                                </div>
                                <div class="flex items-center text-sm text-gray-600">
                                    <svg class="w-5 h-5 mr-2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
                                    </svg>
                                    h-index <span class="ml-1 font-medium">{h}</span>
                                </div>
                            </div>
                        </div>

                        <div class="flex flex-col space-y-2 ml-4">
                            <button onclick="viewPublications('{author_id}')"
                                    class="px-3 py-1 text-sm bg-blue-50 text-blue-700 rounded hover:bg-blue-100 transition-colors">
                                View Pubs
                            </button>
                            <button onclick="refreshAuthorCache('{author_id}')"
                                    class="px-3 py-1 text-sm bg-yellow-50 text-yellow-700 rounded hover:bg-yellow-100 transition-colors" title="Refreshes cache only; does not send messages">
                                Refresh Cache
                            </button>
                            <button onclick="previewFetchAuthor('{author_id}')"
                                    class="px-3 py-1 text-sm bg-green-50 text-green-700 rounded hover:bg-green-100 transition-colors" title="Fetch latest publications (saved) and preview; sending is optional">
                                Fetch & Preview
                            </button>
                            <button onclick="showDeleteModal('{author_id}', '{author_name}')"
                                    class="px-3 py-1 text-sm bg-red-50 text-red-700 rounded hover:bg-red-100 transition-colors">
                                Delete
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            """)

        return HTMLResponse(content="\n".join(html_parts))

    except Exception as e:
        logger.error(f"Error getting authors list: {e}")
        return HTMLResponse(content='<div class="bg-white rounded-lg shadow p-6 text-red-500">Error loading authors</div>', status_code=500)
