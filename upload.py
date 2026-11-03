import os, pickle
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

creds = pickle.load(open("token.pickle", "rb"))
if creds and creds.expired and creds.refresh_token: creds.refresh(Request())
pickle.dump(creds, open("token.pickle", "wb"))

youtube = build("youtube", "v3", credentials=creds)
body = {"snippet": {"title": "Automated YouTube Upload Test", "description": "Automated test video uploaded via GitHub Actions", "tags": ["Automation", "AI", "Test"], "categoryId": "22"}, "status": {"privacyStatus": "private"}}
media = MediaFileUpload("sample_video.mp4", mimetype="video/mp4", resumable=True)

print("YouTube par video upload ho rahi hai...")
req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
resp = req.execute()

print("\n🎉 [SUCCESS] Mubarak ho! Video kamyabi se upload ho gayi hai!")
print("Video URL: https://youtu.be/" + resp.get("id"))
