import os, re, json, time, base64, pickle, random, subprocess, urllib.request
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

try:
    from empire_safety_shield import record_quota_usage
except Exception:
    def record_quota_usage(units=50): pass

STATE_FILE, REQ_FILE, UPLOAD_LOG = "replied_comments.json", "requested_topics.json", "uploaded_videos.json"
OLLAMA_TAGS, OLLAMA_API = "http://localhost:11434/api/tags", "http://localhost:11434/api/generate"
SKIP_TERMS = ("http", "www.", ".com", "whatsapp", "telegram", "sponsor", "promo", "sub4sub", "free fire", "headshot", "1v1", "hack", "sell", "buy")
BLOCKED = ("murder", "serial killer", "suicide", "gore", "torture", "trump", "biden", "election", "gaza", "ukraine", "crypto", "bitcoin", "porn", "naked")
OLD_GAMING = ("free fire", "booyah", "headshot", "1v1", "custom room", "gaming", "ff ")
REQ_TRIGGERS = ("make a video", "do a video", "cover ", "explain ", "next file", "next video", "what about ", "story of ", "mystery of ", "talk about ", "do one on ")

def get_yt():
    tp = os.environ.get("YOUTUBE_TOKEN_PICKLE")
    if not tp: raise ValueError("YOUTUBE_TOKEN_PICKLE missing!")
    creds = pickle.loads(base64.b64decode(tp.strip()))
    if creds.expired and creds.refresh_token: creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)

def get_model():
    for att in range(2):
        try:
            ms = [m.get("name", "") for m in json.loads(urllib.request.urlopen(OLLAMA_TAGS, timeout=5).read()).get("models", [])]
            return next((x for x in ms if "qwen2.5" in x), next((x for x in ms if "llama3.2" in x), ms[0] if ms else None))
        except Exception:
            if att == 0: subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(3)
    return None

def load_json(path, default):
    if not os.path.exists(path): return default
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except Exception: return default

def extract_topic_req(txt, likes):
    low = txt.lower().strip()
    if len(low) < 12 or any(b in low for b in BLOCKED): return ""
    cand = ""
    for tr in REQ_TRIGGERS:
        if tr in low:
            cand = re.sub(r"[^A-Za-z0-9 ,'-]", "", txt.lower().split(tr, 1)[1]).strip(); break
    if not cand and likes >= 2 and "?" in txt and 4 <= len(txt.split()) <= 12:
        cand = re.sub(r"[^A-Za-z0-9 ,'-]", "", txt).strip()
    return cand[:75].title() if 3 <= len(cand.split()) <= 11 else ""

def queue_request(reqs, topic, user, likes):
    low = topic.lower()
    if any(r.get("topic", "").lower() == low for r in reqs): return False
    reqs.append({"topic": topic, "user": user[:24], "likes": int(likes)})
    reqs.sort(key=lambda x: x.get("likes", 0), reverse=True)
    return True

def gen_reply(txt, meta, model, egg_hit=False, req_topic=""):
    clbl, topic, egg = meta.get("case_label", "FILE"), meta.get("topic", "this anomaly"), meta.get("easter_egg_code", "X-014")
    if req_topic:
        return f"Dossier queued for '{req_topic}'. Watch for your handle in an upcoming {clbl.split('#')[0].strip()} file!"[:180]
    if egg_hit:
        return f"Signal confirmed ({egg}). You caught the anomaly faster than 94% of investigators."[:180]
    if not model:
        return "Every mystery leaves a signal. Drop the next anomaly you want decoded."
    prompt = "\n".join([
        f"You are SILENT SIGNAL, a calm, intriguing documentary investigator. Video: '{topic}' ({clbl}).",
        "Reply to the viewer comment in natural English (10-18 words MAX). Rules:",
        "- Match the tone: validate smart observations, answer skeptics with an intriguing real-world clue, never use emojis spam or slang.",
        "- Never promise exact upload dates or links.",
        f"Viewer: {txt[:180]}\nSILENT SIGNAL:",
    ])
    pay = {"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.65, "num_predict": 48}}
    try:
        req = urllib.request.Request(OLLAMA_API, data=json.dumps(pay).encode(), headers={"Content-Type": "application/json"})
        r = json.loads(urllib.request.urlopen(req, timeout=30).read()).get("response", "").strip().replace('"', "").splitlines()[0]
        return r[:180] if (r and len(r.split()) >= 3 and "free fire" not in r.lower()) else "Every mystery leaves a signal. Which anomaly should we open next?"
    except Exception:
        return "Every mystery leaves a signal. Stay sharp for the next dossier."

def run_comment_engine():
    print("\n[*] SILENT SIGNAL: COMMENT & TOPIC-MINING AGENT", flush=True)
    yt = get_yt()
    ch = yt.channels().list(mine=True, part="id,contentDetails").execute().get("items", [])
    if not ch: return
    my_id, up_id = ch[0]["id"], ch[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    pls = yt.playlistItems().list(playlistId=up_id, part="snippet", maxResults=15).execute().get("items", [])
    vids = [it["snippet"]["resourceId"]["videoId"] for it in pls]
    if not vids: return

    vinfo = {v["id"]: v for v in yt.videos().list(part="snippet,status", id=",".join(vids)).execute().get("items", [])}
    replied = set(load_json(STATE_FILE, []))
    reqs = load_json(REQ_FILE, [])
    up_log = load_json(UPLOAD_LOG, {})
    model, posted, units = get_model(), 0, 3

    for vid in vids:
        if posted >= 12: break
        vi = vinfo.get(vid, {})
        if vi.get("status", {}).get("privacyStatus") != "public": continue
        ttl = vi.get("snippet", {}).get("title", "")
        if any(g in ttl.lower() for g in OLD_GAMING): continue
        meta = up_log.get(vid, {"topic": ttl, "case_label": "FILE", "easter_egg_code": "X-014"})
        try:
            threads = yt.commentThreads().list(part="snippet,replies", videoId=vid, maxResults=25, order="relevance", textFormat="plainText").execute().get("items", [])
            units += 1
        except HttpError: continue

        for th in threads:
            if posted >= 12: break
            top = th["snippet"]["topLevelComment"]
            cid, sn = top["id"], top["snippet"]
            txt = sn.get("textOriginal", "").strip()
            if cid in replied or sn.get("authorChannelId", {}).get("value") == my_id: continue
            if any(r.get("snippet", {}).get("authorChannelId", {}).get("value") == my_id for r in th.get("replies", {}).get("comments", [])):
                replied.add(cid); continue
            if not txt or any(k in txt.lower() for k in SKIP_TERMS) or any(b in txt.lower() for b in BLOCKED) or re.search(r"\b\d{10,12}\b", txt):
                replied.add(cid); continue

            likes = int(sn.get("likeCount", 0))
            author = sn.get("authorDisplayName", "@Investigator")
            egg_code = str(meta.get("easter_egg_code", "")).lower()
            egg_hit = bool((egg_code and egg_code in txt.lower()) or ("spotted" in txt.lower()) or re.search(r"\b0:\d{2}\b", txt))
            req_topic = extract_topic_req(txt, likes)
            queued = queue_request(reqs, req_topic, author, likes) if req_topic else False
            rep = gen_reply(txt, meta, model, egg_hit=egg_hit, req_topic=(req_topic if queued else ""))
            try:
                yt.comments().insert(part="snippet", body={"snippet": {"parentId": cid, "textOriginal": rep}}).execute()
                posted += 1; units += 50; replied.add(cid)
                print(f"[+] Reply on {vid}: '{txt[:40]}' -> '{rep[:60]}'", flush=True)
            except Exception as e: print(f"[!] Reply fail: {e}")
            time.sleep(random.uniform(3.0, 6.0))

    with open(STATE_FILE, "w", encoding="utf-8") as f: json.dump(list(replied)[-800:], f)
    with open(REQ_FILE, "w", encoding="utf-8") as f: json.dump(reqs[:20], f, indent=2)
    record_quota_usage(units=units)
    print(f"[+] Agent Complete! Replies: {posted} | Queued Topics: {len(reqs)} | Quota: {units}", flush=True)

if __name__ == "__main__":
    run_comment_engine()
