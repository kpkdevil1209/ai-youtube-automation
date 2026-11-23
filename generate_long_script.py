import json, os, random, re, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
HIST_FILE = "posted_long_history.json"
OUT_FILE = "long_script.json"

CURATED_TOPICS = [
    ("Mariana Trench Challenger Deep Anomaly", "ocean", "10,984 meters deep in the Pacific where crushing 1,086 bar pressure meets unexplained hydrophone signals and life around hydrothermal vents"),
    ("Point Nemo Oceanic Pole of Inaccessibility", "ocean", "the loneliest place on Earth 2,688 km from the nearest land where decommissioned spacecraft fall and strange low-frequency Bloop sounds were recorded"),
    ("Kola Superdeep Borehole 12262 Meters", "earth", "the deepest artificial hole ever drilled on Earth reaching 12,262 meters where rock flowed like plastic at 180C and unexpected water and hydrogen appeared"),
    ("Lake Vostok Subglacial Antarctica", "earth", "a massive liquid freshwater lake sealed beneath 4 kilometers of Antarctic ice for 15 million years in total darkness"),
    ("Wow Signal 1977 Ohio State Radio Telescope", "space", "a 72-second narrowband radio signal at 1420 MHz hydrogen line detected by Big Ear telescope in 1977 that never repeated"),
    ("Apollo 10 Far Side Moon Unexplained Whistle", "space", "recorded VHF radio interference heard by Apollo 10 astronauts in lunar orbit on the far side of the Moon in 1969"),
    ("Voyager 1 Heliopause Boundary Signal", "space", "the 1977 spacecraft crossing over 24 billion kilometers away entering interstellar plasma where solar wind stops"),
    ("Baltic Sea Sonar Anomaly 60 Meters", "ocean", "a 60-meter circular seafloor formation scanned by Ocean X team at 85 meters depth in the Baltic Sea in 2011"),
    ("Byrd 1947 Operation Highjump Antarctica", "expedition", "a 4,700-person US Navy expedition to Antarctica in 1946-47 facing extreme polar weather and sudden early withdrawal"),
    ("Movile Cave Romania 5 Million Years Sealed", "earth", "a sealed underground cavern discovered in 1986 with toxic hydrogen sulfide air and 33 endemic blind species living without sunlight"),
]

RSS_FEEDS = [
    "https://www.livescience.com/feeds/all",
    "https://www.space.com/feeds/all",
    "https://phys.org/rss-feed/earth-news/",
]

CHAPTER_PLAN = [
    {"idx": 1, "words": 155, "hero": True,  "midroll": False, "role": "COLD OPEN HOOK: Drop straight into the strangest verified moment. Zero channel intro. End with an open mystery loop."},
    {"idx": 2, "words": 225, "hero": False, "midroll": True,  "role": "OFFICIAL RECORD: Verified dates, exact measurements, coordinates, coordinates/depth/distance, and how it was first discovered."},
    {"idx": 3, "words": 235, "hero": True,  "midroll": False, "role": "FIRST ANOMALY (RE-HOOK): Introduce the first documented clue that broke normal scientific expectations."},
    {"idx": 4, "words": 240, "hero": False, "midroll": True,  "role": "DEEP INVESTIGATION: Walk through real instruments, sensors, expeditions, or logs used to test the mystery."},
    {"idx": 5, "words": 245, "hero": False, "midroll": False, "role": "COMPETING THEORIES: Compare mainstream scientific explanation vs alternative physical hypothesis objectively."},
    {"idx": 6, "words": 255, "hero": True,  "midroll": True,  "role": "THE SMOKING GUN CLIMAX: Deliver the strongest confirmed physical twist or hard evidence that still baffles experts."},
    {"idx": 7, "words": 175, "hero": True,  "midroll": False, "role": "UNANSWERED SIGNAL & BRIDGE: End on a haunting factual question and tease the next deep mystery dossier. No subscribe begging."},
]

BANNED = ("alien", "ufo", "illuminati", "conspiracy", "magic", "ghost", "demon", "subscribe", "like and share", "welcome back")

def load_history():
    if os.path.exists(HIST_FILE):
        try:
            data = json.load(open(HIST_FILE, encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []

def clean_text(s):
    s = re.sub(r"\[[^\]]*\]", " ", str(s or ""))
    s = re.sub(r"[*_`#<>]", "", s)
    s = re.sub(r"\b(Narrator|Host|Voiceover)\s*:\s*", "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()

def fetch_wiki_facts(topic):
    q = urllib.parse.quote(topic.split()[0] + " " + " ".join(topic.split()[1:4]))
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&format=json&srlimit=2"
    try:
        r = requests.get(url, headers={"User-Agent": "SilentSignalDoc/1.0"}, timeout=10).json()
        hits = r.get("query", {}).get("search", [])
        if hits:
            title = hits[0]["title"]
            s_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_"))
            sd = requests.get(s_url, headers={"User-Agent": "SilentSignalDoc/1.0"}, timeout=10).json()
            ext = sd.get("extract", "")
            if len(ext) > 80:
                return ext[:900]
    except Exception:
        pass
    return ""

def pick_topic(hist):
    used = {str(x).lower() for x in hist}
    if os.path.exists("requested_topics.json"):
        try:
            reqs = json.load(open("requested_topics.json", encoding="utf-8"))
            for item in reqs:
                t = item.get("topic", "") if isinstance(item, dict) else str(item)
                if t and t.lower() not in used and not any(b in t.lower() for b in BANNED):
                    return t, "viewer_request", fetch_wiki_facts(t) or f"Verified real-world documentary case study about {t}."
        except Exception:
            pass
    pool = [x for x in CURATED_TOPICS if x[0].lower() not in used]
    if not pool:
        pool = CURATED_TOPICS
    t, cat, seed_fact = random.choice(pool)
    wiki = fetch_wiki_facts(t)
    facts = (seed_fact + " " + wiki).strip()
    return t, cat, facts[:1200]

def ollama_json(prompt, schema, max_tokens=900):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are an elite investigative documentary writer for Silent Signal (LEMMiNO / National Geographic tone). Strict factual English, zero fluff, zero greetings, return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": schema,
        "options": {"temperature": 0.65, "repeat_penalty": 1.12, "num_ctx": 4096, "num_predict": max_tokens},
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=180)
    r.raise_for_status()
    raw = r.json()["message"]["content"]
    return json.loads(raw)

def make_outline(topic, facts):
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "thumbnail_text": {"type": "string"},
            "description_hook": {"type": "string"},
            "pinned_comment": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "chapters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "focus": {"type": "string"},
                    },
                    "required": ["title", "focus"],
                },
            },
        },
        "required": ["title", "thumbnail_text", "description_hook", "pinned_comment", "tags", "chapters"],
    }
    p = (
        f"Topic: {topic}\nVerified context: {facts}\n"
        "Create a 7-chapter YouTube documentary outline (~10 minutes total). "
        "Rules: title <= 68 chars, high curiosity, NO colons, NO '#Shorts'. "
        "thumbnail_text must be 2 to 3 bold uppercase words different from title (e.g. 'NO ESCAPE BELOW'). "
        "chapters array MUST have exactly 7 short distinct chapter titles and a specific angle for each."
    )
    for _ in range(4):
        try:
            out = ollama_json(p, schema, max_tokens=700)
            if len(out.get("chapters", [])) >= 7 and len(out.get("title", "")) >= 12:
                out["chapters"] = out["chapters"][:7]
                return out
        except Exception as e:
            print(f"[!] Outline retry: {e}", flush=True)
            time.sleep(2)
    raise RuntimeError("Failed to generate 7-chapter outline")

def enrich_prompt(raw_p, topic, ch_title):
    s = clean_text(raw_p)
    if len(s.split()) < 8:
        s = f"Wide documentary 35mm film shot investigating {topic}, {ch_title}, moody natural overcast lighting, authentic textures"
    return s

def write_chapter(topic, facts, ch_spec, ch_outline, prev_tail, used_sentences):
    schema = {
        "type": "object",
        "properties": {
            "narration": {"type": "string"},
            "hero_prompt": {"type": "string"},
            "scene1": {"type": "string"},
            "scene2": {"type": "string"},
            "scene3": {"type": "string"},
            "scene4": {"type": "string"},
            "scene5": {"type": "string"},
        },
        "required": ["narration", "hero_prompt", "scene1", "scene2", "scene3", "scene4", "scene5"],
    }
    target_w = ch_spec["words"]
    min_w = max(115, int(target_w * 0.72))
    p = (
        f"Documentary Topic: {topic}\nFacts: {facts}\n"
        f"Chapter {ch_spec['idx']}/7: {ch_outline['title']}\nAngle: {ch_outline['focus']}\n"
        f"Role: {ch_spec['role']}\n"
        f"Previous ending line (continue smoothly, do NOT repeat it): {prev_tail}\n"
        f"Write EXACTLY around {target_w} words of spoken documentary narration in crisp sentences (no stage directions, no markdown, no welcome/subscribe).\n"
        "Also write 1 hero_prompt (cinematic motion shot for 16:9 video) and 5 distinct photorealistic still documentary scene prompts (scene1..scene5, realistic camera angles, archival/sensor/terrain/ocean/space details, zero neon or sci-fi)."
    )
    best = None
    for attempt in range(4):
        try:
            d = ollama_json(p, schema, max_tokens=950)
            nar = clean_text(d.get("narration", ""))
            wc = len(nar.split())
            if wc < min_w:
                print(f"[!] Ch {ch_spec['idx']} short ({wc}<{min_w}), retry {attempt+1}", flush=True)
                continue
            sents = {x.strip().lower() for x in re.split(r"[.!?]+", nar) if len(x.split()) > 5}
            if sents and len(sents & used_sentences) > 1:
                print(f"[!] Ch {ch_spec['idx']} repetitive sentence, retry {attempt+1}", flush=True)
                continue
            used_sentences.update(sents)
            scenes = [enrich_prompt(d.get(f"scene{k}", ""), topic, ch_outline["title"]) for k in range(1, 6)]
            return {
                "index": ch_spec["idx"],
                "title": clean_text(ch_outline["title"])[:60],
                "hero_motion": ch_spec["hero"],
                "hero_prompt": enrich_prompt(d.get("hero_prompt", ""), topic, ch_outline["title"]),
                "scenes": scenes,
                "narration": nar,
                "word_count": wc,
                "midroll_break_after": ch_spec["midroll"],
            }
        except Exception as e:
            print(f"[!] Ch {ch_spec['idx']} error: {e}", flush=True)
            time.sleep(2)
    raise RuntimeError(f"Failed writing chapter {ch_spec['idx']}")

def main():
    hist = load_history()
    topic, cat, facts = pick_topic(hist)
    print(f"[*] Long-Form Topic ({cat}): {topic}", flush=True)
    outline = make_outline(topic, facts)
    chapters, used_sents = [], set()
    prev_tail = "Start directly with the anomaly."
    for spec, ch_out in zip(CHAPTER_PLAN, outline["chapters"]):
        ch = write_chapter(topic, facts, spec, ch_out, prev_tail, used_sents)
        chapters.append(ch)
        prev_tail = " ".join(ch["narration"].split()[-22:])
        print(f"[*] Chapter {ch['index']}/7 ready ({ch['word_count']} words)", flush=True)

    total_words = sum(c["word_count"] for c in chapters)
    title = re.sub(r"[:<>#]", "", clean_text(outline["title"]))[:76]
    thumb_txt = " ".join(clean_text(outline["thumbnail_text"]).upper().split()[:3]) or "SILENT SIGNAL"
    doc = {
        "format": "long_documentary_16_9",
        "channel_signature": "SILENT SIGNAL",
        "topic": topic,
        "category": cat,
        "title": title,
        "thumbnail_text": thumb_txt,
        "description_hook": clean_text(outline["description_hook"])[:400],
        "pinned_comment": clean_text(outline["pinned_comment"])[:350],
        "tags": [clean_text(t)[:38] for t in outline.get("tags", [])[:15] if clean_text(t)],
        "total_words": total_words,
        "chapters": chapters,
    }
    json.dump(doc, open(OUT_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"[*] Saved {OUT_FILE}: {total_words} words across 7 chapters.", flush=True)

if __name__ == "__main__":
    main()
