# comment_reply_bot.py - Agent 6: Pro Gamer Engagement Bot
import os, re, json, time, base64, pickle, random, subprocess, urllib.request
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

try:
    from empire_safety_shield import record_quota_usage
except Exception:
    def record_quota_usage(units=50): pass

STATE_FILE, OLLAMA_TAGS, OLLAMA_API = "replied_comments.json", "http://localhost:11434/api/tags", "http://localhost:11434/api/generate"
HUMAN_ONLY = ["kahan rehte", "id do", "password", "collab", "number", "whatsapp", "pesa", "paid", "promotion", "meetup", "buy", "sell", "sponsor", "real name", "kon ho"]

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
            return next((x for x in ms if "llama3.2:1b" in x), ms[0] if ms else None)
        except Exception:
            if att == 0:
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(3)
    return None

def gen_reply(txt, model):
    if not model: return None
    prompt = (
        "You are DEVIL-999, pro Free Fire player. Reply in <=10 words (Roman Urdu/English). Never promise 1v1 or uploads.\n"
        "Examples:\nViewer: ♥♥♥♥♥\nDEVIL: Dil se shukriya bhai, love you!\n"
        "Viewer: Nice accuracy bro\nDEVIL: Thanks bro, roz training ground ka kamaal hai!\n"
        "Viewer: Hacker hai yeh\nDEVIL: 0.25x par aim drag check kar lo bro!\n"
        f"Viewer: {txt}\nDEVIL:"
    )
    pay = {"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.65, "num_predict": 35}}
    try:
        req = urllib.request.Request(OLLAMA_API, data=json.dumps(pay).encode(), headers={"Content-Type": "application/json"})
        r = json.loads(urllib.request.urlopen(req, timeout=30).read()).get("response", "").strip().replace('"', "").splitlines()[0]
        return None if (not r or any(w in r.lower() for w in ("custom", "1v1", "kal video", "upload"))) else r[:160]
    except Exception:
        return None

def run_comment_engine():
    print("\n==========================================")
    print("[*] AGENT 6: PRO GAMER COMMENT BOT")
    print("==========================================")
    yt = get_yt()
    ch = yt.channels().list(mine=True, part="id,contentDetails").execute().get("items", [])
    if not ch: return
    my_id, up_id = ch[0]["id"], ch[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    pls = yt.playlistItems().list(playlistId=up_id, part="snippet", maxResults=6).execute().get("items", [])
    replied = set(json.load(open(STATE_FILE))) if os.path.exists(STATE_FILE) else set()
    model, posted, units = get_model(), 0, 2

    for it in pls:
        if posted >= 10: break
        vid, ttl = it["snippet"]["resourceId"]["videoId"], it["snippet"].get("title", "")
        if ttl in ("Deleted video", "Private video"): continue
        try:
            threads = yt.commentThreads().list(part="snippet,replies", videoId=vid, maxResults=20, textFormat="plainText").execute().get("items", [])
            units += 1
        except HttpError:
            continue
        for th in threads:
            if posted >= 10: break
            top = th["snippet"]["topLevelComment"]
            cid, sn = top["id"], top["snippet"]
            txt = sn.get("textOriginal", "")
            if cid in replied or sn.get("authorChannelId", {}).get("value") == my_id: continue
            if any(r.get("snippet", {}).get("authorChannelId", {}).get("value") == my_id for r in th.get("replies", {}).get("comments", [])):
                replied.add(cid); continue
            if any(k in txt.lower() for k in HUMAN_ONLY) or re.search(r"\b\d{10,12}\b", txt) or "@" in txt:
                replied.add(cid); continue
            rep = gen_reply(txt, model)
            if not rep: continue
            try:
                yt.comments().insert(part="snippet", body={"snippet": {"parentId": cid, "textOriginal": rep}}).execute()
                posted += 1; units += 50; replied.add(cid)
                print(f"[+] Replied on {vid}: '{txt}' -> '{rep}'")
            except Exception as e:
                print(f"[!] Reply fail: {e}")
            time.sleep(random.uniform(4.0, 8.0))

    json.dump(list(replied)[-500:], open(STATE_FILE, "w"))
    record_quota_usage(units=units)
    print(f"[+] Agent 6 Complete! Replies: {posted} | Quota: {units}\n")

if __name__ == "__main__":
    run_comment_engine()
