import os
import json
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  Path to the index tracker file (lives at project root)
# ─────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_FILE = os.path.join(_ROOT, "api_key_index.json")

# ─────────────────────────────────────────────────────────────
#  Keywords that indicate a quota / rate-limit error
#  (matches both Gemini and Serper error messages)
# ─────────────────────────────────────────────────────────────
QUOTA_SIGNALS = [
    "quota",
    "rate limit",
    "rate_limit",
    "resourceexhausted",
    "resource_exhausted",
    "429",
    "too many requests",
    "billing",
    "exceeded",
    "limit exceeded",
]


def _is_quota_error(error: Exception) -> bool:
    """Returns True if the exception looks like a quota / rate-limit error."""
    msg = str(error).lower()
    return any(signal in msg for signal in QUOTA_SIGNALS)


# ─────────────────────────────────────────────────────────────
#  Index persistence helpers
# ─────────────────────────────────────────────────────────────

def _load_indices() -> dict:
    """Load the current key indices from the JSON tracker file."""
    if not os.path.exists(INDEX_FILE):
        return {"current_gemini_key": 0, "current_serper_key": 0}
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure both keys exist (backwards-compat)
        data.setdefault("current_gemini_key", 0)
        data.setdefault("current_serper_key", 0)
        return data
    except Exception as e:
        logger.warning(f"[KeyManager] Could not read index file, resetting: {e}")
        return {"current_gemini_key": 0, "current_serper_key": 0}


def _save_indices(indices: dict) -> None:
    """Persist the updated key indices back to the JSON tracker file."""
    try:
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(indices, f, indent=2)
    except Exception as e:
        logger.error(f"[KeyManager] Failed to save index file: {e}")


# ─────────────────────────────────────────────────────────────
#  Public helpers: get key lists
# ─────────────────────────────────────────────────────────────

def _get_all_keys(prefix: str) -> list:
    """
    Collects all environment variables matching:
        <PREFIX>         → treated as key #1
        <PREFIX>_2       → key #2
        <PREFIX>_3       → key #3  … and so on.

    Example for prefix="GEMINI_API_KEY":
        GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3 …
    """
    keys = []
    base = os.getenv(prefix, "").strip()
    if base:
        keys.append(base)

    i = 2
    while True:
        k = os.getenv(f"{prefix}_{i}", "").strip()
        if not k:
            break
        keys.append(k)
        i += 1

    return keys


# ─────────────────────────────────────────────────────────────
#  KeyManager class
# ─────────────────────────────────────────────────────────────

class KeyManager:
    """
    Manages automatic rotation of API keys for Gemini and Serper.

    Usage pattern
    ─────────────
        km = KeyManager()

        # --- Gemini ---
        while True:
            key = km.get_gemini_key()          # returns current active key
            genai.configure(api_key=key)
            try:
                result = model.generate_content(prompt)
                break
            except Exception as e:
                if km.rotate_gemini_key(e):    # returns True if rotated, False if exhausted
                    continue                    # retry with next key
                raise                          # all keys exhausted → propagate

        # --- Serper ---
        key = km.get_serper_key()
        # …on 429 → km.rotate_serper_key(e)
    """

    def __init__(self):
        self._gemini_keys = _get_all_keys("GEMINI_API_KEY")
        self._serper_keys = _get_all_keys("SERPER_API_KEY")
        self._indices = _load_indices()

        if not self._gemini_keys:
            raise ValueError("[KeyManager] No GEMINI_API_KEY found in environment.")
        if not self._serper_keys:
            raise ValueError("[KeyManager] No SERPER_API_KEY found in environment.")

        logger.info(
            f"[KeyManager] Loaded {len(self._gemini_keys)} Gemini key(s) "
            f"and {len(self._serper_keys)} Serper key(s)."
        )

    # ── Gemini ────────────────────────────────────────────────

    def get_gemini_key(self) -> str:
        """Returns the currently active Gemini API key."""
        idx = self._indices["current_gemini_key"] % len(self._gemini_keys)
        return self._gemini_keys[idx]

    def rotate_gemini_key(self, error: Exception) -> bool:
        """
        Rotates to the next Gemini key if the error is quota-related.

        Returns:
            True  → rotated successfully, caller should retry.
            False → not a quota error, or all keys exhausted.
        """
        if not _is_quota_error(error):
            return False

        current_idx = self._indices["current_gemini_key"]
        next_idx = current_idx + 1

        if next_idx >= len(self._gemini_keys):
            logger.error(
                "[KeyManager] All Gemini API keys have hit their quota limit. "
                "Please add more keys or wait for quota reset."
            )
            return False

        logger.warning(
            f"[KeyManager] Gemini key #{current_idx + 1} quota exceeded. "
            f"Rotating to key #{next_idx + 1}..."
        )
        self._indices["current_gemini_key"] = next_idx
        _save_indices(self._indices)
        return True

    # ── Serper ────────────────────────────────────────────────

    def get_serper_key(self) -> str:
        """Returns the currently active Serper API key."""
        idx = self._indices["current_serper_key"] % len(self._serper_keys)
        return self._serper_keys[idx]

    def rotate_serper_key(self, error: Exception) -> bool:
        """
        Rotates to the next Serper key if the error is quota-related.

        Returns:
            True  → rotated successfully, caller should retry.
            False → not a quota error, or all keys exhausted.
        """
        if not _is_quota_error(error):
            return False

        current_idx = self._indices["current_serper_key"]
        next_idx = current_idx + 1

        if next_idx >= len(self._serper_keys):
            logger.error(
                "[KeyManager] All Serper API keys have hit their quota limit. "
                "Please add more keys or wait for quota reset."
            )
            return False

        logger.warning(
            f"[KeyManager] Serper key #{current_idx + 1} quota exceeded. "
            f"Rotating to key #{next_idx + 1}..."
        )
        self._indices["current_serper_key"] = next_idx
        _save_indices(self._indices)
        return True

    # ── Status ────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Returns a human-readable status dict (safe to display in UI)."""
        return {
            "gemini_keys_total": len(self._gemini_keys),
            "gemini_key_active": self._indices["current_gemini_key"] + 1,
            "serper_keys_total": len(self._serper_keys),
            "serper_key_active": self._indices["current_serper_key"] + 1,
        }


# ─────────────────────────────────────────────────────────────
#  Module-level singleton (shared across all agents in process)
# ─────────────────────────────────────────────────────────────
_manager: Optional[KeyManager] = None


def get_key_manager() -> KeyManager:
    """Returns the shared KeyManager singleton, creating it on first call."""
    global _manager
    if _manager is None:
        _manager = KeyManager()
    return _manager
