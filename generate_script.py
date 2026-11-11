"""
generate_script.py (Version 5.5 - Android Client Harvester)
Bypasses YouTube bot check using android player client arguments.
Generates script in 8 seconds and downloads 60FPS gameplay without cookies!
"""

import json
import os
import re
import time
import urllib.request
import subprocess
from niche_brain import build_retention_prompt, scout_live_viral_trend

MANIFEST_PATH = "today_tasks.json"
OUTPUT_SCRIPT_PATH = "current_script.json"
VAULT_DIR = "gameplay_vault"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:3b"

def get_today_manifest() -> dict:
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"channel_name": "DEVIL INSANITY", "in_game_tag": "DEVIL-999"}

def query_local_ollama(prompt: str) -> str:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "num_predict": 320,
            "num_thread": 2,
            "temperature": 0.75
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OLLAMA_API_URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8")).get("response", "")

def auto_repair_json(raw_text: str) -> dict:
    raw_text = raw_text.strip()
    raw_text = re.sub(r"^```(?:json)?", "", raw_text, flags=re.MULTILINE)
    raw_text = re.sub(r"```$", "", raw_text, flags=re.MULTILINE).strip()
    match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
    if match:
        raw_text = match.group(1)
    raw_text = re.sub(r",\s*([\}\]])", r"\1", raw_text)
    return json.loads(raw_text)

def harvest_gameplay_video(search_query: str):
    """Bypasses YouTube Bot Check using Android API Client."""
    os.makedirs(VAULT_DIR, exist_ok=True)
    existing = [os.path.join(VAULT_DIR, f) for f in os.listdir(VAULT_DIR) if f.endswith((".mp4", ".mkv"))]
    if len(existing) >= 2:
        print(f"[+] Vault has {len(existing)} clips ready. Skipping scrape.")
        return

    print(f"[*] AUTO-HARVESTER: Scraping 60FPS gameplay via Android Client for query: '{search_query}'...")
    try:
        import yt_dlp
        ydl_opts = {
            "format": "bestvideo[ext=mp4][height<=1080]/best[ext=mp4]",
            "outtmpl": os.path.join(VAULT_DIR, "harvested_raw.mp4"),
            "default_search": f"ytsearch1:{search_query}",
            "max_downloads": 1,
            "quiet": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios"]  # BYPASSES "Sign in to confirm you're not a bot"
                }
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"ytsearch1:{search_query}"])

        raw_in = os.path.join(VAULT_DIR, "harvested_raw.mp4")
        clean_out = os.path.join(VAULT_DIR, f"clean_{int(time.time())}.mp4")

        if os.path.exists(raw_in):
            cmd = (
                f'ffmpeg -y -i "{raw_in}" '
                f'-vf "crop=in_w*0.94:in_h*0.94:(in_w*0.03):(in_h*0.03),eq=contrast=1.1:saturation=1.25" '
                f'-an -c:v libx264 -preset fast -pix_fmt yuv420p "{clean_out}" -loglevel error'
            )
            os.system(cmd)
            os.remove(raw_in)
            print(f"[+] Clean 60FPS Gameplay saved -> {clean_out}")
    except Exception as e:
        print(f"[!] Harvester notice: {e}. Fallback generator will ensure smooth render.")

def generate_script():
    manifest = get_today_manifest()
    trend = scout_live_viral_trend()
    prompt = build_retention_prompt(manifest)

    print(f"\n[*] SCRIPT ENGINE: Generating for [{trend['hook']}]...")
    script_data = None
    try:
        raw_output = query_local_ollama(prompt)
        script_data = auto_repair_json(raw_output)
    except Exception as e:
        print(f"[!] Runner throttled ({e}). Using resilient dynamic script...")

    if not script_data or "scenes" not in script_data or len(script_data["scenes"]) < 5:
        tag = manifest.get("in_game_tag", "DEVIL-999")
        script_data = {
            "title_urdu": trend["hook"],
            "title_en": trend["hook"],
            "description_en": f"{trend['hook']} #FreeFire #Shorts #DEVIL999 #Clutch",
            "featured_weapon": trend["weapon"],
            "headshot_dmg": trend["headshot_dmg"],
            "search_query": trend["search_query"],
            "infinity_loop_connector": "Aur isi liye sab puchte hain ke...",
            "scenes": [
                {"scene_num": 1, "duration_sec": 4.0, "narration_urdu": f"Kya ye {trend['weapon']} trick sach mein kaam karti hai?", "narration_en": f"Does this {trend['weapon']} trick really work?", "subtitle_en": "SECRET TRICK EXPOSED", "sfx": "vine_boom"},
                {"scene_num": 2, "duration_sec": 4.0, "narration_urdu": "Garena ne is setting ke bare mein kabhi nahi bataya!", "narration_en": "Garena never revealed this secret setting!", "subtitle_en": "GARENA NEVER TOLD YOU", "sfx": "bass_drop"},
                {"scene_num": 3, "duration_sec": 4.2, "narration_urdu": "Samne se poori squad rush kar rahi thi!", "narration_en": "Enemy squad was rushing aggressively!", "subtitle_en": "SQUAD RUSHING IN", "sfx": "whoosh"},
                {"scene_num": 4, "duration_sec": 4.2, "narration_urdu": "Lekin jab screen recording dekhi to sab dang!", "narration_en": "When they saw the recording everyone was shocked!", "subtitle_en": "RECORDING SHOCKED ALL", "sfx": "hitmarker"},
                {"scene_num": 5, "duration_sec": 4.2, "narration_urdu": f"Iska real damage dekh kar hosh ud gaye!", "narration_en": "The real damage output was unbelievable!", "subtitle_en": "REAL INGAME DAMAGE", "sfx": "gun_cock"},
                {"scene_num": 6, "duration_sec": 4.2, "narration_urdu": "Poori lobby mein aisi accuracy kisi ne nahi dekhi!", "narration_en": "Nobody in the server had seen such accuracy!", "subtitle_en": "GOD LEVEL ACCURACY", "sfx": "bass_explosion"},
                {"scene_num": 7, "duration_sec": 4.0, "narration_urdu": "Aur isi liye sab puchte hain ke...", "narration_en": "And that is why everyone asks...", "subtitle_en": "LOOP BACK TO START", "sfx": "whoosh"}
            ]
        }

    urdu_lines = [s.get("narration_urdu", "") for s in script_data.get("scenes", [])]
    en_lines = [s.get("narration_en", "") for s in script_data.get("scenes", [])]
    full_urdu = " ".join(urdu_lines).strip()
    full_en = " ".join(en_lines).strip()

    script_data["title"] = script_data.get("title_en", trend["hook"])
    script_data["narration_urdu"] = full_urdu
    script_data["narration_en"] = full_en
    script_data["subtitles_en"] = [s.get("subtitle_en", "") for s in script_data.get("scenes", [])]
    script_data["narration"] = full_urdu
    script_data["script"] = full_urdu
    script_data["text"] = full_urdu

    with open(OUTPUT_SCRIPT_PATH, "w", encoding="utf-8") as f:
        json.dump(script_data, f, indent=2, ensure_ascii=False)

    print(f"[+] Script saved to {OUTPUT_SCRIPT_PATH}!")
    harvest_gameplay_video(trend["search_query"])

if __name__ == "__main__":
    generate_script()
