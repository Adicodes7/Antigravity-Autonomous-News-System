import logging
from typing import Dict, Any

from agents.researcher import ResearcherAgent
from agents.summarizer import SummarizerAgent
from agents.insight import InsightAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PlannerAgent:
    """
    Controller for the multi-agent news system. Coordinates the workflow between
    the Researcher, Summarizer, and Insight agents to produce a unified intelligence report.
    """
    def __init__(self):
        logger.info("Initializing multi-agent system controller...")
        try:
            self.researcher = ResearcherAgent()
            self.summarizer = SummarizerAgent()
            self.insight = InsightAgent()
            logger.info("All sub-agents initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize agent system: {e}")
            raise e

    def execute_news_workflow(self, query: str = "latest world news", language: str = "en") -> Dict[str, Any]:
        """
        Executes the end-to-end news processing workflow.
        
        Steps:
        1. Fetch raw news articles (ResearcherAgent)
        2. Generate top 10 bulleted summary (SummarizerAgent)
        3. Analyze trends, sentiment, and entities (InsightAgent)
        
        Args:
            query (str): The search query to initiate research.
            
        Returns:
            Dict[str, Any]: Structured result containing the raw articles, summary, and insights.
        """
        logger.info(f"Starting news workflow for query: '{query}'")
        
        result = {
            "query": query,
            "articles": [],
            "summary": "",
            "insights": "",
            "status": "success",
            "error_message": None
        }
        
        # Step 1: Research
        try:
            logger.info("Executing Phase 1: Research")
            result["articles"] = self.researcher.fetch_latest_news(query=query, language=language)
            if not result["articles"]:
                result["status"] = "failed"
                result["error_message"] = "No articles found or failed to fetch articles."
                logger.warning(result["error_message"])
                return result
        except Exception as e:
            logger.error(f"Workflow interrupted at Research stage: {e}")
            result["status"] = "failed"
            result["error_message"] = f"Research Error: {e}"
            return result
            
        # Step 2: Summarize
        try:
            logger.info("Executing Phase 2: Summarization")
            result["summary"] = self.summarizer.summarize_news(result["articles"], language=language)
        except Exception as e:
            logger.error(f"Workflow interrupted at Summarization stage: {e}")
            result["status"] = "partial_success"
            result["summary"] = f"Error generating summary: {e}"
            
        # Step 3: Insight Analysis
        try:
            logger.info("Executing Phase 3: Insight Extraction")
            result["insights"] = self.insight.analyze_news(result["articles"])
        except Exception as e:
            logger.error(f"Workflow interrupted at Insight stage: {e}")
            if result["status"] != "failed":
                result["status"] = "partial_success"
            result["insights"] = f"Error generating insights: {e}"
            
        logger.info(f"News workflow completed with status: {result['status']}.")
        return result

# Example usage
if __name__ == "__main__":
    try:
        planner = PlannerAgent()
        report = planner.execute_news_workflow()
        print("\n" + "="*50)
        print("### SUMMARY ###\n")
        print(report["summary"])
        print("\n" + "="*50)
        print("### INSIGHTS ###\n")
        print(report["insights"])
        print("\n" + "="*50)
    except Exception as e:
        print(f"System Control Error: {e}")
