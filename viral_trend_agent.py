# viral_trend_agent.py - Live Daily Free Fire Viral Topic & Format Scout Agent
import os, re, json, time, base64, pickle, random, shutil, subprocess, requests
import urllib.parse
import xml.etree.ElementTree as ET

OLLAMA_CHAT = "http://localhost:11434/api/chat"
OLLAMA_TAGS = "http://localhost:11434/api/tags"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

TREND_SCHEMA = {
    "type": "object",
    "properties": {
        "winning_topic": {"type": "string"},
        "viral_format": {"type": "string"},
        "why_viral_today": {"type": "string"},
        "hook_line": {"type": "string"},
        "weapon_focus": {"type": "string"},
        "search_query": {"type": "string"},
        "viral_score": {"type": "integer"}
    },
    "required": ["winning_topic", "viral_format", "why_viral_today", "hook_line", "weapon_focus", "search_query", "viral_score"]
}

def fetch_google_news_ff():
    items = []
    for gl, ce in (("IN", "IN:en"), ("PK", "PK:en")):
        try:
            q = urllib.parse.quote("Garena Free Fire when:2d")
            url = f"https://news.google.com/rss/search?q={q}&hl=en-{gl}&gl={gl}&ceid={ce}"
            r = requests.get(url, headers={"User-Agent": UA}, timeout=8)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                for it in root.findall(".//item")[:8]:
                    t = (it.findtext("title") or "").rsplit(" - ", 1)[0].strip()
                    if t and t not in items:
                        items.append(t)
        except Exception:
            pass
    return items[:12]

def fetch_yt_autocomplete():
    sug = []
    for seed in ("free fire ", "free fire new ", "free fire headshot ", "free fire secret "):
        try:
            r = requests.get("https://suggestqueries.google.com/complete/search", params={"client": "firefox", "ds": "yt", "q": seed}, headers={"User-Agent": UA}, timeout=6)
            data = r.json() if r.status_code == 200 else []
            if isinstance(data, list) and len(data) > 1:
                for s in data[1][:5]:
                    if s not in sug:
                        sug.append(s)
        except Exception:
            pass
    return sug[:15]

def fetch_yt_gaming_trending():
    tp = os.environ.get("YOUTUBE_TOKEN_PICKLE")
    if not tp:
        return []
    hits = []
    try:
        from googleapiclient.discovery import build
        yt = build("youtube", "v3", credentials=pickle.loads(base64.b64decode(tp.strip())))
        for reg in ("IN", "PK"):
            res = yt.videos().list(part="snippet,statistics", chart="mostPopular", videoCategoryId="20", regionCode=reg, maxResults=15).execute()
            for v in res.get("items", []):
                ttl = v["snippet"]["title"]
                if any(k in ttl.lower() for k in ("free fire", "freefire", "garena", "booyah", "m1887", "desert eagle", "headshot", "ff")):
                    vc = int(v.get("statistics", {}).get("viewCount", 0))
                    hits.append(f"{ttl} ({vc} views)")
    except Exception:
        pass
    return hits[:8]

def fetch_twitch_24h_hot():
    hdr = {"Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko", "Content-Type": "application/json", "User-Agent": UA}
    q = "query($s: ID!){game(slug:$s){clips(first:15,criteria:{filter:LAST_DAY}){edges{node{title viewCount}}}}}"
    out = []
    try:
        r = requests.post("https://gql.twitch.tv/gql", headers=hdr, json={"query": q, "variables": {"s": "garena-free-fire"}}, timeout=10)
        edges = ((((r.json() or {}).get("data") or {}).get("game") or {}).get("clips") or {}).get("edges") or []
        for e in edges:
            n = e.get("node") or {}
            t = (n.get("title") or "").strip()
            if t:
                out.append(f"{t} ({n.get('viewCount', 0)} views)")
    except Exception:
        pass
    return out[:10]

def get_past_topics():
    if os.path.exists("history.json"):
        try:
            h = json.load(open("history.json", "r", encoding="utf-8"))
            return [str(x.get("title") or "") for x in (h.get("entries") or [])[-12:]]
        except Exception:
            pass
    return []

def ensure_text_model():
    for att in range(2):
        try:
            models = [m.get("name", "") for m in requests.get(OLLAMA_TAGS, timeout=4).json().get("models", [])]
            m = next((x for x in models if "llama3.2:1b" in x), next((x for x in models if "vl" not in x and "moondream" not in x), "llama3.2:1b"))
            if m not in models:
                subprocess.run(["ollama", "pull", m], check=True)
            return m
        except Exception:
            if att == 0:
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(3)
    raise RuntimeError("Ollama unavailable for Trend Scout Agent")

def scout_today_viral_topic(format_type="short"):
    print("\n==========================================")
    print("[*] AGENT 1: LIVE VIRAL TREND SCOUT")
    print("==========================================")
    news = fetch_google_news_ff()
    yt_sug = fetch_yt_autocomplete()
    yt_tr = fetch_yt_gaming_trending()
    tw_hot = fetch_twitch_24h_hot()
    past = get_past_topics()

    if not (news or yt_sug or tw_hot):
        raise RuntimeError("FATAL: Zero live Free Fire trend signals received!")

    print(f"[+] Signals -> News: {len(news)} | YT Search: {len(yt_sug)} | YT Trending: {len(yt_tr)} | Twitch 24h: {len(tw_hot)}")
    model = ensure_text_model()

    prompt = (
        f"You are a viral YouTube Gaming Strategist for DEVIL-999 (Free Fire {format_type}).\n"
        f"TODAY'S LIVE SIGNALS:\n"
        f"- Breaking News (48h): {news}\n"
        f"- Live YouTube Searches: {yt_sug}\n"
        f"- YouTube Trending FF: {yt_tr}\n"
        f"- Twitch 24h Top FF Clips: {tw_hot}\n"
        f"- AVOID repeating recent topics: {past}\n\n"
        "Pick the SINGLE highest-viral-potential Free Fire topic TODAY.\n"
        "viral_format MUST be one of: 'Detective Breakdown', 'Mythbuster Test', '0.25x Slow-Mo Secret', 'Revenge Story', 'New Update Leak'.\n"
        "hook_line MUST be a shocking 6-10 word Roman Urdu 2-second hook.\n"
        "search_query MUST be a plain 4-6 word Free Fire gameplay query (no symbols)."
    )

    payload = {
        "model": model,
        "messages": [{"role": "system", "content": "Output valid compact JSON only."}, {"role": "user", "content": prompt}],
        "format": TREND_SCHEMA,
        "stream": False,
        "options": {"temperature": 0.45, "num_ctx": 4096, "num_predict": 450}
    }
    r = requests.post(OLLAMA_CHAT, json=payload, timeout=90)
    r.raise_for_status()
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", r.json()["message"]["content"].strip()).strip()
    brief = json.loads(txt)
    brief["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(brief, open("viral_topic_brief.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"[+] Winner Topic: {brief['winning_topic']} | Format: {brief['viral_format']} | Score: {brief['viral_score']}/100")
    return brief

if __name__ == "__main__":
    scout_today_viral_topic()
