import os
import sys
import json
import base64
import pickle
import datetime
import google.auth.transport.requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

print("[*] Starting YouTube Autonomous Upload Engine (Pickle Mode)...")

# 1. Video aur Script check
VIDEO_PATH = "final_output.mp4"
if not os.path.exists(VIDEO_PATH):
    print(f"[X] ERROR: {VIDEO_PATH} file nahi mili!")
    sys.exit(1)

title = "Mind-Blowing Facts You Didn't Know #Shorts #Facts"
description = "Subscribe for daily high-retention mind-blowing facts.\n\n#Shorts #viral #facts"

if os.path.exists("current_script.json"):
    try:
        with open("current_script.json", "r", encoding="utf-8") as f:
            script_data = json.load(f)
            title = script_data.get("title", title)
            if not "#Shorts" in title:
                title = f"{title} #Shorts"
    except Exception as e:
        print(f"[!] Warning reading script: {e}")

print(f"[*] Video Title: {title}")

# 2. YOUTUBE_TOKEN_PICKLE ko decode karein
credentials = None

# A. Environment variable se check karein
token_b64 = os.getenv("YOUTUBE_TOKEN_PICKLE", "").strip()

if token_b64:
    try:
        raw_pickle = base64.b64decode(token_b64)
        credentials = pickle.loads(raw_pickle)
        print("[✓] Token successfully loaded from YOUTUBE_TOKEN_PICKLE environment variable!")
    except Exception as e:
        print(f"[!] Error decoding base64 pickle from env: {e}")

# B. File se check karein (agar token.pickle file banayi ho)
if not credentials and os.path.exists("token.pickle"):
    try:
        with open("token.pickle", "rb") as f:
            credentials = pickle.load(f)
        print("[✓] Token successfully loaded from token.pickle file!")
    except Exception as e:
        print(f"[!] Error reading token.pickle file: {e}")

if not credentials:
    print("[X] ERROR: YouTube Credentials load nahi ho sake! Check YOUTUBE_TOKEN_PICKLE.")
    sys.exit(1)

# 3. Agar token expire ho gaya ho to auto-refresh karein
if credentials.expired and credentials.refresh_token:
    print("[*] Token expired, refreshing credentials...")
    credentials.refresh(google.auth.transport.requests.Request())
    print("[✓] Token refreshed successfully!")

youtube = build("youtube", "v3", credentials=credentials)

# 4. Schedule Time: 6:00 PM PKT (13:00 UTC)
now_utc = datetime.datetime.now(datetime.timezone.utc)
target_utc = now_utc.replace(hour=13, minute=0, second=0, microsecond=0)

if now_utc >= target_utc:
    target_utc += datetime.timedelta(days=1)

publish_at_iso = target_utc.isoformat().replace("+00:00", "Z")
print(f"[*] Scheduled Release: 6:00 PM PKT ({publish_at_iso})")

# 5. Upload Video to YouTube
body = {
    "snippet": {
        "title": title[:100],
        "description": description,
        "tags": ["Shorts", "Facts", "Psychology", "Viral"],
        "categoryId": "27"
    },
    "status": {
        "privacyStatus": "private",
        "publishAt": publish_at_iso,
        "selfDeclaredMadeForKids": False
    }
}

print(f"[*] Uploading {VIDEO_PATH} ({os.path.getsize(VIDEO_PATH)/(1024*1024):.2f} MB) to YouTube...")
media = MediaFileUpload(VIDEO_PATH, chunksize=-1, resumable=True, mimetype="video/mp4")

request = youtube.videos().insert(
    part="snippet,status",
    body=body,
    media_body=media
)

response = request.execute()
video_id = response.get("id")

print(f"\n{'='*55}")
print(f"🎉 ALHAMDULILLAH! VIDEO UPLOADED & SCHEDULED!")
print(f"Video URL: https://youtu.be/{video_id}")
print(f"Scheduled Release: 6:00 PM PKT")
print(f"{'='*55}\n")
