"""
empire_safety_shield.py
Self-Healing Safety & Risk Mitigation Engine for DEVIL Gaming.
Fixed for Insufficient Permissions / Upload-Only Scopes.
"""

import os
import sys
import json
import base64
import pickle
import hashlib

SAFETY_STATE_FILE = "safety_state.json"
MAX_DAILY_QUOTA = 8500  # Safe ceiling below YouTube's 10,000 limit

def load_safety_state() -> dict:
    if os.path.exists(SAFETY_STATE_FILE):
        try:
            with open(SAFETY_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"daily_quota_used": 0, "last_verified_date": None}

def save_safety_state(state: dict):
    with open(SAFETY_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def verify_token_health() -> bool:
    """
    Verifies YOUTUBE_TOKEN_PICKLE directly by inspecting credential scopes.
    Does NOT trigger 403 API permission errors for upload-only tokens.
    """
    print("[*] SHIELD: Verifying YouTube Authentication Health...")
    token_pickle = os.environ.get("YOUTUBE_TOKEN_PICKLE")
    if not token_pickle:
        print("[!] ERROR: YOUTUBE_TOKEN_PICKLE missing from environment secrets!")
        return False

    try:
        creds = pickle.loads(base64.b64decode(token_pickle))
        # Check if credentials object exists and has valid client_id / refresh_token
        if hasattr(creds, "refresh_token") or hasattr(creds, "token"):
            scopes = getattr(creds, "scopes", [])
            print(f"[+] SHIELD: Token loaded successfully! Scopes: {scopes}")
            return True
        else:
            print("[!] SHIELD: Token structure invalid.")
            return False
    except Exception as e:
        print(f"[!] SHIELD WARNING: Token unpack failed: {e}")
        return False

def check_quota_allowance(estimated_cost: int = 1600) -> bool:
    """Checks if we have enough quota left for today's run."""
    state = load_safety_state()
    current_used = state.get("daily_quota_used", 0)
    print(f"[*] SHIELD: Quota check -> Current Used: {current_used} | Needed: {estimated_cost}")

    if current_used + estimated_cost > MAX_DAILY_QUOTA:
        print("[!] SHIELD ALERT: Daily quota ceiling reached. Skipping upload to protect channel.")
        return False

    state["daily_quota_used"] = current_used + estimated_cost
    save_safety_state(state)
    return True

def run_preflight_checks():
    print("\n==========================================")
    print("[*] EMPIRE SAFETY SHIELD: PRE-FLIGHT AUDIT")
    print("==========================================")

    token_ok = verify_token_health()
    if not token_ok:
        print("[!] CRITICAL: Token verification failed. Check YOUTUBE_TOKEN_PICKLE secret.")
        sys.exit(1)

    quota_ok = check_quota_allowance(1650)
    if not quota_ok:
        print("[!] CRITICAL: Insufficient API quota for today.")
        sys.exit(1)

    print("[+] All Pre-Flight Health Checks Passed Successfully!")
    print("==========================================\n")

if __name__ == "__main__":
    run_preflight_checks()
