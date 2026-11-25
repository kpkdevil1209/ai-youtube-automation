import json, os, random, re, time, urllib.parse
import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
HIST_FILE = "posted_long_history.json"
OUT_FILE = "long_script.json"

CURATED_TOPICS = [
    ("Mariana Trench Challenger Deep Anomaly", "ocean", "10,984 meters deep in the Pacific where crushing 1,086 bar pressure meets unexplained hydrophone signals around hydrothermal vents"),
    ("Point Nemo Oceanic Pole of Inaccessibility", "ocean", "the loneliest place on Earth 2,688 km from land where decommissioned spacecraft crash and ultra-low Bloop acoustics were recorded"),
    ("Kola Superdeep Borehole 12262 Meters", "earth", "the deepest artificial hole drilled on Earth reaching 12,262 meters where rock flowed like plastic at 180C and unexplained hydrogen water appeared"),
    ("Lake Vostok Subglacial Antarctica", "earth", "a massive liquid freshwater lake sealed beneath 4 kilometers of Antarctic ice for 15 million years in total darkness"),
    ("Wow Signal 1977 Ohio State Radio Telescope", "space", "a 72-second narrowband radio signal at 1420 MHz detected by Big Ear telescope in 1977 that never repeated"),
    ("Apollo 10 Far Side Moon Unexplained Whistle", "space", "recorded VHF radio interference heard by Apollo 10 astronauts in lunar orbit on the far side of the Moon in 1969"),
    ("Voyager 1 Heliopause Boundary Signal", "space", "the 1977 spacecraft crossing over 24 billion kilometers away entering interstellar plasma where solar wind stops"),
    ("Baltic Sea Sonar Anomaly 60 Meters", "ocean", "a 60-meter circular seafloor formation scanned by Ocean X team at 85 meters depth in the Baltic Sea in 2011"),
    ("Byrd 1947 Operation Highjump Antarctica", "expedition", "a 4,700-person US Navy expedition to Antarctica in 1946-47 facing extreme polar conditions and sudden early withdrawal"),
    ("Movile Cave Romania 5 Million Years Sealed", "earth", "a sealed underground cavern discovered in 1986 with toxic hydrogen sulfide air and 33 endemic blind species without sunlight"),
]

CHAPTER_PLAN = [
    {"idx": 1, "words": 150, "hero": True,  "midroll": False, "role": "30-SEC COLD OPEN HOOK: Drop straight into the most dangerous/unexplained moment. DO NOT reveal the answer. Ask a high-stakes question and end with 'the truth buried in this file will make sense only when we rewind to the beginning'."},
    {"idx": 2, "words": 225, "hero": False, "midroll": True,  "role": "THE ORIGIN & NUMBERS: Exact dates, coordinates, depths, failed attempts, and 2 sharp open questions spaced through the chapter."},
    {"idx": 3, "words": 235, "hero": True,  "midroll": False, "role": "2.5-MIN PATTERN INTERRUPT (RE-HOOK): Reveal the first physical clue that broke every rule, end on an urgent cliffhanger question."},
    {"idx": 4, "words": 240, "hero": False, "midroll": True,  "role": "FORENSIC DEEP DIVE: Instruments, sonar/radio logs, what failed, and why experts froze mid-investigation. Include 2 open questions."},
    {"idx": 5, "words": 240, "hero": False, "midroll": False, "role": "CLASHING THEORIES: Pit mainstream physics against the unsettling alternative evidence—keep tension rising with 2 sharp questions."},
    {"idx": 6, "words": 255, "hero": True,  "midroll": True,  "role": "SMOKING GUN CLIMAX: Deliver the strongest confirmed physical twist saved until now—leave the final piece hanging by a thread."},
    {"idx": 7, "words": 175, "hero": True,  "midroll": False, "role": "PAYOFF & HAUNTING ECHO: Answer the core mystery honestly based on hard evidence, then end with one unforgettable final question. Zero subscribe begging."},
]

BANNED = ("alien", "ufo", "illuminati", "conspiracy", "magic", "ghost", "demon", "subscribe", "like and share", "welcome back", "in today's video", "hit the bell")

def load_history():
    if os.path.exists(HIST_FILE):
        try:
            data = json.load(open(HIST_FILE, encoding="utf-8"))
            if isinstance(data, list):
                return [x.get("topic", x) if isinstance(x, dict) else x for x in data]
        except Exception:
            pass
    return []

def clean_text(s):
    s = re.sub(r"\[[^\]]*\]", " ", str(s or ""))
    s = re.sub(r"[*_`#<>]", "", s)
    s = re.sub(r"\b(Narrator|Host|Voiceover)\s*:\s*", "", s, flags=re.I)
    s = re.sub(r"\b(welcome back|don't forget to subscribe|like and share|in today's video)\b[^.!?]*[.!?]?", "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()

def fetch_wiki_facts(topic):
    q = urllib.parse.quote(" ".join(topic.split()[:4]))
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&format=json&srlimit=2"
    try:
        hits = requests.get(url, headers={"User-Agent": "SilentSignalDoc/1.0"}, timeout=10).json().get("query", {}).get("search", [])
        if hits:
            s_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(hits[0]["title"].replace(" ", "_"))
            ext = requests.get(s_url, headers={"User-Agent": "SilentSignalDoc/1.0"}, timeout=10).json().get("extract", "")
            if len(ext) > 80:
                return ext[:900]
    except Exception:
        pass
    return ""

def pick_topic(hist):
    used = {str(x).lower() for x in hist}
    if os.path.exists("requested_topics.json"):
        try:
            for item in json.load(open("requested_topics.json", encoding="utf-8")):
                t = item.get("topic", "") if isinstance(item, dict) else str(item)
                if t and t.lower() not in used and not any(b in t.lower() for b in BANNED):
                    return t, "viewer_request", fetch_wiki_facts(t) or f"Verified real-world documentary case about {t}."
        except Exception:
            pass
    pool = [x for x in CURATED_TOPICS if x[0].lower() not in used] or CURATED_TOPICS
    t, cat, seed = random.choice(pool)
    return t, cat, (seed + " " + fetch_wiki_facts(t)).strip()[:1200]

def ollama_json(prompt, schema, max_tokens=950):
    sys_msg = (
        "You are an elite documentary writer (LEMMiNO / Fern / National Geographic style). "
        "Every single sentence must grip attention (8-16 words, active voice, real numbers, zero filler). "
        "Embed a sharp curiosity question every ~65 words (~25 seconds). Return valid JSON only."
    )
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}],
        "stream": False,
        "format": schema,
        "options": {"temperature": 0.65, "repeat_penalty": 1.12, "num_ctx": 4096, "num_predict": max_tokens},
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=180)
    r.raise_for_status()
    return json.loads(r.json()["message"]["content"])

def make_outline(topic, facts):
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "thumbnail_text": {"type": "string"},
            "description_hook": {"type": "string"},
            "pinned_comment": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "chapters": {"type": "array", "items": {"type": "object", "properties": {"title": {"type": "string"}, "focus": {"type": "string"}}, "required": ["title", "focus"]}},
        },
        "required": ["title", "thumbnail_text", "description_hook", "pinned_comment", "tags", "chapters"],
    }
    p = (
        f"Topic: {topic}\nContext: {facts}\n"
        "Build a viral 7-chapter YouTube documentary outline (~10 min). "
        "Rules: Curiosity-gap title <= 62 chars (NO colons, NO '#Shorts'). "
        "thumbnail_text: 2-3 punchy uppercase words creating tension (e.g. 'NO SIGNAL BACK'). "
        "chapters: exactly 7 short intriguing titles with distinct escalating angles."
    )
    for _ in range(4):
        try:
            out = ollama_json(p, schema, 750)
            if len(out.get("chapters", [])) >= 7 and len(out.get("title", "")) >= 12:
                out["chapters"] = out["chapters"][:7]
                return out
        except Exception as e:
            print(f"[!] Outline retry: {e}", flush=True)
            time.sleep(2)
    raise RuntimeError("Failed to generate outline")

def enrich_prompt(raw_p, topic, ch_title):
    s = clean_text(raw_p)
    return s if len(s.split()) >= 8 else f"Wide documentary 35mm film shot of {topic}, {ch_title}, moody natural lighting, authentic texture"

def expand_narration(topic, facts, ch_title, cur_nar, need_w):
    schema = {"type": "object", "properties": {"continuation": {"type": "string"}}, "required": ["continuation"]}
    tail = " ".join(cur_nar.split()[-35:])
    p = (
        f"Topic: {topic} | Chapter: {ch_title}\nFacts: {facts}\n"
        f"Current ending: {tail}\n"
        f"Write {need_w + 25} MORE gripping spoken documentary words continuing seamlessly after the last sentence. "
        "DO NOT repeat prior ideas. Add concrete measurements/details, include 1 sharp tension question ('?'), and end on a hook."
    )
    try:
        ext = clean_text(ollama_json(p, schema, 450).get("continuation", ""))
        if len(ext.split()) >= 25:
            return (cur_nar + " " + ext).strip()
    except Exception:
        pass
    return cur_nar

def write_chapter(topic, facts, spec, ch_out, prev_tail, used_sents):
    schema = {
        "type": "object",
        "properties": {
            "narration": {"type": "string"},
            "hero_prompt": {"type": "string"},
            "scene1": {"type": "string"}, "scene2": {"type": "string"}, "scene3": {"type": "string"}, "scene4": {"type": "string"}, "scene5": {"type": "string"},
        },
        "required": ["narration", "hero_prompt", "scene1", "scene2", "scene3", "scene4", "scene5"],
    }
    tw = spec["words"]
    min_w = max(125, int(tw * 0.72))
    p = (
        f"Topic: {topic}\nFacts: {facts}\nChapter {spec['idx']}/7: {ch_out['title']}\nAngle: {ch_out['focus']}\n"
        f"Strategy Rule: {spec['role']}\nPrevious chapter ended on: {prev_tail}\n"
        f"Write around {tw} words of high-retention spoken narration: short gripping lines, real evidence, 1 sharp '?' question every ~65 words (20-30s), zero fluff. "
        "Also generate 1 cinematic 16:9 hero_prompt and 5 distinct photorealistic documentary scene prompts (scene1..scene5, zero neon/sci-fi)."
    )
    best = None
    for att in range(4):
        try:
            d = ollama_json(p, schema, 1100)
            nar = clean_text(d.get("narration", ""))
            if len(nar.split()) < min_w and len(nar.split()) >= 75:
                nar = expand_narration(topic, facts, ch_out["title"], nar, tw - len(nar.split()))
            wc = len(nar.split())
            sents = {x.strip().lower() for x in re.split(r"[.!?]+", nar) if len(x.split()) > 5}
            if sents and len(sents & used_sents) > 2:
                print(f"[!] Ch {spec['idx']} duplicate, retry {att+1}", flush=True)
                continue
            cand = {
                "index": spec["idx"],
                "title": clean_text(ch_out["title"])[:60],
                "hero_motion": spec["hero"],
                "hero_prompt": enrich_prompt(d.get("hero_prompt", ""), topic, ch_out["title"]),
                "scenes": [enrich_prompt(d.get(f"scene{k}", ""), topic, ch_out["title"]) for k in range(1, 6)],
                "narration": nar,
                "word_count": wc,
                "midroll_break_after": spec["midroll"],
                "_sents": sents,
            }
            if best is None or wc > best["word_count"]:
                best = cand
            if wc >= min_w:
                break
            print(f"[!] Ch {spec['idx']} short ({wc}<{min_w}), retry {att+1}", flush=True)
        except Exception as e:
            print(f"[!] Ch {spec['idx']} err: {e}", flush=True)
            time.sleep(2)
    if not best or best["word_count"] < 60:
        raise RuntimeError(f"Failed writing chapter {spec['idx']}")
    used_sents.update(best.pop("_sents"))
    return best

def main():
    hist = load_history()
    topic, cat, facts = pick_topic(hist)
    print(f"[*] Long-Form Topic ({cat}): {topic}", flush=True)
    outline = make_outline(topic, facts)
    chapters, used_sents, prev_tail = [], set(), "Start straight inside the strangest verified moment."
    for spec, ch_out in zip(CHAPTER_PLAN, outline["chapters"]):
        ch = write_chapter(topic, facts, spec, ch_out, prev_tail, used_sents)
        chapters.append(ch)
        prev_tail = " ".join(ch["narration"].split()[-22:])
        print(f"[*] Chapter {ch['index']}/7 ready ({ch['word_count']} words)", flush=True)

    total_words = sum(c["word_count"] for c in chapters)
    desc_hook = clean_text(outline["description_hook"])[:400]
    doc = {
        "format": "long_documentary_16_9",
        "channel_signature": "SILENT SIGNAL",
        "topic": topic,
        "category": cat,
        "title": re.sub(r"[:<>#]", "", clean_text(outline["title"]))[:76],
        "thumbnail_text": " ".join(clean_text(outline["thumbnail_text"]).upper().split()[:3]) or "SILENT SIGNAL",
        "description": desc_hook,
        "description_hook": desc_hook,
        "pinned_comment": clean_text(outline["pinned_comment"])[:350],
        "tags": [clean_text(t)[:38] for t in outline.get("tags", [])[:15] if clean_text(t)],
        "total_words": total_words,
        "chapters": chapters,
    }
    json.dump(doc, open(OUT_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"[*] Saved {OUT_FILE}: {total_words} words across 7 chapters.", flush=True)

if __name__ == "__main__":
    main()
