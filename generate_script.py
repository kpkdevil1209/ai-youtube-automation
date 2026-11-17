import os
import re
import json
import time
import socket
import random
import subprocess
import urllib.parse
import requests
import verify_freefire_agent as vfa

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
TEXT_MODEL = "llama3.2:1b"
TWITCH_GQL = "https://gql.twitch.tv/gql"
TWITCH_CID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"

RAW_GAMEPLAY_QUERIES = [
    "free fire one tap headshot gameplay",
    "free fire 1v4 clutch squad wipe",
    "free fire desert eagle headshot montage",
    "free fire m1887 two shot clutch",
    "free fire cs rank grandmaster gameplay",
    "garena free fire pro movement gameplay",
]

BANNED_WORDS = [
    "pubg", "bgmi", "cod", "call of duty", "fortnite", "valorant",
    "minecraft", "gta", "roblox", "free fire live stream giveaway",
    "redeem code giveaway", "how to download mod apk",
]

THEMES = ["CRIMSON", "CYBER", "GOLDEN", "ICE"]


def warp_proxy_url():
    try:
        with socket.create_connection(("127.0.0.1", 1080), timeout=1.5):
            return "socks5://127.0.0.1:1080"
    except Exception:
        return None


def safe_title_ok(title):
    t = (title or "").lower()
    if any(b in t for b in BANNED_WORDS):
        return False
    ff_hints = ["free fire", "freefire", "ff", "booyah", "headshot", "onetap", "one tap", "m1887", "desert eagle", "cs rank", "garena", "alok", "kelly", "ruok", "raistar", "b2k"]
    return any(h in t for h in ff_hints)


def load_trend_brief():
    if os.path.exists("viral_topic_brief.json"):
        try:
            with open("viral_topic_brief.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("topic"):
                return data
        except Exception as e:
            print(f"[!] Trend brief read warning: {e}")
    try:
        import viral_trend_agent
        return viral_trend_agent.scout_today_viral_topic()
    except Exception as e:
        print(f"[!] Viral trend fallback: {e}")
    return {
        "topic": "FREE FIRE SECRET ONE TAP HEADSHOT TRICK PRO PLAYERS HIDE",
        "format": "Detective Breakdown",
        "hook": "99% Free Fire players yeh aik setting ghalat rakhte hain!",
        "weapon": "Desert Eagle",
        "score": 850,
    }


def check_and_finalize(cand_path, title):
    if not os.path.exists(cand_path) or os.path.getsize(cand_path) < 300000:
        if os.path.exists(cand_path):
            os.remove(cand_path)
        return False

    try:
        res = vfa.verify_freefire_video(cand_path, title)
    except TypeError:
        res = vfa.verify_freefire_video(cand_path)

    if isinstance(res, tuple):
        ok, reason = bool(res[0]), str(res[1])
    else:
        ok, reason = bool(res), "vision/quality check"

    if not ok:
        print(f"[-] Rejected candidate ({reason}): {title[:55]}")
        if os.path.exists(cand_path):
            os.remove(cand_path)
        return False

    print(f"[+] VERIFIED FREE FIRE CLIP: {title[:60]}")
    try:
        if hasattr(vfa, "crop_action_peak"):
            vfa.crop_action_peak(cand_path, "raw_gameplay.mp4", 35)
        else:
            os.replace(cand_path, "raw_gameplay.mp4")
    except Exception as e:
        print(f"[!] Peak crop warning ({e}), using verified clip directly")
        os.replace(cand_path, "raw_gameplay.mp4")

    if os.path.exists(cand_path) and os.path.exists("raw_gameplay.mp4"):
        try:
            os.remove(cand_path)
        except Exception:
            pass
    return os.path.exists("raw_gameplay.mp4") and os.path.getsize("raw_gameplay.mp4") > 200000


def ytdlp_download(url, out_path, proxy=None, is_yt=False):
    if os.path.exists(out_path):
        os.remove(out_path)
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--max-filesize", "85M",
        "--socket-timeout", "20",
        "--retries", "2",
        "-f", "bestvideo[height>=360][height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height>=360][ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", out_path,
    ]
    if is_yt:
        cmd += ["--js-runtimes", "deno", "--extractor-args", "youtube:player_client=web_creator,tv"]
    if proxy:
        cmd += ["--proxy", proxy]
    cmd.append(url)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=110)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        last_err = err[-1] if err else "unknown error"
        print(f"    [yt-dlp skip] {last_err[:120]}")
        return False
    return os.path.exists(out_path) and os.path.getsize(out_path) > 300000


def direct_mp4_download(mp4_url, out_path):
    if os.path.exists(out_path):
        os.remove(out_path)
    try:
        with requests.get(mp4_url, headers={"User-Agent": UA}, stream=True, timeout=35) as r:
            if r.status_code != 200:
                return False
            total = 0
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=131072):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)
                        if total > 80 * 1024 * 1024:
                            break
        return os.path.exists(out_path) and os.path.getsize(out_path) > 300000
    except Exception as e:
        print(f"    [direct dl error] {str(e)[:90]}")
        return False


def harvest_twitch():
    print("[*] [Tier 1 - Twitch Free Fire (ID 502732)] Fetching clips...")
    gql_query = """
    query($gameID: ID!, $limit: Int!, $filter: ClipsPeriod!) {
      game(id: $gameID) {
        clips(first: $limit, criteria: { period: $filter }) {
          edges {
            node {
              slug
              title
              url
              durationSeconds
              viewCount
            }
          }
        }
      }
    }
    """.replace('"""', '')
    clean_q = "query($gameID: ID!, $limit: Int!, $filter: ClipsPeriod!) { game(id: $gameID) { clips(first: $limit, criteria: { period: $filter }) { edges { node { slug title url durationSeconds viewCount } } } } }"
    headers = {"Client-Id": TWITCH_CID, "Content-Type": "application/json", "User-Agent": UA}
    for period in ["LAST_DAY", "LAST_WEEK", "LAST_MONTH", "ALL_TIME"]:
        try:
            payload = {"query": clean_q, "variables": {"gameID": "502732", "limit": 15, "filter": period}}
            r = requests.post(TWITCH_GQL, json=payload, headers=headers, timeout=15)
            data = r.json()
            edges = (data.get("data") or {}).get("game", {}).get("clips", {}).get("edges", [])
            print(f"    [Twitch {period}] Found {len(edges)} clips")
            random.shuffle(edges)
            for edge in edges:
                node = edge.get("node") or {}
                dur = node.get("durationSeconds") or 0
                title = node.get("title") or "Free Fire Twitch Clip"
                clip_url = node.get("url") or f"https://clips.twitch.tv/{node.get('slug')}"
                if dur < 12 or dur > 180:
                    continue
                if ytdlp_download(clip_url, "cand_twitch.mp4"):
                    if check_and_finalize("cand_twitch.mp4", f"Free Fire {title}"):
                        return True
        except Exception as e:
            print(f"    [Twitch {period} error] {e}")
    return False


def harvest_tiktok(queries):
    print("[*] [Tier 2 - TikTok HD via TikWM API] Searching...")
    for q in queries:
        try:
            r = requests.get(
                "https://www.tikwm.com/api/feed/search",
                params={"keywords": q, "count": 12, "cursor": 0},
                headers={"User-Agent": UA},
                timeout=15,
            )
            res = r.json()
            videos = (res.get("data") or {}).get("videos") or []
            print(f"    [TikWM '{q[:28]}'] Returned {len(videos)} videos")
            random.shuffle(videos)
            for v in videos[:6]:
                dur = int(v.get("duration") or 0)
                title = v.get("title") or q
                if dur < 12 or dur > 180 or not safe_title_ok(title + " " + q):
                    continue
                mp4_url = v.get("hdplay") or v.get("play")
                if mp4_url and direct_mp4_download(mp4_url, "cand_tt.mp4"):
                    if check_and_finalize("cand_tt.mp4", title):
                        return True
                vid_id = v.get("video_id") or v.get("id")
                author = (v.get("author") or {}).get("unique_id")
                if vid_id and author:
                    tt_url = f"https://www.tiktok.com/@{author}/video/{vid_id}"
                    if ytdlp_download(tt_url, "cand_tt.mp4"):
                        if check_and_finalize("cand_tt.mp4", title):
                            return True
        except Exception as e:
            print(f"    [TikWM error] {str(e)[:90]}")
    return False


def harvest_dailymotion(queries):
    print("[*] [Tier 3 - Dailymotion Gaming API] Searching...")
    for q in queries[:4]:
        try:
            r = requests.get(
                "https://api.dailymotion.com/videos",
                params={
                    "channel": "videogames",
                    "search": q,
                    "sort": "visited",
                    "limit": 10,
                    "fields": "id,title,url,duration",
                },
                headers={"User-Agent": UA},
                timeout=15,
            )
            items = r.json().get("list") or []
            print(f"    [Dailymotion '{q[:28]}'] Returned {len(items)} items")
            for item in items[:5]:
                dur = int(item.get("duration") or 0)
                title = item.get("title") or ""
                v_url = item.get("url")
                if dur < 14 or dur > 420 or not v_url or not safe_title_ok(title):
                    continue
                if ytdlp_download(v_url, "cand_dm.mp4"):
                    if check_and_finalize("cand_dm.mp4", title):
                        return True
        except Exception as e:
            print(f"    [Dailymotion error] {str(e)[:90]}")
    return False


def harvest_youtube_and_piped(queries, proxy):
    print(f"[*] [Tier 4 - YouTube + Piped] Proxy: {'WARP' if proxy else 'Direct'}...")
    for q in queries[:3]:
        try:
            cmd = [
                "yt-dlp",
                "--flat-playlist",
                "--dump-single-json",
                "--js-runtimes", "deno",
            ]
            if proxy:
                cmd += ["--proxy", proxy]
            cmd.append(f"ytsearch6:{q}")
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
            if proc.returncode == 0 and proc.stdout.strip():
                entries = json.loads(proc.stdout).get("entries") or []
                print(f"    [YT Search '{q[:26]}'] Found {len(entries)} entries")
                for e in entries[:4]:
                    dur = int(e.get("duration") or 0)
                    title = e.get("title") or ""
                    vid = e.get("id")
                    if not vid or dur < 14 or dur > 420 or not safe_title_ok(title):
                        continue
                    v_url = f"https://www.youtube.com/watch?v={vid}"
                    if ytdlp_download(v_url, "cand_yt.mp4", proxy=proxy, is_yt=True):
                        if check_and_finalize("cand_yt.mp4", title):
                            return True
        except Exception as e:
            print(f"    [YT search error] {str(e)[:90]}")

    piped_hosts = [
        "https://pipedapi.kavin.rocks",
        "https://api.piped.private.coffee",
        "https://pipedapi.adminforge.de",
    ]
    for host in piped_hosts:
        for q in queries[:2]:
            try:
                r = requests.get(f"{host}/search", params={"q": q, "filter": "videos"}, timeout=12)
                if r.status_code != 200:
                    continue
                items = r.json().get("items") or []
                print(f"    [Piped {host}] Found {len(items)} items")
                for item in items[:4]:
                    dur = int(item.get("duration") or 0)
                    title = item.get("title") or ""
                    u = item.get("url") or ""
                    if dur < 14 or dur > 420 or "v=" not in u or not safe_title_ok(title):
                        continue
                    vid = u.split("v=")[-1].split("&")[0]
                    sr = requests.get(f"{host}/streams/{vid}", timeout=12).json()
                    streams = [s for s in (sr.get("videoStreams") or []) if not s.get("videoOnly") and s.get("url")]
                    if streams and direct_mp4_download(streams[0]["url"], "cand_piped.mp4"):
                        if check_and_finalize("cand_piped.mp4", title):
                            return True
            except Exception as e:
                print(f"    [Piped skip] {str(e)[:80]}")
    return False


def harvest_rumble_and_archive(queries):
    print("[*] [Tier 5 - Rumble & Archive.org] Searching...")
    for q in queries[:2]:
        try:
            url = f"https://rumble.com/search/video?q={urllib.parse.quote_plus(q)}"
            proc = subprocess.run(
                ["yt-dlp", "--flat-playlist", "--dump-single-json", "--playlist-items", "1:5", url],
                capture_output=True, text=True, timeout=30
            )
            if proc.returncode == 0 and proc.stdout.strip():
                entries = json.loads(proc.stdout).get("entries") or []
                print(f"    [Rumble '{q[:24]}'] Found {len(entries)} items")
                for e in entries[:4]:
                    v_url = e.get("webpage_url") or e.get("url")
                    title = e.get("title") or ""
                    if v_url and safe_title_ok(title):
                        if ytdlp_download(v_url, "cand_rumble.mp4"):
                            if check_and_finalize("cand_rumble.mp4", title):
                                return True
        except Exception as e:
            print(f"    [Rumble skip] {str(e)[:80]}")

    try:
        r = requests.get(
            "https://archive.org/advancedsearch.php",
            params={"q": 'title:("free fire") AND mediatype:(movies)', "fl[]": "identifier,title", "output": "json", "rows": 8},
            timeout=15,
        )
        docs = (r.json().get("response") or {}).get("docs") or []
        print(f"    [Archive.org] Found {len(docs)} items")
        for d in docs[:4]:
            title = str(d.get("title") or "Free Fire Gameplay")
            if safe_title_ok(title) and ytdlp_download(f"https://archive.org/details/{d['identifier']}", "cand_arch.mp4"):
                if check_and_finalize("cand_arch.mp4", title):
                    return True
    except Exception as e:
        print(f"    [Archive skip] {str(e)[:80]}")
    return False


def harvest_raw_gameplay(brief):
    queries = list(RAW_GAMEPLAY_QUERIES)
    weapon = (brief.get("weapon") or "").strip()
    if weapon and len(weapon) <= 18 and weapon.lower() not in ["none", "general", "event"]:
        queries.insert(0, f"free fire {weapon.lower()} headshot gameplay")
    random.shuffle(queries[1:])

    proxy = warp_proxy_url()
    if harvest_twitch():
        return True
    if harvest_tiktok(queries):
        return True
    if harvest_dailymotion(queries):
        return True
    if harvest_youtube_and_piped(queries, proxy):
        return True
    if harvest_rumble_and_archive(queries):
        return True
    raise RuntimeError(f"FATAL: No verified Free Fire raw gameplay found across all 5 tiers for {queries}")


def write_script_with_ollama(brief):
    topic = brief.get("topic", "FREE FIRE PRO SECRET")
    fmt = brief.get("format", "Detective Breakdown")
    hook = brief.get("hook", "99% Free Fire players yeh raaz nahi jante!")

    prompt = (
        f"You are DEVIL INSANITY, a viral Free Fire YouTube Shorts narrator speaking energetic Hinglish/Roman Urdu. "
        f"Write a 28-second high-retention Short script about today's viral topic: '{topic}' in style '{fmt}'. "
        f"Start immediately at 0.0s with this shock hook: '{hook}'. "
        f"End with a loop line that connects right back to the hook. "
        f"Return STRICT JSON with keys: "
        f"title (max 85 chars English+Hindi hype with #shorts), "
        f"description (2 lines + hashtags #freefire #freefiremax #shorts), "
        f"tags (array of 8 strings), "
        f"pinned_comment (1 engaging question in Roman Urdu for viewers), "
        f"segments (array of 6 objects with keys: text (6-10 words Roman Urdu/English), pace ('fast' or 'normal' or 'slow'), sfx ('whoosh' or 'hit' or 'none'))."
    )

    for attempt in range(2):
        try:
            r = requests.post(
                OLLAMA_URL,
                json={"model": TEXT_MODEL, "prompt": prompt, "stream": False, "format": "json"},
                timeout=90,
            )
            raw = r.json().get("response", "").strip()
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            parsed = json.loads(m.group(0) if m else raw)
            segs = parsed.get("segments") or []
            if len(segs) >= 3 and parsed.get("title"):
                full_text = " ".join(s.get("text", "").strip() for s in segs if s.get("text"))
                title = str(parsed["title"]).replace("<", "").replace(">", "").strip()[:95]
                if "#shorts" not in title.lower():
                    title = (title[:85] + " #shorts").strip()
                return {
                    "title": title,
                    "description": str(parsed.get("description") or f"{topic}\n#freefire #freefiremax #shorts").replace("<", "").replace(">", ""),
                    "tags": [str(t) for t in (parsed.get("tags") or ["free fire", "free fire max", "free fire shorts", "devil insanity"])[:12]],
                    "pinned_comment": str(parsed.get("pinned_comment") or "Aap ka favorite gun konsa hai? Comment mein batao!"),
                    "topic": topic,
                    "format": fmt,
                    "theme": random.choice(THEMES),
                    "hook": hook,
                    "segments": segs,
                    "narration": full_text,
                    "script": full_text,
                }
        except Exception as e:
            print(f"[!] Ollama script retry {attempt+1}: {e}")
            time.sleep(2)

    raise RuntimeError("FATAL: Ollama failed to generate valid script JSON.")


def generate_script():
    brief = load_trend_brief()
    print(f"[+] Trend Topic: {brief.get('topic')} | Format: {brief.get('format')}")
    harvest_raw_gameplay(brief)
    script_data = write_script_with_ollama(brief)
    with open("current_script.json", "w", encoding="utf-8") as f:
        json.dump(script_data, f, indent=2, ensure_ascii=False)
    print(f"[+] Script & Raw Gameplay Ready! Title: {script_data['title']}")


if __name__ == "__main__":
    generate_script()
