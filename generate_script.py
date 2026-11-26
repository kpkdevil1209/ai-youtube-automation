import json, os, re, urllib.parse, uuid, requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
MODEL = os.environ.get("TEXT_MODEL", "qwen2.5:3b")
BEAT = {"type": "object", "properties": {"narration": {"type": "string"}, "ai_prompt": {"type": "string"}}, "required": ["narration", "ai_prompt"]}
SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"}, "description": {"type": "string"},
        "hook_headline": {"type": "string"}, "hook_flash_words": {"type": "string"},
        "hook_question": {"type": "string"}, "escalation_line": {"type": "string"},
        "hook_ai_prompt": {"type": "string"}, "pinned_question": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "beat1": BEAT, "beat2": BEAT, "beat3": BEAT, "beat4": BEAT,
    },
    "required": ["title", "description", "hook_headline", "hook_flash_words", "hook_question", "escalation_line", "hook_ai_prompt", "pinned_question", "tags", "beat1", "beat2", "beat3", "beat4"],
}
BAN_PHRASES = ("and that is why", "file #", "welcome back", "in today's video", "subscribe", "like and share", "icy cola")


def fetch_wiki(topic):
    q = urllib.parse.quote(" ".join(re.sub(r"[^A-Za-z0-9 ]+", " ", topic).split()[:4]))
    try:
        hits = requests.get(f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&format=json&srlimit=2", headers={"User-Agent": "SilentSignal/2.0"}, timeout=10).json().get("query", {}).get("search", [])
        if hits:
            s_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(hits[0]["title"].replace(" ", "_"))
            ext = requests.get(s_url, headers={"User-Agent": "SilentSignal/2.0"}, timeout=10).json().get("extract", "")
            if len(ext) > 60:
                return ext[:850]
    except Exception:
        pass
    return ""


def clean_str(s):
    s = re.sub(r"\b(and that is why|that is why|file\s*#\s*\d+)\b", "", str(s or ""), flags=re.I)
    s = re.sub(r"[*_`#<>]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def validate_script(d):
    all_txt = " ".join([d.get("title", ""), d.get("hook_headline", ""), d.get("hook_question", ""), d.get("escalation_line", "")] + [d.get(k, {}).get("narration", "") for k in ("beat1", "beat2", "beat3", "beat4")])
    low = all_txt.lower()
    for bp in BAN_PHRASES:
        if bp in low:
            return f"banned({bp})"
    for w in re.findall(r"[A-Za-z]+", d.get("title", "")):
        if len(w) > 15:
            return f"garbled_word({w})"
    if len(d.get("hook_question", "").split()) < 3 or len(d.get("escalation_line", "").split()) < 4:
        return "weak_hook"
    lines = [d.get("escalation_line", "")] + [d[k].get("narration", "") for k in ("beat1", "beat2", "beat3", "beat4")]
    for idx, ln in enumerate(lines[1:], 1):
        wc = len(ln.split())
        if wc < 5 or wc > 13:
            return f"beat{idx}_len({wc})"
    toks = [{w for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 3} for s in lines]
    for i in range(len(toks)):
        for j in range(i + 1, len(toks)):
            inter = toks[i] & toks[j]
            if len(inter) >= 3 and (len(inter) / max(1, min(len(toks[i]), len(toks[j])))) >= 0.55:
                return f"repeat({','.join(sorted(inter)[:2])})"
    return ""


def main():
    if not os.path.exists("trending_topic.json"):
        raise RuntimeError("trending_topic.json missing!")
    m = json.load(open("trending_topic.json", encoding="utf-8"))
    topic = clean_str(m["topic"])
    base_facts = clean_str(m.get("fact_summary", ""))
    if len(base_facts) < 140:
        wiki = fetch_wiki(topic)
        base_facts = f"{base_facts} {wiki}".strip()

    prompt = "\n".join([
        f"You write viral 16-second National Geographic / LEMMiNO style Shorts scripts in flawless native US English.",
        f"Topic: '{topic}'. Angle: '{clean_str(m.get('angle', ''))}'.",
        f"VERIFIED FACTS ONLY (never invent fake science or misspell names): '{base_facts[:1000]}'.",
        "STRICT RULES: Clear cause->effect grammar, ZERO typos, NEVER use 'and that is why', NEVER use 'FILE #', ZERO greetings.",
        "- title: Under 44 chars, intense curiosity gap (e.g. 'Why Russia Sealed the Deepest Hole'). No colons, no FILE #, no hashtags.",
        "- hook_headline: 5-7 bold screen words explaining the shock immediately (e.g. 'EARTHS DEEPEST HOLE HIT SOMETHING IMPOSSIBLE').",
        "- hook_flash_words: 2-3 ALL-CAPS words for micro pop.",
        "- hook_question: 4-6 word direct shocking question about the topic.",
        "- escalation_line: 5-7 words stating exact real scale, depth, year, or danger.",
        "- hook_ai_prompt: 12+ word hyper-realistic 35mm documentary camera shot matching hook_question.",
        "- beat1 (6-9 words): Where/when it happened + real documentary ai_prompt.",
        "- beat2 (6-9 words): First terrifying anomaly or measurement + real documentary ai_prompt.",
        "- beat3 (6-9 words): Shocking verified twist + real documentary ai_prompt.",
        "- beat4 (6-9 words): Complete sentence ending with a smooth conceptual cliffhanger that naturally loops back into hook_question + ai_prompt.",
        "- pinned_question: 1 short intriguing question for viewers to debate in comments.",
    ])
    payload = {
        "model": MODEL, "stream": False, "format": SCHEMA, "keep_alive": "0",
        "messages": [{"role": "system", "content": "Flawless factual English documentary writer. Return strict JSON only."}, {"role": "user", "content": prompt}],
        "options": {"num_ctx": 4096, "num_predict": 900, "temperature": 0.55, "repeat_penalty": 1.15, "repeat_last_n": 64, "top_p": 0.9},
    }
    s, best = None, None
    for a in range(1, 6):
        try:
            r = requests.post(OLLAMA_URL, json=payload, timeout=180)
            r.raise_for_status()
            d = json.loads(r.json()["message"]["content"])
            err = validate_script(d)
            if not err:
                s = d
                break
            best = best or d
            print(f"[!] Retry {a}: {err}", flush=True)
        except Exception as e:
            print(f"[!] Retry {a}: {e}", flush=True)
    s = s or best
    if not s:
        raise RuntimeError("Script generation failed")

    title = clean_str(s["title"]).rstrip(".:-")[:45]
    hq, esc = clean_str(s["hook_question"]), clean_str(s["escalation_line"])
    headline = re.sub(r"[^A-Za-z0-9 '?.,!-]", "", clean_str(s.get("hook_headline", ""))).upper()[:54] or hq.upper()
    hp = clean_str(s.get("hook_ai_prompt", ""))
    if len(hp.split()) < 5:
        hp = f"Real 35mm National Geographic documentary shot of {topic}, dramatic natural lighting"

    beat0 = {
        "narration": f"{hq} {esc}", "hook_question": hq, "escalation_line": esc,
        "hook_flash_words": re.sub(r"[^A-Za-z0-9 ?!.-]", "", s["hook_flash_words"]).upper()[:22] or "LOOK CLOSELY",
        "ai_prompt": hp, "visual_prompt": hp,
    }
    cb = []
    for k in ("beat1", "beat2", "beat3", "beat4"):
        n, ap = clean_str(s[k]["narration"]), clean_str(s[k]["ai_prompt"])
        if len(ap.split()) < 5:
            ap = f"Real documentary footage of {topic}, {n}"
        cb.append({"narration": n, "ai_prompt": ap, "visual_prompt": ap})

    out = {
        "run_id": uuid.uuid4().hex[:10], "theme": m.get("theme", "MYSTERY"), "topic": topic, "format_type": "SHORTS",
        "channel_signature": "SILENT SIGNAL", "title": title, "hook_headline": headline,
        "description": clean_str(s["description"])[:300],
        "tags": [clean_str(t)[:30] for t in s.get("tags", [])[:10] if clean_str(t)],
        "pinned_comment": clean_str(s.get("pinned_question", ""))[:220],
        "hook_badge": "", "beats": [beat0] + cb,
    }
    json.dump(out, open("current_script.json", "w", encoding="utf-8"), indent=2)
    print(f"[+] Ready Short: {out['title']} | Headline: {headline}", flush=True)


if __name__ == "__main__":
    main()
