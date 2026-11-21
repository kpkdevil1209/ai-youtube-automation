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
        "hook_flash_words": {"type": "string"},
        "hook_question": {"type": "string"},
        "escalation_line": {"type": "string"},
        "hook_ai_prompt": {"type": "string"},
        "pinned_comment": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "continuation_beats": {
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
    "required": [
        "title", "description", "hook_flash_words", "hook_question",
        "escalation_line", "hook_ai_prompt", "pinned_comment", "tags", "continuation_beats"
    ],
}


def load_topic():
    if os.path.exists(TOPIC_FILE):
        with open(TOPIC_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    raise RuntimeError("trending_topic.json missing! Run viral_trend_agent.py first.")


def write_documentary_script(meta):
    facts = meta.get("fact_summary", "").strip()
    fact_line = f"Verified Facts: '{facts}'. " if facts else ""
    prompt = "\n".join([
        f"You are a viral YouTube Shorts documentary scriptwriter. Topic: '{meta['topic']}'.",
        f"Angle: '{meta.get('angle', 'SHOCK')}'. {fact_line}",
        "Use SIMPLE 5th-grade English (zero rare academic words). Follow EXACT millisecond hook architecture:",
        "1) hook_flash_words: 2 to 3 ALL-CAPS shock words for instant 0.2s screen pop (e.g. 'SEALED FOREVER', 'ZERO ESCAPE', 'DEAD IN 4S').",
        "2) hook_question (plays 0.2s-1.0s): Strictly 3 to 5 words! An impossible brain-freezing QUESTION or contradiction (e.g. 'Why do compasses fail here?', 'Why seal this forever?', 'How did he breathe?'). NEVER use 'Did you know', 'Stop scrolling', or 'Have you ever'.",
        "3) escalation_line (plays 1.0s-2.5s): Strictly 5 to 8 words immediately raising physical stakes or mystery before the Case File stamp drops.",
        "4) hook_ai_prompt: Explosive opening moving-camera text-to-video shot (fast forward dolly into dark abyss, stormy ocean, giant shadowed ruin). 35mm dark realism, NO text, NO close-up faces/hands.",
        "5) continuation_beats: Array of EXACTLY 4 beats (8 to 11 clear words each):",
        "   - Beat 1: Immediate physical danger or real scale numbers.",
        "   - Beat 2: Rising mystery, do NOT reveal the answer yet.",
        "   - Beat 3: Jaw-dropping factual climax reveal.",
        "   - Beat 4: End MID-SENTENCE (e.g. '...and that is exactly why') so it loops seamlessly back into hook_question.",
        "   Each beat needs a distinct moving-camera ai_prompt (35mm photorealistic dark cinema, NO text, NO faces/hands).",
        "6) title: Under 58 chars, huge curiosity gap, NO emojis.",
    ])
    payload = {
        "model": TEXT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": SCRIPT_SCHEMA,
        "keep_alive": "0",
        "options": {"num_ctx": 4096, "num_predict": 900, "temperature": 0.65},
    }
    for attempt in range(1, 4):
        try:
            print(f"[*] Calling {TEXT_MODEL} (attempt {attempt})...", flush=True)
            r = requests.post(OLLAMA_URL, json=payload, timeout=180)
            r.raise_for_status()
            data = json.loads(r.json()["message"]["content"])
            cont = data.get("continuation_beats") or []
            if len(cont) >= 4 and data.get("hook_question") and data.get("escalation_line"):
                data["continuation_beats"] = cont[:4]
                return data
        except Exception as e:
            print(f"[!] Script retry {attempt}: {e}", flush=True)
    raise RuntimeError("Failed to generate upgraded 5-beat script")


def main():
    meta = load_topic()
    case_num = int(meta.get("case_number", 1))
    case_label = meta.get("case_label", f"FILE #{case_num:03d}")
    next_label = f"FILE #{case_num + 1:03d}"
    egg = meta.get("easter_egg_code", "X-014")
    requested_by = meta.get("requested_by", "")

    s = write_documentary_script(meta)
    flash = re.sub(r"[^A-Za-z0-9 ?!.-]", "", s["hook_flash_words"]).upper().strip()[:24]
    hook_q = s["hook_question"].strip()
    esc_line = s["escalation_line"].strip()

    beat0 = {
        "narration": f"{hook_q} {esc_line}",
        "hook_question": hook_q,
        "escalation_line": esc_line,
        "hook_flash_words": flash or "EXPLAIN THIS",
        "ai_prompt": s["hook_ai_prompt"],
    }
    beats = [beat0] + s["continuation_beats"][:4]

    badge = f"{case_label} | BY {requested_by}" if requested_by else meta.get("badge", case_label)
    badge = re.sub(r"[^A-Za-z0-9 .,:|@+-]", "", badge).upper().strip()[:28]

    pinned = (
        f"{case_label} | Did you spot the hidden code ({egg})? "
        f"Drop the second it appears! Also vote the next mystery for {next_label} — top liked comment gets built next."
    )

    out = {
        "run_id": uuid.uuid4().hex[:10],
        "theme": meta.get("theme", "MYSTERY"),
        "topic": meta["topic"],
        "format_type": "SHORTS",
        "case_number": case_num,
        "case_label": case_label,
        "channel_signature": "DEVIL ARCHIVE",
        "easter_egg_code": egg,
        "requested_by": requested_by,
        "title": f"{s['title'][:48]} ({case_label})"[:85],
        "description": s["description"],
        "tags": s.get("tags", [])[:12],
        "pinned_comment": pinned,
        "hook_badge": badge,
        "beats": beats,
    }
    with open(SCRIPT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"[+] Upgraded Script Ready [{case_label}]: {out['title']}", flush=True)


if __name__ == "__main__":
    main()
