import os, json, pickle
from datetime import datetime, timedelta, timezone
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

video_file = "final_viral_video.mp4" if os.path.exists("final_viral_video.mp4") else "sample_video.mp4"
has_video = os.path.exists(video_file)
has_token = os.path.exists("token.pickle")

pkt_tz = timezone(timedelta(hours=5))
now_pkt = datetime.now(pkt_tz)
target_pkt = now_pkt.replace(hour=18, minute=0, second=0, microsecond=0)
target_pkt = target_pkt + timedelta(days=1) if target_pkt <= now_pkt else target_pkt
publish_at_iso = target_pkt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

print(f"Current Pakistan Time: {now_pkt.strftime('%Y-%m-%d %I:%M %p')}")
print(f"Scheduled Public Release: {target_pkt.strftime('%Y-%m-%d %I:%M %p')} Pakistan Time ({publish_at_iso})")

script_data = json.load(open("current_script.json", "r", encoding="utf-8")) if os.path.exists("current_script.json") else {}
title = script_data.get("title", "Automated Viral Video #shorts")
description = script_data.get("description", "Automated YouTube Upload #trending")

creds = pickle.load(open("token.pickle", "rb")) if has_token else None
creds.refresh(Request()) if (creds and creds.expired and creds.refresh_token) else None
pickle.dump(creds, open("token.pickle", "wb")) if creds else None

youtube = build("youtube", "v3", credentials=creds) if (creds and has_video) else None
body = {"snippet": {"title": title[:70], "description": description, "tags": ["shorts", "viral", "AI", "facts"], "categoryId": "22"}, "status": {"privacyStatus": "private", "publishAt": publish_at_iso}}
media = MediaFileUpload(video_file, mimetype="video/mp4", resumable=True) if (creds and has_video) else None

req = youtube.videos().insert(part="snippet,status", body=body, media_body=media) if (creds and has_video) else None
resp = req.execute() if req else None

print("\n🎉 [SUCCESS] Video upload ho gayi hai aur Shaam 6:00 PM Pakistan Time ke liye SCHEDULED ho chuki hai!") if resp else None
print("Video URL: https://youtu.be/" + resp.get("id")) if resp else None
print("\n⚠️ [NOTE] final_viral_video.mp4 abhi mojood nahi thi. Jab Colab se video push hogi tab upload ho jayegi.") if not has_video else None
