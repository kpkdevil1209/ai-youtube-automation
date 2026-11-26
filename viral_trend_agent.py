import os, re, json, random, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

UA = "SilentSignal-TrendEngine/6.0"
HISTORY_FILE, REQUESTS_FILE, OUTPUT_FILE = "posted_history.json", "requested_topics.json", "trending_topic.json"

PILLARS = [
    ("deep_ocean", "OCEAN", "Deep Ocean", "https://www.livescience.com/feeds/planet-earth", ["ocean", "trench", "mariana", "submarine", "abyss", "bloop", "hydrothermal", "seafloor"]),
    ("forbidden_zones", "MYSTERY", "Forbidden Places", "https://www.smithsonianmag.com/rss/latest_articles/", ["tomb", "island", "bunker", "vault", "temple", "forbidden", "sealed", "cave"]),
    ("vanished_signals", "SIGNAL", "Vanished Signals", "https://www.space.com/feeds/all", ["signal", "radio", "wow", "telemetry", "black box", "satellite", "anomaly", "radar"]),
    ("earth_anomalies", "EARTH", "Earth Anomalies", "https://www.livescience.com/feeds/all", ["borehole", "kola", "vostok", "sinkhole", "crater", "antarctica", "magnetic", "ice"]),
]

CURATED = [
    ("Mariana Trench Bloop Sound", "deep_ocean", "Bloop"),
    ("Kola Superdeep Borehole", "earth_anomalies", "Kola Superdeep Borehole"),
    ("Wow Signal 1977 Radio Mystery", "vanished_signals", "Wow! signal"),
    ("Lake Vostok Subglacial Antarctica", "earth_anomalies", "Lake Vostok"),
    ("Point Nemo Oceanic Pole", "deep_ocean", "Point Nemo"),
    ("North Sentinel Island", "forbidden_zones", "North Sentinel Island"),
    ("Svalbard Global Seed Vault", "forbidden_zones", "Svalbard Global Seed Vault"),
    ("Baltic Sea Anomaly", "deep_ocean", "Baltic Sea anomaly"),
    ("Darvaza Gas Crater", "earth_anomalies", "Darvaza gas crater"),
    ("Vela Incident 1979", "vanished_signals", "Vela incident"),
    ("Tunguska Event 1908", "earth_anomalies", "Tunguska event"),
    ("Mary Celeste Ghost Ship", "deep_ocean", "Mary Celeste"),
    ("Dyatlov Pass Incident", "earth_anomalies", "Dyatlov Pass incident"),
    ("USS Cyclops Disappearance", "deep_ocean", "USS Cyclops"),
    ("Malaysia Airlines Flight 370", "vanished_signals", "Malaysia Airlines Flight 370"),
    ("Submarine Kursk Disaster", "deep_ocean", "Kursk submarine disaster"),
]

BORING = re.compile(r"\b(stock|market|tariff|election|celebrity|movie|trailer|nba|nfl|iphone|review|diet|vaccine|crypto)\b", re.I)

def fetch_text(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")

def fetch_json(url, timeout=12):
    return json.loads(fetch_text(url, timeout))

def wiki_verify(query):
    try:
        q = urllib.parse.quote(query)
        s = fetch_json(f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&format=json&srlimit=3")
        hits = s.get("query", {}).get("search", [])
        for h in hits[:2]:
            title = h.get("title", "")
            if not title: continue
            d = fetch_json("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_")))
            if d.get("type") == "disambiguation": continue
            ext = re.sub(r"\s+", " ", d.get("extract", "")).strip()
            if len(ext) >= 240:
                return title, ext[:1400]
    except Exception:
        pass
    return None, ""

def load_history():
    if not os.path.exists(HISTORY_FILE): return set()
    try:
        data = json.load(open(HISTORY_FILE, encoding="utf-8"))
        out = set()
        for x in data:
            t = x.get("topic") or x.get("title") or (x if isinstance(x, str) else "")
            if t: out.add(t.lower())
        return out
    except Exception:
        return set()

def is_dup(cand, hist):
    w1 = {w for w in re.findall(r"[a-z]{4,}", cand.lower())}
    for h in hist:
        w2 = {w for w in re.findall(r"[a-z]{4,}", h)}
        if w1 and w2 and len(w1 & w2) >= min(3, len(w1)): return True
    return False

def score_title(t, kws):
    if BORING.search(t): return -99
    low = t.lower()
    sc = sum(12 for k in kws if k in low)
    if any(w in low for w in ("mystery", "deepest", "signal", "unexplained", "vanished", "sealed", "record", "impossible", "hidden")): sc += 15
    if re.search(r"\d", t): sc += 8
    return sc

def main():
    hist = load_history()
    if os.path.exists(REQUESTS_FILE):
        try:
            reqs = json.load(open(REQUESTS_FILE, encoding="utf-8"))
            if isinstance(reqs, list) and reqs:
                req_topic = str(reqs.pop(0))
                json.dump(reqs, open(REQUESTS_FILE, "w", encoding="utf-8"), indent=2)
                wtitle, ext = wiki_verify(req_topic)
                if ext:
                    out = {"topic": wtitle or req_topic, "pillar": "earth_anomalies", "pillar_name": "Viewer Request", "fact_summary": ext, "source": "viewer_request"}
                    json.dump(out, open(OUTPUT_FILE, "w", encoding="utf-8"), indent=2)
                    print("[+] Viewer Request Topic:", out["topic"])
                    return
        except Exception:
            pass

    cands = []
    for pid, _, pname, rss_url, kws in PILLARS:
        try:
            root = ET.fromstring(fetch_text(rss_url))
            for item in root.findall(".//item")[:15]:
                t = re.sub(r"\s+", " ", (item.findtext("title") or "")).strip()
                if not t or is_dup(t, hist): continue
                sc = score_title(t, kws)
                if sc >= 15: cands.append((sc, t, pid, pname))
        except Exception:
            pass

    cands.sort(key=lambda x: x[0], reverse=True)
    for _, t, pid, pname in cands[:6]:
        wtitle, ext = wiki_verify(t)
        if ext and not is_dup(wtitle, hist):
            out = {"topic": wtitle, "pillar": pid, "pillar_name": pname, "fact_summary": ext, "source": "rss_wiki"}
            json.dump(out, open(OUTPUT_FILE, "w", encoding="utf-8"), indent=2)
            print(f"[+] Selected RSS+Wiki Topic ({pname}): {wtitle} ({len(ext)} chars)")
            return

    pool = list(CURATED)
    random.shuffle(pool)
    for topic, pid, wquery in pool:
        if is_dup(topic, hist): continue
        wtitle, ext = wiki_verify(wquery)
        if ext:
            pname = next((p[2] for p in PILLARS if p[0] == pid), "Mystery")
            out = {"topic": wtitle or topic, "pillar": pid, "pillar_name": pname, "fact_summary": ext, "source": "curated_wiki"}
            json.dump(out, open(OUTPUT_FILE, "w", encoding="utf-8"), indent=2)
            print(f"[+] Selected Curated+Wiki Topic ({pname}): {out['topic']} ({len(ext)} chars)")
            return

    wtitle, ext = wiki_verify("Kola Superdeep Borehole")
    out = {"topic": wtitle or "Kola Superdeep Borehole", "pillar": "earth_anomalies", "pillar_name": "Earth Anomalies", "fact_summary": ext or "The Kola Superdeep Borehole reached 12,262 meters deep in Russia before extreme 180C heat turned solid rock into flowing plastic, forcing engineers to seal it permanently in 1995.", "source": "emergency"}
    json.dump(out, open(OUTPUT_FILE, "w", encoding="utf-8"), indent=2)
    print("[+] Fallback Topic:", out["topic"])

if __name__ == "__main__":
    main()
