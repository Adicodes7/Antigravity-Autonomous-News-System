import hashlib
import json
import time
import schedule
import logging
import sys
import os
from datetime import datetime, timedelta

# Add the project root to the python path so it can properly import the agents module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.planner import PlannerAgent
from agents.memory import MemoryAgent
from utils.emailer import send_email

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(_ROOT, "automation_state.json")


def _env_value(name: str) -> str:
    """Return a stripped env var, or empty string if unset/blank."""
    value = os.getenv(name)
    if value is None:
        return ""
    return value.strip()


def apply_preference_overrides(prefs: dict) -> dict:
    """
    Overlay GitHub Actions / environment configuration on top of user_config.json.

    Streamlit Cloud writes user_config.json in its own filesystem, which GitHub
    Actions cannot see. Optional env vars let scheduled runs use the latest
    recipient/topics without committing secrets.
    """
    updated = dict(prefs)
    email_override = _env_value("AUTOMATION_EMAIL")
    topics_override = _env_value("NEWS_TOPICS")
    language_override = _env_value("NEWS_LANGUAGE")
    frequency_override = _env_value("NEWS_FREQUENCY")

    if email_override:
        updated["email"] = email_override
    if topics_override:
        updated["topics"] = topics_override
    if language_override:
        updated["language"] = language_override
    if frequency_override:
        try:
            updated["frequency"] = int(frequency_override)
        except ValueError:
            logger.warning("Ignoring invalid NEWS_FREQUENCY env value (expected an integer).")
    return updated


def load_automation_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning(f"Could not read automation state file: {e}")
        return {}


def save_automation_state(state: dict) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save automation state: {e}")


def fingerprint_articles(articles: list) -> str:
    links = sorted(
        {(item or {}).get("link", "").strip() for item in articles if (item or {}).get("link")}
    )
    titles = sorted(
        {(item or {}).get("title", "").strip() for item in articles if (item or {}).get("title")}
    )
    raw = json.dumps({"links": links, "titles": titles}, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _is_agent_error_text(text: str) -> bool:
    return isinstance(text, str) and text.startswith("An error occurred while")


def _should_skip_for_frequency(prefs: dict, state: dict, force: bool) -> bool:
    if force:
        return False
    try:
        freq_hours = int(prefs.get("frequency", 2) or 2)
    except (TypeError, ValueError):
        freq_hours = 2
    last_run = state.get("last_successful_run_at")
    if not last_run:
        return False
    try:
        last_dt = datetime.fromisoformat(last_run)
    except ValueError:
        return False
    # Allow a small window so slightly-early GitHub cron still runs.
    min_wait = timedelta(hours=freq_hours) - timedelta(minutes=20)
    elapsed = datetime.now() - last_dt
    if elapsed < min_wait:
        logger.info(
            f"Skipping pipeline: last successful run was {elapsed} ago "
            f"(configured frequency is every {freq_hours} hours)."
        )
        return True
    return False


def run_news_pipeline(raise_on_failure: bool = False) -> dict:
    """
    Run the existing PlannerAgent news pipeline exactly once.

    This function is reused by:
    - the Streamlit background scheduler (continuous loop in main())
    - GitHub Actions via run_automation.py (one shot, then exit)
    """
    logger.info("Starting autonomous news workflow (single run)...")
    try:
        memory = MemoryAgent()
        prefs = apply_preference_overrides(memory.load_user_preferences())
        email_addr = (prefs.get("email") or "").strip()
        query = (prefs.get("topics") or "latest world news").strip()
        language = (prefs.get("language") or "en").strip()
        force = (
            _env_value("FORCE_AUTOMATION") == "1"
            or _env_value("GITHUB_EVENT_NAME") == "workflow_dispatch"
        )

        logger.info(
            f"Loaded preferences: query={query!r}, language={language!r}, "
            f"frequency={prefs.get('frequency')}, recipient_configured={bool(email_addr)}"
        )

        state = load_automation_state()
        if _should_skip_for_frequency(prefs, state, force):
            return {"status": "skipped", "reason": "frequency_window"}

        planner = PlannerAgent()
        report = planner.execute_news_workflow(query=query, language=language)
        status = report.get("status")
        summary_text = report.get("summary", "") or ""
        insights_text = report.get("insights", "") or ""
        articles = report.get("articles") or []

        logger.info(
            f"Planner finished with status={status!r}, "
            f"articles={len(articles)}, summary_chars={len(summary_text)}"
        )

        if status == "failed" or not articles:
            message = report.get("error_message") or "News workflow failed."
            raise RuntimeError(message)

        if _is_agent_error_text(summary_text):
            raise RuntimeError(summary_text)
        if _is_agent_error_text(insights_text):
            raise RuntimeError(insights_text)

        digest_fp = fingerprint_articles(articles)
        if digest_fp and digest_fp == state.get("last_digest_fingerprint"):
            logger.info("Skipping email: article set matches the previous digest.")
            state["last_duplicate_skip_at"] = datetime.now().isoformat()
            save_automation_state(state)
            return {"status": "skipped", "reason": "duplicate_digest"}

        saved = memory.save_summary(summary_text, insights_text)
        if not saved:
            raise RuntimeError("Failed to save news memory.")

        if not email_addr:
            raise RuntimeError(
                "No automation recipient email configured. "
                "Set user_config.json 'email' or the AUTOMATION_EMAIL environment variable."
            )

        logger.info("Sending digest email to the configured recipient...")
        emailed = send_email(summary_text, email_addr)
        if not emailed:
            raise RuntimeError(
                "Email delivery failed. Check SENDER_EMAIL / SENDER_PASSWORD "
                "(Gmail requires an App Password) and SMTP connectivity."
            )

        state.update({
            "last_successful_run_at": datetime.now().isoformat(),
            "last_digest_fingerprint": digest_fp,
            "last_query": query,
            "last_language": language,
            "last_article_count": len(articles),
        })
        save_automation_state(state)
        logger.info("Autonomous news workflow completed successfully.")
        report["status"] = status
        return report

    except Exception as e:
        logger.error(f"Critical error during scheduled job execution: {e}")
        if raise_on_failure:
            raise
        return {"status": "failed", "error_message": str(e)}


def get_job_frequency() -> int:
    try:
        memory = MemoryAgent()
        prefs = apply_preference_overrides(memory.load_user_preferences())
        return prefs.get("frequency", 24)
    except Exception:
        return 24

current_freq = 0
first_boot = True

def update_schedule_if_needed():
    global current_freq, first_boot
    freq = get_job_frequency()
    
    # Reload schedule only if user changed the frequency or on first boot
    if freq != current_freq:
        logger.info(f"Updating schedule frequency to run every {freq} hours.")
        schedule.clear()
        
        # Mapping to the exact criteria
        if freq == 2:
            schedule.every(2).hours.do(run_news_pipeline)
        elif freq == 12:
            schedule.every(12).hours.do(run_news_pipeline)
        else:
            schedule.every(24).hours.do(run_news_pipeline)
            
        current_freq = freq
        
        # KEY FIX: Run immediately on first boot or when frequency changes.
        # Without this, the schedule library waits the FULL interval before
        # firing for the first time, meaning a 2-hour schedule wouldn't
        # send anything for 2 hours — and Streamlit restarts reset this timer.
        logger.info("Running pipeline immediately (first run / frequency changed)...")
        import threading
        immediate = threading.Thread(target=run_news_pipeline, name="news_immediate_run", daemon=True)
        immediate.start()
        first_boot = False

def main():
    """
    Initializes the schedule configuration and runs the continuous background loop smoothly.
    Designed to run seamlessly inside a background thread (Streamlit).
    GitHub Actions must NOT use this loop; it should call run_news_pipeline once.
    """
    logger.info("Antigravity Autonomous News Scheduler starting up...")
    update_schedule_if_needed()
    logger.info("Waiting in background loop... Automations are actively checking.")
    
    try:
        while True:
            update_schedule_if_needed()
            schedule.run_pending()
            time.sleep(10)  # Check every 10 seconds to not block UI/CPU heavily
    except KeyboardInterrupt:
        logger.info("Scheduler manually stopped. Exiting cleanly.")

if __name__ == "__main__":
    main()
