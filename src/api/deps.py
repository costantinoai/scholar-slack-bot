"""Dependency injection for FastAPI routes.

This module provides reusable dependencies for database connections,
plugin registry access, authentication, and other shared resources.
"""

import os
import sqlite3
import logging
from typing import Generator, Optional
from functools import lru_cache

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from plugins.registry import PluginRegistry, get_global_registry

logger = logging.getLogger(__name__)

# Security
security = HTTPBearer(auto_error=False)

# Configuration
def _data_dir() -> str:
    """Resolve data directory at call time to honor env changes in tests."""
    return os.getenv("DATA_DIR", "./src")


def _authors_db_path() -> str:
    base = _data_dir()
    return os.getenv("AUTHORS_DB_PATH", os.path.join(base, "authors.db"))


def _publications_db_path() -> str:
    base = _data_dir()
    return os.getenv("PUBLICATIONS_DB_PATH", os.path.join(base, "publications.db"))
API_KEY = os.getenv("API_KEY", None)  # Optional API key for simple auth


# ============================================================================
# Database Dependencies
# ============================================================================

def get_authors_db() -> Generator[sqlite3.Connection, None, None]:
    """Provide a connection to the authors database.

    Yields:
        sqlite3.Connection: Database connection with row factory enabled
    """
    conn = sqlite3.connect(_authors_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        # Ensure table exists
        conn.execute(
            """CREATE TABLE IF NOT EXISTS authors (
                name TEXT,
                id TEXT PRIMARY KEY
            )"""
        )
        # Ensure optional columns
        try:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(authors)").fetchall()]
            if 'openalex_id' not in cols:
                conn.execute("ALTER TABLE authors ADD COLUMN openalex_id TEXT")
            if 'orcid' not in cols:
                conn.execute("ALTER TABLE authors ADD COLUMN orcid TEXT")
        except Exception:
            pass
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()


def get_publications_db() -> Generator[sqlite3.Connection, None, None]:
    """Provide a connection to the publications database.

    Yields:
        sqlite3.Connection: Database connection with row factory enabled
    """
    conn = sqlite3.connect(_publications_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        # Ensure table exists
        conn.execute(
            """CREATE TABLE IF NOT EXISTS publications (
                author_id TEXT,
                title TEXT,
                year INTEGER,
                abstract TEXT,
                url TEXT,
                citations INTEGER,
                PRIMARY KEY (author_id, title)
            )"""
        )
        # Ensure optional columns exist and migrate to robust PK if needed
        try:
            cols_info = conn.execute("PRAGMA table_info(publications)").fetchall()
            cols = [row[1] for row in cols_info]
            if 'journal' not in cols:
                conn.execute("ALTER TABLE publications ADD COLUMN journal TEXT")
            if 'authors' not in cols:
                conn.execute("ALTER TABLE publications ADD COLUMN authors TEXT")
            if 'doi' not in cols:
                conn.execute("ALTER TABLE publications ADD COLUMN doi TEXT")
            if 'source_id' not in cols:
                conn.execute("ALTER TABLE publications ADD COLUMN source_id TEXT DEFAULT ''")
            # Optional high-precision publication date and fetch timestamp
            if 'publication_date' not in cols:
                conn.execute("ALTER TABLE publications ADD COLUMN publication_date TEXT")
            if 'fetched_at' not in cols:
                conn.execute("ALTER TABLE publications ADD COLUMN fetched_at TEXT")

            # Detect if PK is still (author_id, title) and migrate to (author_id, title, source_id)
            pk_cols = [row[1] for row in cols_info if row[5] > 0]  # row[5] is pk flag/order
            needs_pk_migration = pk_cols == ['author_id', 'title']

            if needs_pk_migration:
                logger.info("Migrating publications table to composite PK (author_id, title, source_id)")
                conn.execute("BEGIN TRANSACTION")
                # Create new table with desired schema
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS publications_v2 (
                        author_id TEXT,
                        title TEXT,
                        source_id TEXT,
                        year INTEGER,
                        abstract TEXT,
                        url TEXT,
                        doi TEXT,
                        citations INTEGER,
                        journal TEXT,
                        authors TEXT,
                        publication_date TEXT,
                        fetched_at TEXT,
                        PRIMARY KEY (author_id, title, source_id)
                    )
                    """
                )
                # Populate with existing rows; derive source_id from doi/url/title
                conn.execute(
                    """
                    INSERT OR REPLACE INTO publications_v2 (
                        author_id, title, source_id, year, abstract, url, doi, citations, journal, authors, publication_date, fetched_at
                    )
                    SELECT
                        author_id,
                        title,
                        CASE
                            WHEN COALESCE(doi, '') <> '' THEN doi
                            WHEN COALESCE(url, '') <> '' THEN url
                            ELSE title
                        END AS source_id,
                        year,
                        abstract,
                        url,
                        doi,
                        citations,
                        journal,
                        authors,
                        publication_date,
                        fetched_at
                    FROM publications
                    """
                )
                # Replace old table
                conn.execute("DROP TABLE publications")
                conn.execute("ALTER TABLE publications_v2 RENAME TO publications")
                conn.execute("COMMIT")
        except Exception as e:
            logger.debug(f"Publications table alter/migration skipped/failed: {e}")
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()


# ============================================================================
# Plugin Registry Dependency
# ============================================================================

@lru_cache()
def get_plugin_registry() -> PluginRegistry:
    """Get the global plugin registry.

    Returns:
        PluginRegistry: The singleton plugin registry instance
    """
    return get_global_registry()


# ============================================================================
# Authentication Dependencies
# ============================================================================

async def verify_api_key(
    x_api_key: Optional[str] = Header(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> bool:
    """Verify API key from header or bearer token.

    This provides simple API key authentication. Can be extended with JWT.

    Args:
        x_api_key: API key from X-API-Key header
        credentials: Bearer token credentials

    Returns:
        bool: Always True if authentication succeeds

    Raises:
        HTTPException: If authentication fails (when API_KEY is configured)
    """
    # If no API key is configured, allow all requests (development mode)
    if API_KEY is None:
        logger.debug("No API_KEY configured - allowing unauthenticated access")
        return True

    # Check X-API-Key header
    if x_api_key and x_api_key == API_KEY:
        return True

    # Check Bearer token
    if credentials and credentials.credentials == API_KEY:
        return True

    # Authentication failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(authenticated: bool = Depends(verify_api_key)) -> dict:
    """Get the current authenticated user.

    For now, this returns a generic user. Can be extended with JWT claims
    to provide actual user information.

    Args:
        authenticated: Result from verify_api_key dependency

    Returns:
        dict: User information
    """
    return {
        "username": "api_user",
        "authenticated": authenticated
    }


# ============================================================================
# Optional Dependencies for Testing
# ============================================================================

def get_test_mode() -> bool:
    """Check if running in test mode.

    Returns:
        bool: True if TEST_MODE environment variable is set
    """
    return os.getenv("TEST_MODE", "false").lower() == "true"
