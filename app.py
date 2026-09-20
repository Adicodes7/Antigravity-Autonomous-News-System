import streamlit as st
import logging
from datetime import datetime
import threading

from agents.planner import PlannerAgent
from agents.memory import MemoryAgent
from utils.emailer import send_email
from utils.pdf_generator import generate_pdf
from utils.scheduler import main as start_scheduler
from utils.key_manager import get_key_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Threading Check for Scheduler ---
def init_background_scheduler():
    """Initializes exactly one background scheduler thread across all Streamlit sessions."""
    for t in threading.enumerate():
        if t.name == "news_scheduler":
            # Already active.
            return
    logger.info("Starting global background scheduler thread...")
    t = threading.Thread(target=start_scheduler, name="news_scheduler", daemon=True)
    t.start()

# Only run once on script load
try:
    init_background_scheduler()
except Exception as e:
    logger.error(f"Scheduler failed to initialize: {e}")

def main():
    st.set_page_config(page_title="Antigravity News", page_icon="📰", layout="wide")
    
    st.title("📰 Autonomous News Intelligence Platform")
    st.markdown("Get the latest world news, curated, summarized, and analyzed by AI.")
    
    if 'planner' not in st.session_state:
        with st.spinner("Initializing AI Orchestrator & Memory..."):
            try:
                st.session_state.planner = PlannerAgent()
                st.session_state.memory = MemoryAgent()
            except Exception as e:
                st.error(f"Error initializing agents: {e}")
                st.stop()
                
    planner = st.session_state.planner
    memory = st.session_state.memory

    # --- Sidebar ---
    with st.sidebar:
        st.header("⚙️ Controls")
        
        # FEATURE 3: Language selection
        lang_choice = st.selectbox("🌐 Select Language", ["English", "Hindi"])
        lang_map = {"English": "en", "Hindi": "hi"}
        selected_lang = lang_map[lang_choice]
        
        # FEATURE 2: Search Box
        st.subheader("🔍 Search News")
        search_query = st.text_input("Search news by topic", value="latest world news")
        search_button = st.button("Search", use_container_width=True)
        
        st.subheader("🔄 Update Feeds")
        refresh_button = st.button("Refresh News", type="primary", use_container_width=True)
        
        st.divider()
        
        # --- FEATURE 1: Email Automation Preferences ---
        st.header("🤖 Automation Settings")
        
        # Pre-load existing configs
        prefs = memory.load_user_preferences()
        curr_email = prefs.get("email", "")
        curr_freq = prefs.get("frequency", 24)
        
        # Map frequency backward to string indices
        freq_options = ["Every 2 hours", "Every 12 hours", "Every 24 hours"]
        freq_vals = [2, 12, 24]
        try:
            default_idx = freq_vals.index(curr_freq)
        except ValueError:
            default_idx = 2
            
        auto_email = st.text_input("Automation Email", value=curr_email, placeholder="recipient@example.com")
        auto_freq = st.selectbox("Update Frequency", freq_options, index=default_idx)
        
        if st.button("Save Preferences", use_container_width=True):
            mapped_freq = freq_vals[freq_options.index(auto_freq)]
            
            # Use the new robust save_user_preferences method
            prefs_to_save = {
                "email": auto_email,
                "frequency": mapped_freq,
                "language": selected_lang,
                "topics": search_query
            }
            success = memory.save_user_preferences(prefs_to_save)
            
            if success:
                st.success("Preferences saved! System Active.")
                st.info(f"Auto updates enabled: Emails will be sent every {mapped_freq} hours.")
            else:
                st.error("Error saving preferences.")
        
        st.divider()
        st.header("🕰️ System Status")
        recent_runs = memory.get_recent_summaries(limit=1)
        if recent_runs:
            last_dt = datetime.fromisoformat(recent_runs[0]["timestamp"])
            st.success(f"Last Updated:\n\n**{last_dt.strftime('%b %d, %Y - %H:%M:%S')}**")
        else:
            st.info("No prior runs recorded.")

        st.divider()
        st.header("🔑 API Key Status")
        try:
            km = get_key_manager()
            status = km.get_status()
            st.metric(
                label="Gemini Key Active",
                value=f"Key #{status['gemini_key_active']} / {status['gemini_keys_total']}"
            )
            st.metric(
                label="Serper Key Active",
                value=f"Key #{status['serper_key_active']} / {status['serper_keys_total']}"
            )
            if status['gemini_key_active'] > 1:
                st.warning(f"⚠️ Gemini rotated to key #{status['gemini_key_active']} (quota hit)")
            if status['serper_key_active'] > 1:
                st.warning(f"⚠️ Serper rotated to key #{status['serper_key_active']} (quota hit)")
        except Exception as e:
            st.error(f"Key manager error: {e}")

    # --- Triggering the Workflow ---
    run_pipeline = False
    query_to_use = search_query if search_query else "latest world news"
    
    if 'current_report' not in st.session_state:
        run_pipeline = True  
    elif search_button or refresh_button:
        run_pipeline = True
        
    if run_pipeline:
        with st.spinner(f"Autonomous Agents are actively researching '{query_to_use}' in {lang_choice}..."):
            report = planner.execute_news_workflow(query=query_to_use, language=selected_lang)
            
            if report["status"] == "failed":
                st.error(f"Workflow Failed: {report.get('error_message', 'Unknown Error')}")
            else:
                if report["status"] == "partial_success":
                    st.warning("Workflow completed with some errors. The intelligence report may be incomplete.")
                
                # Commit memory
                memory.save_summary(report.get("summary", ""), report.get("insights", ""))
                st.toast("Intelligence Report generated & saved successfully!", icon="✅")
                st.session_state.current_report = report

    # --- Main Tab Dashboard ---
    tab1, tab2 = st.tabs(["📊 Latest Intelligence", "🗄️ Past Memory Archives"])
    
    with tab1:
        if 'current_report' in st.session_state:
            report = st.session_state.current_report
            summary_text = report.get("summary", "No summary available.")
            
            # Action Buttons - Manual PDF & Email
            st.markdown("### 🛠️ Manual Actions")
            action_col1, action_col2, action_col3 = st.columns([2, 1, 1], gap="small")
            
            with action_col1:
                receiver_email = st.text_input("Enter your email manually", placeholder="user@example.com", label_visibility="collapsed")
            with action_col2:
                if st.button("Send to Email Now", use_container_width=True):
                    if receiver_email:
                        with st.spinner("Sending email..."):
                            success = send_email(summary_text, receiver_email)
                            if success:
                                st.success("Email sent successfully!")
                            else:
                                st.error("Failed to send email. Check credentials or inputs.")
                    else:
                        st.warning("Please enter an email address manually, or use Sidebar automation.")
            
            with action_col3:
                pdf_path = generate_pdf(summary_text)
                if pdf_path:
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            label="Download as PDF",
                            data=f,
                            file_name="news_summary.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                else:
                    st.button("PDF Loading Error", disabled=True, use_container_width=True)
            
            st.divider()
            
            # FEATURE 4: 2-Column Professional UI Layout
            col_left, col_right = st.columns([2, 1], gap="large")
            
            with col_left:
                st.markdown("### 📰 Top News")
                st.markdown(summary_text)
                
                st.divider()
                st.markdown("### 🔍 Search Results")
                for item in report.get("articles", []):
                    title = item.get("title", 'Unknown Source')
                    link = item.get("link", '#')
                    date = item.get("date", '')
                    if date:
                        st.markdown(f"- [{title}]({link}) ({date})")
                    else:
                        st.markdown(f"- [{title}]({link})")
                        
            with col_right:
                st.markdown("### 🧠 AI Insights")
                st.info("Trending Topics & Sentiment Analysis")
                with st.container(border=True):
                    st.markdown(report.get("insights", "No insights available."))
                    
        else:
            st.info("No Intelligence Report available. Use controls to fetch.")

    with tab2:
        st.header("🗂️ Historical Summaries")
        st.write("Browse your past multi-agent pipeline executions pulled directly from memory.")
        
        history = memory.get_recent_summaries(limit=10)
        
        if not history:
            st.write("No historical data found in memory.")
        else:
            for i, record in enumerate(history):
                dt = datetime.fromisoformat(record["timestamp"]).strftime('%b %d, %Y - %H:%M:%S')
                with st.expander(f"Report: {dt}"):
                    c_left, c_right = st.columns([2, 1])
                    with c_left:
                        st.markdown("**Summary:**")
                        st.markdown(record.get("summary", ""))
                    with c_right:
                        st.markdown("**Insights:**")
                        st.markdown(record.get("insights", ""))

if __name__ == "__main__":
    main()