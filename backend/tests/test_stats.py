from datetime import datetime, timezone

from backend.main import SessionLocal
from backend.models import Job


def _seed_db(session, job_id, title, company, tags, day):
    session.add(Job(
        job_id=job_id,
        title=title,
        company=company,
        tags=tags,
        location="Remote",
        date_posted=datetime(2026, 8, day, tzinfo=timezone.utc),
        url=f"https://remoteok.com/remote-jobs/{job_id}",
    ))


def test_stats_response_shape(client):
    session = SessionLocal()
    _seed_db(session, "1001", "Python Dev", "Stripe", "python,flask", 30)
    _seed_db(session, "1002", "Django Dev", "Personio", "python, django", 30)
    _seed_db(session, "1003", "DevOps Eng", "Celonis", "docker,kubernetes", 31)
    session.commit()
    session.close()

    resp = client.get("/stats")
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["status"] == "success"

    assert isinstance(data["total_jobs"], int)
    assert data["total_jobs"] == 3

    assert isinstance(data["top_tags"], list)
    assert len(data["top_tags"]) <= 5
    for entry in data["top_tags"]:
        assert isinstance(entry["tag"], str)
        assert isinstance(entry["count"], int)
    assert data["top_tags"][0] == {"tag": "python", "count": 2}

    assert isinstance(data["jobs_per_day"], list)
    for entry in data["jobs_per_day"]:
        assert isinstance(entry["date"], str)
        assert isinstance(entry["count"], int)


def test_stats_empty_database(client):
    resp = client.get("/stats")
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["total_jobs"] == 0
    assert data["top_tags"] == []
    assert data["jobs_per_day"] == []