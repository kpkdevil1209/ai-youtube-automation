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

def rep_reason(d):
    lines = [d.get("escalation_line", "")] + [b.get("narration", "") for b in d.get("continuation_beats", [])[:4]]
    toks = [{w for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 3} for s in lines]
    for i in range(len(toks)):
        for j in range(i + 1, len(toks)):
            inter = toks[i] & toks[j]
            if len(inter) >= 3 and (len(inter) / max(1, min(len(toks[i]), len(toks[j])))) >= 0.60:
                return f"rep({','.join(sorted(inter)[:3])})"
    return ""

def valid_reason(d):
    cb = d.get("continuation_beats", [])
    if len(cb) < 4: return "cb<4"
    if len(re.findall(r"[A-Za-z0-9]+", d.get("hook_question", ""))) < 2: return "hook<2"
    if len(re.findall(r"[A-Za-z0-9]+", d.get("escalation_line", ""))) < 3: return "esc<3"
    for idx, b in enumerate(cb[:4], 1):
        if len(re.findall(r"[A-Za-z0-9]+", b.get("narration", ""))) < 3: return f"empty_narr_b{idx}"
        if len(b.get("ai_prompt", "").split()) < 3: return f"short_ai_b{idx}"
    return ""

def main():
    if not os.path.exists("trending_topic.json"): raise RuntimeError("trending_topic.json missing!")
    with open("trending_topic.json", encoding="utf-8") as f: m = json.load(f)
    facts = f"Verified Facts: '{m.get('fact_summary', '')}'. " if m.get("fact_summary") else ""
    prompt = "\n".join([
        f"National Geographic documentary Shorts writer. Topic: '{m['topic']}'. Angle: '{m.get('angle','')}'. {facts}",
        "SIMPLE natural spoken English with clean commas for realistic narrator pauses. NEVER leave any narration empty. ZERO REPETITION: Every beat must give a NEW concrete fact.",
        "1) hook_flash_words: 2-3 ALL-CAPS shock words for 0.2s screen pop.",
        "2) hook_question (0.2s-1.0s): Strictly 3-5 words, sharp question on EXACT topic (NO 'Stop scrolling'/'Did you know').",
        "3) escalation_line (1.0s-2.5s): Strictly 5-8 words with a physical danger or specific number.",
        "4) hook_ai_prompt: Raw real-world National Geographic documentary shot matching hook_question. Handheld 35mm film, natural light, NO sci-fi CGI.",
        "5) continuation_beats: EXACTLY 4 distinct beats (8-11 words each):",
        "   - Beat 1: Exact real place & measurement. Beat 2: Physical trigger or body reaction. Beat 3: Surprising factual climax twist. Beat 4: Ends MID-SENTENCE ('...and that is why') looping into hook_question.",
        "   - LITERAL REALISM: Each beat ai_prompt must show a DIFFERENT real-world National Geographic documentary shot matching that beat's words (water, rock, gear, rusted metal, nature). NO neon, NO cyberpunk, NO text.",
        "6) title: Under 54 chars, huge curiosity gap, NO emojis.",
    ])
    payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False, "format": SCHEMA, "keep_alive": "0", "options": {"num_ctx": 4096, "num_predict": 900, "temperature": 0.72, "repeat_penalty": 1.28, "repeat_last_n": 128, "top_p": 0.9}}
    s, best = None, None
    for a in range(1, 5):
        try:
            r = requests.post(OLLAMA_URL, json=payload, timeout=180)
            r.raise_for_status()
            d = json.loads(r.json()["message"]["content"])
            err = valid_reason(d)
            if not err:
                best = d
                err = rep_reason(d)
                if not err: s = d; break
            print(f"[!] Retry {a}: {err}", flush=True)
        except Exception as e:
            print(f"[!] Retry {a}: {e}", flush=True)
    s = s or best
    if not s: raise RuntimeError("Script generation failed")

    cnum, clbl = int(m.get("case_number", 1)), m.get("case_label", "FILE #001")
    egg, req_by = m.get("easter_egg_code", "X-014"), m.get("requested_by", "")
    hp = s["hook_ai_prompt"].strip()
    beat0 = {"narration": f"{s['hook_question'].strip()} {s['escalation_line'].strip()}", "hook_question": s["hook_question"].strip(), "escalation_line": s["escalation_line"].strip(), "hook_flash_words": re.sub(r"[^A-Za-z0-9 ?!.-]", "", s["hook_flash_words"]).upper()[:24] or "EXPLAIN THIS", "ai_prompt": hp, "visual_prompt": hp}
    cb = [{"narration": b["narration"].strip(), "ai_prompt": b["ai_prompt"].strip(), "visual_prompt": b["ai_prompt"].strip()} for b in s["continuation_beats"][:4]]
    out = {
        "run_id": uuid.uuid4().hex[:10], "theme": m.get("theme", "MYSTERY"), "topic": m["topic"], "format_type": "SHORTS",
        "case_number": cnum, "case_label": clbl, "channel_signature": "SILENT SIGNAL", "easter_egg_code": egg, "requested_by": req_by,
        "title": f"{s['title'][:46]} ({clbl})"[:85], "description": s["description"], "tags": s.get("tags", [])[:12],
        "pinned_comment": f"{clbl} | Did you spot hidden code ({egg})? Drop the second below + comment next mystery for FILE #{cnum+1:03d}!",
        "hook_badge": re.sub(r"[^A-Za-z0-9 .,:|@+-]", "", m.get("badge", clbl)).upper()[:28],
        "beats": [beat0] + cb,
    }
    with open("current_script.json", "w", encoding="utf-8") as f: json.dump(out, f, indent=2)
    print(f"[+] Ready [{clbl}]: {out['title']}", flush=True)

if __name__ == "__main__":
    main()
