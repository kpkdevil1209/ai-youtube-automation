import os, re, json, random, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

UA = "SilentSignal-TrendEngine/4.2"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
HISTORY_FILE, REQUESTS_FILE, OUTPUT_FILE = "posted_history.json", "requested_topics.json", "trending_topic.json"

PILLARS = [
    ("extreme_survival", "SURVIVAL", "SURVIVAL CASE", "Extreme Survival", ["trapped cave rescue days survived", "lost at sea rescued survival"], ["what happens if you get trapped in", "how long can a human survive without"], "https://www.livescience.com/feeds/all", ["cave", "rescue", "survival", "hypothermia", "trapped"]),
    ("forbidden_places", "MYSTERY", "RESTRICTED ZONE", "Forbidden Places", ["sealed ancient tomb discovered", "forbidden island underground bunker"], ["why nobody is allowed to visit", "secret underground city discovered"], "https://www.smithsonianmag.com/rss/latest_articles/", ["tomb", "island", "bunker", "vault", "temple", "forbidden"]),
    ("deep_ocean", "OCEAN", "ABYSS DEPTH", "Deep Ocean", ["mariana trench deep sea discovery", "underwater volcano wreck exploration"], ["scariest thing found at the bottom of the ocean", "what happens at the bottom of mariana trench"], "https://www.livescience.com/feeds/planet-earth", ["ocean", "trench", "mariana", "submarine", "abyss"]),
    ("cosmic_horror", "COSMOS", "DEEP SPACE", "Cosmic Scale", ["rogue planet black hole discovery", "nasa unexplained signal deep space"], ["what happens if you fall into", "scariest thing discovered in space"], "https://www.space.com/feeds/all", ["black hole", "planet", "nebula", "asteroid", "supernova"]),
    ("mega_disasters", "DISASTER", "CRITICAL FAILURE", "Engineering Disasters", ["kola superdeep borehole earth", "dam collapse submersible implosion"], ["why they sealed the deepest hole", "worst engineering disaster in history"], "https://www.sciencedaily.com/rss/matter_energy/engineering.xml", ["borehole", "dam", "reactor", "implosion", "shipwreck"]),
    ("bizarre_nature", "NATURE", "DEADLY ZONE", "Deadliest Nature", ["boiling river lake natron deadly", "glowing cave toxic crater nature"], ["deadliest place on earth you cant survive", "lake that turns animals into"], "https://www.livescience.com/feeds/planet-earth", ["lake", "volcano", "crater", "desert", "cave", "geyser"]),
    ("human_body_limits", "BIOLOGY", "HUMAN LIMIT", "Human Body Limits", ["everest death zone altitude body", "deep sea diver decompression bends"], ["what happens to your body at the bottom of", "what happens to your body in deep space"], "https://www.livescience.com/feeds/health", ["decompression", "hypothermia", "altitude", "g-force", "bends"]),
    ("lost_expeditions", "EXPEDITION", "LOST RECORD", "Ghost Expeditions", ["endurance shipwreck expedition found", "abandoned arctic station vanished"], ["expedition that vanished without a trace", "ghost ship found drifting with no crew"], "https://www.smithsonianmag.com/rss/history/", ["expedition", "shipwreck", "vanished", "arctic", "lighthouse"]),
    ("prehistoric_earth", "PREHISTORIC", "ANCIENT EARTH", "Prehistoric Earth", ["giant prehistoric predator fossil", "ancient earth before humans extinction"], ["scariest prehistoric creature that actually existed", "what earth looked like before humans"], "https://www.livescience.com/feeds/animals", ["fossil", "extinction", "asteroid", "megalodon", "dinosaur"]),
    ("extreme_weather", "EARTH", "EXTREME FORCE", "Earth Fury", ["giant sinkhole supervolcano caldera", "megatsunami rogue wave recorded"], ["biggest rogue wave ever recorded", "what happens if a supervolcano erupts"], "https://www.sciencedaily.com/rss/earth_climate.xml", ["tsunami", "supervolcano", "sinkhole", "earthquake", "caldera"]),
]

ANGLES = [
    "THE_COUNTDOWN_TRAP: Second-by-second escalation of a real crisis.",
    "FORBIDDEN_REASON: Real terrifying reason a place is sealed.",
    "SCALE_SHOCK: Mind-breaking depth, speed, or pressure comparison.",
    "BODY_UNDER_EXTREME: Exact physical reaction inside extreme conditions.",
    "THE_SEALED_MYSTERY: Why experts locked it down and left.",
    "HIDDEN_MECHANISM: Invisible natural trigger behind a deadly event.",
    "VANISHED_WITHOUT_TRACE: Last recorded clue before everything stopped.",
    "PREHISTORIC_NIGHTMARE: Extinct predator or ancient catastrophe reality.",
    "TINY_FLAW_MEGA_DISASTER: How one small flaw caused total collapse.",
    "STRANGER_THAN_FICTION: Verified anomaly that defies normal physics.",
    "LAST_30_SECONDS: Final moments of a real survival crisis.",
    "THE_SILENT_KILLER: Invisible natural danger with zero warning.",
    "IF_IT_HAPPENED_TODAY: What happens right now if this event struck.",
    "THE_UNSOLVED_SIGNAL: Real recorded anomaly still unexplained.",
    "NATURE_ENGINEERED_TRAP: Nature built a deadlier trap than humans.",
]

BLOCKED = ("murder", "serial killer", "homicide", "suicide", "self-harm", "rape", "sexual", "gore", "decapitat", "torture", "shooting", "massacre", "terrorist", "trump", "biden", "election", "gaza", "israel", "ukraine", "putin", "crypto", "bitcoin", "celebrity", "porn", "onlyfans", "naked", "nfl", "nba", "cricket")
VAGUE = ("deathline", "human body limit", "shocking truth", "mind blowing", "hidden truth", "dark secret", "secret revealed", "unknown mystery", "you wont believe")
STOP = {"the", "and", "for", "with", "that", "this", "from", "what", "why", "how", "into", "you", "your", "are", "was", "were", "have", "has", "really", "happens"}

get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=8).read().decode("utf-8", errors="ignore")
safe = lambda t: len(t.strip()) >= 14 and not any(b in t.lower() for b in BLOCKED)
concrete = lambda t: safe(t) and ":" not in t and not any(v in t.lower() for v in VAGUE) and len(t.split()) >= 5
tok = lambda t: {w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) >= 3 and w not in STOP}

def load_hist():
    if not os.path.exists(HISTORY_FILE): return [], set(), None, 0
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f: raw = json.load(f)
    except Exception: return [], set(), None, 0
    items = raw if isinstance(raw, list) else raw.get("topics", raw.get("history", []))
    titles, last_p = set(), None
    for x in items:
        t = x if isinstance(x, str) else (x.get("topic") or x.get("title") or "")
        if t: titles.add(t.strip().lower())
        if isinstance(x, dict) and x.get("pillar_id"): last_p = x["pillar_id"]
    return raw, titles, last_p, len(items)

def save_hist(raw, topic, pid):
    if isinstance(raw, list): raw.append({"topic": topic, "pillar_id": pid, "ts": datetime.now(timezone.utc).isoformat()})
    elif isinstance(raw, dict): raw.setdefault("topics" if "topics" in raw else "history", []).append(topic)
    else: raw = [{"topic": topic, "pillar_id": pid, "ts": datetime.now(timezone.utc).isoformat()}]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(raw, f, indent=2, ensure_ascii=False)

def is_dup(cand, old_set):
    c, ct = cand.strip().lower(), tok(cand)
    if not ct or c in old_set: return True
    return any(c in o or o in c or (len(ct & tok(o)) / max(1, min(len(ct), len(tok(o))))) >= 0.55 for o in old_set if tok(o))

def fetch_live(p, old_set):
    pool = []
    for q in p[4]:
        try:
            for it in ET.fromstring(get(f"https://news.google.com/rss/search?q={urllib.parse.quote_plus(q)}&hl=en-US&gl=US&ceid=US:en")).findall(".//item")[:6]:
                t = re.sub(r"\s+-\s+[^-]+$", "", (it.findtext("title") or "").strip()).strip()
                if safe(t): pool.append({"title": t, "source": "google_news", "summary": ""})
        except Exception: pass
    for s in p[5]:
        try:
            d = json.loads(get(f"https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q={urllib.parse.quote_plus(s)}"))
            for x in (d[1][:6] if len(d) > 1 else []):
                if len(str(x).split()) >= 5 and safe(str(x)): pool.append({"title": str(x).strip().title(), "source": "yt_trend", "summary": ""})
        except Exception: pass
    try:
        for it in ET.fromstring(get(p[6])).findall(".//item")[:6]:
            t = (it.findtext("title") or "").strip()
            desc = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", it.findtext("description") or ""))[:240]
            if safe(t): pool.append({"title": t, "source": "science_rss", "summary": desc})
    except Exception: pass
    for offset in (1, 2):
        try:
            dt = datetime.now(timezone.utc) - timedelta(days=offset)
            arts = json.loads(get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{dt:%Y/%m/%d}"))["items"][0]["articles"]
            for a in arts[:450]:
                rt = a.get("article", "")
                if not rt.startswith(("Main_Page", "Special:", "Wikipedia:", "File:", "Portal:", "Deaths_in_")):
                    cl = rt.replace("_", " ").strip()
                    if any(h in cl.lower() for h in p[7]) and safe(cl): pool.append({"title": cl, "source": "wiki_spike", "summary": ""})
            break
        except Exception: pass
    out, seen = [], set()
    for x in pool:
        k = x["title"].lower()
        if k not in seen and not is_dup(x["title"], old_set): seen.add(k); out.append(x)
    return out

def wiki_fact(q):
    for query in (q, " ".join(sorted(tok(q), key=len, reverse=True)[:4])):
        if not query.strip(): continue
        try:
            hits = json.loads(get(f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote_plus(query)}&srlimit=1&format=json"))["query"]["search"]
            if hits: return re.sub(r"\s+", " ", json.loads(get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(hits[0]['title'].replace(' ', '_'))}")).get("extract", ""))[:320]
        except Exception: pass
    return ""

def main():
    raw, old_set, last_p, cnt = load_hist()
    case_num, case_lbl = cnt + 1, f"FILE #{cnt + 1:03d}"
    egg, angle = f"{random.choice('XVKZ')}-{cnt+1:02d}{random.randint(1,9)}", random.choice(ANGLES)
    req_by, p, base, topic = "", None, None, ""
    if os.path.exists(REQUESTS_FILE):
        try:
            with open(REQUESTS_FILE, encoding="utf-8") as f: reqs = json.load(f)
            for i, r in enumerate(reqs):
                if safe(r.get("topic", "")) and not is_dup(r["topic"], old_set):
                    p, topic, req_by = random.choice(PILLARS), r["topic"].strip(), r.get("user", "@Fan").strip()
                    base = {"title": topic, "source": "viewer_req", "summary": ""}
                    with open(REQUESTS_FILE, "w", encoding="utf-8") as wf: json.dump(reqs[:i] + reqs[i+1:], wf, indent=2)
                    break
        except Exception: pass
    if not topic:
        elig = [x for x in PILLARS if x[0] != last_p] or PILLARS
        random.shuffle(elig)
        cands = []
        for x in elig[:5]:
            got = fetch_live(x, old_set)
            if len(got) > len(cands): cands, p = got, x
            if len(cands) >= 4: break
        if not cands: raise RuntimeError("No live candidates fetched")
        try:
            lines = "\n".join(f"{i+1}. [{c['source']}] {c['title']}" for i, c in enumerate(cands[:14]))
            prompt = f"Pillar: {p[3]}\nAngle: {angle}\nItems:\n{lines}\nPick #1 concrete real-world item (real place, creature, event, or survival case). Rewrite as 6-10 word English Title Case Shorts hook naming that exact subject. NO colons (:), NO vague words like Deathline, Limit, Secret, Truth, Shocking. JSON only: {{\"index\":int,\"topic\":str}}"
            req = urllib.request.Request(OLLAMA_URL, data=json.dumps({"model": MODEL, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": 0.3, "repeat_penalty": 1.25, "num_predict": 120}}).encode(), headers={"Content-Type": "application/json"}, method="POST")
            res = json.loads(json.loads(urllib.request.urlopen(req, timeout=40).read().decode())["response"])
            base = cands[max(0, min(len(cands)-1, int(res.get("index", 1))-1))]
            t = str(res.get("topic", "")).strip()
            topic = t if concrete(t) and not is_dup(t, old_set) else base["title"]
        except Exception:
            base = sorted(cands, key=lambda c: (3 if c["source"] == "yt_trend" else 2) + len(tok(c["title"]) & {"survive", "trapped", "deepest", "deadliest", "vanished", "forbidden", "mariana", "everest"}), reverse=True)[0]
            topic = base["title"]
    fact = base.get("summary") or wiki_fact(base["title"]) or wiki_fact(topic)
    out = {"theme": p[1], "topic": topic, "badge": f"{case_lbl} | {('BY ' + req_by) if req_by else p[2]}"[:28], "case_number": case_num, "case_label": case_lbl, "easter_egg_code": egg, "requested_by": req_by, "angle": angle, "psych_strategy": angle, "fact_summary": fact, "pillar": p[3], "pillar_id": p[0], "source_type": base["source"]}
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f: json.dump(out, f, indent=2, ensure_ascii=False)
    save_hist(raw, topic, p[0])
    print(f"[*] {case_lbl} | {base['source']} -> {topic} | Clue: {egg}", flush=True)

if __name__ == "__main__":
    main()
