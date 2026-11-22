import base64, json, os, pickle, re
from datetime import datetime, timedelta, timezone
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

try:
    from empire_safety_shield import record_quota_usage
except Exception:
    def record_quota_usage(units=1650): pass

SCRIPT_FILE, SUBTITLE_FILE, UPLOAD_LOG = "current_script.json", "subtitles_en.srt", "uploaded_videos.json"
SEO_TAGS = ["Shorts", "Silent Signal", "True Mystery", "Deep Ocean", "Space Facts", "Survival Story", "Science Explained", "Unexplained Mysteries", "Dark History", "Documentary Shorts"]

def get_video_path():
    for p in ("final_output.mp4", "final_video.mp4"):
        if os.path.exists(p) and os.path.getsize(p) >= 10000: return p
    raise FileNotFoundError("Rendered video missing or empty!")

def clean_yt_text(text, max_len=None):
    s = re.sub(r"\s+", " ", re.sub(r"[<>]", "", str(text or ""))).strip()
    return (s[:max_len - 3].rstrip() + "...") if (max_len and len(s) > max_len) else s

def get_youtube_service():
    tp = os.environ.get("YOUTUBE_TOKEN_PICKLE")
    if not tp: raise ValueError("YOUTUBE_TOKEN_PICKLE secret missing!")
    creds = pickle.loads(base64.b64decode(tp.strip()))
    if creds.expired and creds.refresh_token:
        print("[*] Refreshing YouTube OAuth token..."); creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)

def build_tags(script_tags):
    merged, seen, total = [], set(), 0
    for raw in (list(script_tags or []) + SEO_TAGS):
        t = clean_yt_text(str(raw).replace("#", ""), 40)
        k = t.lower()
        if not t or k in seen: continue
        cost = len(t) + (3 if " " in t else 1)
        if total + cost > 450: break
        seen.add(k); merged.append(t); total += cost
    return merged

def load_metadata():
    title, desc_body, tags, pin_comment, meta = "What Happens In Total Darkness 3000 Meters Deep #Shorts", "Investigating the strangest verified anomalies on Earth and beyond.", build_tags([]), "Did you catch the hidden signal? Comment what mystery we should decode next!", {}
    if os.path.exists(SCRIPT_FILE):
        with open(SCRIPT_FILE, encoding="utf-8") as f: meta = json.load(f)
        if meta.get("title"): title = clean_yt_text(meta["title"], 92)
        if meta.get("description"): desc_body = re.sub(r"[<>]", "", str(meta["description"])).strip()
        tags = build_tags(meta.get("tags", []))
        if meta.get("pinned_comment"): pin_comment = clean_yt_text(meta["pinned_comment"], 400)
    if "#shorts" not in title.lower(): title = clean_yt_text(f"{title} #Shorts", 98)
    clbl = meta.get("case_label", "FILE #001")
    tags_line = "\n#Shorts #SilentSignal #Mystery #Science" if "#shorts" not in desc_body.lower() else ""
    description = f"{desc_body}{tags_line}\n\nSilent Signal | {clbl} — Every mystery leaves a signal.\nSubscribe for daily decoded dossiers."[:4800]
    return title, description, tags, pin_comment, meta

def calculate_publish_time():
    now_utc = datetime.now(timezone.utc)
    for d_off in (0, 1):
        base = now_utc + timedelta(days=d_off)
        for hr in (14, 19, 23):
            cand = base.replace(hour=hr, minute=0, second=0, microsecond=0)
            if cand >= now_utc + timedelta(minutes=20): return cand.strftime("%Y-%m-%dT%H:%M:%SZ")
    return (now_utc + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

def execute_upload(yt, vpath, body):
    media = MediaFileUpload(vpath, chunksize=4 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    req, resp = yt.videos().insert(part="snippet,status", body=body, media_body=media), None
    while resp is None:
        st, resp = req.next_chunk()
        if st: print(f" -> Upload progress: {int(st.progress() * 100)}%")
    return resp

def save_upload_log(vid, title, meta):
    log = {}
    if os.path.exists(UPLOAD_LOG):
        try:
            with open(UPLOAD_LOG, encoding="utf-8") as f: log = json.load(f)
        except Exception: log = {}
    log[vid] = {"title": title, "topic": meta.get("topic", ""), "case_label": meta.get("case_label", ""), "easter_egg_code": meta.get("easter_egg_code", ""), "ts": datetime.now(timezone.utc).isoformat()}
    if len(log) > 100:
        for k in list(log.keys())[:-100]: log.pop(k, None)
    with open(UPLOAD_LOG, "w", encoding="utf-8") as f: json.dump(log, f, indent=2)

def upload_video_to_youtube():
    vpath, yt = get_video_path(), get_youtube_service()
    title, description, tags, pin_comment, meta = load_metadata()
    publish_at = calculate_publish_time()
    print(f"[*] Title: {title}\n[*] Scheduled (US/UK Prime UTC): {publish_at}")
    body = {"snippet": {"title": title, "description": description, "tags": tags, "categoryId": "28", "defaultLanguage": "en", "defaultAudioLanguage": "en"}, "status": {"privacyStatus": "private", "publishAt": publish_at, "selfDeclaredMadeForKids": False}}
    try: resp = execute_upload(yt, vpath, body)
    except HttpError as e:
        if "publishAt" in str(e):
            print(f"[!] Scheduled publishAt notice, retrying draft: {e}")
            body["status"].pop("publishAt", None)
            resp = execute_upload(yt, vpath, body)
        else: raise
    vid, units = resp.get("id"), 1600
    print(f"[+] UPLOAD SUCCESS! https://youtu.be/{vid}")
    save_upload_log(vid, title, meta)
    if os.path.exists(SUBTITLE_FILE) and os.path.getsize(SUBTITLE_FILE) > 0:
        try:
            yt.captions().insert(part="snippet", body={"snippet": {"videoId": vid, "language": "en", "name": "English", "isDraft": False}}, media_body=MediaFileUpload(SUBTITLE_FILE, mimetype="application/octet-stream")).execute()
            units += 400
        except Exception as e: print(f"[!] Captions notice: {e}")
    try:
        yt.commentThreads().insert(part="snippet", body={"snippet": {"videoId": vid, "topLevelComment": {"snippet": {"textOriginal": pin_comment}}}}).execute()
        units += 50
    except Exception as e: print(f"[!] Comment notice: {e}")
    record_quota_usage(units=units)

if __name__ == "__main__":
    upload_video_to_youtube()
