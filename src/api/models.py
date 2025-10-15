"""Pydantic models for API request/response validation."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


# ============================================================================
# Author Models
# ============================================================================

class AuthorCreate(BaseModel):
    """Request model for creating a new author."""

    scholar_id: str = Field(
        ...,
        description="Google Scholar ID for the author",
        examples=["abc123xyz"]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "scholar_id": "abc123xyz"
            }
        }
    )


class AuthorResponse(BaseModel):
    """Response model for author data."""

    id: str = Field(..., description="Google Scholar ID")
    name: str = Field(..., description="Author's full name")
    added_at: Optional[str] = Field(None, description="When the author was added (ISO format)")
    publication_count: int = Field(0, description="Number of publications cached")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "abc123xyz",
                "name": "John Doe",
                "added_at": "2024-10-15T10:30:00",
                "publication_count": 45
            }
        }
    )


# ============================================================================
# Publication Models
# ============================================================================

class PublicationResponse(BaseModel):
    """Response model for publication data."""

    author_id: str = Field(..., description="Google Scholar ID of the author")
    title: str = Field(..., description="Publication title")
    authors: str = Field(..., description="Comma-separated list of authors")
    year: Optional[int] = Field(None, description="Publication year")
    abstract: Optional[str] = Field(None, description="Publication abstract")
    url: Optional[str] = Field(None, description="URL to the publication")
    citations: int = Field(0, description="Number of citations")
    journal: Optional[str] = Field(None, description="Journal or venue")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "author_id": "abc123xyz",
                "title": "Neural Networks for Image Recognition",
                "authors": "Smith, J., Doe, A., Johnson, B.",
                "year": 2024,
                "abstract": "This paper presents a novel approach...",
                "url": "https://scholar.google.com/...",
                "citations": 127,
                "journal": "Nature Machine Intelligence"
            }
        }
    )


class PublicationQueryParams(BaseModel):
    """Query parameters for filtering publications."""

    author_id: Optional[str] = Field(None, description="Filter by author ID")
    year: Optional[int] = Field(None, description="Filter by specific year")
    min_year: Optional[int] = Field(None, description="Minimum year (inclusive)")
    max_year: Optional[int] = Field(None, description="Maximum year (inclusive)")
    min_citations: Optional[int] = Field(None, description="Minimum citations")
    search: Optional[str] = Field(None, description="Search in title and abstract")
    limit: int = Field(100, description="Maximum number of results", ge=1, le=1000)
    offset: int = Field(0, description="Number of results to skip", ge=0)


# ============================================================================
# Job Models
# ============================================================================

class JobCreate(BaseModel):
    """Request model for creating a scheduled job."""

    name: str = Field(..., description="Job name", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="Job description", max_length=500)
    cron_expression: str = Field(
        ...,
        description="Cron expression for scheduling (e.g., '0 9 * * MON')",
        pattern=r"^(\S+\s+){4}\S+$"
    )
    action: str = Field(
        ...,
        description="Action to perform",
        pattern="^(fetch|notify|fetch_and_notify)$"
    )
    plugin_name: Optional[str] = Field(None, description="Plugin to use for notifications")
    author_ids: Optional[List[str]] = Field(None, description="Specific authors (None = all)")
    enabled: bool = Field(True, description="Whether the job is active")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Weekly Publication Fetch",
                "description": "Fetch new publications every Monday and notify Slack",
                "cron_expression": "0 9 * * MON",
                "action": "fetch_and_notify",
                "plugin_name": "slack",
                "author_ids": None,
                "enabled": True
            }
        }
    )


class JobUpdate(BaseModel):
    """Request model for updating a job."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    cron_expression: Optional[str] = Field(None, pattern=r"^(\S+\s+){4}\S+$")
    action: Optional[str] = Field(None, pattern="^(fetch|notify|fetch_and_notify)$")
    plugin_name: Optional[str] = None
    author_ids: Optional[List[str]] = None
    enabled: Optional[bool] = None


class JobResponse(BaseModel):
    """Response model for job data."""

    id: int = Field(..., description="Job ID")
    name: str = Field(..., description="Job name")
    description: Optional[str] = Field(None, description="Job description")
    cron_expression: str = Field(..., description="Cron schedule")
    action: str = Field(..., description="Action type")
    plugin_name: Optional[str] = Field(None, description="Plugin name")
    author_ids: Optional[List[str]] = Field(None, description="Target authors")
    enabled: bool = Field(..., description="Is job enabled")
    next_run: Optional[str] = Field(None, description="Next scheduled run (ISO format)")
    last_run: Optional[str] = Field(None, description="Last execution (ISO format)")
    created_at: str = Field(..., description="When job was created (ISO format)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Weekly Publication Fetch",
                "description": "Fetch new publications every Monday",
                "cron_expression": "0 9 * * MON",
                "action": "fetch_and_notify",
                "plugin_name": "slack",
                "author_ids": None,
                "enabled": True,
                "next_run": "2024-10-21T09:00:00",
                "last_run": "2024-10-14T09:00:00",
                "created_at": "2024-10-01T10:00:00"
            }
        }
    )


class JobExecutionHistory(BaseModel):
    """Response model for job execution history entry."""

    id: int = Field(..., description="Execution ID")
    job_id: int = Field(..., description="Job ID")
    started_at: str = Field(..., description="When execution started (ISO format)")
    finished_at: Optional[str] = Field(None, description="When execution finished (ISO format)")
    status: str = Field(..., description="Execution status (success/failure/running)")
    message: Optional[str] = Field(None, description="Execution message or error")
    publications_found: Optional[int] = Field(None, description="Number of publications found")


# ============================================================================
# Plugin Models
# ============================================================================

class PluginInfo(BaseModel):
    """Response model for plugin information."""

    name: str = Field(..., description="Plugin identifier (lowercase)")
    display_name: str = Field(..., description="Human-readable name")
    version: str = Field(..., description="Plugin version")
    description: str = Field(..., description="Plugin description")
    config_schema: dict = Field(..., description="JSON schema for configuration")
    is_configured: bool = Field(..., description="Whether plugin is configured")
    is_healthy: Optional[bool] = Field(None, description="Health check status")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "slack",
                "display_name": "Slack",
                "version": "1.0.0",
                "description": "Send notifications to Slack channels",
                "config_schema": {
                    "type": "object",
                    "required": ["api_token", "channel"],
                    "properties": {
                        "api_token": {
                            "type": "string",
                            "description": "Slack API token",
                            "secret": True
                        },
                        "channel": {
                            "type": "string",
                            "description": "Default channel"
                        }
                    }
                },
                "is_configured": True,
                "is_healthy": True
            }
        }
    )


class PluginConfigUpdate(BaseModel):
    """Request model for updating plugin configuration."""

    config: dict = Field(..., description="Plugin configuration dictionary")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "config": {
                    "api_token": "xoxb-your-token",
                    "channel": "#publications"
                }
            }
        }
    )


class PluginTestResult(BaseModel):
    """Response model for plugin connection test."""

    success: bool = Field(..., description="Whether the test succeeded")
    message: str = Field(..., description="Test result message")
    timestamp: str = Field(..., description="When the test was performed (ISO format)")


# ============================================================================
# Statistics Models
# ============================================================================

class StatisticsResponse(BaseModel):
    """Response model for overall statistics."""

    total_authors: int = Field(..., description="Total number of authors")
    total_publications: int = Field(..., description="Total number of publications")
    total_citations: int = Field(..., description="Total citations across all publications")
    active_jobs: int = Field(..., description="Number of active scheduled jobs")
    configured_plugins: int = Field(..., description="Number of configured plugins")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_authors": 42,
                "total_publications": 1247,
                "total_citations": 12845,
                "active_jobs": 3,
                "configured_plugins": 2
            }
        }
    )


# ============================================================================
# Fetch Models
# ============================================================================

class FetchRequest(BaseModel):
    """Request model for triggering a fetch operation."""

    author_ids: Optional[List[str]] = Field(None, description="Specific authors (None = all)")
    from_year: Optional[int] = Field(None, description="Only fetch publications from this year onwards")
    notify: bool = Field(False, description="Send notification after fetch")
    plugin_name: Optional[str] = Field(None, description="Plugin to use for notification")


class FetchStatus(BaseModel):
    """Response model for fetch operation status."""

    status: str = Field(..., description="Status (idle/running/completed/failed)")
    started_at: Optional[str] = Field(None, description="When the fetch started (ISO format)")
    completed_at: Optional[str] = Field(None, description="When the fetch completed (ISO format)")
    authors_processed: int = Field(0, description="Number of authors processed")
    total_authors: int = Field(0, description="Total number of authors to process")
    publications_found: int = Field(0, description="Number of new publications found")
    message: Optional[str] = Field(None, description="Status message or error")


# ============================================================================
# System Models
# ============================================================================

class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str = Field(..., description="Service status (healthy/degraded/unhealthy)")
    version: str = Field(..., description="API version")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")
    database_ok: bool = Field(..., description="Database connection status")


class VersionResponse(BaseModel):
    """Response model for version information."""

    api_version: str = Field(..., description="API version")
    app_version: str = Field(..., description="Application version")
    python_version: str = Field(..., description="Python version")


# ============================================================================
# Error Models
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response model."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[dict] = Field(None, description="Additional error details")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "ValidationError",
                "message": "Invalid scholar_id format",
                "detail": {"field": "scholar_id", "issue": "must be alphanumeric"}
            }
        }
    )
