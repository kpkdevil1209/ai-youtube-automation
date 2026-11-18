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
FF_HINTS = ["free fire", "freefire", "ff", "booyah", "headshot", "onetap", "one tap", "m1887", "desert eagle", "cs rank", "garena", "ruok", "raistar", "esta arma", "kills"]
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
                if 18 <= (n.get("durationSeconds") or 0) <= 180:
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
            tried = 0
            for v in vids:
                if tried >= 2: break
                t, u = v.get("title") or q, v.get("hdplay") or v.get("play")
                if 18 <= int(v.get("duration") or 0) <= 180 and safe_title(t + " " + q) and u:
                    tried += 1
                    if dl_mp4(u, "c_tt.mp4") and finalize_clip("c_tt.mp4", t): return True
        except Exception: pass

    print("[*] [Tier 3 - Dailymotion]")
    for q in qs[:2]:
        if time.time() - t_start > 240: break
        try:
            items = requests.get("https://api.dailymotion.com/videos", params={"channel": "videogames", "search": q, "sort": "visited", "limit": 6, "fields": "title,url,duration"},
                                 headers={"User-Agent": UA}, timeout=12).json().get("list") or []
            tried = 0
            for it in items:
                if tried >= 2: break
                if 18 <= int(it.get("duration") or 0) <= 420 and safe_title(it.get("title")):
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
                    if e.get("id") and 18 <= int(e.get("duration") or 0) <= 420 and safe_title(e.get("title")):
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


def cap_segments(raw_segs, max_words=84):
    flat = []
    for s in (raw_segs or []):
        txt = str(s.get("text") if isinstance(s, dict) else s).strip()
        if not txt: continue
        pace = s.get("pace", "normal") if isinstance(s, dict) and s.get("pace") in ["fast", "normal", "slow"] else "normal"
        sfx = s.get("sfx", "whoosh") if isinstance(s, dict) and s.get("sfx") in ["hit", "whoosh", "none"] else "whoosh"
        words = txt.split()
        if len(words) > 20:
            for k in range(0, len(words), 12):
                flat.append({"text": " ".join(words[k:k+12]), "pace": pace, "sfx": sfx})
        else:
            flat.append({"text": txt, "pace": pace, "sfx": sfx})
    out, total = [], 0
    for seg in flat:
        w = len(seg["text"].split())
        if total + w <= max_words or not out:
            out.append(seg); total += w
        else:
            break
    if total > max_words and len(out) == 1:
        out[0]["text"] = " ".join(out[0]["text"].split()[:max_words])
    return out


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
        try: scene = f" On-screen gameplay: {json.load(open('verified_scene.json')).get('scene', '')}."
        except Exception: pass

    base_prompt = (
        f"Write a 28-second viral Free Fire YouTube Short script in Hinglish/Roman Urdu. "
        f"Topic: {brief['topic']}. Style: {brief['format']}.{scene} Start with hook: {brief['hook']}. "
        f"STRICT RULE: Write EXACTLY 6 segments, EACH segment 10 to 12 words (65 to 78 words TOTAL, NEVER over 85 words). "
        f"Return JSON with: title (catchy max 75 chars about '{brief['topic']}' + #shorts), description (2 lines + #freefire #shorts), "
        f"tags (6 strings), pinned_comment (1 Roman Urdu question), segments (6 dicts: text, pace [fast/normal/slow], sfx [hit/whoosh/none])."
    )

    best_p, best_segs, best_wc = None, [], 0
    for i in range(3):
        try:
            extra = "" if best_wc == 0 else f" Keep TOTAL strictly between 60 and 80 words across 6 segments."
            print(f"[*] Calling {model} (attempt {i+1})...")
            r = requests.post(f"{OLLAMA_BASE}/api/generate",
                              json={"model": model, "prompt": base_prompt + extra, "stream": False, "format": SCRIPT_SCHEMA, "keep_alive": 0,
                                    "options": {"num_ctx": 1536, "num_predict": 550, "temperature": 0.4}}, timeout=95)
            if r.status_code != 200: print(f"[!] Ollama {r.status_code}"); time.sleep(2); continue
            p = json.loads(r.json().get("response", "").strip())
            segs = cap_segments(p.get("segments"), max_words=84)
            wc = sum(len(x["text"].split()) for x in segs)
            print(f"    [Draft {i+1}] {len(segs)} segments | {wc} words (~{wc/2.6:.1f}s)")
            if not best_p or abs(wc - 70) < abs(best_wc - 70):
                best_p, best_segs, best_wc = p, segs, wc
            if 50 <= wc <= 84: break
        except Exception as e:
            print(f"[!] Ollama retry {i+1}: {e}"); time.sleep(2)

    if not best_p or best_wc < 20:
        raise RuntimeError("FATAL: Ollama failed to generate valid length script.")

    title = str(best_p.get("title") or brief["topic"]).replace("<", "").replace(">", "").strip()[:95]
    if "#shorts" not in title.lower(): title = (title[:85] + " #shorts").strip()
    txt = " ".join(x["text"] for x in best_segs)
    print(f"[+] Script Approved: {len(best_segs)} segments | {best_wc} words (~{best_wc/2.6:.1f}s)")
    return {"title": title, "description": str(best_p.get("description") or f"{brief['topic']}\n#freefire #shorts").replace("<", "").replace(">", ""),
            "tags": [str(t) for t in (best_p.get("tags") or ["free fire", "free fire max", "shorts"])[:10]],
            "pinned_comment": str(best_p.get("pinned_comment") or "Aap ko yeh trick kaisi lagi? Comment karo!"),
            "topic": brief["topic"], "format": brief["format"], "theme": random.choice(["CRIMSON", "CYBER", "GOLDEN", "ICE"]),
            "hook": brief["hook"], "segments": best_segs, "narration": txt, "script": txt}


def generate_script():
    brief = load_brief()
    print(f"[+] Trend Topic: {brief['topic']} | Format: {brief['format']}")
    harvest(brief)
    data = write_script(brief)
    json.dump(data, open("current_script.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"[+] Ready! Title: {data['title']}")


if __name__ == "__main__":
    generate_script()
