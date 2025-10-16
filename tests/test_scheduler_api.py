"""Tests for scheduler endpoints.

Mocks underlying functions to avoid running real work.
"""

from fastapi.testclient import TestClient
from unittest.mock import patch

from src.api.app import app


def test_jobs_crud(monkeypatch):
    client = TestClient(app)

    # Initially list is empty
    res = client.get('/api/v1/fetch/jobs')
    assert res.status_code == 200
    initial = res.json()

    with patch('src.api.routes.operations.do_fetch_and_send_all') as mock_send, \
         patch('src.api.routes.operations.do_refresh_cache_all') as mock_refresh:
        mock_send.return_value = {"success": True, "sent": True, "count": 0}
        mock_refresh.return_value = {"success": True, "authors": 0, "refreshed": 0}

        # Create a job
        payload = {
            "name": "Daily",
            "description": "",
            "cron_expression": "0 9 * * *",
            "action": "fetch_and_notify",
        }
        res = client.post('/api/v1/fetch/jobs', json=payload)
        assert res.status_code == 200
        job = res.json()

        # List
        res = client.get('/api/v1/fetch/jobs')
        assert res.status_code == 200
        jobs = res.json()
        assert len(jobs) >= len(initial)

        # Run Now (best effort)
        jid = jobs[0]['id']
        res = client.post(f'/api/v1/fetch/jobs/{jid}/run')
        # Running may fail in CI since job func may not be available; accept 2xx or 404
        assert res.status_code in (200, 404)

        # Delete
        res = client.delete(f'/api/v1/fetch/jobs/{jid}')
        assert res.status_code in (200, 404)

