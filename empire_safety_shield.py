import os
import sys
import json
import base64
import pickle
from datetime import datetime, timezone, timedelta

SAFETY_STATE_FILE = "safety_state.json"
MAX_DAILY_QUOTA = 8500  # Safe ceiling below YouTube's 10,000 limit


def today_pt_str() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=8)).strftime("%Y-%m-%d")


def save_safety_state(state: dict):
    with open(SAFETY_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def load_safety_state() -> dict:
    today = today_pt_str()
    state = {"daily_quota_used": 0, "last_verified_date": today}
    if os.path.exists(SAFETY_STATE_FILE):
        try:
            with open(SAFETY_STATE_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if loaded.get("last_verified_date") == today:
                state = loaded
            else:
                print(f"[*] SHIELD: New YouTube quota day ({today}). Resetting false/old counter to 0.")
                save_safety_state(state)
        except Exception:
            save_safety_state(state)
    else:
        save_safety_state(state)
    return state


def verify_token_health() -> bool:
    print("[*] SHIELD: Verifying YouTube Authentication Health...")
    token_pickle = os.environ.get("YOUTUBE_TOKEN_PICKLE")
    if not token_pickle:
        print("[!] ERROR: YOUTUBE_TOKEN_PICKLE missing from environment secrets!")
        return False

    try:
        creds = pickle.loads(base64.b64decode(token_pickle))
        if hasattr(creds, "refresh_token") or hasattr(creds, "token"):
            scopes = getattr(creds, "scopes", []) or []
            print(f"[+] SHIELD: Token loaded successfully! Scopes: {scopes}")
            if "https://www.googleapis.com/auth/youtube.force-ssl" not in scopes:
                print("[!] NOTE: Token has upload-only scope; comments/captions may need youtube.force-ssl later.")
            return True
        print("[!] SHIELD: Token structure invalid.")
        return False
    except Exception as e:
        print(f"[!] SHIELD WARNING: Token unpack failed: {e}")
        return False


def check_quota_allowance(estimated_cost: int = 1600) -> bool:
    state = load_safety_state()
    current_used = int(state.get("daily_quota_used", 0))
    print(f"[*] SHIELD: Quota check -> Current Used: {current_used} | Needed: {estimated_cost}")

    if current_used + estimated_cost > MAX_DAILY_QUOTA:
        print("[!] SHIELD ALERT: Daily quota ceiling reached. Skipping upload to protect channel.")
        return False
    return True


def record_quota_usage(units: int = 1650):
    state = load_safety_state()
    state["daily_quota_used"] = int(state.get("daily_quota_used", 0)) + int(units)
    save_safety_state(state)


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
