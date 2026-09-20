"""
Non-interactive entry point for the autonomous news pipeline.

Runs the existing PlannerAgent workflow exactly once, then exits.
Used by GitHub Actions as a scheduled worker. Does not start Streamlit
and does not contain an infinite scheduler loop.
"""
import logging
import sys

from utils.scheduler import run_news_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger("run_automation")


def main() -> int:
    logger.info("GitHub Actions / CLI automation starting (single execution).")
    try:
        result = run_news_pipeline(raise_on_failure=True)
        status = (result or {}).get("status", "unknown")
        logger.info(f"Automation finished with status: {status}")
        if status == "failed":
            logger.error(result.get("error_message", "Unknown automation failure"))
            return 1
        return 0
    except Exception:
        logger.exception("Automation failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
