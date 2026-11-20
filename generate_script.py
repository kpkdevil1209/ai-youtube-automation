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
                    "shot_a": {"type": "string"},
                    "shot_b": {"type": "string"},
                },
                "required": ["narration", "shot_a", "shot_b"],
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
        "psych_strategy": "IMMEDIATE_SURVIVAL_THREAT: Open with an exact countdown or biological failure.",
    }


def write_documentary_script(meta):
    prompt = (
        f"You are an elite viral YouTube Shorts documentary writer. Topic: '{meta['topic']}'. "
        f"Angle: '{meta['angle']}'. Hook Style: '{meta.get('psych_strategy', 'SURVIVAL')}'. "
        "Write an intense 33-second 6-beat English script designed for 100% viewer retention. Rules: "
        "1) Beat 0 MUST drop mid-danger in the first 5 words with zero greetings. "
        "2) Beats 1-3 escalate dread with specific numbers, sounds, or physical horrors. "
        "3) Beat 4 delivers the chilling twist reveal. "
        "4) Beat 5 ends mid-clause so it loops straight back into Beat 0. "
        "5) Keep EACH beat narration 10 to 15 punchy words. "
        "6) For EACH beat provide TWO visually different cinematic prompts: shot_a and shot_b "
        "(dark moody photorealistic 35mm documentary scene, dramatic shadows, NO text, NO watermarks, avoid human hand/face close-ups). "
        "7) Title must be under 62 chars, pure curiosity gap, NO emojis, NO generic words like unveiled or shocking truth. "
        "8) pinned_comment must spark debate in 1 sentence."
    )
    payload = {
        "model": TEXT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": SCRIPT_SCHEMA,
        "keep_alive": "0",
        "options": {"num_ctx": 4096, "num_predict": 1100, "temperature": 0.65},
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
    raise RuntimeError("Failed to generate 6-beat script")


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
    print(f"[+] 12-Shot Script Ready [{out['run_id']}]: {out['title']}", flush=True)


if __name__ == "__main__":
    main()
