"""
generate_script.py
Executes Local Llama 3.2 on GitHub Actions Runner.
Dynamically adapts scene counts to match daily_task_planner randomized seconds.
"""

import json
import os
import re
import time
import urllib.request
from niche_brain import build_retention_prompt, pick_daily_short_topic

MANIFEST_PATH = "today_tasks.json"
OUTPUT_SCRIPT_PATH = "current_script.json"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:3b"

def get_today_manifest() -> dict:
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {
        "channel_name": "DEVIL INSANITY",
        "in_game_tag": "DEVIL-999",
        "tasks": {
            "daily_short": {
                "target_duration_sec": 21.4,
                "calculated_scenes_count": 10
            }
        }
    }

def query_local_ollama(prompt: str) -> str:
    print(f"[*] Querying local Ollama runner ({MODEL_NAME})...")
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.82,
            "top_p": 0.9
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_API_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result.get("response", "")

def auto_repair_json(raw_text: str) -> dict:
    raw_text = raw_text.strip()
    raw_text = re.sub(r"^```(?:json)?", "", raw_text, flags=re.MULTILINE)
    raw_text = re.sub(r"```$", "", raw_text, flags=re.MULTILINE).strip()

    match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
    if match:
        raw_text = match.group(1)

    raw_text = re.sub(r",\s*([\}\]])", r"\1", raw_text)
    return json.loads(raw_text)

def generate_script():
    manifest = get_today_manifest()
    today_topic = pick_daily_short_topic()
    target_sec = manifest.get("tasks", {}).get("daily_short", {}).get("target_duration_sec", 21.5)

    print(f"\n[*] RESEARCH SCOUT: Target -> [{today_topic['name']}] (Target Duration: {target_sec}s)")
    prompt = build_retention_prompt(manifest)

    max_attempts = 3
    script_data = None

    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[*] AI Generation Attempt {attempt}/{max_attempts} with 65 Psychological Strategies...")
            raw_output = query_local_ollama(prompt)
            script_data = auto_repair_json(raw_output)

            if "scenes" in script_data and len(script_data["scenes"]) >= 5:
                print(f"[+] AI Generation Verified! Found {len(script_data['scenes'])} scenes.")
                break
            else:
                print("[!] Incomplete scenes, retrying...")
                time.sleep(2)
        except Exception as e:
            print(f"[!] Attempt {attempt} error: {e}. Retrying with fresh seed...")
            time.sleep(2)

    if not script_data:
        raise RuntimeError("AI model unparseable after 3 attempts. Local runner status check karein!")

    urdu_lines = [s.get("narration_urdu", "") for s in script_data.get("scenes", [])]
    en_lines = [s.get("narration_en", "") for s in script_data.get("scenes", [])]
    subtitles_en = [s.get("subtitle_en", "") for s in script_data.get("scenes", [])]

    full_urdu_narration = " ".join(urdu_lines).strip()
    full_en_narration = " ".join(en_lines).strip()

    script_data["title"] = script_data.get("title_en", today_topic["hook"])
    script_data["narration_urdu"] = full_urdu_narration
    script_data["narration_en"] = full_en_narration
    script_data["subtitles_en"] = subtitles_en

    script_data["narration"] = full_urdu_narration
    script_data["script"] = full_urdu_narration
    script_data["text"] = full_urdu_narration

    print("\n==========================================")
    print(f"[+] 65-STRATEGY SCRIPT GENERATED:")
    print(f" -> Title: {script_data['title']}")
    print(f" -> Duration: ~{target_sec}s")
    print(f" -> Urdu Voice Line: {full_urdu_narration}")
    print("==========================================\n")

    with open(OUTPUT_SCRIPT_PATH, "w", encoding="utf-8") as f:
        json.dump(script_data, f, indent=2, ensure_ascii=False)

    print(f"[+] Pristine script saved to {OUTPUT_SCRIPT_PATH}!")

if __name__ == "__main__":
    generate_script()
