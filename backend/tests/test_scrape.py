from unittest.mock import patch

from backend.main import SessionLocal
from backend.models import Job

FAKE_JOBS = [
    {
        "job_id": "2001",
        "title": "Backend Engineer",
        "company": "Notion",
        "tags": "python,postgres",
        "location": "Munich",
        "date_posted": None,
        "url": "https://remoteok.com/remote-jobs/2001",
    },
    {
        "job_id": "2002",
        "title": "Platform Engineer",
        "company": "Linear",
        "tags": "go,kubernetes",
        "location": None,
        "date_posted": None,
        "url": "https://remoteok.com/remote-jobs/2002",
    },
]


@patch("backend.main.Scraper")
def test_scrape_is_idempotent(mock_scraper_class, client):
    mock_scraper_class.return_value.run.return_value = FAKE_JOBS

    first = client.post("/scrape")
    assert first.status_code == 200
    first_data = first.get_json()
    assert first_data["added"] == 2
    assert first_data["skipped"] == 0

    second = client.post("/scrape")
    assert second.status_code == 200
    second_data = second.get_json()
    assert second_data["added"] == 0
    assert second_data["skipped"] == 2

    session = SessionLocal()
    total = session.query(Job).count()
    session.close()
    assert total == 2


@patch("backend.main.Scraper")
def test_scrape_handles_upstream_failure(mock_scraper_class, client):
    mock_scraper_class.return_value.run.side_effect = Exception("Connection timed out")

    resp = client.post("/scrape")

    assert resp.status_code == 502
    data = resp.get_json()
    assert data["status"] == "error"
    assert "message" in data
