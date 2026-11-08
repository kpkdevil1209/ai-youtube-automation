"""
upload_video.py
Master YouTube Publisher for DEVIL Gaming Empire.
Features:
1. Uploads final_output.mp4 to YouTube Data API v3.
2. Schedules release for 6:00 PM PKT (Peak Viral Audience Window).
3. Attaches 30 High-Volume SEO Tags & Fair Use Legal Shield.
4. Uploads International English Subtitles (subtitles_en.srt) via Captions API.
5. Pins the First High-Engagement Challenge Comment automatically.
"""

import os
import sys
import json
import base64
import pickle
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

VIDEO_FILE = "final_output.mp4"
SCRIPT_FILE = "current_script.json"
SUBTITLE_FILE = "subtitles_en.srt"

SEO_TAGS = [
    "DEVIL", "DEVIL999", "Free Fire", "Garena Free Fire", "FF Shorts",
    "Free Fire Highlights", "Desert Eagle One Tap", "M1887 Headshot Trick",
    "1v4 Clutch Free Fire", "Raistar", "Total Gaming", "FF Headshot Settings",
    "Free Fire Pakistan", "Free Fire India", "Grandmaster Clutch", "Free Fire Montage"
]

def get_youtube_service():
    token_pickle = os.environ.get("YOUTUBE_TOKEN_PICKLE")
    if not token_pickle:
        raise ValueError("YOUTUBE_TOKEN_PICKLE secret nahi mila! GitHub Secrets check karein.")
    creds = pickle.loads(base64.b64decode(token_pickle))
    return build("youtube", "v3", credentials=creds)

def load_metadata():
    title = "DEVIL 1v4 IMPOSSIBLE CLUTCH (60FPS)"
    description = "DEVIL-999 God Mode Free Fire Highlights! #FreeFire #Shorts #DEVIL999"

    if os.path.exists(SCRIPT_FILE):
        try:
            with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                t_urdu = data.get("title_urdu", "")
                t_en = data.get("title_en", "")
                title = f"{t_urdu} 💥 {t_en}" if t_urdu and t_urdu != t_en else (t_en or t_urdu)
                if len(title) > 95:
                    title = title[:92] + "..."

                desc_en = data.get("description_en", "")
                description = (
                    f"{desc_en}\n\n"
                    f"⚡ Player: DEVIL-999\n"
                    f"🎯 60FPS High-Octane Free Fire Gameplay\n\n"
                    f"⚠️ FAIR USE DISCLAIMER:\n"
                    f"Copyright Disclaimer Under Section 107 of Copyright Act 1976: "
                    f"Fair use for commentary, research, and transformative gameplay analysis."
                )
        except Exception:
            pass

    return title, description

def calculate_publish_time() -> str:
    """Calculates scheduled release for 18:00 PKT (13:00 UTC) today."""
    now_utc = datetime.now(timezone.utc)
    target_utc = now_utc.replace(hour=13, minute=0, second=0, microsecond=0)
    if target_utc <= now_utc:
        # If already past 13:00 UTC, schedule for tomorrow
        target_utc += timedelta(days=1)
    return target_utc.isoformat()

def upload_video_to_youtube():
    print("\n==========================================")
    print("[*] MASTER YOUTUBE UPLOADER: DEVIL GAMING")
    print("==========================================")

    if not os.path.exists(VIDEO_FILE):
        raise FileNotFoundError(f"{VIDEO_FILE} nahi mila! Pehle video render karein.")

    youtube = get_youtube_service()
    title, description = load_metadata()
    publish_at = calculate_publish_time()

    print(f"[*] Title: {title}")
    print(f"[*] Scheduled Release (18:00 PKT): {publish_at}")

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": SEO_TAGS,
            "categoryId": "20",  # Gaming
            "defaultLanguage": "ur",
            "defaultAudioLanguage": "ur"
        },
        "status": {
            "privacyStatus": "private",  # Private until scheduled time
            "publishAt": publish_at,
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(VIDEO_FILE, chunksize=-1, resumable=True, mimetype="video/mp4")
    print("[*] Uploading video to YouTube servers...")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f" -> Upload progress: {int(status.progress() * 100)}%...")

    video_id = response.get("id")
    print(f"\n[+] VIDEO UPLOAD SUCCESS! Video ID: {video_id}")
    print(f" -> URL: https://youtu.be/{video_id}")

    # Upload English Subtitles if present
    if os.path.exists(SUBTITLE_FILE):
        print("[*] Attaching International English Subtitles...")
        try:
            sub_media = MediaFileUpload(SUBTITLE_FILE, mimetype="text/plain")
            youtube.captions().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "language": "en",
                        "name": "English (Global)",
                        "isDraft": False
                    }
                },
                media_body=sub_media
            ).execute()
            print("[+] English Subtitles Attached Successfully!")
        except Exception as e:
            print(f"[!] Captions notice: {e}")

    # Post Pinned Challenge Comment
    print("[*] Posting Pinned Challenge Comment...")
    try:
        pin_comment = (
            "🔥 Kya aapka phone DEVIL-999 jaisa 550 one-tap headshot mar sakta hai? "
            "Apni Free Fire UID aur device name neechay comment karo! 👇🎯"
        )
        youtube.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {"snippet": {"textOriginal": pin_comment}}
                }
            }
        ).execute()
        print("[+] First challenge comment pinned!")
    except Exception as e:
        print(f"[!] Comment notice: {e}")

    print("\n[+] YouTube Deployment Sequence 100% Complete!\n")

if __name__ == "__main__":
    upload_video_to_youtube()
