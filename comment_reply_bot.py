# comment_reply_bot.py - Phase 4 Live Engagement Bot for DEVIL Gaming

import os
import re
import json
import time
import base64
import pickle
import random
import subprocess
import urllib.request
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

try:
    from empire_safety_shield import record_quota_usage
except Exception:
    def record_quota_usage(units=50):
        pass

STATE_FILE = "replied_comments.json"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2:1b"
MAX_REPLIES_PER_RUN = 10

HUMAN_ONLY_KEYWORDS = [
    "kahan rehte", "id do", "password", "collab", "collaboration",
    "number", "whatsapp", "pesa", "paid", "promotion", "meetup",
    "account de do", "buy", "sell", "contact", "sponsor", "real name",
    "kahan se ho", "voice over", "kon ho"
]

def get_youtube_service():
    token_pickle = os.environ.get("YOUTUBE_TOKEN_PICKLE")
    if not token_pickle:
        raise ValueError("YOUTUBE_TOKEN_PICKLE secret nahi mila!")
    creds = pickle.loads(base64.b64decode(token_pickle.strip()))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)

def get_active_ollama_model():
    for attempt in range(2):
        try:
            with urllib.request.urlopen(OLLAMA_TAGS_URL, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                if DEFAULT_MODEL in models:
                    return DEFAULT_MODEL
                if models:
                    return models[0]
        except Exception:
            if attempt == 0:
                try:
                    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(3)
                except Exception:
                    break
    return None

def load_replied_ids():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def save_replied_ids(replied_set):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(replied_set)[-500:], f, indent=2)

def get_recent_videos(youtube):
    ch_res = youtube.channels().list(mine=True, part="id,contentDetails").execute()
    items = ch_res.get("items", [])
    if not items:
        return None, []
    my_channel_id = items[0]["id"]
    uploads_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    pl_items = youtube.playlistItems().list(
        playlistId=uploads_id, part="snippet", maxResults=5
    ).execute().get("items", [])
    videos = []
    for it in pl_items:
        vid = it["snippet"]["resourceId"]["videoId"]
        title = it["snippet"].get("title", "")
        videos.append((vid, title))
    return my_channel_id, videos

def is_human_only_question(text):
    lower = text.lower()
    if any(kw in lower for kw in HUMAN_ONLY_KEYWORDS):
        return True
    if re.search(r"\b\d{10,12}\b", lower) or "@" in lower:
        return True
    return False

def already_replied_by_owner(thread, my_channel_id):
    replies = thread.get("replies", {}).get("comments", [])
    for r in replies:
        ch = r.get("snippet", {}).get("authorChannelId", {}).get("value")
        if ch == my_channel_id:
            return True
    return False

def generate_cognitive_reply(comment_text, model_name):
    if not model_name:
        return None
    prompt = (
        "[SYSTEM: DEVIL-999, ultra-skilled Free Fire mobile player]\n"
        "Tone: Chill, confident, sharp, humble to fans, cold to haters.\n"
        "RULES:\n"
        "1. NEVER accept custom rooms or 1v1 challenges.\n"
        "2. NEVER promise to upload a video or say 'kal video aayegi'.\n"
        "3. Reply STRICTLY in under 12 words in natural Roman Urdu / English.\n\n"
        f"Viewer Comment: {comment_text}\n"
        "DEVIL Reply:"
    )
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 40}
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(OLLAMA_API_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            reply = res.get("response", "").strip().replace('"', "").splitlines()[0]
            if not reply or any(w in reply.lower() for w in ["custom", "1v1", "kal video", "upload"]):
                return None
            return reply[:180]
    except Exception as e:
        print(f" -> [!] Ollama reply error: {e}")
        return None

def run_comment_engine():
    print("\n==========================================")
    print("[*] PHASE 4: COGNITIVE LIVE ENGAGEMENT BOT")
    print("==========================================")

    youtube = get_youtube_service()
    my_channel_id, videos = get_recent_videos(youtube)
    if not my_channel_id or not videos:
        print("[!] Channel ya uploaded videos nahi mili, bot safely exit kar raha hai.")
        return

    model_name = get_active_ollama_model()
    print(f"[*] Active Ollama Model: {model_name or 'Unavailable'}")
    replied_set = load_replied_ids()
    replies_posted = 0
    used_units = 2

    for video_id, title in videos:
        if replies_posted >= MAX_REPLIES_PER_RUN:
            break
        print(f"[*] Checking comments on: {title} ({video_id})")
        try:
            threads = youtube.commentThreads().list(
                part="snippet,replies",
                videoId=video_id,
                maxResults=20,
                textFormat="plainText"
            ).execute().get("items", [])
            used_units += 1
        except HttpError as e:
            print(f" -> [!] Skipping video ({video_id}): {e}")
            continue

        for thread in threads:
            if replies_posted >= MAX_REPLIES_PER_RUN:
                break
            top_obj = thread["snippet"]["topLevelComment"]
            comment_id = top_obj["id"]
            top = top_obj["snippet"]
            author = top.get("authorDisplayName", "Viewer")
            author_ch = top.get("authorChannelId", {}).get("value")
            text = top.get("textOriginal", "")

            if comment_id in replied_set or author_ch == my_channel_id:
                continue
            if already_replied_by_owner(thread, my_channel_id):
                replied_set.add(comment_id)
                continue

            print(f"\n[Viewer] {author}: '{text}'")
            if is_human_only_question(text):
                print(" -> [HUMAN ONLY] Personal/collab sawaal hai, AI reply skip kiya.")
                replied_set.add(comment_id)
                continue

            ai_reply = generate_cognitive_reply(text, model_name)
            if not ai_reply:
                print(" -> [!] Reply generate nahi ho saka, skip kar rahe hain.")
                continue

            print(f" -> [DEVIL-999]: '{ai_reply}'")
            try:
                youtube.comments().insert(
                    part="snippet",
                    body={"snippet": {"parentId": comment_id, "textOriginal": ai_reply}}
                ).execute()
                replies_posted += 1
                used_units += 50
                replied_set.add(comment_id)
                print(" -> [SUCCESS] Reply published!")
            except Exception as e:
                print(f" -> [!] Could not post reply: {e}")

            time.sleep(random.uniform(4.0, 9.0))

    save_replied_ids(replied_set)
    record_quota_usage(units=used_units)
    print(f"\n[+] PHASE 4 COMPLETE! Replies posted: {replies_posted} | Quota: {used_units}\n")

if __name__ == "__main__":
    run_comment_engine()
