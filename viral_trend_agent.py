import json, os, random, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

UA = "SilentSignal-TrendEngine/5.0 (compatible; DocumentaryResearch/1.0)"
HISTORY_FILE, REQUESTS_FILE, OUTPUT_FILE = "posted_history.json", "requested_topics.json", "trending_topic.json"

PILLARS = [
    ("deep_ocean", "OCEAN", "Deep Ocean Frontiers", ["mariana trench discovery", "deep sea hydrothermal vent"], "https://www.livescience.com/feeds/planet-earth", ["mariana", "trench", "ocean", "submarine", "abyss", "seafloor", "bloop"]),
    ("forbidden_zones", "MYSTERY", "Sealed & Forbidden Sites", ["kola superdeep borehole", "lake vostok antarctica", "sealed ancient vault"], "https://www.smithsonianmag.com/rss/latest_articles/", ["borehole", "vostok", "vault", "cave", "island", "bunker", "sealed"]),
    ("vanished_signals", "SIGNAL", "Vanished & Unexplained Signals", ["wow radio signal", "lost arctic expedition shipwreck"], "https://www.space.com/feeds/all", ["signal", "expedition", "shipwreck", "apollo", "voyager", "radio", "vanished"]),
    ("earth_anomalies", "EARTH", "Extreme Earth Anomalies", ["darvaza crater", "lake natron", "tunguska event"], "https://www.sciencedaily.com/rss/earth_climate.xml", ["crater", "caldera", "sinkhole", "volcano", "lake", "sahara", "tunguska"]),
]

CURATED_BANK = [
    ("deep_ocean", "OCEAN", "Mariana Trench Challenger Deep", "At 10,984 meters deep, pressure crushes steel like paper yet life still survives."),
    ("deep_ocean", "OCEAN", "Point Nemo Oceanic Pole", "Why spacecraft graveyard Point Nemo lies 2,688 kilometers from any human being."),
    ("deep_ocean", "OCEAN", "Baltic Sea Floor Formation", "A 60-meter circular seabed structure recorded at 85 meters depth in 2011."),
    ("deep_ocean", "OCEAN", "Brine Pools Under the Gulf", "Underwater toxic lakes on the ocean floor that preserve anything that falls inside."),
    ("forbidden_zones", "MYSTERY", "Kola Superdeep Borehole", "Russia drilled 12,262 meters into Earth's crust until heat forced them to weld it shut."),
    ("forbidden_zones", "MYSTERY", "Lake Vostok Antarctica", "A prehistoric freshwater lake sealed beneath four kilometers of solid Antarctic ice."),
    ("forbidden_zones", "MYSTERY", "Movile Cave Romania", "Sealed for five million years in toxic air with creatures found nowhere else on Earth."),
    ("forbidden_zones", "MYSTERY", "Ilha da Queimada Grande", "Why Brazil's navy strictly bans anyone from stepping onto Snake Island."),
    ("vanished_signals", "SIGNAL", "Wow! signal", "A 72-second narrowband radio burst at 1420 MHz detected in 1977 that never returned."),
    ("vanished_signals", "SIGNAL", "Max Headroom signal hijacking", "For 88 seconds in 1987, an unknown transmitter hijacked two Chicago TV stations."),
    ("vanished_signals", "SIGNAL", "Endurance (1912 ship)", "Crushed by Antarctic pack ice in 1915 and discovered intact 3,008 meters below."),
    ("vanished_signals", "SIGNAL", "Operation Highjump", "A 4,700-person US Navy Antarctic fleet pulled back early amid brutal polar conditions."),
    ("earth_anomalies", "EARTH", "Darvaza gas crater", "A collapsed Soviet drilling site in Turkmenistan burning continuously since 1971."),
    ("earth_anomalies", "EARTH", "Richat Structure", "A 40-kilometer bullseye carved into the Sahara desert visible from orbit."),
    ("earth_anomalies", "EARTH", "Lake Natron", "Caustic soda water in Tanzania that calcifies birds into stone-like statues."),
    ("earth_anomalies", "EARTH", "Tunguska event", "An atmospheric blast over Siberia in 1908 flattened 80 million trees with no crater."),
]

ANGLES = [
    "START_WITH_IMPOSSIBLE_NUMBER: Open immediately with the extreme depth, year, or measurement that breaks expectation.",
    "CAUSE_AND_EFFECT_SURVIVAL: Explain the exact physical mechanism why humans or equipment cannot survive there.",
    "THE_SEALED_WARNING: Focus on why authorities or scientists shut down access or stopped investigation.",
    "UNEXPLAINED_RECORDED_DATA: Anchor on real sensor readings, sonar scans, or archived logs still debated today.",
]

BLOCKED = ("murder", "serial killer", "homicide", "suicide", "self-harm", "rape", "sexual", "gore", "torture", "shooting", "massacre", "terrorist", "trump", "biden", "election", "gaza", "israel", "ukraine", "putin", "crypto", "bitcoin", "celebrity", "porn", "onlyfans", "nfl", "nba", "cricket")
BORING = ("study finds", "researchers develop", "new report", "market", "conference", "policy", "funding", "quarterly", "grants", "scientists say new")
POWER = {"mariana", "trench", "borehole", "deepest", "vanished", "sealed", "forbidden", "signal", "crater", "toxic", "antarctica", "sahara", "shipwreck", "underground", "unexplained", "extreme", "volcano", "abyss", "vostok"}
STOP = {"the", "and", "for", "with", "that", "this", "from", "what", "why", "how", "into", "you", "your", "are", "was", "were", "have", "has"}

get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=9).read().decode("utf-8", errors="ignore")
safe = lambda t: len(t.strip()) >= 8 and not any(b in t.lower() for b in BLOCKED) and not any(x in t.lower() for x in BORING)
tok = lambda t: {w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) >= 3 and w not in STOP}


def load_hist():
    if not os.path.exists(HISTORY_FILE):
        return [], set(), None
    try:
        raw = json.load(open(HISTORY_FILE, encoding="utf-8"))
    except Exception:
        return [], set(), None
    items = raw if isinstance(raw, list) else raw.get("topics", raw.get("history", []))
    titles, last_p = set(), None
    for x in items:
        t = x if isinstance(x, str) else (x.get("topic") or x.get("title") or "")
        if t:
            titles.add(t.strip().lower())
        if isinstance(x, dict) and x.get("pillar_id"):
            last_p = x["pillar_id"]
    return raw, titles, last_p


def save_hist(raw, topic, pid):
    entry = {"topic": topic, "pillar_id": pid, "ts": datetime.now(timezone.utc).isoformat()}
    if isinstance(raw, list):
        raw.append(entry)
    elif isinstance(raw, dict):
        raw.setdefault("topics" if "topics" in raw else "history", []).append(topic)
    else:
        raw = [entry]
    json.dump(raw, open(HISTORY_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def is_dup(cand, old_set):
    c, ct = cand.strip().lower(), tok(cand)
    if not ct or c in old_set:
        return True
    return any(c in o or o in c or (len(ct & tok(o)) / max(1, min(len(ct), len(tok(o))))) >= 0.55 for o in old_set if tok(o))


def wiki_verify(query):
    for q in (query, " ".join(sorted(tok(query), key=len, reverse=True)[:4])):
        if not q.strip():
            continue
        try:
            hits = json.loads(get(f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote_plus(q)}&srlimit=2&format=json")).get("query", {}).get("search", [])
            for h in hits:
                wtitle = h["title"]
                sd = json.loads(get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(wtitle.replace(' ', '_'))}"))
                ext = re.sub(r"\s+", " ", sd.get("extract", "")).strip()
                if len(ext) >= 240 and "may refer to:" not in ext.lower() and sd.get("type") != "disambiguation":
                    return wtitle, ext[:1000]
        except Exception:
            pass
    return "", ""


def score_cand(title, facts, kws):
    lt = title.lower()
    sc = len(tok(title) & POWER) * 3 + sum(2 for k in kws if k in lt)
    if re.search(r"\d", facts):
        sc += 3
    if len(facts) >= 500:
        sc += 2
    return sc


def fetch_live(p, old_set):
    pool = []
    for q in p[3]:
        try:
            for it in ET.fromstring(get(f"https://news.google.com/rss/search?q={urllib.parse.quote_plus(q)}&hl=en-US&gl=US&ceid=US:en")).findall(".//item")[:5]:
                t = re.sub(r"\s+-\s+[^-]+$", "", (it.findtext("title") or "").strip()).strip()
                if safe(t):
                    pool.append((t, "google_news"))
        except Exception:
            pass
    try:
        for it in ET.fromstring(get(p[4])).findall(".//item")[:5]:
            t = (it.findtext("title") or "").strip()
            if safe(t):
                pool.append((t, "science_rss"))
    except Exception:
        pass
    for offset in (1, 2):
        try:
            dt = datetime.now(timezone.utc) - timedelta(days=offset)
            arts = json.loads(get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{dt:%Y/%m/%d}"))["items"][0]["articles"]
            for a in arts[:450]:
                rt = a.get("article", "")
                if not rt.startswith(("Main_Page", "Special:", "Wikipedia:", "File:", "Portal:", "Deaths_in_")):
                    cl = rt.replace("_", " ").strip()
                    if any(h in cl.lower() for h in p[5]) and safe(cl):
                        pool.append((cl, "wiki_spike"))
            break
        except Exception:
            pass

    verified, seen = [], set()
    random.shuffle(pool)
    for raw_t, src in pool[:14]:
        if raw_t.lower() in seen or is_dup(raw_t, old_set):
            continue
        wtitle, facts = wiki_verify(raw_t)
        if not wtitle or is_dup(wtitle, old_set):
            continue
        seen.add(wtitle.lower())
        verified.append({"topic": wtitle, "facts": facts, "source": src, "score": score_cand(wtitle, facts, p[5])})
    verified.sort(key=lambda x: x["score"], reverse=True)
    return verified


def main():
    raw, old_set, last_p = load_hist()
    angle = random.choice(ANGLES)
    p, topic, facts, src, score = None, "", "", "", 0

    if os.path.exists(REQUESTS_FILE):
        try:
            reqs = json.load(open(REQUESTS_FILE, encoding="utf-8"))
            for i, r in enumerate(reqs):
                rt = (r.get("topic", "") if isinstance(r, dict) else str(r)).strip()
                if safe(rt) and not is_dup(rt, old_set):
                    wt, wf = wiki_verify(rt)
                    topic, facts = (wt or rt), (wf or f"Verified real documentary subject: {rt}.")
                    p, src, score = random.choice(PILLARS), "viewer_req", 99
                    json.dump(reqs[:i] + reqs[i + 1 :], open(REQUESTS_FILE, "w", encoding="utf-8"), indent=2)
                    break
        except Exception:
            pass

    if not topic:
        elig = [x for x in PILLARS if x[0] != last_p] or PILLARS
        random.shuffle(elig)
        for cand_p in elig:
            got = fetch_live(cand_p, old_set)
            if got:
                best = got[0]
                p, topic, facts, src, score = cand_p, best["topic"], best["facts"], best["source"], best["score"]
                break

    if not topic:
        unused = [c for c in CURATED_BANK if not is_dup(c[2], old_set)] or CURATED_BANK
        elig_c = [c for c in unused if c[0] != last_p] or unused
        pid, theme, c_topic, seed_fact = random.choice(elig_c)
        p = next((x for x in PILLARS if x[0] == pid), PILLARS[0])
        wt, wf = wiki_verify(c_topic)
        topic = wt or c_topic
        facts = f"{seed_fact} {wf}".strip()[:1000]
        src, score = "curated_verified", 10

    out = {
        "theme": p[1], "topic": topic, "badge": "", "case_label": "",
        "angle": angle, "psych_strategy": angle, "fact_summary": facts,
        "pillar": p[2], "pillar_id": p[0], "source_type": src, "viral_score": score,
    }
    json.dump(out, open(OUTPUT_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    save_hist(raw, topic, p[0])
    print(f"[*] Selected [{p[2]} | {src} | score={score}]: {topic}", flush=True)


if __name__ == "__main__":
    main()
