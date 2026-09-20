import os
import logging
from typing import List, Dict
import google.generativeai as genai
from dotenv import load_dotenv

from utils.key_manager import get_key_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class InsightAgent:
    """
    Agent responsible for analyzing a list of news articles to extract
    trending topics, overall sentiment, and key entities using Gemini.
    Automatically rotates to the next Gemini API key on quota/rate-limit errors.
    """
    def __init__(self):
        self.km = get_key_manager()
        self._configure_model()

    def _configure_model(self):
        """Configures Gemini with the currently active key."""
        genai.configure(api_key=self.km.get_gemini_key())
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    def analyze_news(self, articles: List[Dict[str, str]]) -> str:
        """
        Takes a list of news article dicts and returns a clean, structured
        markdown analysis containing trending topics, sentiment, and key entities.
        Retries automatically with the next Gemini key on quota errors.

        Args:
            articles (List[Dict[str, str]]): List of dicts with title, link, snippet, date.

        Returns:
            str: Markdown formatted string of the analysis.
        """
        if not articles:
            return "No news articles provided to analyze."

        # Format articles into a prompt string
        articles_text = ""
        for i, article in enumerate(articles, 1):
            articles_text += f"Article {i}:\n"
            articles_text += f"Title: {article.get('title', 'N/A')}\n"
            articles_text += f"Snippet: {article.get('snippet', 'N/A')}\n"
            articles_text += f"Date: {article.get('date', 'N/A')}\n\n"

        prompt = (
            "You are an expert news analyst. Review the following list of news articles "
            "and provide a highly structured analysis. Ensure the response contains EXACTLY these sections:\n\n"
            "### 📈 Trending Topics\n"
            "List the top 5 most prominent trending topics or themes across these articles.\n\n"
            "### ⚖️ Overall Sentiment\n"
            "Analyze the general tone of these articles and classify the overall sentiment as "
            "**Positive**, **Negative**, or **Neutral**. Provide a brief 1-2 sentence explanation.\n\n"
            "### 🔍 Key Entities\n"
            "Identify and categorize the most significant entities mentioned across the articles "
            "into subcategories (use bullet points):\n"
            "- **Companies**\n"
            "- **Countries**\n"
            "- **People**\n\n"
            "Format the output strictly as a clean, professional Markdown string "
            "so it can be rendered beautifully in a Streamlit application.\n\n"
            f"Here are the recent world news articles to analyze:\n\n{articles_text}"
        )

        # Retry loop — tries every available Gemini key at most once
        max_attempts = len(self.km._gemini_keys)
        last_error = None

        for attempt in range(max_attempts):
            try:
                logger.info(
                    f"Sending articles to Gemini for insight analysis "
                    f"(key #{self.km._indices['current_gemini_key'] + 1})..."
                )
                response = self.model.generate_content(
                    prompt,
                    generation_config={"temperature": 0.2}
                )
                analysis = response.text
                logger.info("Successfully generated news analysis.")
                return analysis

            except Exception as e:
                last_error = e
                logger.warning(f"[InsightAgent] Gemini error on attempt {attempt + 1}: {e}")
                rotated = self.km.rotate_gemini_key(e)
                if rotated:
                    # Re-configure the SDK with the new key before retrying
                    self._configure_model()
                    continue
                else:
                    # Not a quota error, or all keys exhausted — stop retrying
                    break

        error_msg = f"An error occurred while analyzing the news insights: {last_error}"
        logger.error(f"[InsightAgent] All attempts failed: {last_error}")
        return error_msg


# Example usage
if __name__ == "__main__":
    sample_articles = [
        {
            "title": "Tech Giant Unveils Revolutionary AI Model",
            "snippet": "The new AI model promises to revolutionize multiple industries including healthcare and finance.",
            "date": "2 hours ago"
        },
        {
            "title": "Global Markets Rally Amid Positive Economic Data",
            "snippet": "Stock markets around the world saw significant gains following better-than-expected inflation numbers from the US.",
            "date": "4 hours ago"
        }
    ]

    try:
        analyzer = InsightAgent()
        result = analyzer.analyze_news(sample_articles)
        print("Generated Insights:\n")
        print(result)
    except Exception as e:
        print(f"Setup Error: {e}")
