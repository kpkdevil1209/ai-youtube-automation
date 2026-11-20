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
SLOP_TITLE = ["punchy", "english", "script", "youtube short", "viral title", "hook_badge", "analysis"]
PSYCH_STRATEGIES = [
    ("Zeigarnik Open-Loop", "Start mid-crisis claiming he broke an impossible 0.4s rule so the brain demands closure."),
    ("Loss Aversion Near-Death", "Frame the 7s buildup as 100% doomed defeat (low HP, trapped, zero cover) before flipping it."),
    ("Illusion of Error", "Point at his seemingly wrong crosshair/miss right before the impossible kill connects."),
    ("Micro-Second Secret", "Make viewers look closer at a split-second shadow, reload, or crosshair flick nobody noticed."),
    ("Grandmaster Ego Challenge", "Challenge players: only top 1% CS-Rank pushers recognize why he waited 2 seconds here."),
    ("Forbidden Unwritten Rule", "Reveal an unspoken drag-timing trick pro players abuse in close/mid bridge fights."),
    ("Reverse Cliffhanger", "Tease the final knock at 0.0s, rewind 7 seconds, then race back to how it happened."),
    ("Pattern Contradiction", "Claim every guide says NEVER take this peek—then show why doing the opposite wiped the squad."),
    ("50-50 Controversy Trap", "Spark an urgent skill-vs-macro debate right over the 0.35x slow-mo frame."),
    ("Ouroboros Loop Hook", "End Beat 5 mid-thought so the final word crashes straight back into Beat 1's shock hook."),
]
SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"}, "description": {"type": "string"},
        "hook_badge": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}},
        "pinned_comment": {"type": "string"},
        "segments": {"type": "array", "items": {"type": "object", "properties": {"hi": {"type": "string"}, "en": {"type": "string"}}, "required": ["hi", "en"]}},
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
        "topic": str(d.get("topic") or d.get("winner_topic") or "IMPOSSIBLE FREE FIRE ONE TAP").strip(),
        "format": str(d.get("format") or d.get("viral_format") or "0.35x Forensic Twist").strip(),
        "weapon": str(d.get("weapon") or "").strip(),
    }


def finalize_clip(cand, title):
    if not os.path.exists(cand) or os.path.getsize(cand) < 400000:
        if os.path.exists(cand): os.remove(cand)
        return False
    res = vfa.verify_freefire_video(cand, title)
    ok, msg = (bool(res[0]), str(res[1])) if isinstance(res, tuple) else (bool(res), "checked")
    if not ok:
        print(f"[-] Rejected ({msg}): {title[:50]}")
        if os.path.exists(cand): os.remove(cand)
        return False
    print(f"[+] VERIFIED HIGHEST HD: {title[:60]} ({msg})")
    try: vfa.crop_action_peak(cand, "raw_gameplay.mp4", pre_sec=7.5, post_sec=4.0)
    except Exception: os.replace(cand, "raw_gameplay.mp4")
    if os.path.exists(cand) and os.path.exists("raw_gameplay.mp4"):
        try: os.remove(cand)
        except Exception: pass
    return os.path.exists("raw_gameplay.mp4") and os.path.getsize("raw_gameplay.mp4") > 200000


def dl_ytdlp(url, out, proxy=None, is_yt=False):
    if os.path.exists(out): os.remove(out)
    cmd = ["yt-dlp", "--no-playlist", "--max-filesize", "120M", "--socket-timeout", "15", "--retries", "1",
           "-f", "bestvideo[height>=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[height>=720]/best",
           "--merge-output-format", "mp4", "-o", out]
    if is_yt: cmd += ["--js-runtimes", "deno", "--extractor-args", "youtube:player_client=web_creator,tv"]
    if proxy: cmd += ["--proxy", proxy]
    try:
        p = subprocess.run(cmd + [url], capture_output=True, text=True, timeout=75)
        return p.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 400000
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
                    if total > 110 * 1024 * 1024 or (time.time() - t0) > 45: break
        return os.path.exists(out) and os.path.getsize(out) > 400000
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

    print("[*] [Tier 1 - Twitch Free Fire (Source Quality)]")
    gql = "query($id:ID!,$f:ClipsPeriod!){game(id:$id){clips(first:15,criteria:{period:$f}){edges{node{slug title url durationSeconds}}}}}"
    for per in ["LAST_DAY", "LAST_WEEK", "ALL_TIME"]:
        if time.time() - t_start > 240: break
        try:
            r = requests.post("https://gql.twitch.tv/gql", json={"query": gql, "variables": {"id": "502732", "f": per}},
                              headers={"Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko", "User-Agent": UA}, timeout=12)
            edges = (((r.json().get("data") or {}).get("game") or {}).get("clips") or {}).get("edges") or []
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

    print("[*] [Tier 2 - TikTok HD TikWM]")
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

    print("[*] [Tier 3 - Dailymotion HD]")
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

    print(f"[*] [Tier 4 - YouTube 1080p] Proxy={'WARP' if proxy else 'Direct'}")
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
    raise RuntimeError("FATAL: No verified HD raw Free Fire gameplay found.")


def has_devanagari(s):
    return any("\u0900" <= ch <= "\u097f" for ch in (s or ""))


def to_hindi(text):
    try:
        u = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=hi&dt=t&q=" + urllib.parse.quote(text)
        res = requests.get(u, headers={"User-Agent": UA}, timeout=10).json()
        hi = "".join(part[0] for part in (res[0] or []) if part and part[0]).strip()
        return hi if hi else text
    except Exception: return text


def normalize_beats(raw_segs, max_words=64):
    out, total = [], 0
    for s in (raw_segs or []):
        if not isinstance(s, dict): continue
        en, hi = str(s.get("en") or "").strip(), str(s.get("hi") or "").strip()
        if not en: continue
        w = len(en.split())
        if total + w <= max_words or not out:
            out.append({"en": en, "hi": hi}); total += w
        else: break
    return out


def clean_yt_title(raw_t, tl):
    t = re.sub(r"\s+", " ", str(raw_t or "")).replace("<", "").replace(">", "").strip()
    if len(t) < 12 or any(bad in t.lower() for bad in SLOP_TITLE):
        w = tl.get("weapon", "").strip()
        w_tag = w if w and w.lower() not in ["unknown", "none"] else "One-Tap"
        t = f"How Did That {w_tag} Shot Connect?! #shorts"
    if "#shorts" not in t.lower(): t = (t[:84] + " #shorts").strip()
    return t[:95]


def write_script(brief, tl):
    picks = random.sample(PSYCH_STRATEGIES, 3)
    strat_block = "\n".join(f"- {n}: {d}" for n, d in picks)
    scenes = f"7s Before: {tl.get('before_7s','')}. Tension: {tl.get('tension_aim','')}. Headshot Hit: {tl.get('headshot_hit','')}. Aftermath: {tl.get('after_kill','')}. Gun: {tl.get('weapon','unknown')}."

    prompt = (
        f"You are an elite viral gaming storyteller writing a 20s Free Fire YouTube Short for THIS clip:\n{scenes}\n"
        f"ACTIVATE ALL 3 PSYCHOLOGY TRIGGERS BELOW (Do NOT blindly narrate like a boring announcer!):\n{strat_block}\n"
        f"5-BEAT TIMELINE:\n"
        f"1) Beat 1 (0.0s Flash-Forward Mind-Break Hook, 8-11 words): Shock question about the kill ('Wait... his aim was off, so how did that kill?!').\n"
        f"2) Beat 2 (Rewind 7s Earlier, 8-11 words): Extreme danger / loss aversion setup 7 seconds before the shot.\n"
        f"3) Beat 3 (Hidden Clue, 8-11 words): Point to a tiny detail viewers miss right before firing.\n"
        f"4) Beat 4 (0.35x Climax Slow-Mo Reveal, 8-11 words): Payoff twist as the headshot connects + enemy drops.\n"
        f"5) Beat 5 (Controversy + Ouroboros Loop, 8-10 words): End unfinished so Beat 5 loops straight into Beat 1.\n"
        f"RULES:\n"
        f"- 'hi': Natural casual Indian gamer Hindi in Devanagari (भाई, रुक, देख, बंदा, खत्म) with commas and '...' pauses.\n"
        f"- 'en': Crisp short English subtitles matching 'hi'.\n"
        f"- 'title': High-CTR 5-8 word English mystery title ending #shorts (NEVER write 'punchy', 'English', 'analysis', or 'script').\n"
        f"- 'hook_badge': 3 uppercase words (e.g. '7 SECONDS EARLIER')."
    )

    best_p, best_segs, best_wc = None, [], 0
    for i in range(3):
        try:
            print(f"[*] Calling qwen2.5vl:3b [{picks[0][0]}] (attempt {i+1})...")
            r = requests.post(f"{OLLAMA_BASE}/api/generate",
                              json={"model": "qwen2.5vl:3b", "prompt": prompt, "stream": False, "format": SCRIPT_SCHEMA, "keep_alive": 0,
                                    "options": {"num_ctx": 2048, "num_predict": 720, "temperature": 0.68}}, timeout=145)
            if r.status_code != 200: print(f"[!] Ollama {r.status_code}"); time.sleep(2); continue
            p = json.loads(r.json().get("response", "").strip())
            segs = normalize_beats(p.get("segments"), max_words=64)
            wc = sum(len(x["en"].split()) for x in segs)
            print(f"    [Draft {i+1}] {len(segs)} beats | {wc} EN words | Title: {str(p.get('title',''))[:45]}")
            if len(segs) >= 4 and wc >= 28:
                best_p, best_segs, best_wc = p, segs, wc
                break
            elif not best_p or wc > best_wc:
                best_p, best_segs, best_wc = p, segs, wc
        except Exception as e: print(f"[!] Script retry {i+1}: {e}"); time.sleep(2)

    if not best_p or best_wc < 22: raise RuntimeError(f"FATAL: Qwen script too short ({best_wc} words).")
    final_segs = []
    for idx, s in enumerate(best_segs):
        hi_txt = s["hi"] if has_devanagari(s["hi"]) else to_hindi(s["en"])
        sfx = "hit" if idx in [0, 3] else ("rewind" if idx == 1 else "whoosh")
        pace = "fast" if idx in [0, 4] else ("slow" if idx == 3 else "normal")
        final_segs.append({"text": hi_txt, "en": s["en"], "sfx": sfx, "pace": pace})

    title = clean_yt_title(best_p.get("title"), tl)
    desc = str(best_p.get("description") or "Rewind 7 seconds earlier to see the real trap!\n#freefire #freefiremax #shorts #gaming").replace("<", "").replace(">", "")
    badge = re.sub(r"[^A-Za-z0-9 .!?/-]", "", str(best_p.get("hook_badge") or "WAIT FOR THE TWIST")).upper().strip()[:28]
    return {
        "title": title, "description": desc, "hook_badge": badge or "WAIT FOR THE TWIST",
        "tags": [str(t) for t in (best_p.get("tags") or ["free fire", "free fire shorts", "one tap headshot", "gaming"])[:10]],
        "pinned_comment": str(best_p.get("pinned_comment") or "Skill or broken aim? Look at 0.35x and decide!"),
        "topic": brief["topic"], "psychology": [n for n, _ in picks], "voice_lang": "hi",
        "theme": random.choice(["CRIMSON", "CYBER", "GOLDEN", "ICE"]),
        "timeline": tl, "segments": final_segs,
        "narration": " ".join(x["text"] for x in final_segs),
        "script": " ".join(x["en"] for x in final_segs),
    }


def generate_script():
    brief = load_brief()
    print(f"[+] Trend Topic: {brief['topic']} | Format: {brief['format']}")
    harvest(brief)
    tl = vfa.inspect_timeline_phases("raw_gameplay.mp4")
    data = write_script(brief, tl)
    json.dump(data, open("current_script.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"[+] 10-Strategy Script Ready! Title: {data['title']}")


if __name__ == "__main__":
    generate_script()
