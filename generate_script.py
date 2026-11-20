import os, re, sys, json, time, socket, random, subprocess, urllib.parse, requests
import verify_freefire_agent as vfa

try: sys.stdout.reconfigure(line_buffering=True)
except Exception: pass

OLLAMA_BASE = "http://127.0.0.1:11434"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"
RAW_Q = [
    "free fire raw headshot gameplay no commentary",
    "free fire 1v4 clutch unedited gameplay",
    "free fire desert eagle one tap montage",
    "free fire m1887 solo vs squad clutch",
    "free fire cs rank raw gameplay no voice",
]
BANNED = ["pubg", "bgmi", "cod", "fortnite", "valorant", "minecraft", "gta", "roblox", "giveaway", "mod apk", "facecam", "reaction", "lobby", "spin"]
FF_HINTS = ["free fire", "freefire", "ff", "booyah", "headshot", "onetap", "one tap", "m1887", "desert eagle", "cs rank", "garena", "ruok", "raistar", "esta arma", "kills"]
SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "hook_badge": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "pinned_comment": {"type": "string"},
        "segments": {"type": "array", "items": {"type": "object", "properties": {"en": {"type": "string"}, "pace": {"type": "string"}, "sfx": {"type": "string"}}, "required": ["en", "pace", "sfx"]}},
    },
    "required": ["title", "description", "hook_badge", "tags", "pinned_comment", "segments"],
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
        "topic": str(d.get("topic") or d.get("winner_topic") or "IMPOSSIBLE FREE FIRE ONE TAP BREAKDOWN").strip(),
        "format": str(d.get("format") or d.get("viral_format") or "0.25x Forensic Breakdown").strip(),
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
    print(f"[+] VERIFIED RAW CLIP: {title[:60]}")
    try: vfa.crop_action_peak(cand, "raw_gameplay.mp4", pre_sec=8.5, post_sec=2.5)
    except Exception: os.replace(cand, "raw_gameplay.mp4")
    if os.path.exists(cand) and os.path.exists("raw_gameplay.mp4"):
        try: os.remove(cand)
        except Exception: pass
    return os.path.exists("raw_gameplay.mp4") and os.path.getsize("raw_gameplay.mp4") > 150000


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
    except Exception: return False


def dl_mp4(url, out):
    if os.path.exists(out): os.remove(out)
    t0 = time.time()
    try:
        with requests.get(url, headers={"User-Agent": UA}, stream=True, timeout=20) as r:
            if r.status_code != 200: return False
            total = 0
            with open(out, "wb") as f:
                for c in r.iter_content(131072):
                    if c: f.write(c); total += len(c)
                    if total > 75 * 1024 * 1024 or (time.time() - t0) > 40: break
        return os.path.exists(out) and os.path.getsize(out) > 300000
    except Exception: return False


def harvest(brief):
    t_start = time.time()
    qs = list(RAW_Q)
    if brief["weapon"] and len(brief["weapon"]) <= 18:
        qs.insert(0, f"free fire {brief['weapon'].lower()} raw headshot gameplay")
    random.shuffle(qs[1:])
    proxy = None
    try:
        with socket.create_connection(("127.0.0.1", 1080), timeout=1.5): proxy = "socks5://127.0.0.1:1080"
    except Exception: pass

    print("[*] [Tier 1 - Twitch Free Fire]")
    gql = "query($id:ID!,$f:ClipsPeriod!){game(id:$id){clips(first:15,criteria:{period:$f}){edges{node{slug title url durationSeconds}}}}}"
    for per in ["LAST_DAY", "LAST_WEEK", "ALL_TIME"]:
        if time.time() - t_start > 240: break
        try:
            r = requests.post("https://gql.twitch.tv/gql", json={"query": gql, "variables": {"id": "502732", "f": per}},
                              headers={"Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko", "User-Agent": UA}, timeout=12)
            game_node = ((r.json().get("data") or {}).get("game")) or {}
            edges = ((game_node.get("clips")) or {}).get("edges") or []
            print(f"    [Twitch {per}] {len(edges)} clips")
            random.shuffle(edges)
            tried = 0
            for e in edges:
                if tried >= 3 or time.time() - t_start > 240: break
                n = e.get("node") or {}
                if 16 <= (n.get("durationSeconds") or 0) <= 180 and safe_title("free fire " + (n.get("title") or "")):
                    tried += 1
                    if dl_ytdlp(n.get("url") or f"https://clips.twitch.tv/{n.get('slug')}", "c_tw.mp4"):
                        if finalize_clip("c_tw.mp4", f"Free Fire {n.get('title','')}"): return True
        except Exception as ex: print(f"    [Twitch err] {ex}")

    print("[*] [Tier 2 - TikTok TikWM]")
    for q in qs[:3]:
        if time.time() - t_start > 240: break
        try:
            vids = (requests.get("https://www.tikwm.com/api/feed/search", params={"keywords": q, "count": 10, "cursor": 0},
                                 headers={"User-Agent": UA}, timeout=12).json().get("data") or {}).get("videos") or []
            tried = 0
            for v in vids:
                if tried >= 2: break
                t, u = v.get("title") or q, v.get("hdplay") or v.get("play")
                if 16 <= int(v.get("duration") or 0) <= 180 and safe_title(t + " " + q) and u:
                    tried += 1
                    if dl_mp4(u, "c_tt.mp4") and finalize_clip("c_tt.mp4", t): return True
        except Exception: pass

    print("[*] [Tier 3 - Dailymotion]")
    for q in qs[:2]:
        if time.time() - t_start > 240: break
        try:
            items = requests.get("https://api.dailymotion.com/videos", params={"channel": "videogames", "search": q, "sort": "visited", "limit": 8, "fields": "title,url,duration"},
                                 headers={"User-Agent": UA}, timeout=12).json().get("list") or []
            tried = 0
            for it in items:
                if tried >= 2: break
                if 16 <= int(it.get("duration") or 0) <= 420 and safe_title(it.get("title")):
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
                    if e.get("id") and 16 <= int(e.get("duration") or 0) <= 420 and safe_title(e.get("title")):
                        if dl_ytdlp(f"https://www.youtube.com/watch?v={e['id']}", "c_yt.mp4", proxy, True) and finalize_clip("c_yt.mp4", e["title"]): return True
        except Exception: pass

    print("[*] [Tier 5 - Archive.org]")
    try:
        docs = (requests.get("https://archive.org/advancedsearch.php", params={"q": 'title:("free fire") AND mediatype:(movies)', "fl[]": "identifier,title", "output": "json", "rows": 6}, timeout=12).json().get("response") or {}).get("docs") or []
        for d in docs[:2]:
            t = str(d.get("title") or "Free Fire")
            if safe_title(t) and dl_ytdlp(f"https://archive.org/details/{d['identifier']}", "c_ar.mp4") and finalize_clip("c_ar.mp4", t): return True
    except Exception: pass
    raise RuntimeError("FATAL: No verified raw Free Fire gameplay found.")


def to_hindi(text):
    try:
        u = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=hi&dt=t&q=" + urllib.parse.quote(text)
        res = requests.get(u, headers={"User-Agent": UA}, timeout=10).json()
        hi = "".join(part[0] for part in (res[0] or []) if part and part[0]).strip()
        return hi if hi else text
    except Exception: return text


def normalize_beats(raw_segs, max_words=60):
    words_all = []
    out = []
    for s in (raw_segs or []):
        en = str((s.get("en") or s.get("text")) if isinstance(s, dict) else s).strip()
        if not en: continue
        w = en.split()
        words_all.extend(w)
        out.append({"en": en, "pace": "normal", "sfx": "whoosh"})
    if len(out) < 4 and len(words_all) >= 20:
        words_all = words_all[:max_words]
        chunk = max(4, (len(words_all) + 4) // 5)
        out = [{"en": " ".join(words_all[i:i+chunk]), "pace": "normal", "sfx": "whoosh"} for i in range(0, len(words_all), chunk)][:5]
    capped, total = [], 0
    for s in out:
        n = len(s["en"].split())
        if total + n <= max_words or not capped:
            capped.append(s); total += n
        else: break
    return capped


def write_script(brief, tl):
    model = "llama3.2:1b"
    try:
        names = [m.get("name", "") for m in (requests.get(f"{OLLAMA_BASE}/api/tags", timeout=8).json().get("models") or [])]
        model = next((n for n in names if "llama3.2" in n and "vl" not in n), next((n for n in names if "vl" not in n), model))
    except Exception: pass

    scenes = f"5s Before Shot: {tl.get('before_setup','')}. Tension: {tl.get('tension_aim','')}. Climax Hit: {tl.get('headshot_hit','')}. Aftermath: {tl.get('aftermath','')}. Weapon: {tl.get('weapon','unknown')}."
    prompt = (
        f"Write a TIGHT 19-second Climax-First Free Fire YouTube Short JSON in PUNCHY ENGLISH matching this clip: {scenes} "
        f"Rules: segments MUST be an array of EXACTLY 5 separate objects (8-11 words per 'en' field, ~48 words total). "
        f"Beat 1 (0.0s hook, NEVER Hello/Guys/Today): e.g. 'Stop scrolling! How did he land this bridge shot?!' "
        f"Beat 2: Rewind 5s before on the bridge. Beat 3: Enemy target mistake. Beat 4: 0.25x slow-mo headshot impact. Beat 5: Debate loop back to Beat 1. "
        f"Return JSON with title (max 72 chars + #shorts), description (2 English lines + #freefire #shorts), hook_badge (3 uppercase words), tags (6 strings), pinned_comment (1 question), segments (5 dicts: en, pace, sfx)."
    )

    best_p, best_segs, best_wc = None, [], 0
    for i in range(4):
        try:
            print(f"[*] Calling {model} (attempt {i+1})...")
            r = requests.post(f"{OLLAMA_BASE}/api/generate",
                              json={"model": model, "prompt": prompt, "stream": False, "format": SCRIPT_SCHEMA, "keep_alive": 0,
                                    "options": {"num_ctx": 1536, "num_predict": 720, "temperature": 0.4}}, timeout=95)
            if r.status_code != 200: print(f"[!] Ollama {r.status_code}"); time.sleep(2); continue
            p = json.loads(r.json().get("response", "").strip())
            segs = normalize_beats(p.get("segments"), max_words=60)
            wc = sum(len(x["en"].split()) for x in segs)
            print(f"    [Draft {i+1}] {len(segs)} beats | {wc} EN words")
            if wc > best_wc and wc >= 28: best_p, best_segs, best_wc = p, segs, wc
            elif not best_p: best_p, best_segs, best_wc = p, segs, wc
            if 36 <= wc <= 60 and len(segs) >= 4: break
        except Exception as e: print(f"[!] Ollama retry {i+1}: {e}"); time.sleep(2)

    if not best_p or best_wc < 28: raise RuntimeError(f"FATAL: Ollama script too short ({best_wc} words).")
    for idx, s in enumerate(best_segs):
        s["text"] = to_hindi(s["en"])
        s["sfx"] = "hit" if idx in [0, 3] else "whoosh"
        s["pace"] = "fast" if idx in [0, 4] else ("slow" if idx == 3 else "normal")

    title = str(best_p.get("title") or "How Did This Bridge Headshot Even Hit? #shorts").replace("<", "").replace(">", "").strip()[:95]
    if "#shorts" not in title.lower(): title = (title[:85] + " #shorts").strip()
    desc = str(best_p.get("description") or "Wait for the 0.25x forensic headshot breakdown!\n#freefire #freefiremax #shorts #gaming").replace("<", "").replace(">", "")
    badge = re.sub(r"[^A-Za-z0-9 .!?/-]", "", str(best_p.get("hook_badge") or "0.25X CLIMAX ANALYSIS")).upper().strip()[:28]
    return {
        "title": title, "description": desc, "hook_badge": badge or "0.25X CLIMAX ANALYSIS",
        "tags": [str(t) for t in (best_p.get("tags") or ["free fire", "free fire shorts", "one tap headshot", "gaming"])[:10]],
        "pinned_comment": str(best_p.get("pinned_comment") or "Pure skill or insane aim luck? Drop your level below!"),
        "topic": brief["topic"], "format": brief["format"], "voice_lang": "hi",
        "theme": random.choice(["CRIMSON", "CYBER", "GOLDEN", "ICE"]),
        "timeline": tl, "segments": best_segs,
        "narration": " ".join(x["text"] for x in best_segs),
        "script": " ".join(x["en"] for x in best_segs),
    }


def generate_script():
    brief = load_brief()
    print(f"[+] Trend Topic: {brief['topic']} | Format: {brief['format']}")
    harvest(brief)
    tl = vfa.inspect_timeline_phases("raw_gameplay.mp4")
    data = write_script(brief, tl)
    json.dump(data, open("current_script.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"[+] Surgical Script Ready! Title: {data['title']} | Kill Offset: {tl.get('kill_at')}s")


if __name__ == "__main__":
    generate_script()
