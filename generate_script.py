import os
import sys
import json
import time
import shutil
import random
import subprocess
import requests
import yt_dlp
from niche_brain import scout_live_viral_trend, save_history_entry, load_history

INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://yewtu.be",
    "https://vid.priv.au",
    "https://invidious.nerdvpn.de",
    "https://inv.tux.pizza"
]

PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.adminforge.de",
    "https://api.piped.private.coffee"
]

# Strict Ollama JSON Schemas (Eliminates "Expecting ',' delimiter" errors forever)
CONCEPT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "topic_angle": {"type": "string"},
        "title": {"type": "string"},
        "search_query": {"type": "string"},
        "visual_focus": {"type": "string"}
    },
    "required": ["topic_angle", "title", "search_query", "visual_focus"]
}

SCRIPT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "pinned_comment": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "time": {"type": "number"},
                    "narration": {"type": "string"},
                    "english_subtitle": {"type": "string"},
                    "focus_cue": {"type": "string"}
                },
                "required": ["time", "narration", "english_subtitle", "focus_cue"]
            }
        }
    },
    "required": ["title", "description", "tags", "pinned_comment", "scenes"]
}

def call_llama_json(prompt, json_schema, max_tokens=420, retries=2):
    """Calls local Ollama Llama 3.2 with hardware-enforced JSON Schema grammar."""
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
    model_name = os.environ.get("OLLAMA_MODEL", "llama3.2")

    payload = {
        "model": model_name,
        "prompt": prompt,
        "format": json_schema,
        "stream": False,
        "options": {
            "temperature": 0.8,
            "num_predict": max_tokens,
            "num_thread": 2
        }
    }

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            print(f"[*] Calling Llama AI ({model_name}) [Attempt {attempt}/{retries}]...")
            res = requests.post(ollama_url, json=payload, timeout=90)
            res.raise_for_status()
            raw = res.json().get("response", "").strip()
            parsed = json.loads(raw)
            return parsed
        except Exception as e:
            last_err = e
            print(f"[!] Llama attempt {attempt} error: {e}")
            time.sleep(2)

    raise RuntimeError(f"FATAL: AI model failed to generate structured output after {retries} attempts: {last_err}. Zero fallback policy enforced!")

def load_planner_blueprint():
    """Reads daily plan from Step 1 (daily_task_planner.py) or scouts fresh live Pillar Blueprint."""
    plan_data = {}
    for candidate in ["daily_plan.json", "task_plan.json"]:
        if os.path.exists(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    plan_data = json.load(f)
                print(f"[+] Loaded Step 1 Planner blueprint from {candidate}")
                break
            except Exception:
                pass

    format_type = plan_data.get("format_type", plan_data.get("type", "short"))
    target_duration = float(plan_data.get("target_duration", random.uniform(28.0, 34.0)))
    blueprint = scout_live_viral_trend(format_type=format_type)
    blueprint["target_duration"] = target_duration
    return blueprint

def ai_invent_fresh_concept(blueprint):
    """Step A: AI reads the 6-Pillar Blueprint + Live Trends and invents a brand-new query & concept."""
    prompt = f"""You are the Lead Free Fire YouTube Strategist for DEVIL INSANITY (DEVIL-999).
Read this Pillar & Live Trend Blueprint and invent ONE 100% NEW video concept and YouTube search query.

{blueprint['prompt_context']}

STRICT RULES:
1. Never repeat any query or title from the Banned list above.
2. 'search_query' must be 5 to 8 clean English keywords that find a REAL high-FPS Free Fire gameplay video (NO fake words, NO quotes).
3. 'title' must be high-CTR, under 55 chars, relevant to the Pillar + Weapon + Psychology strategy, ending with #shorts #freefire (or #freefire for long).
4. Return ONLY valid JSON matching the schema."""

    concept = call_llama_json(prompt, CONCEPT_JSON_SCHEMA, max_tokens=180, retries=2)
    print(f"[+] AI Invented Topic: {concept['title']}")
    print(f"[+] AI Search Query: '{concept['search_query']}'")
    return concept

def prepare_cookies_file():
    if os.path.exists("cookies.txt") and os.path.getsize("cookies.txt") > 30:
        return "cookies.txt"
    cookies_env = os.environ.get("YOUTUBE_COOKIES", "").strip()
    if len(cookies_env) > 30:
        with open("cookies.txt", "w", encoding="utf-8") as f:
            f.write(cookies_env)
        print("[+] Configured cookies.txt from YOUTUBE_COOKIES secret.")
        return "cookies.txt"
    return None

def get_video_duration(filepath):
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", filepath
        ]
        out = subprocess.check_output(cmd, text=True).strip()
        return float(out)
    except Exception:
        return 0.0

def download_ytdlp(query, used_video_ids):
    """Tier 1: yt-dlp with multi-client rotation, JS runtime detection, and duplicate-ID skip."""
    print(f"[*] [Tier 1] yt-dlp searching top 5 fresh results for: '{query}'...")
    cookie_file = prepare_cookies_file()
    js_runtime = "deno" if shutil.which("deno") else ("node" if shutil.which("node") else None)

    search_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "default_search": "ytsearch5",
        "noplaylist": True
    }
    if cookie_file:
        search_opts["cookiefile"] = cookie_file

    candidate_ids = []
    try:
        with yt_dlp.YoutubeDL(search_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            for entry in info.get("entries", []):
                vid = entry.get("id")
                if vid and vid not in used_video_ids:
                    candidate_ids.append((vid, entry.get("title", "")))
    except Exception as e:
        print(f"[!] Tier 1 Search Notice: {e}")

    for vid, vtitle in candidate_ids:
        url = f"https://www.youtube.com/watch?v={vid}"
        print(f"[*] Attempting download of un-used clip [{vid}]: {vtitle[:45]}...")
        dl_opts = {
            "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]/best[ext=mp4]/best",
            "outtmpl": "raw_gameplay.mp4",
            "overwrites": True,
            "quiet": False,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android_creator", "tv_embedded", "ios", "web_creator"],
                    "player_skip": ["configs"]
                }
            }
        }
        if cookie_file:
            dl_opts["cookiefile"] = cookie_file
        if js_runtime:
            dl_opts["js_runtimes"] = {js_runtime: {}}

        try:
            with yt_dlp.YoutubeDL(dl_opts) as ydl:
                ydl.download([url])
            if os.path.exists("raw_gameplay.mp4") and os.path.getsize("raw_gameplay.mp4") > 500000:
                print(f"[+] Tier 1 Success: Downloaded real gameplay ({vid})!")
                return vid
        except Exception as e:
            print(f"[!] Tier 1 Download Notice ({vid}): {e}")
            if os.path.exists("raw_gameplay.mp4"):
                os.remove("raw_gameplay.mp4")
    return None

def download_invidious(query, used_video_ids):
    """Tier 2: Public Invidious REST API bypasses datacenter bot check."""
    print(f"[*] [Tier 2] Querying Invidious API nodes for: '{query}'...")
    nodes = list(INVIDIOUS_INSTANCES)
    random.shuffle(nodes)
    for node in nodes:
        try:
            r = requests.get(f"{node}/api/v1/search?q={requests.utils.quote(query)}&type=video", timeout=12)
            if r.status_code != 200:
                continue
            items = [it for it in r.json() if it.get("videoId") and it.get("videoId") not in used_video_ids]
            for item in items[:3]:
                vid = item["videoId"]
                vr = requests.get(f"{node}/api/v1/videos/{vid}", timeout=12)
                if vr.status_code != 200:
                    continue
                vdata = vr.json()
                stream_url = None
                for s in vdata.get("formatStreams", []):
                    if s.get("container") == "mp4":
                        stream_url = s.get("url")
                if stream_url:
                    sr = requests.get(stream_url, stream=True, timeout=40)
                    if sr.status_code == 200:
                        with open("raw_gameplay.mp4", "wb") as f:
                            for chunk in sr.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                        if os.path.exists("raw_gameplay.mp4") and os.path.getsize("raw_gameplay.mp4") > 500000:
                            print(f"[+] Tier 2 Success via Invidious ({vid})!")
                            return vid
        except Exception as e:
            print(f"[!] Invidious ({node}) notice: {e}")
    return None

def download_piped(query, used_video_ids):
    """Tier 3: Public Piped API proxy stream fallback-free alternative."""
    print(f"[*] [Tier 3] Querying Piped API nodes for: '{query}'...")
    nodes = list(PIPED_INSTANCES)
    random.shuffle(nodes)
    for node in nodes:
        try:
            r = requests.get(f"{node}/search?q={requests.utils.quote(query)}&filter=videos", timeout=12)
            if r.status_code != 200:
                continue
            items = r.json().get("items", [])
            for item in items[:4]:
                raw_url = item.get("url", "")
                if "v=" not in raw_url:
                    continue
                vid = raw_url.split("v=")[-1].split("&")[0]
                if vid in used_video_ids:
                    continue
                sr = requests.get(f"{node}/streams/{vid}", timeout=12)
                if sr.status_code != 200:
                    continue
                streams = sr.json().get("videoStreams", [])
                mp4_streams = [s for s in streams if s.get("format") == "MPEG_4" and not s.get("videoOnly")]
                if not mp4_streams:
                    mp4_streams = [s for s in streams if s.get("format") == "MPEG_4"]
                if mp4_streams:
                    stream_url = mp4_streams[0].get("url")
                    vr = requests.get(stream_url, stream=True, timeout=40)
                    if vr.status_code == 200:
                        with open("raw_gameplay.mp4", "wb") as f:
                            for chunk in vr.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                        if os.path.exists("raw_gameplay.mp4") and os.path.getsize("raw_gameplay.mp4") > 500000:
                            print(f"[+] Tier 3 Success via Piped ({vid})!")
                            return vid
        except Exception as e:
            print(f"[!] Piped ({node}) notice: {e}")
    return None

def download_reddit_freefire(used_video_ids):
    """Tier 4: Unblocked 60FPS real Free Fire clips from Reddit communities."""
    print("[*] [Tier 4] Harvesting fresh Free Fire clips from Reddit...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FreeFireHarvest/4.0"}
    for sub in ["freefire", "freefireclips"]:
        for sort in ["hot", "new"]:
            try:
                r = requests.get(f"https://www.reddit.com/r/{sub}/{sort}.json?limit=25", headers=headers, timeout=10)
                if r.status_code != 200:
                    continue
                for post in r.json().get("data", {}).get("children", []):
                    pdata = post.get("data", {})
                    pid = f"reddit_{pdata.get('id', '')}"
                    if pid in used_video_ids or not pdata.get("is_video"):
                        continue
                    v_url = pdata.get("media", {}).get("reddit_video", {}).get("fallback_url")
                    if v_url:
                        vr = requests.get(v_url, headers=headers, stream=True, timeout=30)
                        if vr.status_code == 200:
                            with open("raw_gameplay.mp4", "wb") as f:
                                for chunk in vr.iter_content(chunk_size=1024 * 1024):
                                    if chunk:
                                        f.write(chunk)
                            if os.path.exists("raw_gameplay.mp4") and os.path.getsize("raw_gameplay.mp4") > 500000:
                                print(f"[+] Tier 4 Success via Reddit ({pid})!")
                                return pid
            except Exception as e:
                print(f"[!] Reddit ({sub}/{sort}) notice: {e}")
    return None

def ai_write_full_script(blueprint, concept, real_duration):
    """Step C: AI writes full 7-scene Roman Urdu voiceover + English subtitles synced to downloaded clip."""
    target_dur = round(blueprint.get("target_duration", 30.5), 1)
    step = round(target_dur / 7.0, 1)
    timestamps = [round(i * step, 1) for i in range(7)]

    prompt = f"""Write the complete 7-scene commentary script for this real downloaded Free Fire clip.
Channel: DEVIL INSANITY (Pro Tag: DEVIL-999)
Title: {concept['title']}
Pillar: {blueprint['pillar_name']} | Weapon: {blueprint['weapon']} (Headshot Damage: {blueprint['damage']})
Psychological Hook: {blueprint['psychology_strategy']}
Angle: {concept['topic_angle']}
Visual Focus: {concept['visual_focus']}
Raw Clip Duration: {real_duration:.1f}s | Target Edited Short Duration: {target_dur}s

REQUIREMENTS:
1. Create EXACTLY 7 scenes with timestamps: {timestamps}.
2. 'narration': Natural, punchy Pakistani/Indian Roman Urdu gamer commentary (human mobile player vibe, 1-2 short sentences per scene, ZERO emojis, NEVER claim fake personal face-cam or fake 1v1 promises).
3. 'english_subtitle': Clean English translation of each scene for international viewers.
4. 'focus_cue': Short FFmpeg visual emphasis note (e.g., "red_damage_zoom", "crosshair_lock", "gloo_flick").
5. 'pinned_comment': Engaging viewer question/challenge related to {blueprint['weapon']} and {concept['topic_angle']}.
6. Output ONLY valid JSON matching the schema."""

    script_obj = call_llama_json(prompt, SCRIPT_JSON_SCHEMA, max_tokens=480, retries=2)
    return script_obj

def generate_script():
    # 1. Read Pillars & Live Signals from niche_brain.py
    blueprint = load_planner_blueprint()
    history = load_history()
    used_ids = set(history.get("video_ids", []))

    # 2. AI invents unique Concept & Search Query from Pillars
    concept = ai_invent_fresh_concept(blueprint)
    query = concept["search_query"]

    # 3. Download 100% REAL fresh gameplay (Zero Fallback)
    if os.path.exists("raw_gameplay.mp4"):
        os.remove("raw_gameplay.mp4")

    downloaded_id = download_ytdlp(query, used_ids)
    if not downloaded_id:
        downloaded_id = download_invidious(query, used_ids)
    if not downloaded_id:
        downloaded_id = download_piped(query, used_ids)
    if not downloaded_id:
        downloaded_id = download_reddit_freefire(used_ids)

    if not downloaded_id or not os.path.exists("raw_gameplay.mp4") or os.path.getsize("raw_gameplay.mp4") < 500000:
        raise RuntimeError(f"FATAL: All 4 real video streams failed for '{query}'. Zero fallback policy enforced!")

    real_dur = get_video_duration("raw_gameplay.mp4")
    size_mb = os.path.getsize("raw_gameplay.mp4") / (1024 * 1024)
    print(f"[+] 100% REAL GAMEPLAY LOCKED: raw_gameplay.mp4 ({size_mb:.2f} MB, {real_dur:.1f}s)")

    # 4. AI writes full 7-scene Roman Urdu + English script based on Pillar + Real Video
    ai_script = ai_write_full_script(blueprint, concept, real_dur)

    final_payload = {
        "title": ai_script.get("title", concept["title"]),
        "description": ai_script.get("description", ""),
        "tags": ai_script.get("tags", ["freefire", "shorts", "headshot", "gaming"]),
        "pinned_comment": ai_script.get("pinned_comment", ""),
        "pillar_id": blueprint["pillar_id"],
        "pillar_name": blueprint["pillar_name"],
        "psychology_strategy": blueprint["psychology_strategy"],
        "search_query": query,
        "source_video_id": downloaded_id,
        "weapon": blueprint["weapon"],
        "damage": blueprint["damage"],
        "target_duration": blueprint.get("target_duration", 30.5),
        "player_tag": "DEVIL-999",
        "scenes": ai_script["scenes"]
    }

    with open("current_script.json", "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2, ensure_ascii=False)

    # 5. Save query, video_id, title & pillar to permanent history to block repetition
    save_history_entry(
        query=query,
        video_id=downloaded_id,
        title=final_payload["title"],
        pillar_id=blueprint["pillar_id"]
    )
    print("[+] Success: 100% AI Pillar Script + Real Gameplay saved to current_script.json!")

if __name__ == "__main__":
    generate_script()
