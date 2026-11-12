import os
import json
import random
import requests
import subprocess
import yt_dlp
from niche_brain import NicheBrain

brain = NicheBrain()

INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://yewtu.be",
    "https://vid.priv.au",
    "https://invidious.nerdvpn.de"
]

def get_cookies_arg():
    # Check if cookies file exists or passed via secret
    if os.path.exists("cookies.txt") and os.path.getsize("cookies.txt") > 10:
        return ["--cookies", "cookies.txt"]
    cookies_env = os.environ.get("YOUTUBE_COOKIES", "")
    if len(cookies_env) > 20:
        with open("cookies.txt", "w", encoding="utf-8") as f:
            f.write(cookies_env)
        return ["--cookies", "cookies.txt"]
    return []

def harvest_via_ytdlp(query):
    print(f"[*] [Tier 1] Attempting yt-dlp with client rotation for: '{query}'...")
    cookie_args = get_cookies_arg()
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'raw_gameplay.mp4',
        'quiet': False,
        'no_warnings': False,
        'default_search': 'ytsearch1',
        'noplaylist': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android_creator', 'tv_embedded', 'ios', 'web_creator'],
                'player_skip': ['configs']
            }
        }
    }
    if cookie_args:
        ydl_opts['cookiefile'] = 'cookies.txt'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"ytsearch1:{query}"])
        if os.path.exists("raw_gameplay.mp4") and os.path.getsize("raw_gameplay.mp4") > 500000:
            print("[+] Tier 1 Success: Real YouTube gameplay downloaded!")
            return True
    except Exception as e:
        print(f"[!] Tier 1 Notice: {e}")
    return False

def harvest_via_invidious_api(query):
    print(f"[*] [Tier 2] Bypassing datacenter block via Invidious Stream API...")
    random.shuffle(INVIDIOUS_INSTANCES)
    for instance in INVIDIOUS_INSTANCES:
        try:
            search_url = f"{instance}/api/v1/search?q={requests.utils.quote(query)}&type=video"
            resp = requests.get(search_url, timeout=12)
            if resp.status_code != 200:
                continue
            items = resp.json()
            if not items:
                continue
            video_id = items[0].get("videoId")
            if not video_id:
                continue

            # Fetch direct video stream
            vid_res = requests.get(f"{instance}/api/v1/videos/{video_id}", timeout=12)
            if vid_res.status_code != 200:
                continue
            v_data = vid_res.json()
            stream_url = None
            for s in v_data.get("formatStreams", []):
                if s.get("container") == "mp4":
                    stream_url = s.get("url")
                    break

            if stream_url:
                print(f"[+] Found direct stream from {instance}. Downloading MP4...")
                stream_res = requests.get(stream_url, stream=True, timeout=30)
                if stream_res.status_code == 200:
                    with open("raw_gameplay.mp4", "wb") as f:
                        for chunk in stream_res.iter_content(chunk_size=1024*1024):
                            f.write(chunk)
                    if os.path.exists("raw_gameplay.mp4") and os.path.getsize("raw_gameplay.mp4") > 500000:
                        print("[+] Tier 2 Success: 100% Real gameplay downloaded via Invidious!")
                        return True
        except Exception as e:
            print(f"[!] Invidious node {instance} error: {e}")
            continue
    return False

def harvest_via_reddit_freefire():
    print("[*] [Tier 3] Scraping Fresh 60FPS Free Fire Gameplay from Reddit...")
    subreddits = ["freefire", "freefireclips"]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FreeFireHarvester/1.0"}
    for sub in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=25"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200:
                continue
            data = res.json()
            posts = data.get("data", {}).get("children", [])
            for post in posts:
                p_data = post.get("data", {})
                if p_data.get("is_video"):
                    video_url = p_data.get("media", {}).get("reddit_video", {}).get("fallback_url")
                    if video_url:
                        print(f"[+] Found 60FPS Reddit Free Fire clip: {p_data.get('title')[:40]}...")
                        v_res = requests.get(video_url, stream=True, headers=headers, timeout=25)
                        if v_res.status_code == 200:
                            with open("raw_gameplay.mp4", "wb") as f:
                                for chunk in v_res.iter_content(chunk_size=1024*1024):
                                    f.write(chunk)
                            if os.path.exists("raw_gameplay.mp4") and os.path.getsize("raw_gameplay.mp4") > 500000:
                                print("[+] Tier 3 Success: Real Reddit Free Fire gameplay secured!")
                                return True
        except Exception as e:
            print(f"[!] Reddit scraper notice: {e}")
    return False

def generate_script():
    trend = brain.get_daily_trend()
    query = trend["search_query"]
    print(f"[*] REAL HARVESTER 11.0: Harvesting 100% Fresh Gameplay for: '{query}'")

    # Step 1: Try yt-dlp (with cookies if available)
    success = harvest_via_ytdlp(query)
    
    # Step 2: Try Invidious API
    if not success:
        success = harvest_via_invidious_api(query)

    # Step 3: Try Reddit Free Fire Clutches
    if not success:
        success = harvest_via_reddit_freefire()

    # STRICT ZERO FALLBACK ENFORCEMENT
    if not success or not os.path.exists("raw_gameplay.mp4") or os.path.getsize("raw_gameplay.mp4") < 500000:
        raise RuntimeError(f"FATAL: All 3 real gameplay streams failed for '{query}'. Zero fallback policy enforced!")

    print(f"[+] REAL GAMEPLAY READY: raw_gameplay.mp4 ({os.path.getsize('raw_gameplay.mp4') / (1024*1024):.2f} MB)")
    
    # Generate current_script.json
    script_data = {
        "title": trend["title"],
        "search_query": query,
        "scenes": [
            {"time": 0.0, "narration": "Agar tumhara one tap nahi lag raha to ye angle miss mat karna."},
            {"time": 4.5, "narration": "Crosshair ko hamesha chest ke barabar lock rakho aur smooth drag do."},
            {"time": 9.0, "narration": "Notice karo headshot damage crystal clear red numbers ke sath aata hai."},
            {"time": 14.0, "narration": "Ye settings lagane ke baad custom room mein tumhein koi beat nahi kar sakega."},
            {"time": 19.0, "narration": "Next match mein test karo aur comment mein apna favorite gun batao."}
        ]
    }
    with open("current_script.json", "w", encoding="utf-8") as f:
        json.dump(script_data, f, indent=2)
    print("[+] Script saved to current_script.json!")

if __name__ == "__main__":
    generate_script()
