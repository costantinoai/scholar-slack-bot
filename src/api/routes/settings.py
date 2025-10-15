"""Settings API endpoints.

Provides read/write access to local settings without exposing external APIs.
Settings are stored in the repository's `settings.json` file.
"""

import json
import os
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
import requests

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
)


SETTINGS_FILE = Path("./settings.json")


class SettingsModel(BaseModel):
    backend: str = Field("scholar", pattern="^(scholar|openalex)$", description="Publication backend")
    openalex_email: Optional[str] = Field(None, description="Contact email for OpenAlex polite pool")
    api_call_delay: Optional[str] = Field("1.0", description="Legacy UI delay; kept for compatibility")


def _read_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except Exception as e:
            logger.warning(f"Failed to parse settings.json: {e}")
    # defaults
    return {
        "authors_db": "./src/authors.db",
        "publications_db": "./src/publications.db",
        "slack_config_path": "./src/slack.config",
        "api_call_delay": "1.0",
        "backend": "scholar",
        "openalex_email": None,
    }


def _write_settings(data: dict) -> None:
    # Merge with existing to avoid losing unrelated keys
    current = _read_settings()
    current.update(data)
    SETTINGS_FILE.write_text(json.dumps(current, indent=2))
    logger.info("Settings updated: %s", {k: current.get(k) for k in ("backend", "openalex_email", "api_call_delay")})


@router.get("", response_model=SettingsModel)
async def get_settings():
    """Retrieve core settings.

    Does not expose secrets or external service credentials.
    """
    raw = _read_settings()
    return SettingsModel(
        backend=raw.get("backend", "scholar"),
        openalex_email=raw.get("openalex_email"),
        api_call_delay=str(raw.get("api_call_delay", "1.0")),
    )


@router.put("", response_model=SettingsModel)
async def update_settings(payload: SettingsModel):
    """Update core settings locally.

    Notes:
    - `backend` must be either `scholar` or `openalex`
    - `openalex_email` is recommended when using OpenAlex to join the polite pool
    - No external APIs are called as part of this endpoint
    """
    try:
        _write_settings(payload.model_dump())
        return payload
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/test/openalex")
async def test_openalex_connectivity():
    """Test connectivity to the OpenAlex API (polite pool if email is set)."""
    try:
        email = _read_settings().get("openalex_email")
        params = {"search": "test", "per_page": 1}
        if email:
            params["mailto"] = email
        r = requests.get("https://api.openalex.org/authors", params=params, timeout=10)
        ok = r.status_code == 200
        return {"success": ok, "status": r.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/test/scholar")
async def test_scholar_connectivity():
    """Best-effort test for scholarly availability (no real scrape)."""
    try:
        import scholarly  # noqa: F401
        # We avoid real requests to Scholar here to be respectful.
        return {"success": True, "message": "scholarly library available"}
    except Exception as e:
        return {"success": False, "error": str(e)}
