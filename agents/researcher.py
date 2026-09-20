import os
import logging
import requests
from typing import List, Dict, Any
from dotenv import load_dotenv

from utils.key_manager import get_key_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class ResearcherAgent:
    """
    Agent responsible for fetching the latest world news using the Serper API.
    Automatically rotates to the next Serper API key if a quota/rate-limit error
    is encountered.
    """
    def __init__(self):
        self.km = get_key_manager()
        self.base_url = "https://google.serper.dev/news"

    def fetch_latest_news(self, query: str = "latest world news", language: str = "en") -> List[Dict[str, str]]:
        """
        Fetches news articles related to the given query.
        Retries automatically with the next Serper key on quota errors.

        Args:
            query (str): The search query to use. Defaults to 'latest world news'.
            language (str): Language code, e.g. 'en' or 'hi'.

        Returns:
            List[Dict[str, str]]: A list of dicts with title, link, snippet, and date.
        """
        payload = {
            "q": query,
            "num": 20,
            "hl": language,
            "gl": "in"
        }

        # Retry loop — tries every available Serper key at most once
        max_attempts = self.km._serper_keys.__len__()
        for attempt in range(max_attempts):
            active_key = self.km.get_serper_key()
            headers = {
                'X-API-KEY': active_key,
                'Content-Type': 'application/json'
            }

            try:
                logger.info(
                    f"Fetching news with query: '{query}' "
                    f"(Serper key #{self.km._indices['current_serper_key'] + 1})"
                )
                response = requests.post(self.base_url, headers=headers, json=payload, timeout=15)

                # Serper returns 429 or 402 on quota exhaustion
                if response.status_code in (429, 402):
                    error_text = f"HTTP {response.status_code}: {response.text}"
                    logger.warning(f"[ResearcherAgent] Quota signal received: {error_text}")
                    rotated = self.km.rotate_serper_key(Exception(error_text))
                    if rotated:
                        continue   # retry with next key
                    else:
                        logger.error("[ResearcherAgent] All Serper keys exhausted.")
                        return []

                response.raise_for_status()
                data = response.json()
                articles = self._parse_results(data)
                logger.info(f"Successfully fetched {len(articles)} articles.")
                return articles

            except requests.exceptions.RequestException as e:
                # Check if it's a quota-type network error
                if self.km.rotate_serper_key(e):
                    logger.warning(f"[ResearcherAgent] Network quota error, retrying: {e}")
                    continue
                logger.error(f"[ResearcherAgent] Non-quota network error: {e}")
                return []

        logger.error("[ResearcherAgent] All retry attempts failed.")
        return []

    def _parse_results(self, data: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Parses the raw JSON response from Serper API into a structured format.
        """
        articles = []
        news_results = data.get("news", [])

        for item in news_results:
            article = {
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "date": item.get("date", "")
            }
            articles.append(article)

        return articles


# Example usage
if __name__ == "__main__":
    try:
        researcher = ResearcherAgent()
        news = researcher.fetch_latest_news()
        for i, n in enumerate(news[:3], 1):
            print(f"{i}. {n['title']} ({n['date']})\n   {n['link']}\n   {n['snippet']}\n")
    except Exception as e:
        print(f"Setup Error: {e}")
