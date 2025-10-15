# Scholar Slack Bot API Documentation

Welcome to the Scholar Slack Bot REST API documentation. This API provides programmatic access to all features of the Scholar Publication Monitoring Bot.

## Quick Links

- **[Getting Started](#getting-started)** - Installation and first steps
- **[Authentication](#authentication)** - API security
- **[API Reference](reference.md)** - Complete endpoint documentation
- **[Examples](examples.md)** - Code examples and common use cases
- **[Interactive Docs](#interactive-documentation)** - Swagger UI and ReDoc

## Overview

The Scholar Slack Bot API is a RESTful API that allows you to:

- 📚 Manage monitored authors
- 🔍 Query and filter publications
- 🔌 Configure messaging platform plugins
- 📊 Retrieve system statistics

## Getting Started

### Starting the API Server

```bash
# Activate the scholarbot environment
conda activate scholarbot

# Start the server
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000

# Or with auto-reload for development
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

### Your First API Call

```bash
# Check if the API is running
curl http://localhost:8000/api/v1/health

# Get all authors
curl http://localhost:8000/api/v1/authors

# Query publications from 2024
curl "http://localhost:8000/api/v1/publications?min_year=2024&limit=10"
```

## Authentication

The API supports optional API key authentication:

### Development Mode (No Authentication)

By default, if no `API_KEY` environment variable is set, the API allows all requests:

```bash
# No authentication needed in development mode
curl http://localhost:8000/api/v1/authors
```

### Production Mode (API Key Required)

Set the `API_KEY` environment variable to enable authentication:

```bash
export API_KEY="your-secret-api-key-here"
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

Then provide the key via header or bearer token:

```bash
# Option 1: X-API-Key header
curl -H "X-API-Key: your-secret-api-key-here" \
     http://localhost:8000/api/v1/authors

# Option 2: Bearer token
curl -H "Authorization: Bearer your-secret-api-key-here" \
     http://localhost:8000/api/v1/authors
```

## Interactive Documentation

The API provides two interactive documentation interfaces:

### Swagger UI
Visit http://localhost:8000/docs for an interactive API explorer where you can:
- Browse all endpoints
- Try API calls directly from your browser
- See request/response examples
- View data models

### ReDoc
Visit http://localhost:8000/redoc for a clean, readable API reference.

## Base URL

All API endpoints are prefixed with `/api/v1`:

```
http://localhost:8000/api/v1/
```

## Response Format

All responses are in JSON format. Successful responses return the requested data:

```json
{
  "id": "abc123",
  "name": "John Doe",
  "publication_count": 45
}
```

Error responses include an error message:

```json
{
  "error": "NotFound",
  "message": "Author with ID abc123 not found",
  "detail": null
}
```

## HTTP Status Codes

The API uses standard HTTP status codes:

| Status Code | Meaning |
|------------|---------|
| `200 OK` | Request succeeded |
| `201 Created` | Resource created successfully |
| `204 No Content` | Request succeeded, no content to return |
| `400 Bad Request` | Invalid request parameters |
| `401 Unauthorized` | Authentication required or failed |
| `404 Not Found` | Resource not found |
| `409 Conflict` | Resource already exists |
| `422 Unprocessable Entity` | Validation error |
| `500 Internal Server Error` | Server error |

## Rate Limiting

Rate limiting is planned for a future version but not currently implemented.

## Endpoints Overview

### System Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API root with basic info |
| `/api/v1/health` | GET | Health check |
| `/api/v1/version` | GET | Version information |
| `/api/v1/stats` | GET | Overall statistics |

### Authors

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/authors` | GET | List all authors |
| `/api/v1/authors` | POST | Add a new author |
| `/api/v1/authors/{id}` | GET | Get author details |
| `/api/v1/authors/{id}` | DELETE | Delete an author |
| `/api/v1/authors/{id}/publications` | GET | Get author's publications |

### Publications

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/publications` | GET | Query publications with filters |
| `/api/v1/publications/stats` | GET | Publication statistics |
| `/api/v1/publications/{author_id}/{title}` | DELETE | Delete a publication |

### Plugins

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/plugins` | GET | List all plugins |
| `/api/v1/plugins/{name}` | GET | Get plugin details |
| `/api/v1/plugins/{name}/config` | PUT | Update plugin configuration |
| `/api/v1/plugins/{name}/test` | POST | Test plugin connection |
| `/api/v1/plugins/{name}/notify` | POST | Send test notification |

## Next Steps

- Browse the **[Complete API Reference](reference.md)** for detailed endpoint documentation
- Check out **[Code Examples](examples.md)** for common use cases
- Try the **[Interactive Documentation](http://localhost:8000/docs)** at /docs

## Support

For issues or questions:
- Check the [GitHub Issues](https://github.com/yourusername/scholar-slack-bot/issues)
- Read the main [README](../../README.md)
- Review the [MODERNIZATION_PLAN.md](../../MODERNIZATION_PLAN.md) for architecture details
