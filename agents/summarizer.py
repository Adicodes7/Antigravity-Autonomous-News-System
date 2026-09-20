import os
import logging
import google.generativeai as genai
from typing import List, Dict
from dotenv import load_dotenv

from utils.key_manager import get_key_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class SummarizerAgent:
    """
    Agent responsible for summarizing a list of news articles into a top-10 bulleted
    list using Google Gemini API, formatted cleanly for Streamlit visualization.
    Automatically rotates to the next Gemini API key on quota/rate-limit errors.
    """
    def __init__(self):
        self.km = get_key_manager()
        self._configure_model()

    def _configure_model(self):
        """Configures Gemini with the currently active key."""
        genai.configure(api_key=self.km.get_gemini_key())
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    def summarize_news(self, articles: List[Dict[str, str]], language: str = "en") -> str:
        """
        Takes a list of news article dicts and returns a markdown-formatted
        bulleted list of the top 10 news stories using Gemini.
        Retries automatically with the next Gemini key on quota errors.

        Args:
            articles (List[Dict[str, str]]): List of dicts with title, link, snippet, date.
            language (str): Language code, e.g. 'en' or 'hi'.

        Returns:
            str: Markdown formatted string of the top 10 news.
        """
        if not articles:
            return "No news articles provided to summarize."

        # Format articles into a prompt string
        articles_text = ""
        for i, article in enumerate(articles, 1):
            articles_text += f"Article {i}:\n"
            articles_text += f"Title: {article.get('title', 'N/A')}\n"
            articles_text += f"Snippet: {article.get('snippet', 'N/A')}\n"
            articles_text += f"Date: {article.get('date', 'N/A')}\n"
            articles_text += f"Link: {article.get('link', 'N/A')}\n\n"

        prompt = (
            "You are an expert news editor and summarizer. "
            "Your task is to review the following list of news articles and create a clean, professional, "
            "and engaging summary of the most impactful world news stories. "
            "Follow these strict rules:\n"
            "1. Remove any duplicate news entries.\n"
            "2. Prioritize important, high-impact global events.\n"
            "3. Format the output strictly as a Markdown bulleted list suitable for Streamlit.\n"
            "4. For each bullet point, include the story title in bold, followed by a concise 1-2 line summary.\n"
            "5. Embed the original link cleanly as an inline markdown link like '[Read more](url)' at the end of the bullet point.\n"
            "6. You MUST output a minimum of 8 to 10 bullet points. DO NOT skip any important topics.\n"
            "7. Do not include extra conversational filler; just provide the formatted list.\n"
            f"8. CRITICAL: The ENTIRE summary output MUST be written in the '{language}' language code. "
            f"If it is 'hi', output entirely in Hindi. If it is 'en', output entirely in English.\n\n"
            f"Here are the recent world news articles to summarize:\n\n{articles_text}"
        )

        # Retry loop — tries every available Gemini key at most once
        max_attempts = len(self.km._gemini_keys)
        last_error = None

        for attempt in range(max_attempts):
            try:
                logger.info(
                    f"Sending articles to Gemini for summarization "
                    f"(key #{self.km._indices['current_gemini_key'] + 1})..."
                )
                response = self.model.generate_content(
                    prompt,
                    generation_config={"temperature": 0.3}
                )
                summary = response.text
                logger.info("Successfully generated news summary.")
                return summary

            except Exception as e:
                last_error = e
                logger.warning(f"[SummarizerAgent] Gemini error on attempt {attempt + 1}: {e}")
                rotated = self.km.rotate_gemini_key(e)
                if rotated:
                    # Re-configure the SDK with the new key before retrying
                    self._configure_model()
                    continue
                else:
                    # Not a quota error, or all keys exhausted — stop retrying
                    break

        error_msg = f"An error occurred while summarizing the news: {last_error}"
        logger.error(f"[SummarizerAgent] All attempts failed: {last_error}")
        return error_msg


# Example usage
if __name__ == "__main__":
    sample_articles = [
        {
            "title": "Global Summit Reaches Historic Climate Agreement",
            "link": "https://example.com/climate",
            "snippet": "Leaders from 195 countries have agreed to ambitious new carbon reduction targets starting next year.",
            "date": "2 hours ago"
        },
        {
            "title": "Major Breakthrough in Quantum Computing Unveiled",
            "link": "https://example.com/quantum",
            "snippet": "Researchers successfully maintained qubit coherence at room temperature for over a minute.",
            "date": "4 hours ago"
        }
    ]

    try:
        summarizer = SummarizerAgent()
        result = summarizer.summarize_news(sample_articles)
        print("Generated Summary:\n")
        print(result)
    except Exception as e:
        print(f"Setup Error: {e}")
