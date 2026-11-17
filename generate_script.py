import os, re, json, time, socket, random, subprocess, urllib.parse, requests
import verify_freefire_agent as vfa

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


def safe_title(t):
    s = (t or "").lower()
    return not any(b in s for b in BANNED) and any(h in s for h in FF_HINTS)


def load_brief():
    d = {}
    if os.path.exists("viral_topic_brief.json"):
        try:
            d = json.load(open("viral_topic_brief.json", "r", encoding="utf-8"))
        except Exception:
            pass
    if not d:
        try:
            import viral_trend_agent
            d = viral_trend_agent.scout_today_viral_topic() or {}
        except Exception:
            pass
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
    try:
        vfa.crop_action_peak(cand, "raw_gameplay.mp4", 35)
    except Exception:
        os.replace(cand, "raw_gameplay.mp4")
    if os.path.exists(cand) and os.path.exists("raw_gameplay.mp4"):
        try: os.remove(cand)
        except Exception: pass
    return os.path.exists("raw_gameplay.mp4") and os.path.getsize("raw_gameplay.mp4") > 200000


def dl_ytdlp(url, out, proxy=None, is_yt=False):
    if os.path.exists(out): os.remove(out)
    cmd = ["yt-dlp", "--no-playlist", "--max-filesize", "85M", "--socket-timeout", "20", "--retries", "2",
           "-f", "bestvideo[height>=360][height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height>=360][ext=mp4]/best",
           "--merge-output-format", "mp4", "-o", out]
    if is_yt: cmd += ["--js-runtimes", "deno", "--extractor-args", "youtube:player_client=web_creator,tv"]
    if proxy: cmd += ["--proxy", proxy]
    p = subprocess.run(cmd + [url], capture_output=True, text=True, timeout=110)
    return p.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 300000


def dl_mp4(url, out):
    if os.path.exists(out): os.remove(out)
    try:
        with requests.get(url, headers={"User-Agent": UA}, stream=True, timeout=35) as r:
            if r.status_code != 200: return False
            with open(out, "wb") as f:
                for c in r.iter_content(131072):
                    if c: f.write(c)
        return os.path.exists(out) and os.path.getsize(out) > 300000
    except Exception:
        return False


def harvest(brief):
    qs = list(RAW_Q)
    if brief["weapon"] and len(brief["weapon"]) <= 18:
        qs.insert(0, f"free fire {brief['weapon'].lower()} headshot gameplay")
    random.shuffle(qs[1:])
    proxy = None
    try:
        with socket.create_connection(("127.0.0.1", 1080), timeout=1.5): proxy = "socks5://127.0.0.1:1080"
    except Exception: pass

    print("[*] [Tier 1 - Twitch Free Fire]")
    gql = "query($id:ID!,$f:ClipsPeriod!){game(id:$id){clips(first:15,criteria:{period:$f}){edges{node{slug title url durationSeconds}}}}}"
    for per in ["LAST_DAY", "LAST_WEEK", "LAST_MONTH", "ALL_TIME"]:
        try:
            r = requests.post("https://gql.twitch.tv/gql", json={"query": gql, "variables": {"id": "502732", "f": per}},
                              headers={"Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko", "User-Agent": UA}, timeout=15)
            edges = (r.json().get("data") or {}).get("game", {}).get("clips", {}).get("edges", [])
            print(f"    [Twitch {per}] {len(edges)} clips")
            random.shuffle(edges)
            for e in edges:
                n = e.get("node") or {}
                if 12 <= (n.get("durationSeconds") or 0) <= 180 and dl_ytdlp(n.get("url") or f"https://clips.twitch.tv/{n.get('slug')}", "c_tw.mp4"):
                    if finalize_clip("c_tw.mp4", f"Free Fire {n.get('title','')}"): return True
        except Exception as ex: print(f"    [Twitch err] {ex}")

    print("[*] [Tier 2 - TikTok TikWM]")
    for q in qs[:4]:
        try:
            vids = (requests.get("https://www.tikwm.com/api/feed/search", params={"keywords": q, "count": 10, "cursor": 0},
                                 headers={"User-Agent": UA}, timeout=15).json().get("data") or {}).get("videos") or []
            print(f"    [TikWM] {len(vids)} videos")
            for v in vids[:5]:
                t, u = v.get("title") or q, v.get("hdplay") or v.get("play")
                if 12 <= int(v.get("duration") or 0) <= 180 and safe_title(t + " " + q) and u and dl_mp4(u, "c_tt.mp4"):
                    if finalize_clip("c_tt.mp4", t): return True
        except Exception: pass

    print("[*] [Tier 3 - Dailymotion]")
    for q in qs[:3]:
        try:
            items = requests.get("https://api.dailymotion.com/videos", params={"channel": "videogames", "search": q, "sort": "visited", "limit": 8, "fields": "title,url,duration"},
                                 headers={"User-Agent": UA}, timeout=15).json().get("list") or []
            print(f"    [Dailymotion] {len(items)} items")
            for it in items[:4]:
                if 14 <= int(it.get("duration") or 0) <= 420 and safe_title(it.get("title")) and dl_ytdlp(it["url"], "c_dm.mp4"):
                    if finalize_clip("c_dm.mp4", it["title"]): return True
        except Exception: pass

    print(f"[*] [Tier 4 - YouTube/Piped] Proxy={'WARP' if proxy else 'Direct'}")
    for q in qs[:2]:
        try:
            cmd = ["yt-dlp", "--flat-playlist", "--dump-single-json", "--js-runtimes", "deno"] + (["--proxy", proxy] if proxy else []) + [f"ytsearch5:{q}"]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if p.returncode == 0 and p.stdout.strip():
                for e in (json.loads(p.stdout).get("entries") or [])[:4]:
                    if e.get("id") and 14 <= int(e.get("duration") or 0) <= 420 and safe_title(e.get("title")):
                        if dl_ytdlp(f"https://www.youtube.com/watch?v={e['id']}", "c_yt.mp4", proxy, True) and finalize_clip("c_yt.mp4", e["title"]): return True
        except Exception: pass

    print("[*] [Tier 5 - Archive.org & Rumble]")
    try:
        docs = (requests.get("https://archive.org/advancedsearch.php", params={"q": 'title:("free fire") AND mediatype:(movies)', "fl[]": "identifier,title", "output": "json", "rows": 8}, timeout=15).json().get("response") or {}).get("docs") or []
        for d in docs[:4]:
            t = str(d.get("title") or "Free Fire")
            if safe_title(t) and dl_ytdlp(f"https://archive.org/details/{d['identifier']}", "c_ar.mp4") and finalize_clip("c_ar.mp4", t): return True
    except Exception: pass
    raise RuntimeError("FATAL: No verified Free Fire raw gameplay found.")


def write_script(brief):
    try: requests.post(f"{OLLAMA_BASE}/api/generate", json={"model": "qwen2.5vl:3b", "prompt": "", "keep_alive": 0}, timeout=10)
    except Exception: pass
    model = "llama3.2:1b"
    try:
        names = [m.get("name", "") for m in (requests.get(f"{OLLAMA_BASE}/api/tags", timeout=10).json().get("models") or [])]
        model = next((n for n in names if "llama3.2" in n and "vl" not in n), next((n for n in names if "vl" not in n), model))
    except Exception: pass

    scene = ""
    if os.path.exists("verified_scene.json"):
        try: scene = f" Clip scene: {json.load(open('verified_scene.json')).get('scene', '')}."
        except Exception: pass

    prompt = (f"Write a viral 25s Free Fire Short script in Hinglish/Roman Urdu for DEVIL INSANITY. Topic: {brief['topic']}. Style: {brief['format']}.{scene} "
              f"Hook: {brief['hook']}. Return JSON ONLY with keys: title (max 80 chars #shorts), description (2 lines + #freefire #shorts), "
              f"tags (array of 6 strings), pinned_comment (1 question), segments (array of 5 dicts: text, pace [fast/normal/slow], sfx [hit/whoosh/none]).")

    for i in range(3):
        try:
            r = requests.post(f"{OLLAMA_BASE}/api/generate", json={"model": model, "prompt": prompt, "stream": False, "format": "json", "keep_alive": 0, "options": {"num_ctx": 1536, "num_predict": 420, "temperature": 0.7}}, timeout=180)
            if r.status_code != 200: print(f"[!] Ollama {r.status_code}"); time.sleep(3); continue
            raw = r.json().get("response", "").strip()
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            p = json.loads(m.group(0) if m else raw)
            segs = [{"text": str(s.get("text") if isinstance(s, dict) else s).strip(),
                     "pace": s.get("pace", "normal") if isinstance(s, dict) and s.get("pace") in ["fast", "normal", "slow"] else "normal",
                     "sfx": s.get("sfx", "whoosh") if isinstance(s, dict) and s.get("sfx") in ["hit", "whoosh", "none"] else "whoosh"}
                    for s in (p.get("segments") or p.get("lines") or []) if (s.get("text") if isinstance(s, dict) else str(s)).strip()]
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
            print(f"[!] Ollama retry {i+1}: {e}"); time.sleep(3)
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
