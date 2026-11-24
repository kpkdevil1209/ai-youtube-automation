import base64
import datetime
import json
import os
import pickle
import sys
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

HISTORY_FILE = "posted_long_history.json"


def load_youtube_service():
    creds = None
    raw = os.environ.get("YOUTUBE_TOKEN_PICKLE", "").strip()
    if raw:
        if raw.startswith("{"):
            creds = Credentials.from_authorized_user_info(json.loads(raw))
        else:
            decoded = base64.b64decode(raw)
            try:
                creds = pickle.loads(decoded)
            except Exception:
                creds = Credentials.from_authorized_user_info(json.loads(decoded.decode("utf-8")))
    elif os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as f:
            creds = pickle.load(f)

    if not creds:
        raise RuntimeError("Missing YOUTUBE_TOKEN_PICKLE credentials.")
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def next_publish_iso():
    now = datetime.datetime.now(datetime.timezone.utc)
    target = now.replace(hour=16, minute=30, second=0, microsecond=0)
    if target <= now + datetime.timedelta(minutes=30):
        target += datetime.timedelta(days=1)
    return target.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_chapters_block(meta):
    txt = (meta.get("chapters_text") or "").strip()
    if "00:00" in txt:
        return txt
    lines = []
    for idx, ch in enumerate(meta.get("chapters", [])):
        sec = 0 if idx == 0 else int(float(ch.get("start_sec", idx * 75)))
        mm, ss = divmod(max(0, sec), 60)
        title = (ch.get("title") or ch.get("chapter_title") or f"Part {idx + 1}").strip()
        lines.append(f"{mm:02d}:{ss:02d} - {title}")
    return "\n".join(lines)


def update_history(entry):
    hist = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                hist = data if isinstance(data, list) else data.get("videos", [])
        except Exception:
            hist = []
    hist.append(entry)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(hist[-200:], f, indent=2)


def upload_long():
    video_path = "long_final.mp4"
    script_path = "long_script.json"
    thumb_path = "thumbnail.jpg"
    srt_path = "long_subtitles.srt"

    if not os.path.exists(video_path) or os.path.getsize(video_path) < 5_000_000:
        raise RuntimeError(f"Invalid or missing {video_path}")
    with open(script_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    title = (meta.get("title") or meta.get("video_title") or meta.get("topic") or "The Unexplained Signal").strip()
    if len(title) > 98:
        title = title[:95].rstrip() + "..."

    summary = (meta.get("description") or meta.get("hook") or meta.get("topic") or "").strip()
    chapters_blk = build_chapters_block(meta)
    desc = (
        f"{summary}\n\n"
        "Every chapter in this dossier reconstructs documented anomalies, declassified timelines, and unanswered evidence.\n\n"
        f"CHAPTERS:\n{chapters_blk}\n\n"
        "#Documentary #UnsolvedMystery #SilentSignal #TrueMystery"
    ).strip()

    tags = meta.get("tags") or ["documentary", "unsolved mystery", "silent signal", "declassified", "true mystery"]
    publish_at = next_publish_iso()
    yt = load_youtube_service()

    body = {
        "snippet": {
            "title": title,
            "description": desc[:4900],
            "tags": [str(t)[:30] for t in tags[:12]],
            "categoryId": "28",
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": publish_at,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
        },
    }

    media = MediaFileUpload(video_path, chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    try:
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            status, resp = req.next_chunk()
            if status:
                print(f"[Upload] {int(status.progress() * 100)}%", flush=True)
    except Exception as exc:
        if "containsSyntheticMedia" in str(exc):
            body["status"].pop("containsSyntheticMedia", None)
            media = MediaFileUpload(video_path, chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4")
            req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
            resp = None
            while resp is None:
                status, resp = req.next_chunk()
        else:
            raise

    vid = resp["id"]
    print(f"[+] Uploaded Long-Form Video ID: {vid} | Scheduled: {publish_at}", flush=True)

    if os.path.exists(thumb_path):
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb_path, mimetype="image/jpeg")).execute()
            print("[+] Custom thumbnail.jpg attached!", flush=True)
        except Exception as e:
            print(f"[!] Thumbnail upload skipped: {e}", flush=True)

    if os.path.exists(srt_path):
        try:
            yt.captions().insert(
                part="snippet",
                body={"snippet": {"videoId": vid, "language": "en", "name": "English", "isDraft": False}},
                media_body=MediaFileUpload(srt_path, mimetype="application/octet-stream"),
            ).execute()
            print("[+] English CC subtitles attached!", flush=True)
        except Exception as e:
            print(f"[!] Captions skipped (needs youtube.force-ssl scope): {e}", flush=True)

    update_history({
        "video_id": vid,
        "topic": meta.get("topic") or title,
        "title": title,
        "published_at": publish_at,
        "duration_sec": meta.get("total_duration_sec", 0),
        "url": f"https://www.youtube.com/watch?v={vid}",
    })


if __name__ == "__main__":
    upload_long()
