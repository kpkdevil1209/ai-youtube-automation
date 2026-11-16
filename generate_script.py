# generate_script.py - Multi-Platform Verified Gameplay + Winner-Aware AI Script Engine
import os, re, json, time, base64, pickle, socket, shutil, random, subprocess, requests, yt_dlp
from niche_brain import scout_live_viral_trend, save_history_entry, load_history
from verify_freefire_agent import verify_freefire_video, is_metadata_clean

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
BANNED = {"devil", "insanity", "999", "devil999", "investigation", "enigma", "mystery", "documentary", "story", "analysis", "exposed", "truth", "panel", "vs", "pure", "skill", "reflex", "hindi", "urdu", "shorts", "short", "viral", "video", "youtube", "channel"}
SHORT_Q = ["free fire one tap headshot gameplay", "free fire awm sniper highlights", "free fire m1887 two shot clutch", "free fire desert eagle headshot", "free fire cs rank headshot montage", "garena free fire pro movement gameplay"]
LONG_Q = ["free fire full gameplay 60fps", "free fire grandmaster rank push gameplay", "free fire solo vs squad full match", "free fire clash squad ranked gameplay", "garena free fire tournament highlights"]

SCENE_ITEM = {"type": "object", "properties": {"time": {"type": "number"}, "narration": {"type": "string"}, "english_subtitle": {"type": "string"}, "focus_cue": {"type": "string"}}, "required": ["time", "narration", "english_subtitle", "focus_cue"]}
CONCEPT_SCHEMA = {"type": "object", "properties": {"topic_angle": {"type": "string"}, "title": {"type": "string"}, "search_query": {"type": "string"}, "visual_focus": {"type": "string"}}, "required": ["topic_angle", "title", "search_query", "visual_focus"]}
META_SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}, "pinned_comment": {"type": "string"}}, "required": ["title", "description", "tags", "pinned_comment"]}
SCENES_SCHEMA = {"type": "object", "properties": {"scenes": {"type": "array", "items": SCENE_ITEM}}, "required": ["scenes"]}
SCRIPT_SCHEMA = {"type": "object", "properties": {**META_SCHEMA["properties"], "scenes": {"type": "array", "items": SCENE_ITEM}}, "required": ["title", "description", "tags", "pinned_comment", "scenes"]}

def warp_proxy():
    try:
        with socket.create_connection(("127.0.0.1", 1080), timeout=1):
            return "socks5://127.0.0.1:1080"
    except Exception:
        return None

def clean_query(raw_q, weapon):
    q = re.sub(r"[\[\]\(\)\{\}_\-|/:#@\"',.?!]+", " ", str(raw_q or "").split(",")[0].lower())
    words = [w for w in q.split() if len(w) > 1 and w not in BANNED][:6]
    c = " ".join(words).strip()
    if c and "free fire" not in c and "garena" not in c:
        c = f"free fire {c}"
    return c if len(c.split()) >= 3 else f"free fire {weapon} headshot highlights"

def build_queries(raw_q, weapon, is_short=True):
    pool = list(SHORT_Q if is_short else LONG_Q)
    random.shuffle(pool)
    out = []
    for item in [clean_query(raw_q, weapon), f"free fire {str(weapon or 'awm').lower()} headshot gameplay"] + pool:
        if item and item not in out:
            out.append(item)
    return out[:6]

def ensure_ollama():
    base = os.environ.get("OLLAMA_URL", "http://localhost:11434").split("/api/")[0].rstrip("/")
    gm = lambda: [m["name"] for m in requests.get(f"{base}/api/tags", timeout=3).json().get("models", []) if m.get("name")]
    try:
        return base, gm()
    except Exception:
        pass
    if not shutil.which("ollama"):
        subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(15):
        time.sleep(1.5)
        try:
            return base, gm()
        except Exception:
            pass
    raise RuntimeError("FATAL: Ollama failed to start.")

def call_ollama_schema(prompt, schema, max_tokens=2048, raise_on_fail=True):
    base, models = ensure_ollama()
    model = next((m for m in models if "llama3.2:1b" in m), next((m for m in models if "vl" not in m and "moondream" not in m), "llama3.2:1b"))
    if not any(model == m for m in models):
        subprocess.run(["ollama", "pull", model], check=True)
    payload = {"model": model, "messages": [{"role": "system", "content": "Output valid compact JSON matching schema. Concise strings, no raw newlines."}, {"role": "user", "content": prompt}], "format": schema, "stream": False, "keep_alive": "10m", "options": {"temperature": 0.4, "repeat_penalty": 1.1, "num_ctx": 4096, "num_predict": max_tokens, "num_thread": os.cpu_count() or 2}}
    for att in range(1, 3):
        try:
            print(f"[*] Calling Ollama ({model}) [Attempt {att}/2]...")
            r = requests.post(f"{base}/api/chat", json=payload, timeout=140)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", r.json().get("message", {}).get("content", "").strip()).strip()
            data = json.loads(txt)
            if all(k in data and data[k] for k in schema["required"]):
                return data
        except Exception as e:
            print(f"[!] Ollama attempt {att}: {e}")
            time.sleep(1.5)
    if raise_on_fail:
        raise RuntimeError("FATAL: AI structured output failed.")
    return None

def top_channel_winner():
    tp = os.environ.get("YOUTUBE_TOKEN_PICKLE")
    if not tp:
        return ""
    try:
        from googleapiclient.discovery import build
        yt = build("youtube", "v3", credentials=pickle.loads(base64.b64decode(tp.strip())))
        up = yt.channels().list(mine=True, part="contentDetails").execute()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        ids = [i["snippet"]["resourceId"]["videoId"] for i in yt.playlistItems().list(playlistId=up, part="snippet", maxResults=8).execute().get("items", [])]
        vids = yt.videos().list(id=",".join(ids), part="snippet,statistics").execute().get("items", []) if ids else []
        best = max(vids, key=lambda v: int(v.get("statistics", {}).get("viewCount", 0)), default=None)
        if best:
            t, vc = best["snippet"]["title"], int(best.get("statistics", {}).get("viewCount", 0))
            if any(w in t.lower() for w in ("free fire", "desert eagle", "m1887", "awm", "headshot", "1v4", "devil")):
                return f" | Winning Channel Reference: '{t}' ({vc} views)"
    except Exception:
        pass
    return ""

def get_dur(p):
    try:
        return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", p], text=True, timeout=15).strip())
    except Exception:
        return 0.0

def valid_mp4(p, min_s=12.0):
    return os.path.exists(p) and os.path.getsize(p) >= 350000 and get_dur(p) >= min_s

def clean_tmp():
    if os.path.exists("raw_gameplay.mp4"):
        os.remove("raw_gameplay.mp4")

def accept_clip(cid, title, used, t_dur, trusted=False):
    ok, reason = verify_freefire_video("raw_gameplay.mp4", source_title=title, trusted_category=trusted, remove_on_fail=True, target_dur=t_dur)
    if ok:
        return cid
    print(f"[Agent Rejected] {cid}: {reason}")
    used.add(cid)
    return None

def fetch_stream(url, hdr=None):
    clean_tmp()
    try:
        with requests.get(url, headers={"User-Agent": UA, **(hdr or {})}, stream=True, timeout=35) as r:
            if r.status_code < 400:
                with open("raw_gameplay.mp4", "wb") as f:
                    for c in r.iter_content(524288):
                        if c:
                            f.write(c)
                if valid_mp4("raw_gameplay.mp4"):
                    return True
    except Exception:
        pass
    clean_tmp()
    return False

def ytdl_get(url, extra=None):
    clean_tmp()
    opts = {"format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/best[height<=1080][ext=mp4]/best", "outtmpl": "raw_gameplay.mp4", "merge_output_format": "mp4", "overwrites": True, "quiet": True, **(extra or {})}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        if valid_mp4("raw_gameplay.mp4"):
            return True
    except Exception:
        pass
    clean_tmp()
    return False

def dl_tg_vault(used, t_dur):
    sess, aid, ah, ch = os.environ.get("TELEGRAM_SESSION"), os.environ.get("TELEGRAM_API_ID"), os.environ.get("TELEGRAM_API_HASH"), os.environ.get("TELEGRAM_VAULT_CHANNEL")
    if not (sess and aid and ah and ch):
        return None
    try:
        import asyncio
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        async def pull():
            async with TelegramClient(StringSession(sess), int(aid), ah) as cl:
                async for m in cl.iter_messages(ch, limit=15):
                    cid = f"tg_{m.id}"
                    if cid not in used and m.video and (m.file.size or 0) < 90_000_000:
                        clean_tmp()
                        await cl.download_media(m, file="raw_gameplay.mp4")
                        if valid_mp4("raw_gameplay.mp4") and accept_clip(cid, m.text or "free fire vault", used, t_dur, trusted=True):
                            return cid
        return asyncio.run(pull())
    except Exception:
        clean_tmp()
        return None

def dl_twitch(used, min_d, max_d, t_dur):
    print("[*] [Tier 1 - Twitch Garena Free Fire Clips] Checking...")
    hdr = {"Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko", "Content-Type": "application/json", "User-Agent": UA}
    qs = "query($s: ID!, $l: Int, $c: GameClipsInput){game(slug:$s){clips(first:$l,criteria:$c){edges{node{slug title durationSeconds url}}}}}"
    for flt in ("LAST_DAY", "LAST_WEEK", "LAST_MONTH", "ALL_TIME"):
        try:
            r = requests.post("https://gql.twitch.tv/gql", headers=hdr, json={"query": qs, "variables": {"s": "garena-free-fire", "l": 25, "c": {"filter": flt}}}, timeout=12)
            edges = ((((r.json() or {}).get("data") or {}).get("game") or {}).get("clips") or {}).get("edges") or [] if r.status_code == 200 else []
            for e in edges:
                n = e.get("node") or {}
                sl, ttl, dur = n.get("slug") or "", n.get("title") or "", int(n.get("durationSeconds") or 0)
                cid = f"tw_{sl}"
                if sl and cid not in used and (dur == 0 or min_d <= dur <= max_d) and is_metadata_clean(ttl, trusted=True)[0]:
                    if ytdl_get(n.get("url") or f"https://clips.twitch.tv/{sl}") and accept_clip(cid, ttl, used, t_dur, trusted=True):
                        return cid
        except Exception:
            pass
    return None

def dl_tt(q, used, min_d, max_d, t_dur):
    print(f"[*] [Tier 2 - TikTok HD] Searching: '{q}'...")
    time.sleep(2.2)
    hdr, pay = {"User-Agent": UA, "Referer": "https://www.tikwm.com/", "Origin": "https://www.tikwm.com"}, {"keywords": q, "count": 15, "cursor": 0, "hd": 1}
    for post in (True, False):
        try:
            r = requests.post("https://www.tikwm.com/api/feed/search", data=pay, headers=hdr, timeout=15) if post else requests.get("https://www.tikwm.com/api/feed/search", params=pay, headers=hdr, timeout=15)
            d = r.json().get("data") if r.status_code == 200 and r.json().get("code") == 0 else None
            for v in (d.get("videos", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])):
                vid, ttl, dur = str(v.get("video_id") or v.get("id") or "").strip(), str(v.get("title") or ""), int(v.get("duration") or 0)
                u = v.get("hdplay") or v.get("play") or ""
                u = f"https://www.tikwm.com{u}" if u.startswith("/") else u
                cid = f"tt_{vid}"
                if vid and cid not in used and (dur == 0 or min_d <= dur <= max_d) and is_metadata_clean(ttl)[0] and u:
                    if fetch_stream(u, {"Referer": "https://www.tikwm.com/"}) and accept_clip(cid, ttl, used, t_dur):
                        return cid
        except Exception:
            time.sleep(2.0)
    return None

def dl_dm(q, used, min_d, max_d, t_dur):
    print(f"[*] [Tier 3 - Dailymotion HD] Searching: '{q}'...")
    for s in ("relevance", "visited"):
        try:
            r = requests.get("https://api.dailymotion.com/videos", params={"search": q, "fields": "id,title,duration,url", "sort": s, "limit": 15, "longer_than": int(min_d), "shorter_than": int(max_d)}, headers={"User-Agent": UA}, timeout=10)
            for it in (r.json().get("list") or []) if r.status_code == 200 else []:
                did, ttl, dur = f"dm_{it.get('id', '')}", it.get("title") or "", int(it.get("duration") or 0)
                if did not in used and min_d <= dur <= max_d and is_metadata_clean(ttl)[0] and it.get("url"):
                    if ytdl_get(it["url"]) and accept_clip(did, ttl, used, t_dur):
                        return did
        except Exception:
            pass
    return None

def dl_inv_yt(q, used, min_d, max_d, t_dur):
    print(f"[*] [Tier 4 - Invidious/YT Bonus] Checking: '{q}'...")
    inv = ["https://inv.nadeko.net", "https://yewtu.be"]
    try:
        for node in inv:
            r = requests.get(f"{node}/api/v1/search", params={"q": q, "type": "video"}, timeout=6)
            for it in (r.json() if r.status_code == 200 else [])[:4]:
                vid, ttl = it.get("videoId"), it.get("title") or ""
                if vid and vid not in used and min_d <= int(it.get("lengthSeconds") or 0) <= max_d and is_metadata_clean(ttl)[0]:
                    vr = requests.get(f"{node}/api/v1/videos/{vid}", timeout=6)
                    for s in (vr.json().get("formatStreams") or []) if vr.status_code == 200 else []:
                        if s.get("container") == "mp4" and s.get("url") and fetch_stream(s["url"]) and accept_clip(vid, ttl, used, t_dur):
                            return vid
    except Exception:
        pass
    px = warp_proxy()
    ex = {"extractor_args": {"youtube": {"player_client": ["tv", "android_vr", "mweb"]}}, "sleep_requests": 1, **({"proxy": px} if px else {}), **({"cookiefile": "cookies.txt"} if os.path.exists("cookies.txt") else {})}
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True, **({"proxy": px} if px else {})}) as ydl:
            cands = [(e["id"], e.get("title") or "") for e in ((ydl.extract_info(f"ytsearch5:{q}", download=False) or {}).get("entries") or []) if e.get("id") and e["id"] not in used and is_metadata_clean(e.get("title") or "")[0]]
        for vid, ttl in cands[:3]:
            if ytdl_get(f"https://www.youtube.com/watch?v={vid}", ex) and accept_clip(vid, ttl, used, t_dur):
                return vid
    except Exception:
        pass
    return None

def generate_script():
    plan = next((json.load(open(f, encoding="utf-8")) for f in ("daily_plan.json", "task_plan.json") if os.path.exists(f)), {})
    fmt = plan.get("format_type", plan.get("type", "short"))
    is_short = str(fmt).lower() != "long"
    bp = scout_live_viral_trend(format_type=fmt)
    bp["target_duration"] = float(plan.get("target_duration", random.uniform(28.0, 33.5) if is_short else 900.0))
    t_dur = round(bp["target_duration"], 1)
    used = set(load_history().get("video_ids", []))
    win_hint = top_channel_winner()

    concept = call_ollama_schema(f"DEVIL INSANITY (DEVIL-999). Invent ONE viral Free Fire concept.{win_hint}\nsearch_query MUST be a plain 4-6 word phrase (NO brackets/commas/hyphens).\n{bp['prompt_context']}", CONCEPT_SCHEMA, max_tokens=350)
    queries = build_queries(concept["search_query"], bp["weapon"], is_short=is_short)
    q, min_d, max_d = queries[0], *((15, 300) if is_short else (120, 1800))
    print(f"[+] AI Topic: {concept['title']} | Primary Query: '{q}'")

    vid = dl_tg_vault(used, t_dur if is_short else None) or dl_twitch(used, 15, max_d, t_dur if is_short else None)
    if not vid:
        for cq in queries:
            vid = (dl_tt(cq, used, 15, 240, t_dur if is_short else None) if is_short else None) or dl_dm(cq, used, min_d, max_d, t_dur if is_short else None)
            if vid:
                q = cq; break
    if not vid:
        for cq in queries[:3]:
            vid = dl_inv_yt(cq, used, min_d, max_d, t_dur if is_short else None)
            if vid:
                q = cq; break
    if not vid or not valid_mp4("raw_gameplay.mp4"):
        raise RuntimeError(f"FATAL: No verified Free Fire clip found for {queries}. Zero fallback enforced!")

    dur = get_dur("raw_gameplay.mp4")
    times = [round(i * (t_dur / 7.0), 1) for i in range(7)]
    print(f"[+] VERIFIED FREE FIRE LOCKED: {vid} ({os.path.getsize('raw_gameplay.mp4')/1048576:.2f} MB, {dur:.1f}s)")
    base_p = f"Topic: '{concept['title']}'{win_hint} | Pillar: {bp['pillar_name']} | Weapon: {bp['weapon']} (Dmg: {bp['damage']}) | Hook: {bp['psychology_strategy']} | Clip: {dur:.1f}s -> Target: {t_dur}s | Scene 0 MUST open with a 2.5s curiosity hook!"
    ai_s = call_ollama_schema(f"Write 7-scene Roman Urdu narration (10-14 words each, no emojis) + short English subtitles for {base_p} | Timestamps: {times} | Max 5 tags, 1-line description.", SCRIPT_SCHEMA, max_tokens=2048, raise_on_fail=False)
    if not ai_s:
        ai_m = call_ollama_schema(f"YouTube title, 1-line description, max 5 tags, 1 Roman Urdu pinned_comment for {base_p}.", META_SCHEMA, max_tokens=600)
        ai_sc = call_ollama_schema(f"EXACTLY 7 scenes with timestamps {times}. Short Roman Urdu narration (10-14 words, no emojis), short english_subtitle, focus_cue for {base_p}.", SCENES_SCHEMA, max_tokens=1600)
        ai_s = {**ai_m, "scenes": ai_sc["scenes"]}

    scenes = [{"time": float(s.get("time", times[min(i, 6)])), "narration": str(s.get("narration", "")).strip(), "text": str(s.get("narration", "")).strip(), "english_subtitle": str(s.get("english_subtitle", "")).strip(), "focus_cue": str(s.get("focus_cue") or "crosshair_lock")} for i, s in enumerate(ai_s["scenes"])]
    out = {"title": ai_s.get("title") or concept["title"], "topic": concept["topic_angle"], "description": ai_s.get("description", ""), "tags": ai_s.get("tags", ["freefire", "shorts", "gaming"]), "pinned_comment": ai_s.get("pinned_comment", ""), "pillar": bp["pillar"], "pillar_id": bp["pillar_id"], "pillar_name": bp["pillar_name"], "psychology_strategy": bp["psychology_strategy"], "search_query": q, "source_video_id": vid, "weapon": bp["weapon"], "damage": bp["damage"], "format_type": fmt, "target_duration": bp["target_duration"], "player_tag": "DEVIL-999", "script": " ".join(s["narration"] for s in scenes), "english_script": " ".join(s["english_subtitle"] for s in scenes), "scenes": scenes}
    json.dump(out, open("current_script.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    if os.path.isdir("kaggle_render"):
        shutil.copy2("current_script.json", "kaggle_render/current_script.json")
    save_history_entry(query=q, video_id=vid, title=out["title"], pillar_id=bp["pillar_id"])
    print("[+] Done! Verified Free Fire Gameplay & Script saved.")

if __name__ == "__main__":
    generate_script()
