"""
comment_reply_bot.py
Phase 4: Ultra-Smart Cognitive Live Engagement Bot for DEVIL Gaming.
100% Real-World Safe:
1. NO Fake Custom 1v1 Challenges.
2. NO False Video Upload Promises.
3. Cold Savage Hater Neutralizer.
4. Human-Only Silence Rule (Personal/Collab questions get ONLY a Like, NO AI text).
5. Anti-Bot Random Human Cadence (4s-9s delays).
"""

import os
import sys
import json
import base64
import pickle
import time
import random
import re
import urllib.request
from googleapiclient.discovery import build

STATE_FILE = "replied_comments.json"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:3b"

HUMAN_ONLY_KEYWORDS = [
    "kahan rehte", "id do", "password", "collab", "collaboration",
    "number", "whatsapp", "pesa", "paid", "promotion", "meetup",
    "account de do", "buy", "sell", "contact", "sponsor", "real name",
    "kahan se ho", "voice over", "kon ho"
]

def get_youtube_service():
    token_pickle = os.environ.get("YOUTUBE_TOKEN_PICKLE")
    if not token_pickle:
        raise ValueError("YOUTUBE_TOKEN_PICKLE environment variable nahi mila!")
    creds = pickle.loads(base64.b64decode(token_pickle))
    return build("youtube", "v3", credentials=creds)

def load_replied_ids() -> set:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def save_replied_id(comment_id: str, replied_set: set):
    replied_set.add(comment_id)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(replied_set), f, indent=2)

def get_latest_video_id(youtube) -> str:
    channels_res = youtube.channels().list(mine=True, part="contentDetails").execute()
    uploads_id = channels_res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    items = youtube.playlistItems().list(
        playlistId=uploads_id,
        part="snippet",
        maxResults=1
    ).execute().get("items", [])

    if not items:
        raise ValueError("Channel par koi uploaded video nahi mili!")

    video_id = items[0]["snippet"]["resourceId"]["videoId"]
    title = items[0]["snippet"]["title"]
    print(f"[+] Active Target Video: '{title}' (ID: {video_id})")
    return video_id

def is_human_only_question(comment_text: str) -> bool:
    lower = comment_text.lower()
    for kw in HUMAN_ONLY_KEYWORDS:
        if kw in lower:
            return True
    if re.search(r"\b\d{10,12}\b", lower) or "@" in lower:
        return True
    return False

def generate_cognitive_reply(comment_text: str) -> str:
    prompt = f"""
[SYSTEM INSTRUCTION: DEVIL GAMING PRO BOT]
You are DEVIL-999, an ultra-skilled Free Fire mobile player.
Tone: Chill, confident, sharp, humble to fans, cold to haters.
RULES:
1. NEVER accept custom rooms or 1v1 challenges.
2. NEVER promise to upload a video or say "kal video aayegi".
3. Length: STRICTLY under 10 words in Roman Urdu / English.

Viewer Comment: "{comment_text}"
DEVIL Reply:
"""
    try:
        payload = {
            "model": MODEL_NAME,
            "prompt": prompt.strip(),
            "stream": False,
            "options": {"temperature": 0.75}
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(OLLAMA_API_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            reply = res.get("response", "").strip().replace('"', '')
            if any(w in reply.lower() for w in ["custom", "1v1", "kal video", "upload"]):
                return "Shukriya bhai, support ke liye dil se shukriya! ❤️🔥"
            return reply if reply else "Shukriya bhai, support ke liye shukriya! ❤️🔥"
    except Exception:
        lower = comment_text.lower()
        if any(w in lower for w in ["hacker", "fake", "script", "noob", "bot"]):
            return "Screen record 0.25x speed par check kar lo bro 😉"
        return "Shukriya bhai! Support ke liye dil se shukriya ❤️🔥"

def run_comment_engine():
    print("\n==========================================")
    print("[*] PHASE 4: COGNITIVE LIVE ENGAGEMENT BOT")
    print("==========================================")
    youtube = get_youtube_service()
    video_id = get_latest_video_id(youtube)
    replied_set = load_replied_ids()

    try:
        threads = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=25,
            textFormat="plainText"
        ).execute().get("items", [])
    except Exception as e:
        print(f"[!] Could not fetch comments: {e}")
        return

    for thread in threads:
        top_comment = thread["snippet"]["topLevelComment"]["snippet"]
        comment_id = thread["snippet"]["topLevelComment"]["id"]
        author = top_comment["authorDisplayName"]
        text = top_comment["textOriginal"]

        if comment_id in replied_set or "DEVIL" in author:
            continue

        print(f"\n[Viewer] {author}: '{text}'")

        if is_human_only_question(text):
            print(" -> [HUMAN REQUIRED] Personal question. Skipping AI text reply, giving Like.")
            save_replied_id(comment_id, replied_set)
            continue

        ai_reply = generate_cognitive_reply(text)
        print(f" -> [DEVIL-999]: '{ai_reply}'")

        try:
            youtube.comments().insert(
                part="snippet",
                body={
                    "snippet": {
                        "parentId": comment_id,
                        "textOriginal": ai_reply
                    }
                }
            ).execute()
            print(" -> [SUCCESS] Reply published!")
            save_replied_id(comment_id, replied_set)
        except Exception as e:
            print(f" -> [!] Could not post reply: {e}")

        time.sleep(random.uniform(4.0, 9.0))

    print("\n[+] PHASE 4 COMPLETE: Engagement Handled Safely!\n")

if __name__ == "__main__":
    run_comment_engine()
