import json
import os
import re
import uuid
import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
TEXT_MODEL = os.environ.get("TEXT_MODEL", "qwen2.5:3b")

TOPIC_FILE = "trending_topic.json"
SCRIPT_FILE = "current_script.json"

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
                    "ai_prompt": {"type": "string"},
                },
                "required": ["narration", "ai_prompt"],
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
        "angle": "crush pressure and pitch darkness",
        "badge": "DEPTH: 3,000M",
        "psych_strategy": "IMMEDIATE_SURVIVAL_THREAT",
    }


def write_documentary_script(meta):
    prompt = (
        f"You are an elite viral YouTube Shorts documentary writer. Topic: '{meta['topic']}'. "
        f"Angle: '{meta['angle']}'. Hook Style: '{meta.get('psych_strategy', 'SURVIVAL')}'. "
        "Write an ultra-gripping 25-second 5-beat script in SIMPLE, EASY-TO-UNDERSTAND English (no rare academic words). Rules: "
        "1) Beat 0 Hook MUST shock in the first 4 words (e.g., 'Stop scrolling. If you...', 'Never dive past...', 'At 3 seconds left...'). "
        "2) Beats 1-2 build fast terrifying tension with real numbers or physical danger. "
        "3) Beat 3 is the shocking climax reveal. "
        "4) Beat 4 ends mid-sentence so it loops straight back into Beat 0. "
        "5) Keep EACH beat narration 9 to 13 clear punchy words. "
        "6) For EACH beat write ai_prompt for text-to-video AI: specify clear CAMERA MOTION (slow dolly forward, aerial sweep, underwater drift) + moving subject (waves crashing, giant shadowy sea monster, swirling black hole, blizzard storm). Dark photorealistic 35mm cinema, NO text, NO close-up hands/faces. "
        "7) Title under 60 chars, huge curiosity gap, NO emojis."
    )
    payload = {
        "model": TEXT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": SCRIPT_SCHEMA,
        "keep_alive": "0",
        "options": {"num_ctx": 4096, "num_predict": 850, "temperature": 0.65},
    }
    for attempt in range(1, 4):
        try:
            print(f"[*] Calling {TEXT_MODEL} (attempt {attempt})...", flush=True)
            r = requests.post(OLLAMA_URL, json=payload, timeout=180)
            r.raise_for_status()
            data = json.loads(r.json()["message"]["content"])
            beats = data.get("beats") or []
            if len(beats) >= 5:
                data["beats"] = beats[:5]
                return data
        except Exception as e:
            print(f"[!] Script retry {attempt}: {e}", flush=True)
    raise RuntimeError("Failed to generate 5-beat script")


def main():
    meta = load_topic()
    script = write_documentary_script(meta)
    badge = re.sub(r"[^A-Za-z0-9 .,:+-]", "", script.get("hook_badge") or meta["badge"]).upper().strip()[:22]
    out = {
        "run_id": uuid.uuid4().hex[:10],
        "theme": meta.get("theme", "OCEAN"),
        "topic": meta["topic"],
        "format_type": "SHORTS",
        "title": script["title"][:90],
        "description": script["description"],
        "tags": script.get("tags", [])[:12],
        "pinned_comment": script["pinned_comment"],
        "hook_badge": badge or meta["badge"],
        "beats": script["beats"],
    }
    with open(SCRIPT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"[+] 5-Beat Video Script Ready [{out['run_id']}]: {out['title']}", flush=True)


if __name__ == "__main__":
    main()
