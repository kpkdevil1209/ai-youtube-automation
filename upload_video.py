import os
import sys
import json
import base64
import datetime
import google.oauth2.credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

print("[*] Starting YouTube Autonomous Upload Engine...")

# 1. Video aur Script check
VIDEO_PATH = "final_output.mp4"
if not os.path.exists(VIDEO_PATH):
    print(f"[X] ERROR: {VIDEO_PATH} file nahi mili!")
    sys.exit(1)

title = "Mind-Blowing Facts You Didn't Know #Shorts #Facts"
description = "Subscribe for daily high-retention mind-blowing facts and dark psychology secrets.\n\n#Shorts #viral #facts"

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

# 2. Token File Read & Decode
TOKEN_FILE = "client_secrets.json"
if not os.path.exists(TOKEN_FILE):
    print(f"[X] ERROR: {TOKEN_FILE} file nahi mili!")
    sys.exit(1)

with open(TOKEN_FILE, "r", encoding="utf-8") as f:
    raw_content = f.read().strip()

if not raw_content:
    print("[X] ERROR: client_secrets.json khali hai! GitHub Secrets mein YOUTUBE_CLIENT_SECRET_JSON check karein.")
    sys.exit(1)

# Auto-detect: Direct JSON ya Base64
token_info = None
try:
    token_info = json.loads(raw_content)
except Exception:
    try:
        decoded_bytes = base64.b64decode(raw_content)
        token_info = json.loads(decoded_bytes.decode("utf-8"))
        print("[✓] Base64 encoded token successfully decoded!")
    except Exception as e:
        print(f"[X] ERROR: Token decode nahi ho saka: {e}")
        sys.exit(1)

# Key structure handle karein
data = token_info.get("installed") or token_info.get("web") or token_info

credentials = google.oauth2.credentials.Credentials(
    token=data.get("token") or data.get("access_token"),
    refresh_token=data.get("refresh_token"),
    token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
    client_id=data.get("client_id"),
    client_secret=data.get("client_secret")
)

youtube = build("youtube", "v3", credentials=credentials)

# 3. Schedule Time: 6:00 PM PKT (13:00 UTC)
now_utc = datetime.datetime.now(datetime.timezone.utc)
target_utc = now_utc.replace(hour=13, minute=0, second=0, microsecond=0)

if now_utc >= target_utc:
    target_utc += datetime.timedelta(days=1)

publish_at_iso = target_utc.isoformat().replace("+00:00", "Z")
print(f"[*] Scheduled Release: 6:00 PM PKT ({publish_at_iso})")

# 4. Upload to YouTube
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

print("[*] Uploading video to YouTube...")
media = MediaFileUpload(VIDEO_PATH, chunksize=-1, resumable=True, mimetype="video/mp4")

request = youtube.videos().insert(
    part="snippet,status",
    body=body,
    media_body=media
)

response = request.execute()
video_id = response.get("id")

print(f"\n{'='*55}")
print(f"🎉 SUCCESS! VIDEO UPLOADED & SCHEDULED!")
print(f"Video URL: https://youtu.be/{video_id}")
print(f"Scheduled Release: 6:00 PM PKT")
print(f"{'='*55}\n")
