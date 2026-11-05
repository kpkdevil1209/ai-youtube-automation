import os
import sys
import json
import datetime
import google.oauth2.credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

print("[*] Starting YouTube Autonomous Upload Engine...")

# 1. Video aur Script check karein
VIDEO_PATH = "final_output.mp4"
if not os.path.exists(VIDEO_PATH):
    print(f"[X] ERROR: {VIDEO_PATH} nahi mili!")
    sys.exit(1)

title = "Mind-Blowing Facts You Didn't Know #Shorts #Facts"
description = "Subscribe for daily high-retention mind-blowing facts and dark psychology secrets.\n\n#Shorts #viral #facts #psychology"

if os.path.exists("current_script.json"):
    try:
        with open("current_script.json", "r", encoding="utf-8") as f:
            script_data = json.load(f)
            title = script_data.get("title", title)
            if not "#Shorts" in title:
                title = f"{title} #Shorts"
    except Exception as e:
        print(f"[!] Warning reading current_script.json: {e}")

print(f"[*] Video Title: {title}")

# 2. YouTube OAuth Token authenticate karein
TOKEN_FILE = "client_secrets.json"
if not os.path.exists(TOKEN_FILE):
    print(f"[X] ERROR: {TOKEN_FILE} nahi mili!")
    sys.exit(1)

with open(TOKEN_FILE, "r") as f:
    token_info = json.load(f)

# Token setup
credentials = google.oauth2.credentials.Credentials(
    token=token_info.get("access_token"),
    refresh_token=token_info.get("refresh_token"),
    token_uri=token_info.get("token_uri", "https://oauth2.googleapis.com/token"),
    client_id=token_info.get("client_id"),
    client_secret=token_info.get("client_secret")
)

youtube = build("youtube", "v3", credentials=credentials)

# 3. Schedule Time Calculate karein: Aaj shaam 6:00 PM PKT (Pakistan Time = UTC+5)
# 6:00 PM PKT = 1:00 PM UTC (13:00 UTC)
now_utc = datetime.datetime.now(datetime.timezone.utc)
target_utc = now_utc.replace(hour=13, minute=0, second=0, microsecond=0)

# Agar abhi ka waqt 1:00 PM UTC se guzar chuka ho to kal shaam 6:00 PM schedule karein
if now_utc >= target_utc:
    target_utc += datetime.timedelta(days=1)

publish_at_iso = target_utc.isoformat().replace("+00:00", "Z")
print(f"[*] Scheduling video for 6:00 PM PKT (UTC: {publish_at_iso})")

# 4. Upload Metadata (Scheduled videos must be private with publishAt)
body = {
    "snippet": {
        "title": title[:100],
        "description": description,
        "tags": ["Shorts", "Facts", "Psychology", "Viral", "YouTubeShorts"],
        "categoryId": "27"  # Education / Facts
    },
    "status": {
        "privacyStatus": "private",
        "publishAt": publish_at_iso,
        "selfDeclaredMadeForKids": False
    }
}

print("[*] Uploading final_output.mp4 to YouTube Channel...")
media = MediaFileUpload(VIDEO_PATH, chunksize=-1, resumable=True, mimetype="video/mp4")

request = youtube.videos().insert(
    part="snippet,status",
    body=body,
    media_body=media
)

response = request.execute()
video_id = response.get("id")

print(f"\n{'='*50}")
print(f"🎉 BINGO! VIDEO SUCCESSFULLY UPLOADED & SCHEDULED!")
print(f"Video URL: https://youtu.be/{video_id}")
print(f"Scheduled Release Time: 6:00 PM PKT")
print(f"{'='*50}\n")
