import json, os, re, uuid, requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
MODEL = os.environ.get("TEXT_MODEL", "qwen2.5:3b")
BEAT = {"type": "object", "properties": {"narration": {"type": "string"}, "ai_prompt": {"type": "string"}}, "required": ["narration", "ai_prompt"]}
SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"}, "description": {"type": "string"},
        "hook_flash_words": {"type": "string"}, "hook_question": {"type": "string"},
        "escalation_line": {"type": "string"}, "hook_ai_prompt": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "beat1": BEAT, "beat2": BEAT, "beat3": BEAT, "beat4": BEAT,
    },
    "required": ["title", "description", "hook_flash_words", "hook_question", "escalation_line", "hook_ai_prompt", "tags", "beat1", "beat2", "beat3", "beat4"],
}

def rep_reason(d):
    lines = [d.get("escalation_line", "")] + [d[k].get("narration", "") for k in ("beat1", "beat2", "beat3", "beat4")]
    toks = [{w for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 3} for s in lines]
    for i in range(len(toks)):
        for j in range(i + 1, len(toks)):
            inter = toks[i] & toks[j]
            if len(inter) >= 3 and (len(inter) / max(1, min(len(toks[i]), len(toks[j])))) >= 0.60:
                return f"rep({','.join(sorted(inter)[:3])})"
    return ""

def valid_reason(d):
    if len(re.findall(r"[A-Za-z0-9]+", d.get("hook_question", ""))) < 2: return "hook<2"
    if len(re.findall(r"[A-Za-z0-9]+", d.get("escalation_line", ""))) < 3: return "esc<3"
    for k in ("beat1", "beat2", "beat3", "beat4"):
        if len(re.findall(r"[A-Za-z0-9]+", d.get(k, {}).get("narration", ""))) < 3: return f"empty_{k}"
    return ""

def main():
    if not os.path.exists("trending_topic.json"): raise RuntimeError("trending_topic.json missing!")
    with open("trending_topic.json", encoding="utf-8") as f: m = json.load(f)
    facts = f"Facts: '{m.get('fact_summary', '')}'. " if m.get("fact_summary") else ""
    prompt = "\n".join([
        f"National Geographic Shorts scriptwriter. Topic: '{m['topic']}'. Angle: '{m.get('angle','')}'. {facts}",
        "Write clear spoken English with commas for pauses. Every beat MUST give a NEW fact and never repeat lines:",
        "- hook_flash_words: 2-3 ALL-CAPS words for 0.2s screen pop.",
        "- hook_question: 3-5 word sharp question about the exact topic.",
        "- escalation_line: 5-8 words giving an immediate danger or number.",
        "- hook_ai_prompt: 10+ word real handheld National Geographic documentary shot matching hook_question (no sci-fi CGI).",
        "- beat1: Real location and scale (8-11 words) + detailed real documentary ai_prompt.",
        "- beat2: Physical danger or body reaction (8-11 words) + detailed real documentary ai_prompt.",
        "- beat3: Surprising factual climax twist (8-11 words) + detailed real documentary ai_prompt.",
        "- beat4: Ends mid-sentence ('...and that is why') looping to hook_question + detailed real documentary ai_prompt.",
        "- title: Under 54 chars, high curiosity, no emojis.",
    ])
    payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False, "format": SCHEMA, "keep_alive": "0", "options": {"num_ctx": 4096, "num_predict": 950, "temperature": 0.7, "repeat_penalty": 1.12, "repeat_last_n": 64, "top_p": 0.9}}
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
    hp = s.get("hook_ai_prompt", "").strip()
    if len(hp.split()) < 4: hp = f"Real documentary footage of {m['topic']}, {s['hook_question']}"
    beat0 = {"narration": f"{s['hook_question'].strip()} {s['escalation_line'].strip()}", "hook_question": s["hook_question"].strip(), "escalation_line": s["escalation_line"].strip(), "hook_flash_words": re.sub(r"[^A-Za-z0-9 ?!.-]", "", s["hook_flash_words"]).upper()[:24] or "EXPLAIN THIS", "ai_prompt": hp, "visual_prompt": hp}
    cb = []
    for k in ("beat1", "beat2", "beat3", "beat4"):
        n, ap = s[k]["narration"].strip(), s[k]["ai_prompt"].strip()
        if len(ap.split()) < 4: ap = f"Real National Geographic shot of {m['topic']}, {n}"
        cb.append({"narration": n, "ai_prompt": ap, "visual_prompt": ap})
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
