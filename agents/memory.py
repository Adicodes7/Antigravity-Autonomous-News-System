import os
import json
import logging
from datetime import datetime   
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MemoryAgent:
    """
    Agent responsible for persistently storing and retrieving past news summaries.
    Currently utilizes a minimalist local JSON file for lightweight list-storage, 
    but effectively acts as the scaffold for a future FAISS Vector Database integration.
    """
    def __init__(self, storage_file: str = "news_memory.json"):
        # Store the memory file in the root directory alongside .env
        self.storage_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            storage_file
        )
        self.config_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            "user_config.json"
        )
        self._ensure_storage_exists()

    def _ensure_storage_exists(self):
        """Creates the local storage JSON array if it doesn't already exist."""
        if not os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'w', encoding='utf-8') as f:
                    json.dump([], f)
                logger.info(f"Created new blank memory storage list at {self.storage_file}")
            except Exception as e:
                logger.error(f"Failed to initialize memory storage file: {e}")

    def save_summary(self, summary_text: str, insights: str = "") -> bool:
        """
        Stores a generated news summary (and optionally insights) alongside an automated timestamp.
        
        Args:
            summary_text (str): The main summary text to persist in memory.
            insights (str, optional): The AI insights analysis. Defaults to "".
            
        Returns:
            bool: True if saved successfully, False otherwise.
        """
        if not summary_text:
            logger.warning("No summary provided to save into memory.")
            return False
            
        record = {
            "timestamp": datetime.now().isoformat(),
            "summary": summary_text,
            "insights": insights
        }
        
        try:
            # Load existing memory list
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                memory = json.load(f)
                
            # Append new record to the list
            memory.append(record)
            
            # Save list back
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(memory, f, indent=4)
                
            logger.info("Successfully permanently saved news generation into memory.")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save summary to memory: {e}")
            return False

    def get_recent_summaries(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves the most recent news summaries from the memory store.
        
        Args:
            limit (int): The maximum number of recent records to return. Defaults to 5.
            
        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing timestamps and summaries.
        """
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                memory = json.load(f)
                
            # Sort memory by timestamp descending (newest first)
            memory.sort(key=lambda x: x["timestamp"], reverse=True)
            
            # Return up to the `limit`
            return memory[:limit]
            
        except Exception as e:
            logger.error(f"Failed to retrieve summaries from memory: {e}")
            return []

    def get_default_preferences(self) -> dict:
        """Returns the base structure for user preferences."""
        return {
            "email": "",
            "frequency": 24,
            "language": "en",
            "topics": "latest world news"
        }

    def load_user_preferences(self) -> dict:
        """Loads user automation preferences securely from JSON."""
        if not os.path.exists(self.config_file):
            return self.get_default_preferences()
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Merge with defaults to ensure all expected keys exist even if file is outdated
            defaults = self.get_default_preferences()
            defaults.update(data)
            return defaults
        except Exception as e:
            logger.error(f"Failed to load user preferences: {e}")
            return self.get_default_preferences()

    def save_user_preferences(self, prefs: dict) -> bool:
        """Saves a complete dictionary of user preferences to storage."""
        try:
            # Ensure folder exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(prefs, f, indent=4)
            logger.info("Saved user automation preferences.")
            return True
        except Exception as e:
            logger.error(f"Failed to save user preferences: {e}")
            return False
            
    def update_user_preferences(self, key: str, value: Any) -> bool:
        """Updates a single preference key-value pair without overriding the rest."""
        prefs = self.load_user_preferences()
        prefs[key] = value
        return self.save_user_preferences(prefs)

# Example usage
if __name__ == "__main__":
    memory_agent = MemoryAgent()
    
    # Test saving functionality
    memory_agent.save_summary("Global economy stabilizes post-summit.", "Positive sentiment across major international banks.")
    
    # Test retrieval functionality
    recent = memory_agent.get_recent_summaries(limit=2)
    print(f"\nRetrieved {len(recent)} records from memory:")
    for rec in recent:
        print(f"[{rec['timestamp']}]\n{rec['summary'][:45]}...\n")
