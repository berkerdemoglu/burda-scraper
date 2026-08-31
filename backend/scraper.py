import logging
from typing import List, Dict, Any

import requests

### Parse and clean the relevant fields: job title, company, tags/skills, location, date posted, URL ###


# Use logger for debugging
logger = logging.getLogger(__name__)


class Scraper:
    API_URL = 'https://remoteok.com/api'
    REQUEST_TIMEOUT = 10  # 10 secs

    def __init__(self):
        self.session = requests.Session()

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        """Call the RemoteOK API and return the unprocessed job entries."""
        try:
            response = self.session.get(
                self.API_URL, timeout=self.REQUEST_TIMEOUT
            )
            response.raise_for_status()
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

    def run(self) -> List[Dict[str, Any]]:
        """Runs the scraper. Fetches jobs from the API, normalizes them and drops irregular entries."""
        # TODO: Implement full scraper functionality
        return self.fetch_jobs()
