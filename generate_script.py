import os, re, json, time, socket, shutil, random, subprocess, requests, yt_dlp
from niche_brain import scout_live_viral_trend, save_history_entry, load_history

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
BANNED_WORDS = {"devil", "insanity", "999", "devil999", "investigation", "enigma", "mystery", "documentary", "story", "analysis", "exposed", "truth", "panel", "vs", "pure", "skill", "reflex", "hindi", "urdu", "shorts", "short", "viral", "video", "youtube", "channel"}
FALLBACK_SHORT_Q = ["free fire one tap headshot gameplay", "free fire awm sniper highlights", "free fire m1887 two shot clutch", "free fire desert eagle headshot", "free fire cs rank headshot montage", "garena free fire pro movement gameplay"]
FALLBACK_LONG_Q = ["free fire full gameplay 60fps", "free fire grandmaster rank push gameplay", "free fire solo vs squad full match", "free fire clash squad ranked gameplay", "garena free fire tournament highlights"]

CONCEPT_SCHEMA = {
    "type": "object",
    "properties": {"topic_angle": {"type": "string"}, "title": {"type": "string"}, "search_query": {"type": "string"}, "visual_focus": {"type": "string"}},
    "required": ["topic_angle", "title", "search_query", "visual_focus"]
}

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"}, "description": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}, "pinned_comment": {"type": "string"},
        "scenes": {"type": "array", "items": {"type": "object", "properties": {"time": {"type": "number"}, "narration": {"type": "string"}, "english_subtitle": {"type": "string"}, "focus_cue": {"type": "string"}}, "required": ["time", "narration", "english_subtitle", "focus_cue"]}}
    },
    "required": ["title", "description", "tags", "pinned_comment", "scenes"]
}

def warp_proxy():
    try:
        with socket.create_connection(("127.0.0.1", 1080), timeout=1):
            return "socks5://127.0.0.1:1080"
    except Exception:
        return None

def clean_query(raw_q, weapon):
    q = str(raw_q or "").split(",")[0]
    q = re.sub(r"[\[\]\(\)\{\}_\-|/:#@\"',.?!]+", " ", q.lower())
    words = [w for w in q.split() if len(w) > 1 and w not in BANNED_WORDS][:6]
    cleaned = " ".join(words).strip()
    if cleaned and "free fire" not in cleaned and "garena" not in cleaned:
        cleaned = f"free fire {cleaned}"
    return cleaned if len(cleaned.split()) >= 3 else f"free fire {weapon} headshot highlights"

def build_queries(raw_q, weapon, is_short=True):
    q1 = clean_query(raw_q, weapon)
    q2 = f"free fire {str(weapon or 'awm').lower()} headshot gameplay"
    pool = list(FALLBACK_SHORT_Q if is_short else FALLBACK_LONG_Q)
    random.shuffle(pool)
    out = []
    for item in [q1, q2] + pool:
        if item and item not in out:
            out.append(item)
    return out[:6]

def ensure_ollama():
    base = os.environ.get("OLLAMA_URL", "http://localhost:11434").split("/api/")[0].rstrip("/")
    def get_models():
        return [m["name"] for m in requests.get(f"{base}/api/tags", timeout=3).json().get("models", []) if m.get("name")]
    try:
        return base, get_models()
    except Exception:
        pass
    if not shutil.which("ollama"):
        subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(15):
        time.sleep(1.5)
        try:
            return base, get_models()
        except Exception:
            continue
    raise RuntimeError("FATAL: Ollama failed to start.")

def call_ollama_schema(prompt, schema, max_tokens=600):
    base, models = ensure_ollama()
    model = models[0] if models else "llama3.2:1b"
    if not models:
        subprocess.run(["ollama", "pull", model], check=True)
    payload = {"model": model, "messages": [{"role": "system", "content": "Free Fire YouTube strategist. Output valid JSON strictly matching schema."}, {"role": "user", "content": prompt}], "format": schema, "stream": False, "keep_alive": "10m", "options": {"temperature": 0.5, "num_ctx": 1536, "num_predict": max_tokens, "num_thread": os.cpu_count() or 2}}
    for att in range(1, 4):
        try:
            print(f"[*] Calling Ollama ({model}) [Attempt {att}/3]...")
            r = requests.post(f"{base}/api/chat", json=payload, timeout=110)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
            txt = r.json().get("message", {}).get("content", "").strip()
            data = json.loads(txt)
            if all(k in data and data[k] for k in schema["required"]):
                return data
        except Exception as e:
            print(f"[!] Ollama attempt {att} notice: {e}")
            time.sleep(2)
    raise RuntimeError("FATAL: AI structured output failed. Zero fallback policy enforced!")

def get_dur(path):
    if shutil.which("ffprobe"):
        try:
            return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path], text=True, timeout=15).strip())
        except Exception:
            return 0.0
    return 15.0

def valid_mp4(p, min_sec=10.0):
    if not os.path.exists(p) or os.path.getsize(p) < 350000:
        return False
    return get_dur(p) >= min_sec

def clean_tmp():
    if os.path.exists("raw_gameplay.mp4"):
        os.remove("raw_gameplay.mp4")

def fetch_stream(url, hdr=None):
    clean_tmp()
    h = {"User-Agent": UA}
    if hdr:
        h.update(hdr)
    try:
        with requests.get(url, headers=h, stream=True, timeout=40) as r:
            if r.status_code < 400:
                with open("raw_gameplay.mp4", "wb") as f:
                    for c in r.iter_content(524288):
                        if c:
                            f.write(c)
                return valid_mp4("raw_gameplay.mp4")
    except Exception:
        pass
    clean_tmp()
    return False

def dl_dailymotion(q, used, min_d, max_d):
    print(f"[*] [Tier 1 - Dailymotion HD] Searching: '{q}'...")
    for sort_mode in ("relevance", "visited"):
        for page in (1, 2):
            try:
                r = requests.get("https://api.dailymotion.com/videos", params={"search": q, "fields": "id,duration,url", "sort": sort_mode, "limit": 15, "page": page, "longer_than": int(min_d), "shorter_than": int(max_d)}, headers={"User-Agent": UA}, timeout=10)
                if r.status_code != 200:
                    continue
                for it in (r.json().get("list") or []):
                    did = f"dm_{it.get('id', '')}"
                    dur = int(it.get("duration") or 0)
                    if did in used or dur < min_d or dur > max_d or not it.get("url"):
                        continue
                    clean_tmp()
                    try:
                        with yt_dlp.YoutubeDL({"format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/best[height<=1080][ext=mp4]/best", "outtmpl": "raw_gameplay.mp4", "merge_output_format": "mp4", "overwrites": True, "quiet": True}) as ydl:
                            ydl.download([it["url"]])
                        if valid_mp4("raw_gameplay.mp4"):
                            return did
                    except Exception:
                        pass
                    clean_tmp()
            except Exception:
                continue
    return None

def dl_tiktok_tikwm(q, used, min_d, max_d):
    print(f"[*] [Tier 2 - TikTok No-Watermark HD] Searching: '{q}'...")
    time.sleep(2.2)
    hdr = {"User-Agent": UA, "Accept": "application/json, text/javascript, */*; q=0.01", "Referer": "https://www.tikwm.com/", "Origin": "https://www.tikwm.com"}
    payload = {"keywords": q, "count": 15, "cursor": 0, "hd": 1}
    videos = []
    for use_post in (True, False):
        try:
            r = requests.post("https://www.tikwm.com/api/feed/search", data=payload, headers=hdr, timeout=15) if use_post else requests.get("https://www.tikwm.com/api/feed/search", params=payload, headers=hdr, timeout=15)
            if r.status_code == 200 and r.json().get("code") == 0:
                d = r.json().get("data")
                videos = d.get("videos", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])
                if videos:
                    break
        except Exception:
            time.sleep(2.0)
    for v in videos:
        vid = str(v.get("video_id") or v.get("id") or "").strip()
        dur = int(v.get("duration") or 0)
        tid = f"tt_{vid}"
        if not vid or tid in used or (dur > 0 and (dur < min_d or dur > max_d)):
            continue
        dl_url = v.get("hdplay") or v.get("play") or ""
        if dl_url.startswith("/"):
            dl_url = "https://www.tikwm.com" + dl_url
        if dl_url and fetch_stream(dl_url, {"Referer": "https://www.tikwm.com/"}):
            return tid
    return None

def dl_twitch_clips(used, min_d, max_d):
    print("[*] [Tier 3 - Twitch Garena Free Fire Clips] Checking...")
    hdr = {"Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko", "Content-Type": "application/json", "User-Agent": UA}
    q_slug = "query($slug: ID!, $limit: Int, $criteria: GameClipsInput) { game(slug: $slug) { clips(first: $limit, criteria: $criteria) { edges { node { slug durationSeconds url } } } } }"
    q_name = "query($name: String!, $limit: Int, $criteria: GameClipsInput) { game(name: $name) { clips(first: $limit, criteria: $criteria) { edges { node { slug durationSeconds url } } } } }"
    for gq, gvar in [(q_slug, {"slug": "garena-free-fire", "limit": 20, "criteria": {"filter": "LAST_MONTH"}}), (q_slug, {"slug": "garena-free-fire", "limit": 20, "criteria": {"filter": "ALL_TIME"}}), (q_name, {"name": "Garena Free Fire", "limit": 20, "criteria": {"filter": "ALL_TIME"}})]:
        try:
            r = requests.post("https://gql.twitch.tv/gql", headers=hdr, json={"query": gq, "variables": gvar}, timeout=12)
            if r.status_code != 200:
                continue
            edges = ((((r.json() or {}).get("data") or {}).get("game") or {}).get("clips") or {}).get("edges") or []
            for e in edges:
                n = e.get("node") or {}
                slug = n.get("slug") or ""
                dur = int(n.get("durationSeconds") or 0)
                twid = f"tw_{slug}"
                if not slug or twid in used or (dur > 0 and (dur < min_d or dur > max_d)):
                    continue
                clean_tmp()
                try:
                    with yt_dlp.YoutubeDL({"format": "best[ext=mp4]/best", "outtmpl": "raw_gameplay.mp4", "overwrites": True, "quiet": True}) as ydl:
                        ydl.download([n.get("url") or f"https://clips.twitch.tv/{slug}"])
                    if valid_mp4("raw_gameplay.mp4"):
                        return twid
                except Exception:
                    pass
                clean_tmp()
        except Exception:
            continue
    return None

def dl_invid_piped(q, used, min_d, max_d):
    print(f"[*] [Tier 4 - Live Invidious/Piped] Checking: '{q}'...")
    inv_nodes = ["https://inv.nadeko.net", "https://yewtu.be"]
    try:
        ir = requests.get("https://api.invidious.io/instances.json?sort_by=health", timeout=6)
        if ir.status_code == 200:
            live = [f"https://{x[0]}" for x in ir.json() if isinstance(x, list) and len(x) >= 2 and isinstance(x[1], dict) and x[1].get("type") == "https" and x[1].get("api") is True]
            inv_nodes = live[:5] + inv_nodes
    except Exception:
        pass
    for node in inv_nodes[:5]:
        try:
            r = requests.get(f"{node}/api/v1/search", params={"q": q, "type": "video"}, timeout=6)
            if r.status_code != 200:
                continue
            for it in [i for i in r.json() if i.get("videoId") and i.get("videoId") not in used and min_d <= int(i.get("lengthSeconds") or 0) <= max_d][:3]:
                vr = requests.get(f"{node}/api/v1/videos/{it['videoId']}", timeout=6)
                if vr.status_code == 200:
                    for s in (vr.json().get("formatStreams") or []):
                        if s.get("container") == "mp4" and s.get("url") and fetch_stream(s["url"]):
                            return it["videoId"]
        except Exception:
            continue

    piped_nodes = ["https://pipedapi.kavin.rocks"]
    try:
        pr = requests.get("https://piped-instances.kavin.rocks/", headers={"Accept": "application/json"}, timeout=6)
        if pr.status_code == 200:
            raw = pr.json()
            lst = raw if isinstance(raw, list) else raw.get("instances", [])
            piped_nodes = [x.get("api_url").rstrip("/") for x in lst if isinstance(x, dict) and x.get("api_url")][:5] + piped_nodes
    except Exception:
        pass
    for node in piped_nodes[:5]:
        try:
            r = requests.get(f"{node}/search", params={"q": q, "filter": "videos"}, timeout=6)
            if r.status_code != 200:
                continue
            for it in (r.json().get("items") or [])[:4]:
                if "v=" not in it.get("url", ""):
                    continue
                vid = it["url"].split("v=")[-1].split("&")[0]
                dur = int(it.get("duration") or 0)
                if vid in used or (dur > 0 and (dur < min_d or dur > max_d)):
                    continue
                sr = requests.get(f"{node}/streams/{vid}", timeout=6)
                streams = sr.json().get("videoStreams", []) if sr.status_code == 200 else []
                mp4s = [s for s in streams if s.get("format") == "MPEG_4" and not s.get("videoOnly")] or [s for s in streams if s.get("format") == "MPEG_4"]
                if mp4s and mp4s[0].get("url") and fetch_stream(mp4s[0]["url"]):
                    return vid
        except Exception:
            continue
    return None

def dl_yt(q, used, min_d, max_d):
    px = warp_proxy()
    print(f"[*] [Tier 5 - YouTube Bonus] Searching (WARP={'ON' if px else 'OFF'}): '{q}'...")
    js_rt = "deno" if shutil.which("deno") else ("node" if shutil.which("node") else None)
    s_opts = {"quiet": True, "extract_flat": True, "noplaylist": True}
    if px:
        s_opts["proxy"] = px
    try:
        with yt_dlp.YoutubeDL(s_opts) as ydl:
            entries = (ydl.extract_info(f"ytsearch5:{q}", download=False) or {}).get("entries") or []
            cands = [e.get("id") for e in entries if e.get("id") and e.get("id") not in used and (int(e.get("duration") or 0) == 0 or min_d <= int(e.get("duration") or 0) <= max_d)]
    except Exception:
        cands = []
    for vid in cands[:3]:
        opts = {"format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best", "outtmpl": "raw_gameplay.mp4", "overwrites": True, "quiet": True, "sleep_requests": 1, "extractor_args": {"youtube": {"player_client": ["tv", "android_vr", "mweb"]}}}
        if px:
            opts["proxy"] = px
        if js_rt:
            opts["js_runtimes"] = {js_rt: {}}
        if os.path.exists("cookies.txt"):
            opts["cookiefile"] = "cookies.txt"
        clean_tmp()
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={vid}"])
            if valid_mp4("raw_gameplay.mp4"):
                return vid
        except Exception as e:
            print(f"[!] YouTube bonus notice ({vid}): {str(e)[:80]}")
        clean_tmp()
    return None

def generate_script():
    plan = {}
    for fn in ["daily_plan.json", "task_plan.json"]:
        if os.path.exists(fn):
            plan = json.load(open(fn, "r", encoding="utf-8"))
            break
    fmt = plan.get("format_type", plan.get("type", "short"))
    is_short = str(fmt).lower() != "long"
    bp = scout_live_viral_trend(format_type=fmt)
    bp["target_duration"] = float(plan.get("target_duration", random.uniform(28.0, 33.5) if is_short else 900.0))
    used = set(load_history().get("video_ids", []))

    concept = call_ollama_schema(
        f"DEVIL INSANITY (DEVIL-999). Invent ONE new Free Fire concept. IMPORTANT: search_query MUST be a single plain 4-6 word phrase (NO brackets, NO lists, NO commas, NO hyphens).\n{bp['prompt_context']}",
        CONCEPT_SCHEMA, max_tokens=220
    )
    queries = build_queries(concept["search_query"], bp["weapon"], is_short=is_short)
    q = queries[0]
    print(f"[+] AI Topic: {concept['title']} | Primary Query: '{q}'")

    min_d, max_d = (15, 300) if is_short else (120, 1800)
    clean_tmp()
    vid = None
    for cand_q in queries:
        vid = dl_dailymotion(cand_q, used, min_d, max_d)
        if vid:
            q = cand_q
            break
        if is_short:
            vid = dl_tiktok_tikwm(cand_q, used, 15, 240)
            if vid:
                q = cand_q
                break

    if not vid:
        vid = dl_twitch_clips(used, 15, max_d)
    if not vid:
        for cand_q in queries[:3]:
            vid = dl_invid_piped(cand_q, used, min_d, max_d) or dl_yt(cand_q, used, min_d, max_d)
            if vid:
                q = cand_q
                break

    if not vid or not valid_mp4("raw_gameplay.mp4"):
        raise RuntimeError(f"FATAL: All real gameplay platforms failed for {queries}. Zero fallback policy enforced!")

    dur = get_dur("raw_gameplay.mp4")
    print(f"[+] REAL GAMEPLAY LOCKED: {vid} ({os.path.getsize('raw_gameplay.mp4')/1048576:.2f} MB, {dur:.1f}s)")
    t_dur = round(bp["target_duration"], 1)
    times = [round(i * (t_dur / 7.0), 1) for i in range(7)]

    ai_s = call_ollama_schema(
        f"Write 7-scene Roman Urdu narration + English subtitles for '{concept['title']}' | Pillar: {bp['pillar_name']} | Weapon: {bp['weapon']} (Dmg: {bp['damage']}) | Hook: {bp['psychology_strategy']} | Clip: {dur:.1f}s -> Target: {t_dur}s | Exact 7 timestamps: {times}. Keep narration punchy mobile-gamer Roman Urdu without emojis.",
        SCRIPT_SCHEMA, max_tokens=700
    )
    scenes = [{"time": float(s.get("time", times[min(i, 6)])), "narration": str(s.get("narration", "")).strip(), "text": str(s.get("narration", "")).strip(), "english_subtitle": str(s.get("english_subtitle", "")).strip(), "focus_cue": str(s.get("focus_cue") or "crosshair_lock")} for i, s in enumerate(ai_s["scenes"])]

    out = {"title": ai_s.get("title") or concept["title"], "topic": concept["topic_angle"], "description": ai_s.get("description", ""), "tags": ai_s.get("tags", ["freefire", "shorts", "gaming"]), "pinned_comment": ai_s.get("pinned_comment", ""), "pillar": bp["pillar"], "pillar_id": bp["pillar_id"], "pillar_name": bp["pillar_name"], "psychology_strategy": bp["psychology_strategy"], "search_query": q, "source_video_id": vid, "weapon": bp["weapon"], "damage": bp["damage"], "format_type": fmt, "target_duration": bp["target_duration"], "player_tag": "DEVIL-999", "script": " ".join(s["narration"] for s in scenes), "english_script": " ".join(s["english_subtitle"] for s in scenes), "scenes": scenes}
    json.dump(out, open("current_script.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    if os.path.isdir("kaggle_render"):
        shutil.copy2("current_script.json", "kaggle_render/current_script.json")
    save_history_entry(query=q, video_id=vid, title=out["title"], pillar_id=bp["pillar_id"])
    print("[+] Done! Structured AI Script & Real Video saved.")

if __name__ == "__main__":
    generate_script()
