import os, sys, re, json, time, socket, random, subprocess, requests
import verify_freefire_agent as vfa

try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass

OLLAMA_BASE = "http://127.0.0.1:11434"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"
RAW_Q = [
    "free fire one tap headshot gameplay",
    "free fire 1v4 clutch squad wipe",
    "free fire desert eagle headshot montage",
    "free fire m1887 two shot clutch",
    "free fire cs rank grandmaster gameplay",
]
BANNED = ["pubg", "bgmi", "cod", "fortnite", "valorant", "minecraft", "gta", "roblox", "giveaway", "mod apk"]
FF_HINTS = ["free fire", "freefire", "ff", "booyah", "headshot", "onetap", "one tap", "m1887", "desert eagle", "cs rank", "garena", "ruok", "raistar", "esta arma"]
SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "pinned_comment": {"type": "string"},
        "segments": {"type": "array", "items": {"type": "object", "properties": {"text": {"type": "string"}, "pace": {"type": "string"}, "sfx": {"type": "string"}}, "required": ["text", "pace", "sfx"]}},
    },
    "required": ["title", "description", "tags", "pinned_comment", "segments"],
}


def safe_title(t):
    s = (t or "").lower()
    return not any(b in s for b in BANNED) and any(h in s for h in FF_HINTS)


def load_brief():
    d = {}
    if os.path.exists("viral_topic_brief.json"):
        try: d = json.load(open("viral_topic_brief.json", "r", encoding="utf-8"))
        except Exception: pass
    if not d:
        try:
            import viral_trend_agent
            d = viral_trend_agent.scout_today_viral_topic() or {}
        except Exception: pass
    return {
        "topic": str(d.get("topic") or d.get("winner_topic") or d.get("headline") or d.get("title") or "FREE FIRE ONE TAP HEADSHOT SECRET").strip(),
        "format": str(d.get("format") or d.get("viral_format") or d.get("style") or "Detective Breakdown").strip(),
        "hook": str(d.get("hook") or d.get("hook_line") or "99% Free Fire players yeh secret nahi jante!").strip(),
        "weapon": str(d.get("weapon") or "").strip(),
    }


def finalize_clip(cand, title):
    if not os.path.exists(cand) or os.path.getsize(cand) < 300000:
        if os.path.exists(cand): os.remove(cand)
        return False
    res = vfa.verify_freefire_video(cand, title)
    ok, msg = (bool(res[0]), str(res[1])) if isinstance(res, tuple) else (bool(res), "checked")
    if not ok:
        print(f"[-] Rejected ({msg}): {title[:50]}")
        if os.path.exists(cand): os.remove(cand)
        return False
    print(f"[+] VERIFIED: {title[:60]}")
    try: vfa.crop_action_peak(cand, "raw_gameplay.mp4", 35)
    except Exception: os.replace(cand, "raw_gameplay.mp4")
    if os.path.exists(cand) and os.path.exists("raw_gameplay.mp4"):
        try: os.remove(cand)
        except Exception: pass
    return os.path.exists("raw_gameplay.mp4") and os.path.getsize("raw_gameplay.mp4") > 200000


def dl_ytdlp(url, out, proxy=None, is_yt=False):
    if os.path.exists(out): os.remove(out)
    cmd = ["yt-dlp", "--no-playlist", "--max-filesize", "75M", "--socket-timeout", "15", "--retries", "1",
           "-f", "bestvideo[height>=360][height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height>=360][ext=mp4]/best",
           "--merge-output-format", "mp4", "-o", out]
    if is_yt: cmd += ["--js-runtimes", "deno", "--extractor-args", "youtube:player_client=web_creator,tv"]
    if proxy: cmd += ["--proxy", proxy]
    try:
        p = subprocess.run(cmd + [url], capture_output=True, text=True, timeout=65)
        return p.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 300000
    except Exception:
        return False


def dl_mp4(url, out):
    if os.path.exists(out): os.remove(out)
    t0 = time.time()
    try:
        with requests.get(url, headers={"User-Agent": UA}, stream=True, timeout=20) as r:
            if r.status_code != 200: return False
            total = 0
            with open(out, "wb") as f:
                for c in r.iter_content(131072):
                    if c:
                        f.write(c); total += len(c)
                    if total > 75 * 1024 * 1024 or (time.time() - t0) > 40:
                        break
        return os.path.exists(out) and os.path.getsize(out) > 300000
    except Exception:
        return False


def harvest(brief):
    t_start = time.time()
    qs = list(RAW_Q)
    if brief["weapon"] and len(brief["weapon"]) <= 18:
        qs.insert(0, f"free fire {brief['weapon'].lower()} headshot gameplay")
    random.shuffle(qs[1:])
    proxy = None
    try:
        with socket.create_connection(("127.0.0.1", 1080), timeout=1.5): proxy = "socks5://127.0.0.1:1080"
    except Exception: pass

    print("[*] [Tier 1 - Twitch Free Fire]")
    gql = "query($id:ID!,$f:ClipsPeriod!){game(id:$id){clips(first:12,criteria:{period:$f}){edges{node{slug title url durationSeconds}}}}}"
    for per in ["LAST_DAY", "LAST_WEEK", "ALL_TIME"]:
        if time.time() - t_start > 240: break
        try:
            r = requests.post("https://gql.twitch.tv/gql", json={"query": gql, "variables": {"id": "502732", "f": per}},
                              headers={"Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko", "User-Agent": UA}, timeout=12)
            edges = (r.json().get("data") or {}).get("game", {}).get("clips", {}).get("edges", [])
            print(f"    [Twitch {per}] {len(edges)} clips")
            random.shuffle(edges)
            tried = 0
            for e in edges:
                if tried >= 2 or time.time() - t_start > 240: break
                n = e.get("node") or {}
                if 12 <= (n.get("durationSeconds") or 0) <= 180:
                    tried += 1
                    if dl_ytdlp(n.get("url") or f"https://clips.twitch.tv/{n.get('slug')}", "c_tw.mp4"):
                        if finalize_clip("c_tw.mp4", f"Free Fire {n.get('title','')}"): return True
        except Exception as ex: print(f"    [Twitch err] {ex}")

    print("[*] [Tier 2 - TikTok TikWM]")
    for q in qs[:3]:
        if time.time() - t_start > 240: break
        try:
            vids = (requests.get("https://www.tikwm.com/api/feed/search", params={"keywords": q, "count": 8, "cursor": 0},
                                 headers={"User-Agent": UA}, timeout=12).json().get("data") or {}).get("videos") or []
            print(f"    [TikWM] {len(vids)} videos")
            tried = 0
            for v in vids:
                if tried >= 2: break
                t, u = v.get("title") or q, v.get("hdplay") or v.get("play")
                if 12 <= int(v.get("duration") or 0) <= 180 and safe_title(t + " " + q) and u:
                    tried += 1
                    if dl_mp4(u, "c_tt.mp4") and finalize_clip("c_tt.mp4", t): return True
        except Exception: pass

    print("[*] [Tier 3 - Dailymotion]")
    for q in qs[:2]:
        if time.time() - t_start > 240: break
        try:
            items = requests.get("https://api.dailymotion.com/videos", params={"channel": "videogames", "search": q, "sort": "visited", "limit": 6, "fields": "title,url,duration"},
                                 headers={"User-Agent": UA}, timeout=12).json().get("list") or []
            print(f"    [Dailymotion] {len(items)} items")
            tried = 0
            for it in items:
                if tried >= 2: break
                if 14 <= int(it.get("duration") or 0) <= 420 and safe_title(it.get("title")):
                    tried += 1
                    if dl_ytdlp(it["url"], "c_dm.mp4") and finalize_clip("c_dm.mp4", it["title"]): return True
        except Exception: pass

    print(f"[*] [Tier 4 - YouTube] Proxy={'WARP' if proxy else 'Direct'}")
    for q in qs[:2]:
        if time.time() - t_start > 240: break
        try:
            cmd = ["yt-dlp", "--flat-playlist", "--dump-single-json", "--js-runtimes", "deno"] + (["--proxy", proxy] if proxy else []) + [f"ytsearch4:{q}"]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
            if p.returncode == 0 and p.stdout.strip():
                for e in (json.loads(p.stdout).get("entries") or [])[:2]:
                    if e.get("id") and 14 <= int(e.get("duration") or 0) <= 420 and safe_title(e.get("title")):
                        if dl_ytdlp(f"https://www.youtube.com/watch?v={e['id']}", "c_yt.mp4", proxy, True) and finalize_clip("c_yt.mp4", e["title"]): return True
        except Exception: pass

    print("[*] [Tier 5 - Archive.org]")
    try:
        docs = (requests.get("https://archive.org/advancedsearch.php", params={"q": 'title:("free fire") AND mediatype:(movies)', "fl[]": "identifier,title", "output": "json", "rows": 6}, timeout=12).json().get("response") or {}).get("docs") or []
        for d in docs[:2]:
            t = str(d.get("title") or "Free Fire")
            if safe_title(t) and dl_ytdlp(f"https://archive.org/details/{d['identifier']}", "c_ar.mp4") and finalize_clip("c_ar.mp4", t): return True
    except Exception: pass
    raise RuntimeError("FATAL: No verified Free Fire raw gameplay found.")


def write_script(brief):
    try: requests.post(f"{OLLAMA_BASE}/api/generate", json={"model": "qwen2.5vl:3b", "prompt": "", "keep_alive": 0}, timeout=8)
    except Exception: pass
    model = "llama3.2:1b"
    try:
        names = [m.get("name", "") for m in (requests.get(f"{OLLAMA_BASE}/api/tags", timeout=8).json().get("models") or [])]
        model = next((n for n in names if "llama3.2" in n and "vl" not in n), next((n for n in names if "vl" not in n), model))
    except Exception: pass

    scene = ""
    if os.path.exists("verified_scene.json"):
        try: scene = f" Clip scene: {json.load(open('verified_scene.json')).get('scene', '')}."
        except Exception: pass

    prompt = (f"Write a viral 25s Free Fire Short script in Hinglish/Roman Urdu for DEVIL INSANITY. Topic: {brief['topic']}. Style: {brief['format']}.{scene} "
              f"Hook: {brief['hook']}. Output valid JSON with title (max 80 chars #shorts), description (with #freefire #shorts), 6 tags, 1 pinned_comment, and 5 segments (text, pace=fast/normal/slow, sfx=hit/whoosh/none).")

    for i in range(3):
        try:
            print(f"[*] Calling {model} (attempt {i+1})...")
            r = requests.post(f"{OLLAMA_BASE}/api/generate",
                              json={"model": model, "prompt": prompt, "stream": False, "format": SCRIPT_SCHEMA, "keep_alive": 0,
                                    "options": {"num_ctx": 1024, "num_predict": 320, "temperature": 0.3}}, timeout=75)
            if r.status_code != 200: print(f"[!] Ollama {r.status_code}"); time.sleep(2); continue
            raw = r.json().get("response", "").strip()
            p = json.loads(raw)
            segs = [{"text": str(s.get("text") if isinstance(s, dict) else s).strip(),
                     "pace": s.get("pace", "normal") if isinstance(s, dict) and s.get("pace") in ["fast", "normal", "slow"] else "normal",
                     "sfx": s.get("sfx", "whoosh") if isinstance(s, dict) and s.get("sfx") in ["hit", "whoosh", "none"] else "whoosh"}
                    for s in (p.get("segments") or []) if (s.get("text") if isinstance(s, dict) else str(s)).strip()]
            if len(segs) < 2:
                segs = [{"text": brief["hook"], "pace": "fast", "sfx": "hit"}, {"text": f"{brief['topic']} ka asli raaz dekho!", "pace": "normal", "sfx": "whoosh"}]
            title = str(p.get("title") or brief["topic"]).replace("<", "").replace(">", "").strip()[:95]
            if "#shorts" not in title.lower(): title = (title[:85] + " #shorts").strip()
            txt = " ".join(x["text"] for x in segs)
            return {"title": title, "description": str(p.get("description") or f"{brief['topic']}\n#freefire #shorts").replace("<", "").replace(">", ""),
                    "tags": [str(t) for t in (p.get("tags") or ["free fire", "free fire max", "shorts"])[:10]],
                    "pinned_comment": str(p.get("pinned_comment") or "Aap ko yeh trick kaisi lagi? Comment karo!"),
                    "topic": brief["topic"], "format": brief["format"], "theme": random.choice(["CRIMSON", "CYBER", "GOLDEN", "ICE"]),
                    "hook": brief["hook"], "segments": segs, "narration": txt, "script": txt}
        except Exception as e:
            print(f"[!] Ollama retry {i+1}: {e}"); time.sleep(2)
    raise RuntimeError("FATAL: Ollama failed to generate script.")


def generate_script():
    brief = load_brief()
    print(f"[+] Trend Topic: {brief['topic']} | Format: {brief['format']}")
    harvest(brief)
    data = write_script(brief)
    json.dump(data, open("current_script.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"[+] Ready! Title: {data['title']}")


if __name__ == "__main__":
    generate_script()
