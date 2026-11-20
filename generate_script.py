import json
import os
import re
import shutil
import subprocess
import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
TEXT_MODEL = os.environ.get("TEXT_MODEL", "qwen2.5:3b")
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY", "").strip()

TOPIC_FILE = "trending_topic.json"
SCRIPT_FILE = "current_script.json"
CLIP_DIR = "stock_clips"

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "hook_badge": {"type": "string"},
        "pinned_comment": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "beats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "narration": {"type": "string"},
                    "search_query": {"type": "string"},
                    "ai_prompt": {"type": "string"},
                },
                "required": ["narration", "search_query", "ai_prompt"],
            },
        },
    },
    "required": ["title", "description", "hook_badge", "pinned_comment", "tags", "beats"],
}


def load_topic():
    if os.path.exists(TOPIC_FILE):
        with open(TOPIC_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "theme": "OCEAN",
        "topic": "What Happens To Your Body 3000 Meters Under The Ocean",
        "angle": "crush pressure and pitch blackness",
        "badge": "3,000M DEEP",
    }


def write_documentary_script(meta):
    prompt = (
        f"You are an elite viral YouTube Shorts documentary writer. Topic: '{meta['topic']}'. Angle: '{meta['angle']}'. "
        "Write a gripping 35-second 6-beat narration script in crisp natural English. "
        "Rules: "
        "1) Beat 0 MUST drop mid-danger in the very first sentence with zero intro greetings. "
        "2) Beats 1-3 escalate tension with real numbers or physical sensory details. "
        "3) Beat 4 is the chilling climax reveal. "
        "4) Beat 5 MUST end mid-thought so it loops seamlessly back into Beat 0. "
        "5) Keep EACH beat narration between 11 and 16 words (total ~80 words). "
        "6) For each beat provide search_query (2-3 simple nature/space/ocean keywords for stock video) and ai_prompt (photorealistic 9:16 dark cinematic scene description with camera motion, NO text, NO faces close-up). "
        "7) Title must be under 65 chars, punchy curiosity gap, NO emojis, NO generic words like 'unveiled' or 'shocking truth'. "
        "8) pinned_comment must ask a gripping debate question to spark replies."
    )
    payload = {
        "model": TEXT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": SCRIPT_SCHEMA,
        "keep_alive": "0",
        "options": {"num_ctx": 4096, "num_predict": 950, "temperature": 0.65},
    }
    for attempt in range(1, 4):
        try:
            print(f"[*] Calling {TEXT_MODEL} (attempt {attempt})...", flush=True)
            r = requests.post(OLLAMA_URL, json=payload, timeout=180)
            r.raise_for_status()
            data = json.loads(r.json()["message"]["content"])
            beats = data.get("beats") or []
            if len(beats) >= 5:
                data["beats"] = beats[:6]
                return data
        except Exception as e:
            print(f"[!] Script retry {attempt}: {e}", flush=True)
    raise RuntimeError("Failed to generate valid 6-beat documentary script")


def search_pixabay(query, theme, seen_urls):
    if not PIXABAY_KEY:
        return None
    cat = "science" if theme == "SPACE" else "nature"
    for q_try, use_cat in [(query, cat), (query, ""), (theme.lower() + " dark", "")]:
        params = {
            "key": PIXABAY_KEY,
            "q": q_try[:90],
            "video_type": "film",
            "safesearch": "true",
            "order": "popular",
            "per_page": 12,
        }
        if use_cat:
            params["category"] = use_cat
        try:
            r = requests.get("https://pixabay.com/api/videos/", params=params, timeout=20)
            if r.status_code != 200:
                continue
            for hit in r.json().get("hits", []):
                vids = hit.get("videos", {})
                cand = vids.get("large") or vids.get("medium") or vids.get("small") or {}
                url = cand.get("url")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    return url
        except Exception:
            continue
    return None


def search_nasa(query, seen_urls):
    for q_try in [query, "black hole space nebula", "earth ocean storm from space"]:
        try:
            r = requests.get(
                "https://images-api.nasa.gov/search",
                params={"q": q_try, "media_type": "video"},
                timeout=20,
            )
            if r.status_code != 200:
                continue
            for item in r.json().get("collection", {}).get("items", [])[:8]:
                nid = (item.get("data") or [{}])[0].get("nasa_id")
                if not nid:
                    continue
                ar = requests.get(f"https://images-api.nasa.gov/asset/{nid}", timeout=15)
                if ar.status_code != 200:
                    continue
                for f in ar.json().get("collection", {}).get("items", []):
                    href = f.get("href", "")
                    if href.endswith(".mp4") and "mobile" not in href.lower() and href not in seen_urls:
                        seen_urls.add(href)
                        return href
        except Exception:
            continue
    return None


def download_and_normalize(url, out_path):
    tmp_raw = out_path + ".raw.mp4"
    with requests.get(url, stream=True, timeout=45) as r:
        r.raise_for_status()
        with open(tmp_raw, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", tmp_raw, "-t", "6.5",
        "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30",
        "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p",
        out_path,
    ]
    subprocess.run(cmd, check=True)
    os.remove(tmp_raw)


def main():
    meta = load_topic()
    script = write_documentary_script(meta)
    shutil.rmtree(CLIP_DIR, ignore_errors=True)
    os.makedirs(CLIP_DIR, exist_ok=True)

    seen_urls = set()
    beats = script["beats"]
    theme = meta.get("theme", "MYSTERY")
    fallback_clip = None

    for idx, beat in enumerate(beats):
        beat["visual_mode"] = "ai_video" if idx in (0, 4) else "stock_video"
        q = re.sub(r"[^A-Za-z0-9 ]", "", beat.get("search_query", "")).strip() or theme.lower()
        url = None
        if theme == "SPACE":
            url = search_nasa(q, seen_urls) or search_pixabay(q, theme, seen_urls)
        else:
            url = search_pixabay(q, theme, seen_urls) or search_nasa(q, seen_urls)

        clip_name = f"stock_{idx}.mp4"
        clip_path = os.path.join(CLIP_DIR, clip_name)
        if url:
            try:
                print(f"[*] Beat {idx} downloading stock ({q})...", flush=True)
                download_and_normalize(url, clip_path)
                beat["stock_file"] = clip_name
                if not fallback_clip:
                    fallback_clip = clip_path
                continue
            except Exception as e:
                print(f"[!] Download error beat {idx}: {e}", flush=True)

        if fallback_clip and os.path.exists(fallback_clip):
            shutil.copyfile(fallback_clip, clip_path)
            beat["stock_file"] = clip_name

    if not fallback_clip:
        raise RuntimeError("No stock video clips could be downloaded from Pixabay or NASA")

    badge = re.sub(r"[^A-Za-z0-9 .,-]", "", script.get("hook_badge") or meta["badge"]).upper().strip()[:24]
    out = {
        "theme": theme,
        "topic": meta["topic"],
        "format_type": "SHORTS",
        "title": script["title"][:90],
        "description": script["description"],
        "tags": script.get("tags", [])[:12],
        "pinned_comment": script["pinned_comment"],
        "hook_badge": badge or meta["badge"],
        "beats": beats,
    }
    with open(SCRIPT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"[+] Script & {len(beats)} beats saved! Title: {out['title']}", flush=True)


if __name__ == "__main__":
    main()
