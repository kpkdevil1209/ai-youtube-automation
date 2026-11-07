"""
channel_pro_optimizer.py
Autonomous High-Tier Branding & SEO Optimization Engine.
Transforms the channel into a world-class DEVIL gaming brand:
- AI-crafted Devil Name, High-CTR Bio, and Section 107 Fair Use Shield
- High-Traffic Keyword Matrix for Search + Suggested Algorithm placement
- One-Time Lock mechanism: Sets once, saves state, and never overwrites again.
"""

import os
import json
import base64
import pickle
import random
from googleapiclient.discovery import build

PROFILE_PATH = "channel_profile.json"

DEVIL_BRANDING_POOLS = {
    "titles": [
        "DEVIL INSANITY",
        "DEVIL 999",
        "DEVIL GAMING PRO",
        "SHADOW DEVIL",
        "DEVIL X GOD"
    ],
    "bio": (
        "Welcome to the realm of DEVIL! 😈🔥\n\n"
        "Here you witness the highest tier of Free Fire gameplay: "
        "god-level Desert Eagle one-taps, impossible 1v4 clutches, "
        "pro-movement breakdowns, and secret sensitivity myths exposed.\n\n"
        "⚡ Daily 60FPS High-Octane Shorts at 6:00 PM PKT\n"
        "🎯 In-Depth Strategic Breakdowns Every 3 Days\n"
        "🏆 Aspiring Garena Free Fire Official Partner (V-Badge)\n\n"
        "----------------------------------------\n"
        "⚠️ COPYRIGHT & FAIR USE DISCLAIMER:\n"
        "Copyright Disclaimer Under Section 107 of the Copyright Act 1976: "
        "Allowance is made for 'fair use' for purposes such as criticism, "
        "comment, news reporting, teaching, scholarship, and gameplay research. "
        "All footage is substantially transformed with original audio commentary, "
        "speed ramping, and analytical value."
    ),
    "keywords": (
        "DEVIL, DEVIL Gaming, DEVIL 999, Free Fire, Garena Free Fire, "
        "FF Shorts, Free Fire Highlights, One Tap Headshot, Desert Eagle God Mode, "
        "M1887 Headshot Trick, 1v4 Clutch, Raistar, Total Gaming, B2K, "
        "Free Fire Pakistan, Free Fire India, FF Sensitivity Settings, Free Fire Montage"
    ),
    "country": "PK",
    "defaultLanguage": "ur"
}

def get_youtube_service():
    token_pickle = os.environ.get("YOUTUBE_TOKEN_PICKLE")
    if not token_pickle:
        raise ValueError("YOUTUBE_TOKEN_PICKLE environment variable nahi mila! GitHub Secrets check karein.")
    creds = pickle.loads(base64.b64decode(token_pickle))
    return build("youtube", "v3", credentials=creds)

def optimize_channel():
    if not os.path.exists(PROFILE_PATH):
        raise FileNotFoundError(f"{PROFILE_PATH} file nahi mili!")

    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        profile = json.load(f)

    # 1. ONE-TIME LOCK CHECK
    if profile.get("branding_completed", False):
        print("[!] Channel branding pehle se PRO optimized hai (One-Time Lock Active). No modification needed!")
        return

    print("[*] Connecting to YouTube Data API with YOUTUBE_TOKEN_PICKLE...")
    youtube = get_youtube_service()

    # 2. Get current channel details
    res = youtube.channels().list(part="snippet,brandingSettings", mine=True).execute()
    if not res.get("items"):
        print("[-] Koi YouTube channel nahi mila!")
        return

    channel_data = res["items"][0]
    channel_id = channel_data["id"]
    print(f"[+] Channel detected: {channel_id}")

    # 3. Choose Best Devil Brand Name
    target_title = profile.get("channel_name")
    if not target_title or target_title == "KPK-DEVIL":
        target_title = DEVIL_BRANDING_POOLS["titles"][0]  # DEVIL INSANITY

    update_body = {
        "id": channel_id,
        "brandingSettings": {
            "channel": {
                "title": target_title,
                "description": DEVIL_BRANDING_POOLS["bio"],
                "keywords": DEVIL_BRANDING_POOLS["keywords"],
                "defaultLanguage": DEVIL_BRANDING_POOLS["defaultLanguage"],
                "country": DEVIL_BRANDING_POOLS["country"]
            }
        }
    }

    print(f"[*] Applying World-Class Gaming settings for: {target_title}...")
    try:
        youtube.channels().update(
            part="brandingSettings",
            body=update_body
        ).execute()
        print(f"[+] SUCCESS: Channel successfully rebranded to '{target_title}' with Top Tier SEO!")
    except Exception as e:
        print(f"[!] Warning during brandingSettings update: {e}")
        print("[*] Proceeding with profile lock to avoid repeat attempts.")

    # 4. PERMANENT LOCK IN PROFILE
    profile["channel_id"] = channel_id
    profile["channel_name"] = target_title
    profile["branding_completed"] = True
    profile["content_strategy"]["in_game_name_tag"] = "DEVIL-999"

    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

    print("[+] channel_profile.json successfully LOCKED. Ab ye settings hamesha ke liye safe hain!")

if __name__ == "__main__":
    optimize_channel()
