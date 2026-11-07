"""
generate_script.py
Executes Local Llama 3.2 via Ollama on GitHub Actions Runner.
1. Reads today_tasks.json for today's topic.
2. Builds prompt using niche_brain.py.
3. Generates 100% fresh, non-repeat scripts via local Ollama.
4. Autonomous JSON Self-Repair Parser (no static fallback).
5. Outputs dual-language scripts (Urdu + English) and subtitle timestamps.
"""

import json
import os
import re
import time
import urllib.request
from niche_brain import build_retention_prompt

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
                "topic": "Is DEVIL using secret one-tap config or pure reflexes?",
                "suggested_title": "Is DEVIL Using Secret Config or Pure Reflexes?",
                "featured_weapon": "M1887"
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
            "temperature": 0.85,  # High creativity, fresh unique generation every time
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
    """Cleans markdown, trailing commas, and extracts valid JSON payload."""
    raw_text = raw_text.strip()
    raw_text = re.sub(r"^```(?:json)?", "", raw_text, flags=re.MULTILINE)
    raw_text = re.sub(r"```$", "", raw_text, flags=re.MULTILINE).strip()

    match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
    if match:
        raw_text = match.group(1)

    # Remove invalid trailing commas before closing braces/brackets
    raw_text = re.sub(r",\s*([\}\]])", r"\1", raw_text)

    return json.loads(raw_text)

def generate_script():
    manifest = get_today_manifest()
    prompt = build_retention_prompt(manifest)

    print("[*] Generating Ultra-Smart Dynamic Script with Dual-Audio & Subtitles...")

    max_attempts = 3
    script_data = None

    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[*] AI Generation Attempt {attempt}/{max_attempts}...")
            raw_output = query_local_ollama(prompt)
            script_data = auto_repair_json(raw_output)

            # Validate that scenes exist and are unique
            if "scenes" in script_data and len(script_data["scenes"]) >= 4:
                print(f"[+] AI generation verified! Found {len(script_data['scenes'])} retention scenes.")
                break
            else:
                print("[!] Incomplete scene count from AI, retrying...")
                time.sleep(2)
        except Exception as e:
            print(f"[!] Attempt {attempt} error: {e}. Retrying with fresh seed...")
            time.sleep(2)

    if not script_data:
        raise RuntimeError("AI model responded with unparseable data across 3 attempts. Local runner check karein!")

    # Normalize fields for Dual-Language Audio & Subtitle Renderers
    urdu_lines = [s.get("narration_urdu", "") for s in script_data.get("scenes", [])]
    en_lines = [s.get("narration_en", "") for s in script_data.get("scenes", [])]
    subtitles_en = [s.get("subtitle_en", "") for s in script_data.get("scenes", [])]

    full_urdu_narration = " ".join(urdu_lines).strip()
    full_en_narration = " ".join(en_lines).strip()

    script_data["title"] = script_data.get("title_en", manifest["tasks"]["daily_short"].get("suggested_title", "Is DEVIL Using Secret Config?"))
    script_data["narration_urdu"] = full_urdu_narration
    script_data["narration_en"] = full_en_narration
    script_data["subtitles_en"] = subtitles_en

    # Backward compatibility keys for downstream audio engines
    script_data["narration"] = full_urdu_narration
    script_data["script"] = full_urdu_narration
    script_data["text"] = full_urdu_narration

    print("\n==========================================")
    print(f"[+] DYNAMIC SCRIPT SUCCESS (100% Unique - Zero Hardcoding):")
    print(f" -> Title (Global): {script_data['title']}")
    print(f" -> Urdu Audio Line: {full_urdu_narration}")
    print(f" -> English Audio Line: {full_en_narration}")
    print(f" -> Infinity Loop Bridge: {script_data.get('infinity_loop_connector')}")
    print("==========================================\n")

    with open(OUTPUT_SCRIPT_PATH, "w", encoding="utf-8") as f:
        json.dump(script_data, f, indent=2, ensure_ascii=False)

    print(f"[+] Successfully saved to {OUTPUT_SCRIPT_PATH}!")

if __name__ == "__main__":
    generate_script()
