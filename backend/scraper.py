import logging
import html
import re
from typing import List, Dict, Any, Union
from datetime import datetime, timezone

import requests

# Use logger for debugging
logger = logging.getLogger(__name__)


class Scraper:
    API_URL = "https://remoteok.com/api"
    REQUEST_TIMEOUT = 10  # 10 secs

    def __init__(self):
        self.session = requests.Session()

    def _clean_text(self, value: Any) -> str:
        """Convert any API value to clean, unescaped, single-spaced string."""
        if value is None:
            return ""
        
        text = str(value)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        """Call the RemoteOK API and return the unprocessed job entries."""
        try:
            response = self.session.get(
                self.API_URL, timeout=self.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            response.encoding = "utf-8"
        except requests.RequestException:
            logger.exception("Failed to fetch data from RemoteOK API")
            return []

        try:
            data = response.json()
        except ValueError:
            logger.exception("RemoteOK API returned non-JSON content")
            return []

        if not isinstance(data, list) or len(data) < 2:
            logger.warning(f"Unexpected RemoteOK response shape: {type(data)}")
            return []

        return data[1:]  # 0-th entry is legal notice so skip that

    def normalize_raw_job(self, raw_job: Dict) -> Union[Dict, None]:
        """Safely extracts and cleans raw dictionary fields from a (raw) job entry."""
        job_id = str(raw_job.get("id", "")).strip()
        title = self._clean_text(raw_job.get("position"))
        company = self._clean_text(raw_job.get("company"))
        url = str(raw_job.get("url", "")).strip()

        # Drop entries missing non-nullable fields
        if not job_id or not title or not company or not url:
            return None

        # Flatten list of tags to comma separated string
        raw_tags = raw_job.get("tags", list())
        if isinstance(raw_tags, list):
            cleaned_tags = []
            for t in raw_tags:
                cleaned_tag = self._clean_text(t)
                if cleaned_tag:
                    cleaned_tags.append(cleaned_tag)
            tags = ", ".join(cleaned_tags) or None
        else:
            tags = self._clean_text(raw_tags) or None

        location = self._clean_text(raw_job.get("location")) or None

        # Parse date_posted from Unix timestamp (epoch seconds) or ISO date string
        epoch = raw_job.get("epoch")
        date_posted = None
        if epoch:
            try:
                date_posted = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
            except (ValueError, TypeError, OSError):
                date_posted = None

        if date_posted is None:
            raw_date = raw_job.get("date")
            if raw_date and isinstance(raw_date, str):
                try:
                    date_posted = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                except ValueError:
                    date_posted = None

        return {
            "job_id": job_id,
            "title": title,
            "company": company,
            "tags": tags,
            "location": location,
            "date_posted": date_posted,
            "url": url,
        }

    def run(self) -> List[Dict[str, Any]]:
        """Runs the scraper. Fetches jobs from the API, normalizes them and drops irregular entries."""
        raw_jobs = self.fetch_jobs()
        normalized_jobs = []
        for job in raw_jobs:
            normalized_job = self.normalize_raw_job(job)
            if normalized_job is not None:
                normalized_jobs.append(normalized_job)

        logger.info(f"Successfully fetched and normalized {len(normalized_jobs)} jobs.")

        return normalized_jobs
