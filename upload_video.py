# upload_video.py - Master YouTube Publisher for DEVIL Gaming

import os
import re
import json
import base64
import pickle
from datetime import datetime, timedelta, timezone
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

try:
    from empire_safety_shield import record_quota_usage
except Exception:
    def record_quota_usage(units=1650):
        pass

VIDEO_FILE = "final_output.mp4"
SCRIPT_FILE = "current_script.json"
SUBTITLE_FILE = "subtitles_en.srt"

SEO_TAGS = [
    "DEVIL", "DEVIL999", "Free Fire", "Garena Free Fire", "FF Shorts",
    "Free Fire Highlights", "Desert Eagle One Tap", "M1887 Headshot Trick",
    "1v4 Clutch Free Fire", "FF Headshot Settings", "Free Fire Pakistan",
    "Free Fire India", "Grandmaster Clutch", "Free Fire Montage"
]

def clean_yt_text(text, max_len=None):
    s = re.sub(r"[<>]", "", str(text or "")).strip()
    s = re.sub(r"\s+", " ", s)
    if max_len and len(s) > max_len:
        s = s[: max_len - 3].rstrip() + "..."
    return s

def get_youtube_service():
    token_pickle = os.environ.get("YOUTUBE_TOKEN_PICKLE")
    if not token_pickle:
        raise ValueError("YOUTUBE_TOKEN_PICKLE secret nahi mila!")
    creds = pickle.loads(base64.b64decode(token_pickle.strip()))
    if creds.expired and creds.refresh_token:
        print("[*] Refreshing YouTube OAuth token...")
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)

def build_tags(script_tags):
    merged = []
    seen = set()
    total_chars = 0
    for raw in (list(script_tags or []) + SEO_TAGS):
        t = clean_yt_text(str(raw).replace("#", ""), 40)
        key = t.lower()
        if not t or key in seen:
            continue
        cost = len(t) + (3 if " " in t else 1)
        if total_chars + cost > 450:
            break
        seen.add(key)
        merged.append(t)
        total_chars += cost
    return merged

def load_metadata():
    title = "DEVIL-999 1v4 Impossible Clutch (60FPS) #Shorts"
    desc_body = "DEVIL-999 High-Octane Free Fire Highlights!"
    tags = build_tags([])
    pin_comment = "Kya aapka phone DEVIL-999 jaisa one-tap headshot mar sakta hai? Apni Free Fire UID aur device name neeche comment karo!"
    player_tag = "DEVIL-999"
    fmt = "SHORTS"

    if os.path.exists(SCRIPT_FILE):
        with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        player_tag = clean_yt_text(data.get("player_tag") or "DEVIL-999", 30)
        fmt = str(data.get("format_type") or "SHORTS").upper()

        raw_title = data.get("title") or data.get("title_en") or data.get("title_urdu") or data.get("topic")
        if raw_title:
            title = clean_yt_text(raw_title, 95)

        raw_desc = data.get("description") or data.get("description_en") or data.get("english_script") or data.get("topic")
        if raw_desc:
            desc_body = re.sub(r"[<>]", "", str(raw_desc)).strip()

        tags = build_tags(data.get("tags", []))

        raw_pin = data.get("pinned_comment")
        if raw_pin:
            pin_comment = clean_yt_text(raw_pin, 400)

    shorts_tag = "\n#Shorts #FreeFire #DEVIL999" if (fmt == "SHORTS" and "#shorts" not in desc_body.lower()) else ""
    description = (
        f"{desc_body}{shorts_tag}\n\n"
        f"Player: {player_tag}\n"
        f"60FPS High-Octane Free Fire Gameplay\n\n"
        f"FAIR USE DISCLAIMER:\n"
        f"Copyright Disclaimer Under Section 107 of Copyright Act 1976: "
        f"Fair use for commentary, analysis, and transformative gameplay."
    )[:4800]

    return title, description, tags, pin_comment

def calculate_publish_time():
    now_utc = datetime.now(timezone.utc)
    target_utc = now_utc.replace(hour=13, minute=0, second=0, microsecond=0)
    if target_utc <= now_utc + timedelta(minutes=15):
        target_utc += timedelta(days=1)
    return target_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

def execute_upload(youtube, body):
    media = MediaFileUpload(VIDEO_FILE, chunksize=4 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f" -> Upload progress: {int(status.progress() * 100)}%")
    return response

def upload_video_to_youtube():
    print("\n==========================================")
    print("[*] MASTER YOUTUBE UPLOADER: DEVIL GAMING")
    print("==========================================")

    if not os.path.exists(VIDEO_FILE) or os.path.getsize(VIDEO_FILE) < 10000:
        raise FileNotFoundError(f"{VIDEO_FILE} missing ya khali hai!")

    youtube = get_youtube_service()
    title, description, tags, pin_comment = load_metadata()
    publish_at = calculate_publish_time()

    print(f"[*] Title: {title}")
    print(f"[*] Tags count: {len(tags)}")
    print(f"[*] Scheduled Release (18:00 PKT): {publish_at}")

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "20",
            "defaultLanguage": "ur",
            "defaultAudioLanguage": "ur"
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": publish_at,
            "selfDeclaredMadeForKids": False
        }
    }

    print("[*] Uploading video to YouTube servers...")
    try:
        response = execute_upload(youtube, body)
    except HttpError as e:
        if "publishAt" in str(e):
            print(f"[!] Scheduled publishAt notice, retrying as private draft: {e}")
            body["status"].pop("publishAt", None)
            response = execute_upload(youtube, body)
        else:
            raise

    video_id = response.get("id")
    used_units = 1600
    print(f"\n[+] VIDEO UPLOAD SUCCESS! Video ID: {video_id}")
    print(f" -> URL: https://youtu.be/{video_id}")

    if os.path.exists(SUBTITLE_FILE) and os.path.getsize(SUBTITLE_FILE) > 0:
        print("[*] Attaching International English Subtitles...")
        try:
            sub_media = MediaFileUpload(SUBTITLE_FILE, mimetype="application/octet-stream")
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
            used_units += 400
            print("[+] English Subtitles Attached Successfully!")
        except Exception as e:
            print(f"[!] Captions notice: {e}")

    print("[*] Posting First Challenge Comment...")
    try:
        youtube.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {"snippet": {"textOriginal": pin_comment}}
                }
            }
        ).execute()
        used_units += 50
        print("[+] First challenge comment posted!")
    except Exception as e:
        print(f"[!] Comment notice: {e}")

    record_quota_usage(units=used_units)
    print(f"\n[+] YouTube Deployment Complete! (Quota recorded: {used_units})\n")

if __name__ == "__main__":
    upload_video_to_youtube()
