import base64, json, os, pickle, re, time
from datetime import datetime, timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

try:
    from empire_safety_shield import record_quota_usage
except Exception:
    def record_quota_usage(units=1650):
        pass

SCRIPT_FILE, SUBTITLE_FILE, UPLOAD_LOG = "current_script.json", "subtitles_en.srt", "uploaded_videos.json"
SEO_TAGS = ["Shorts", "Silent Signal", "True Mystery", "Deep Ocean", "Space Facts", "Science Explained", "Unexplained Mysteries", "Documentary"]


def get_video_path():
    for p in ("final_output.mp4", "final_video.mp4"):
        if os.path.exists(p) and os.path.getsize(p) >= 10000:
            return p
    raise FileNotFoundError("Rendered video missing or empty!")


def clean_yt_text(text, max_len=None):
    s = re.sub(r"\(FILE\s*#?\d+\)", "", str(text or ""), flags=re.I)
    s = re.sub(r"\s+", " ", re.sub(r"[<>]", "", s)).strip()
    return (s[: max_len - 3].rstrip() + "...") if (max_len and len(s) > max_len) else s


def get_youtube_service():
    raw = os.environ.get("YOUTUBE_TOKEN_PICKLE", "").strip()
    if not raw:
        raise ValueError("YOUTUBE_TOKEN_PICKLE secret missing!")
    if raw.startswith("{"):
        creds = Credentials.from_authorized_user_info(json.loads(raw))
    else:
        dec = base64.b64decode(raw)
        try:
            creds = pickle.loads(dec)
        except Exception:
            creds = Credentials.from_authorized_user_info(json.loads(dec.decode("utf-8")))
    if creds.expired and creds.refresh_token:
        print("[*] Refreshing YouTube OAuth token...")
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def build_tags(script_tags):
    merged, seen, total = [], set(), 0
    for raw in list(script_tags or []) + SEO_TAGS:
        t = clean_yt_text(str(raw).replace("#", ""), 40)
        k = t.lower()
        if not t or k in seen:
            continue
        cost = len(t) + (3 if " " in t else 1)
        if total + cost > 450:
            break
        seen.add(k)
        merged.append(t)
        total += cost
    return merged


def load_metadata():
    title = "Why This Deep Signal Should Not Exist"
    desc_body = "Investigating real, verified anomalies from Earth's strangest frontiers."
    tags = build_tags([])
    pin_comment = "What do you think caused this? Drop your theory below."
    meta = {}
    if os.path.exists(SCRIPT_FILE):
        meta = json.load(open(SCRIPT_FILE, encoding="utf-8"))
        if meta.get("title"):
            title = clean_yt_text(meta["title"], 55)
        if meta.get("description"):
            desc_body = clean_yt_text(meta["description"], 1200)
        tags = build_tags(meta.get("tags", []))
        if meta.get("pinned_comment"):
            pin_comment = clean_yt_text(meta["pinned_comment"], 300)
    title = re.sub(r"\s*#shorts\b", "", title, flags=re.I).strip()[:52]
    tags_line = "\n#Shorts #SilentSignal #Mystery #Science" if "#shorts" not in desc_body.lower() else ""
    description = f"{desc_body}{tags_line}\n\nSilent Signal — Real documented anomalies."[:4800]
    return title, description, tags, pin_comment, meta


def execute_upload(yt, vpath, body):
    media = MediaFileUpload(vpath, chunksize=4 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    req, resp = yt.videos().insert(part="snippet,status", body=body, media_body=media), None
    while resp is None:
        st, resp = req.next_chunk()
        if st:
            print(f" -> Upload progress: {int(st.progress() * 100)}%")
    return resp


def save_upload_log(vid, title, meta):
    log = {}
    if os.path.exists(UPLOAD_LOG):
        try:
            log = json.load(open(UPLOAD_LOG, encoding="utf-8"))
        except Exception:
            log = {}
    log[vid] = {"title": title, "topic": meta.get("topic", ""), "ts": datetime.now(timezone.utc).isoformat()}
    if len(log) > 100:
        for k in list(log.keys())[:-100]:
            log.pop(k, None)
    json.dump(log, open(UPLOAD_LOG, "w", encoding="utf-8"), indent=2)


def upload_video_to_youtube():
    vpath, yt = get_video_path(), get_youtube_service()
    title, description, tags, pin_comment, meta = load_metadata()
    privacy = os.environ.get("UPLOAD_PRIVACY", "public").strip().lower()
    if privacy not in ("public", "private", "unlisted"):
        privacy = "public"
    print(f"[*] Title: {title} | Privacy: {privacy}")
    body = {
        "snippet": {"title": title, "description": description, "tags": tags, "categoryId": "28", "defaultLanguage": "en", "defaultAudioLanguage": "en"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True},
    }
    try:
        resp = execute_upload(yt, vpath, body)
    except HttpError as e:
        if "containsSyntheticMedia" in str(e):
            body["status"].pop("containsSyntheticMedia", None)
            resp = execute_upload(yt, vpath, body)
        else:
            raise
    vid, units = resp.get("id"), 1600
    print(f"[+] UPLOAD SUCCESS! https://youtu.be/{vid}")
    save_upload_log(vid, title, meta)

    if os.path.exists(SUBTITLE_FILE) and os.path.getsize(SUBTITLE_FILE) > 0:
        try:
            yt.captions().insert(part="snippet", body={"snippet": {"videoId": vid, "language": "en", "name": "English", "isDraft": False}}, media_body=MediaFileUpload(SUBTITLE_FILE, mimetype="application/octet-stream")).execute()
            units += 400
        except Exception as e:
            print(f"[!] Captions notice: {e}")

    if privacy == "public" and pin_comment:
        time.sleep(8)
        try:
            yt.commentThreads().insert(part="snippet", body={"snippet": {"videoId": vid, "topLevelComment": {"snippet": {"textOriginal": pin_comment}}}}).execute()
            units += 50
            print("[+] Comment posted!")
        except Exception as e:
            print(f"[!] Comment notice: {e}")
    record_quota_usage(units=units)


if __name__ == "__main__":
    upload_video_to_youtube()
