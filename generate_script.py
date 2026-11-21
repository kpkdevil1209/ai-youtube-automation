import json, os, re, uuid, requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
MODEL = os.environ.get("TEXT_MODEL", "qwen2.5:3b")
SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"}, "description": {"type": "string"},
        "hook_flash_words": {"type": "string"}, "hook_question": {"type": "string"},
        "escalation_line": {"type": "string"}, "hook_ai_prompt": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "continuation_beats": {"type": "array", "items": {"type": "object", "properties": {"narration": {"type": "string"}, "ai_prompt": {"type": "string"}}, "required": ["narration", "ai_prompt"]}},
    },
    "required": ["title", "description", "hook_flash_words", "hook_question", "escalation_line", "hook_ai_prompt", "tags", "continuation_beats"],
}

def main():
    if not os.path.exists("trending_topic.json"): raise RuntimeError("trending_topic.json missing!")
    m = json.load(open("trending_topic.json", encoding="utf-8"))
    facts = f"Verified Facts: '{m.get('fact_summary', '')}'. " if m.get("fact_summary") else ""
    prompt = "\n".join([
        f"Elite YouTube Shorts documentary writer. Topic: '{m['topic']}'. Angle: '{m.get('angle','')}'. {facts}",
        "Use SIMPLE 5th-grade English, direct 'you/your' storytelling (NO boring textbook tone). Exact rules:",
        "1) hook_flash_words: 2-3 ALL-CAPS shock words for 0.2s screen pop (e.g. 'SEALED FOREVER').",
        "2) hook_question (0.2s-1.0s): Strictly 3-5 words, impossible brain-blocking question (NEVER 'Stop scrolling' or 'Did you know').",
        "3) escalation_line (1.0s-2.5s): Strictly 5-8 words raising instant physical danger or shock.",
        "4) hook_ai_prompt: Must LITERALLY depict the exact subject/danger in hook_question + escalation_line with dynamic moving camera.",
        "5) continuation_beats: EXACTLY 4 beats (8-11 clear words each, micro-payoff in every beat):",
        "   - Beat 1: Immediate physical danger/scale. Beat 2: Rising mystery. Beat 3: Jaw-dropping factual climax. Beat 4: Ends MID-SENTENCE ('...and that is why') looping into hook_question.",
        "   - LITERAL VISUAL MATCH RULE: Each beat's ai_prompt MUST literally show the EXACT physical object, environment, creature, or action spoken in THAT beat's narration (if voice says 'steel implodes' show crushing steel; if 'compass spins' show spinning brass compass). Specify camera motion + bright dramatic rim lighting, NO text, NO deformed close-up faces/hands.",
        "6) title: Under 54 chars, high curiosity gap, NO emojis.",
    ])
    payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False, "format": SCHEMA, "keep_alive": "0", "options": {"num_ctx": 4096, "num_predict": 900, "temperature": 0.65}}
    s = None
    for a in range(1, 4):
        try:
            r = requests.post(OLLAMA_URL, json=payload, timeout=180)
            r.raise_for_status()
            d = json.loads(r.json()["message"]["content"])
            if len(d.get("continuation_beats", [])) >= 4 and d.get("hook_question"):
                s = d; break
        except Exception as e:
            print(f"[!] Retry {a}: {e}", flush=True)
    if not s: raise RuntimeError("Script generation failed")

    cnum, clbl = int(m.get("case_number", 1)), m.get("case_label", "FILE #001")
    egg, req_by = m.get("easter_egg_code", "X-014"), m.get("requested_by", "")
    beat0 = {"narration": f"{s['hook_question'].strip()} {s['escalation_line'].strip()}", "hook_question": s["hook_question"].strip(), "escalation_line": s["escalation_line"].strip(), "hook_flash_words": re.sub(r"[^A-Za-z0-9 ?!.-]", "", s["hook_flash_words"]).upper()[:24] or "EXPLAIN THIS", "ai_prompt": s["hook_ai_prompt"]}
    out = {
        "run_id": uuid.uuid4().hex[:10], "theme": m.get("theme", "MYSTERY"), "topic": m["topic"], "format_type": "SHORTS",
        "case_number": cnum, "case_label": clbl, "channel_signature": "SILENT SIGNAL", "easter_egg_code": egg, "requested_by": req_by,
        "title": f"{s['title'][:46]} ({clbl})"[:85], "description": s["description"], "tags": s.get("tags", [])[:12],
        "pinned_comment": f"{clbl} | Did you spot hidden code ({egg})? Drop the second below + comment next mystery for FILE #{cnum+1:03d}!",
        "hook_badge": re.sub(r"[^A-Za-z0-9 .,:|@+-]", "", m.get("badge", clbl)).upper()[:28],
        "beats": [beat0] + s["continuation_beats"][:4],
    }
    json.dump(out, open("current_script.json", "w", encoding="utf-8"), indent=2)
    print(f"[+] Ready [{clbl}]: {out['title']}", flush=True)

if __name__ == "__main__":
    main()
