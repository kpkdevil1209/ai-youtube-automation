import json
import os
import random
import re
import shutil
import subprocess
import time
import urllib.parse
import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

BANNED_QUERY_WORDS = {
    "devil", "insanity", "999", "devil999", "investigation", "enigma",
    "mystery", "documentary", "story", "analysis", "exposed", "truth",
    "panel", "vs", "pure", "skill", "reflex", "hindi", "urdu", "pk",
    "shorts", "short", "viral", "video", "youtube", "channel"
}

EVERGREEN_SHORT_QUERIES = [
    "free fire one tap headshot gameplay",
    "free fire awm sniper highlights",
    "free fire desert eagle headshot",
    "free fire m1887 two shot clutch",
    "free fire cs rank headshot montage",
    "garena free fire pro movement gameplay",
    "free fire solo vs squad rush",
]

EVERGREEN_LONG_QUERIES = [
    "free fire full gameplay 60fps",
    "free fire grandmaster rank push gameplay",
    "free fire solo vs squad full match",
    "free fire clash squad ranked match gameplay",
    "garena free fire tournament highlights",
]


def sanitize_phrase(text):
    if not text:
        return ""
    clean = re.sub(r"[\[\]\(\)\{\}_\-|/:#@\"',.?!]+", " ", str(text).lower())
    words = [w for w in clean.split() if len(w) > 1 and w not in BANNED_QUERY_WORDS]
    if not words:
        return ""
    joined = " ".join(words[:6])
    if "free fire" not in joined and "garena" not in joined:
        joined = "free fire " + joined
    return joined.strip()


def build_clean_queries(raw_query, is_short=True):
    queries = []
    q1 = sanitize_phrase(raw_query)
    if q1 and len(q1.split()) >= 3:
        queries.append(q1)
    pool = list(EVERGREEN_SHORT_QUERIES if is_short else EVERGREEN_LONG_QUERIES)
    random.shuffle(pool)
    for q in pool:
        if q not in queries:
            queries.append(q)
    return queries[:6]


def verify_video(path, min_dur=12):
    if not path or not os.path.exists(path):
        return None
    size_bytes = os.path.getsize(path)
    if size_bytes < 200 * 1024:
        return None
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-show_entries", "format=duration",
            "-of", "json", path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if res.returncode != 0:
            return None
        info = json.loads(res.stdout or "{}")
        streams = info.get("streams") or []
        if not streams:
            return None
        w = int(streams[0].get("width") or 0)
        h = int(streams[0].get("height") or 0)
        dur = float((info.get("format") or {}).get("duration") or 0)
        if w < 320 or h < 240 or dur < max(8, min_dur):
            return None
        return {
            "width": w,
            "height": h,
            "duration": round(dur, 1),
            "size_mb": round(size_bytes / (1024 * 1024), 2),
        }
    except Exception:
        return None


def _run_ytdlp(url, out_path, extra_args=None, timeout=180):
    if os.path.exists(out_path):
        os.remove(out_path)
    cmd = [
        "yt-dlp",
        "--no-warnings",
        "--no-playlist",
        "--retries", "2",
        "--user-agent", UA,
        "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
        "--merge-output-format", "mp4",
        "-o", out_path,
    ]
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(url)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode == 0
    except Exception:
        return False


def _download_direct(url, out_path, headers=None, timeout=60):
    if os.path.exists(out_path):
        os.remove(out_path)
    hdrs = {"User-Agent": UA}
    if headers:
        hdrs.update(headers)
    try:
        with requests.get(url, headers=hdrs, stream=True, timeout=timeout) as r:
            if r.status_code >= 400:
                return False
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
        return os.path.exists(out_path) and os.path.getsize(out_path) >= 200 * 1024
    except Exception:
        return False


def dl_dailymotion(query, used_ids, min_dur, max_dur, out_path):
    print(f"[*] [Tier 1 - Dailymotion HD] Searching: '{query}'...")
    for sort_mode in ("relevance", "visited"):
        for page in (1, 2):
            try:
                params = {
                    "search": query,
                    "fields": "id,title,duration,url",
                    "sort": sort_mode,
                    "limit": 15,
                    "page": page,
                    "longer_than": max(15, int(min_dur)),
                    "shorter_than": int(max_dur),
                }
                r = requests.get(
                    "https://api.dailymotion.com/videos",
                    params=params,
                    headers={"User-Agent": UA},
                    timeout=15,
                )
                if r.status_code != 200:
                    continue
                items = (r.json() or {}).get("list") or []
                for v in items:
                    vid = v.get("id")
                    dur = int(v.get("duration") or 0)
                    vurl = v.get("url") or f"https://www.dailymotion.com/video/{vid}"
                    uid = f"dm_{vid}"
                    if not vid or uid in used_ids:
                        continue
                    if dur < min_dur or dur > max_dur:
                        continue
                    if _run_ytdlp(vurl, out_path):
                        meta = verify_video(out_path, min_dur=min(15, min_dur))
                        if meta:
                            return uid, meta
            except Exception:
                continue
    return None, None


def dl_tiktok_tikwm(query, used_ids, min_dur, max_dur, out_path):
    print(f"[*] [Tier 2 - TikTok No-Watermark HD] Searching: '{query}'...")
    time.sleep(2.2)
    hdrs = {
        "User-Agent": UA,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://www.tikwm.com/",
        "Origin": "https://www.tikwm.com",
    }
    payload = {"keywords": query, "count": 15, "cursor": 0, "hd": 1}
    videos = []
    for method in ("post", "get"):
        try:
            if method == "post":
                r = requests.post("https://www.tikwm.com/api/feed/search", data=payload, headers=hdrs, timeout=20)
            else:
                r = requests.get("https://www.tikwm.com/api/feed/search", params=payload, headers=hdrs, timeout=20)
            if r.status_code != 200:
                continue
            j = r.json()
            if j.get("code") == 0:
                d = j.get("data")
                if isinstance(d, dict):
                    videos = d.get("videos") or []
                elif isinstance(d, list):
                    videos = d
                if videos:
                    break
        except Exception:
            time.sleep(2.5)
    for v in videos:
        vid = str(v.get("video_id") or v.get("id") or "").strip()
        dur = int(v.get("duration") or 0)
        uid = f"tt_{vid}"
        if not vid or uid in used_ids:
            continue
        if dur > 0 and (dur < min_dur or dur > max_dur):
            continue
        dl_url = v.get("hdplay") or v.get("play") or ""
        if not dl_url:
            continue
        if dl_url.startswith("/"):
            dl_url = "https://www.tikwm.com" + dl_url
        if _download_direct(dl_url, out_path, headers={"Referer": "https://www.tikwm.com/"}):
            meta = verify_video(out_path, min_dur=min(12, min_dur))
            if meta:
                return uid, meta
    return None, None


def dl_twitch_clips(used_ids, min_dur, max_dur, out_path):
    print("[*] [Tier 3 - Twitch Garena Free Fire Clips] Fetching...")
    gql_url = "https://gql.twitch.tv/gql"
    hdrs = {
        "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
        "Content-Type": "application/json",
        "User-Agent": UA,
    }
    q_slug = "query($slug: ID!, $limit: Int, $criteria: GameClipsInput) { game(slug: $slug) { clips(first: $limit, criteria: $criteria) { edges { node { slug durationSeconds url } } } } }"
    q_name = "query($name: String!, $limit: Int, $criteria: GameClipsInput) { game(name: $name) { clips(first: $limit, criteria: $criteria) { edges { node { slug durationSeconds url } } } } }"
    attempts = [
        (q_slug, {"slug": "garena-free-fire", "limit": 20, "criteria": {"filter": "LAST_MONTH"}}),
        (q_slug, {"slug": "garena-free-fire", "limit": 20, "criteria": {"filter": "ALL_TIME"}}),
        (q_name, {"name": "Garena Free Fire", "limit": 20, "criteria": {"filter": "ALL_TIME"}}),
    ]
    for q_str, vars_dict in attempts:
        try:
            r = requests.post(gql_url, headers=hdrs, json={"query": q_str, "variables": vars_dict}, timeout=15)
            if r.status_code != 200:
                continue
            game = ((r.json() or {}).get("data") or {}).get("game") or {}
            edges = (game.get("clips") or {}).get("edges") or []
            for e in edges:
                node = e.get("node") or {}
                slug = node.get("slug") or ""
                dur = int(node.get("durationSeconds") or 0)
                uid = f"tw_{slug}"
                if not slug or uid in used_ids:
                    continue
                if dur > 0 and (dur < min_dur or dur > max_dur):
                    continue
                clip_url = node.get("url") or f"https://clips.twitch.tv/{slug}"
                if _run_ytdlp(clip_url, out_path):
                    meta = verify_video(out_path, min_dur=min(12, min_dur))
                    if meta:
                        return uid, meta
        except Exception:
            continue
    return None, None


def dl_invidious_piped(query, used_ids, min_dur, max_dur, out_path):
    print(f"[*] [Tier 4 - Live Invidious/Piped] Searching: '{query}'...")
    inv_hosts = []
    try:
        r = requests.get("https://api.invidious.io/instances.json?sort_by=health", timeout=10)
        if r.status_code == 200:
            for item in r.json():
                if isinstance(item, list) and len(item) >= 2 and isinstance(item[1], dict):
                    if item[1].get("type") == "https" and item[1].get("api") is True:
                        inv_hosts.append(f"https://{item[0]}")
    except Exception:
        pass
    for host in inv_hosts[:5]:
        try:
            sr = requests.get(f"{host}/api/v1/search", params={"q": query, "type": "video"}, headers={"User-Agent": UA}, timeout=10)
            if sr.status_code != 200:
                continue
            for v in sr.json()[:8]:
                vid = v.get("videoId")
                dur = int(v.get("lengthSeconds") or 0)
                uid = f"yt_{vid}"
                if not vid or uid in used_ids or dur < min_dur or dur > max_dur:
                    continue
                vr = requests.get(f"{host}/api/v1/videos/{vid}", headers={"User-Agent": UA}, timeout=10)
                if vr.status_code != 200:
                    continue
                for fs in (vr.json().get("formatStreams") or []):
                    surl = fs.get("url")
                    if surl and _download_direct(surl, out_path):
                        meta = verify_video(out_path, min_dur=min(15, min_dur))
                        if meta:
                            return uid, meta
        except Exception:
            continue

    piped_hosts = []
    try:
        pr = requests.get("https://piped-instances.kavin.rocks/", headers={"Accept": "application/json"}, timeout=10)
        if pr.status_code == 200:
            raw = pr.json()
            lst = raw if isinstance(raw, list) else raw.get("instances", [])
            for inst in lst[:6]:
                au = inst.get("api_url") or inst.get("apiUrl")
                if au:
                    piped_hosts.append(au.rstrip("/"))
    except Exception:
        pass
    for host in piped_hosts[:5]:
        try:
            sr = requests.get(f"{host}/search", params={"q": query, "filter": "videos"}, headers={"User-Agent": UA}, timeout=10)
            if sr.status_code != 200:
                continue
            for v in (sr.json().get("items") or [])[:8]:
                vpath = v.get("url") or ""
                vid = vpath.split("v=")[-1].split("&")[0] if "v=" in vpath else ""
                dur = int(v.get("duration") or 0)
                uid = f"yt_{vid}"
                if not vid or uid in used_ids or dur < min_dur or dur > max_dur:
                    continue
                vr = requests.get(f"{host}/streams/{vid}", headers={"User-Agent": UA}, timeout=10)
                if vr.status_code != 200:
                    continue
                for vs in (vr.json().get("videoStreams") or []):
                    if not vs.get("videoOnly") and vs.get("url"):
                        if _download_direct(vs["url"], out_path):
                            meta = verify_video(out_path, min_dur=min(15, min_dur))
                            if meta:
                                return uid, meta
        except Exception:
            continue
    return None, None


def dl_youtube_bonus(query, used_ids, min_dur, max_dur, out_path):
    print(f"[*] [Tier 5 - YouTube Bonus] Trying: '{query}'...")
    extra = ["--extractor-args", "youtube:player_client=tv,android_vr,mweb"]
    if shutil.which("deno"):
        extra.extend(["--js-runtimes", "deno"])
    if os.path.exists("cookies.txt"):
        extra.extend(["--cookies", "cookies.txt"])
    warp_proxy = os.environ.get("WARP_PROXY", "").strip()
    if warp_proxy:
        extra.extend(["--proxy", warp_proxy])
    try:
        meta_cmd = ["yt-dlp", "--no-warnings", "--dump-single-json", "--flat-playlist"] + extra + [f"ytsearch8:{query}"]
        p = subprocess.run(meta_cmd, capture_output=True, text=True, timeout=30)
        if p.returncode != 0:
            return None, None
        entries = (json.loads(p.stdout or "{}").get("entries") or [])
        for e in entries:
            vid = e.get("id")
            dur = int(e.get("duration") or 0)
            uid = f"yt_{vid}"
            if not vid or uid in used_ids:
                continue
            if dur > 0 and (dur < min_dur or dur > max_dur):
                continue
            if _run_ytdlp(f"https://www.youtube.com/watch?v={vid}", out_path, extra_args=extra):
                meta = verify_video(out_path, min_dur=min(15, min_dur))
                if meta:
                    return uid, meta
    except Exception:
        pass
    return None, None


def harvest_real_gameplay(raw_query, used_ids, out_path, is_short=True):
    queries = build_clean_queries(raw_query, is_short=is_short)
    used_set = set(str(x) for x in (used_ids or []))
    if is_short:
        dm_min, dm_max = 20, 180
        tt_min, tt_max = 15, 180
    else:
        dm_min, dm_max = 180, 1200
        tt_min, tt_max = 180, 600

    for q in queries:
        uid, meta = dl_dailymotion(q, used_set, dm_min, dm_max, out_path)
        if uid:
            print(f"[+] REAL GAMEPLAY LOCKED (Dailymotion): {uid} ({meta['size_mb']} MB, {meta['duration']}s)")
            return uid, meta, q

        uid, meta = dl_tiktok_tikwm(q, used_set, tt_min, tt_max, out_path)
        if uid:
            print(f"[+] REAL GAMEPLAY LOCKED (TikTok HD): {uid} ({meta['size_mb']} MB, {meta['duration']}s)")
            return uid, meta, q

    uid, meta = dl_twitch_clips(used_set, 15, dm_max, out_path)
    if uid:
        print(f"[+] REAL GAMEPLAY LOCKED (Twitch Clip): {uid} ({meta['size_mb']} MB, {meta['duration']}s)")
        return uid, meta, "twitch_garena_free_fire"

    for q in queries[:3]:
        uid, meta = dl_invidious_piped(q, used_set, dm_min, dm_max, out_path)
        if uid:
            print(f"[+] REAL GAMEPLAY LOCKED (Invidious/Piped): {uid} ({meta['size_mb']} MB, {meta['duration']}s)")
            return uid, meta, q

        uid, meta = dl_youtube_bonus(q, used_set, dm_min, dm_max, out_path)
        if uid:
            print(f"[+] REAL GAMEPLAY LOCKED (YouTube): {uid} ({meta['size_mb']} MB, {meta['duration']}s)")
            return uid, meta, q

    raise RuntimeError(f"FATAL: All real platforms (Dailymotion/TikTok/Twitch/Invidious/YouTube) failed for queries {queries}. Zero fallback policy enforced!")
