import base64
import json
import os
import pickle
import re
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
    "Shorts", "True Mystery", "Deep Ocean", "Space Facts",
    "Survival Story", "Science Explained", "Unexplained Mysteries",
    "Dark History", "Documentary Shorts", "Facts"
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
        raise ValueError("YOUTUBE_TOKEN_PICKLE secret missing!")
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
    title = "What Happens In Total Darkness 3000 Meters Deep #Shorts"
    desc_body = "A deep dive into the strangest real mysteries on Earth and beyond."
    tags = build_tags([])
    pin_comment = "Would you survive even 10 seconds here? Drop your answer below!"

    if os.path.exists(SCRIPT_FILE):
        with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("title"):
            title = clean_yt_text(data["title"], 92)
        if data.get("description"):
            desc_body = re.sub(r"[<>]", "", str(data["description"])).strip()
        tags = build_tags(data.get("tags", []))
        if data.get("pinned_comment"):
            pin_comment = clean_yt_text(data["pinned_comment"], 400)

    if "#shorts" not in title.lower():
        title = clean_yt_text(f"{title} #Shorts", 98)
    shorts_tag = "\n#Shorts #Mystery #Science #Documentary" if "#shorts" not in desc_body.lower() else ""
    description = (
        f"{desc_body}{shorts_tag}\n\n"
        "Original narrated documentary short with AI-visualized reconstructions and licensed public stock footage."
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
    if not os.path.exists(VIDEO_FILE) or os.path.getsize(VIDEO_FILE) < 10000:
        raise FileNotFoundError(f"{VIDEO_FILE} missing or empty!")

    youtube = get_youtube_service()
    title, description, tags, pin_comment = load_metadata()
    publish_at = calculate_publish_time()

    print(f"[*] Title: {title}")
    print(f"[*] Scheduled (18:00 PKT): {publish_at}")

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "28",
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": publish_at,
            "selfDeclaredMadeForKids": False,
        },
    }

    try:
        response = execute_upload(youtube, body)
    except HttpError as e:
        if "publishAt" in str(e):
            print(f"[!] Scheduled publishAt notice, retrying as draft: {e}")
            body["status"].pop("publishAt", None)
            response = execute_upload(youtube, body)
        else:
            raise

    video_id = response.get("id")
    used_units = 1600
    print(f"[+] UPLOAD SUCCESS! https://youtu.be/{video_id}")

    if os.path.exists(SUBTITLE_FILE) and os.path.getsize(SUBTITLE_FILE) > 0:
        try:
            sub_media = MediaFileUpload(SUBTITLE_FILE, mimetype="application/octet-stream")
            youtube.captions().insert(
                part="snippet",
                body={"snippet": {"videoId": video_id, "language": "en", "name": "English", "isDraft": False}},
                media_body=sub_media,
            ).execute()
            used_units += 400
        except Exception as e:
            print(f"[!] Captions notice: {e}")

    try:
        youtube.commentThreads().insert(
            part="snippet",
            body={"snippet": {"videoId": video_id, "topLevelComment": {"snippet": {"textOriginal": pin_comment}}}},
        ).execute()
        used_units += 50
    except Exception as e:
        print(f"[!] Comment notice: {e}")

    record_quota_usage(units=used_units)


if __name__ == "__main__":
    upload_video_to_youtube()
