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
    "https://invidious.nerdvpn.de",
    "https://invidious.privacydev.net",
    "https://invidious.private.coffee"
]

PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi-libre.kavin.rocks",
    "https://pipedapi.leptons.xyz",
    "https://pipedapi.adminforge.de",
    "https://api.piped.private.coffee",
    "https://api.piped.yt",
    "https://pipedapi.drgns.space"
]

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

def get_ollama_base_url():
    raw_url = os.environ.get("OLLAMA_URL", "http://localhost:11434").strip()
    if "/api/" in raw_url:
        raw_url = raw_url.split("/api/")[0]
    return raw_url.rstrip("/")

def ensure_ollama_and_model():
    """Ensures Ollama server is alive and resolves exact installed model tag (eliminates 404 errors)."""
    base_url = get_ollama_base_url()
    tags_url = f"{base_url}/api/tags"

    # 1. Verify Ollama server is running; start if unreachable
    installed_models = []
    server_up = False
    for _ in range(3):
        try:
            r = requests.get(tags_url, timeout=5)
            if r.status_code == 200:
                server_up = True
                installed_models = [m.get("name") for m in r.json().get("models", []) if m.get("name")]
                break
        except Exception:
            time.sleep(1)

    if not server_up:
        print("[*] Ollama server not responding. Booting 'ollama serve' in background...")
        if shutil.which("ollama"):
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(15):
                try:
                    r = requests.get(tags_url, timeout=3)
                    if r.status_code == 200:
                        server_up = True
                        installed_models = [m.get("name") for m in r.json().get("models", []) if m.get("name")]
                        break
                except Exception:
                    time.sleep(1.5)

    if not server_up:
        raise RuntimeError("FATAL: Ollama service is not installed or failed to start on localhost:11434.")

    # 2. Match exact installed model name so /api/generate NEVER returns 404
    preferred = os.environ.get("OLLAMA_MODEL", "").strip()
    if preferred and preferred in installed_models:
        print(f"[+] Using configured Ollama model: {preferred}")
        return base_url, preferred

    if installed_models:
        # Prefer llama3.2 family if present, otherwise use first available model
        for m in installed_models:
            if "llama3.2" in m or "llama3" in m or "qwen" in m:
                print(f"[+] Auto-detected installed Ollama model: {m}")
                return base_url, m
        print(f"[+] Auto-detected installed Ollama model: {installed_models[0]}")
        return base_url, installed_models[0]

    # 3. No models installed yet -> pull fast CPU-friendly model automatically
    default_pull = preferred or "llama3.2:1b"
    print(f"[*] No models found in Ollama. Pulling '{default_pull}' automatically...")
    subprocess.run(["ollama", "pull", default_pull], check=True)
    return base_url, default_pull

def extract_json_object(raw_text):
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
        raise

def call_llama_json(prompt, json_schema, max_tokens=420, retries=2):
    base_url, model_name = ensure_ollama_and_model()
    gen_url = f"{base_url}/api/generate"

    format_mode = json_schema
    last_err = None

    for attempt in range(1, retries + 1):
        payload = {
            "model": model_name,
            "prompt": prompt,
            "format": format_mode,
            "stream": False,
            "options": {
                "temperature": 0.8,
                "num_predict": max_tokens,
                "num_thread": 2
            }
        }
        try:
            print(f"[*] Calling Ollama ({model_name}) [Attempt {attempt}/{retries}]...")
            res = requests.post(gen_url, json=payload, timeout=110)
            if res.status_code == 400 and isinstance(format_mode, dict):
                print("[!] Server requires basic JSON mode. Retrying with format='json'...")
                format_mode = "json"
                payload["format"] = "json"
                res = requests.post(gen_url, json=payload, timeout=110)

            if res.status_code >= 400:
                raise RuntimeError(f"HTTP {res.status_code}: {res.text[:200]}")

            raw = res.json().get("response", "").strip()
            return extract_json_object(raw)
        except Exception as e:
            last_err = e
            print(f"[!] Ollama attempt {attempt} error: {e}")
            time.sleep(2)

    raise RuntimeError(f"FATAL: AI model failed after {retries} attempts: {last_err}. Zero fallback policy enforced!")

def load_planner_blueprint():
    plan_data = {}
    for candidate in ["daily_plan.json", "task_plan.json"]:
        if os.path.exists(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    plan_data = json.load(f)
                print(f"[+] Loaded Step 1 plan from {candidate}")
                break
            except Exception:
                pass

    format_type = plan_data.get("format_type", plan_data.get("type", "short"))
    target_duration = float(plan_data.get("target_duration", random.uniform(28.0, 33.5)))
    blueprint = scout_live_viral_trend(format_type=format_type)
    blueprint["target_duration"] = target_duration
    return blueprint

def ai_invent_fresh_concept(blueprint):
    prompt = f"""You are the Lead Free Fire YouTube Strategist for DEVIL INSANITY (DEVIL-999).
Read this Pillar & Live Trend Blueprint and invent ONE 100% NEW video concept and search query.

{blueprint['prompt_context']}

STRICT RULES:
1. Never repeat any query or title from the Banned list above.
2. 'search_query' must be 5 to 7 clean English words to find a REAL 60FPS Free Fire gameplay video.
3. 'title' must be catchy, under 55 chars, relevant to Pillar + Weapon + Strategy, ending with #shorts #freefire.
4. Reply ONLY with valid JSON keys: topic_angle, title, search_query, visual_focus."""

    concept = call_llama_json(prompt, CONCEPT_JSON_SCHEMA, max_tokens=200, retries=2)
    print(f"[+] AI Invented Title: {concept['title']}")
    print(f"[+] AI Search Query: '{concept['search_query']}'")
    return concept

def prepare_cookies_file():
    if os.path.exists("cookies.txt") and os.path.getsize("cookies.txt") > 30:
        return "cookies.txt"
    cookies_env = os.environ.get("YOUTUBE_COOKIES", "").strip()
    if len(cookies_env) > 30:
        with open("cookies.txt", "w", encoding="utf-8") as f:
            f.write(cookies_env)
        print("[+] Injected cookies.txt from YOUTUBE_COOKIES secret.")
        return "cookies.txt"
    return None

def get_video_duration(filepath):
    if shutil.which("ffprobe"):
        try:
            cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", filepath
            ]
            out = subprocess.check_output(cmd, text=True).strip()
            return float(out)
        except Exception:
            return 0.0
    # Fallback header sanity check only if ffprobe binary is missing on PATH
    try:
        with open(filepath, "rb") as f:
            head = f.read(64)
        if b"ftyp" in head or b"webm" in head.lower() or b"\x1a\x45\xdf\xa3" in head:
            return 15.0
    except Exception:
        pass
    return 0.0

def is_valid_video_file(filepath):
    if not os.path.exists(filepath) or os.path.getsize(filepath) < 350000:
        return False
    return get_video_duration(filepath) >= 4.0

def download_ytdlp(query, used_video_ids):
    print(f"[*] [Tier 1] yt-dlp searching top 5 un-used YouTube clips for: '{query}'...")
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

    candidates = []
    try:
        with yt_dlp.YoutubeDL(search_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            for entry in info.get("entries", []):
                vid = entry.get("id")
                if vid and vid not in used_video_ids:
                    candidates.append((vid, entry.get("title", "")))
    except Exception as e:
        print(f"[!] Tier 1 Search Notice: {e}")

    for vid, vtitle in candidates:
        url = f"https://www.youtube.com/watch?v={vid}"
        print(f"[*] Downloading un-used clip [{vid}]: {vtitle[:45]}...")
        dl_opts = {
            "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]/best[ext=mp4]/best",
            "outtmpl": "raw_gameplay.mp4",
            "overwrites": True,
            "quiet": False,
            "sleep_requests": 1,
            "extractor_args": {
                "youtube": {
                    "player_client": ["web_safari", "tv_embedded", "android_creator", "ios"],
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
            if is_valid_video_file("raw_gameplay.mp4"):
                print(f"[+] Tier 1 Success: Verified gameplay ({vid})!")
                return vid
        except Exception as e:
            print(f"[!] Tier 1 Download Notice ({vid}): {e}")
        if os.path.exists("raw_gameplay.mp4"):
            os.remove("raw_gameplay.mp4")
    return None

def download_piped(query, used_video_ids):
    print(f"[*] [Tier 2] Querying Piped API nodes for: '{query}'...")
    nodes = list(PIPED_INSTANCES)
    random.shuffle(nodes)
    for node in nodes:
        try:
            r = requests.get(f"{node}/search?q={requests.utils.quote(query)}&filter=videos", timeout=10)
            if r.status_code != 200:
                continue
            for item in r.json().get("items", [])[:4]:
                raw_url = item.get("url", "")
                if "v=" not in raw_url:
                    continue
                vid = raw_url.split("v=")[-1].split("&")[0]
                if vid in used_video_ids:
                    continue
                sr = requests.get(f"{node}/streams/{vid}", timeout=10)
                if sr.status_code != 200:
                    continue
                streams = sr.json().get("videoStreams", [])
                mp4s = [s for s in streams if s.get("format") == "MPEG_4" and not s.get("videoOnly")]
                if not mp4s:
                    mp4s = [s for s in streams if s.get("format") == "MPEG_4"]
                if mp4s:
                    vr = requests.get(mp4s[0].get("url"), stream=True, timeout=35)
                    if vr.status_code == 200:
                        with open("raw_gameplay.mp4", "wb") as f:
                            for chunk in vr.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                        if is_valid_video_file("raw_gameplay.mp4"):
                            print(f"[+] Tier 2 Success via Piped ({vid})!")
                            return vid
                        if os.path.exists("raw_gameplay.mp4"):
                            os.remove("raw_gameplay.mp4")
        except Exception as e:
            print(f"[!] Piped ({node}) notice: {e}")
    return None

def download_invidious(query, used_video_ids):
    print(f"[*] [Tier 3] Querying Invidious API nodes for: '{query}'...")
    nodes = list(INVIDIOUS_INSTANCES)
    random.shuffle(nodes)
    for node in nodes:
        try:
            r = requests.get(f"{node}/api/v1/search?q={requests.utils.quote(query)}&type=video", timeout=10)
            if r.status_code != 200:
                continue
            items = [it for it in r.json() if it.get("videoId") and it.get("videoId") not in used_video_ids]
            for item in items[:3]:
                vid = item["videoId"]
                vr = requests.get(f"{node}/api/v1/videos/{vid}", timeout=10)
                if vr.status_code != 200:
                    continue
                stream_url = None
                for s in vr.json().get("formatStreams", []):
                    if s.get("container") == "mp4":
                        stream_url = s.get("url")
                if stream_url:
                    sr = requests.get(stream_url, stream=True, timeout=35)
                    if sr.status_code == 200:
                        with open("raw_gameplay.mp4", "wb") as f:
                            for chunk in sr.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                        if is_valid_video_file("raw_gameplay.mp4"):
                            print(f"[+] Tier 3 Success via Invidious ({vid})!")
                            return vid
                        if os.path.exists("raw_gameplay.mp4"):
                            os.remove("raw_gameplay.mp4")
        except Exception as e:
            print(f"[!] Invidious ({node}) notice: {e}")
    return None

def download_dailymotion(query, used_video_ids):
    print(f"[*] [Tier 4] Querying Unblocked Dailymotion HD API for: '{query}'...")
    try:
        api_url = f"https://api.dailymotion.com/videos?search={requests.utils.quote(query)}&limit=10&fields=id,title,duration,url"
        r = requests.get(api_url, timeout=12)
        if r.status_code != 200:
            return None
        for item in r.json().get("list", []):
            did = f"dm_{item.get('id', '')}"
            dur = int(item.get("duration", 0) or 0)
            if did in used_video_ids or dur < 12 or dur > 1200:
                continue
            vurl = item.get("url")
            if not vurl:
                continue
            print(f"[*] Downloading Dailymotion Free Fire clip [{did}]: {item.get('title', '')[:45]}...")
            dl_opts = {
                "format": "best[height<=1080]/best",
                "outtmpl": "raw_gameplay.mp4",
                "merge_output_format": "mp4",
                "overwrites": True,
                "quiet": False
            }
            try:
                with yt_dlp.YoutubeDL(dl_opts) as ydl:
                    ydl.download([vurl])
                if is_valid_video_file("raw_gameplay.mp4"):
                    print(f"[+] Tier 4 Success via Dailymotion ({did})!")
                    return did
            except Exception as e:
                print(f"[!] Dailymotion dl notice ({did}): {e}")
            if os.path.exists("raw_gameplay.mp4"):
                os.remove("raw_gameplay.mp4")
    except Exception as e:
        print(f"[!] Tier 4 Dailymotion API notice: {e}")
    return None

def download_reddit_freefire(used_video_ids):
    print("[*] [Tier 5] Harvesting fresh unblocked Free Fire clips from Reddit...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36"}
    for sub in ["freefire", "freefireclips"]:
        for sort in ["hot", "new", "top"]:
            try:
                r = requests.get(f"https://www.reddit.com/r/{sub}/{sort}.json?limit=25&t=month", headers=headers, timeout=10)
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
                            if is_valid_video_file("raw_gameplay.mp4"):
                                print(f"[+] Tier 5 Success via Reddit ({pid})!")
                                return pid
                            if os.path.exists("raw_gameplay.mp4"):
                                os.remove("raw_gameplay.mp4")
            except Exception as e:
                print(f"[!] Reddit ({sub}/{sort}) notice: {e}")
    return None

def ai_write_full_script(blueprint, concept, real_duration):
    target_dur = round(blueprint.get("target_duration", 30.5), 1)
    step = round(target_dur / 7.0, 1)
    timestamps = [round(i * step, 1) for i in range(7)]

    prompt = f"""Write the complete 7-scene commentary script for this real downloaded Free Fire clip.
Channel: DEVIL INSANITY (Tag: DEVIL-999)
Title: {concept['title']}
Pillar: {blueprint['pillar_name']} | Weapon: {blueprint['weapon']} (Headshot Damage: {blueprint['damage']})
Psychology Hook: {blueprint['psychology_strategy']}
Angle: {concept['topic_angle']}
Visual Focus: {concept['visual_focus']}
Raw Clip Duration: {real_duration:.1f}s | Edited Target Duration: {target_dur}s

REQUIREMENTS:
1. Create EXACTLY 7 scenes with timestamps: {timestamps}.
2. 'narration': Punchy Pakistani/Indian Roman Urdu gamer commentary (human mobile player vibe, 1-2 short sentences per scene, NO emojis, NO fake 1v1 or upload promises).
3. 'english_subtitle': Clean English translation per scene for subtitles.
4. 'focus_cue': Short visual emphasis tag (e.g. "red_damage_zoom", "crosshair_lock", "gloo_flick").
5. 'pinned_comment': Engaging viewer question about {blueprint['weapon']} and {concept['topic_angle']}.
6. Output ONLY valid JSON keys: title, description, tags, pinned
