import os
import re
import json
import random
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

USER_AGENT = "DevilOS-TrendEngine/4.0 (Documentary Research)"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
HISTORY_FILE = "posted_history.json"
OUTPUT_FILE = "trending_topic.json"

PILLARS = [
    {
        "id": "extreme_survival",
        "theme": "SURVIVAL",
        "badge": "SURVIVAL CASE",
        "name": "Extreme Human Survival & What-If",
        "news_queries": ["extreme survival rescued days lost", "cave diving trapped rescue science"],
        "yt_seeds": ["what happens if you get trapped in", "how long can a human survive without"],
        "rss_urls": ["https://www.livescience.com/feeds/all"],
        "wiki_hints": ["cave", "rescue", "survival", "hypothermia", "mountain", "trapped"],
    },
    {
        "id": "forbidden_places",
        "theme": "MYSTERY",
        "badge": "RESTRICTED ZONE",
        "name": "Forbidden Places & Sealed Mysteries",
        "news_queries": ["sealed ancient tomb discovered archaeologists", "forbidden island secret underground city"],
        "yt_seeds": ["why nobody is allowed to visit", "secret underground city discovered"],
        "rss_urls": ["https://www.smithsonianmag.com/rss/latest_articles/"],
        "wiki_hints": ["tomb", "island", "bunker", "vault", "temple", "underground", "forbidden"],
    },
    {
        "id": "deep_ocean",
        "theme": "OCEAN",
        "badge": "ABYSS DEPTH",
        "name": "Deep Ocean & Abyssal Anomalies",
        "news_queries": ["deep sea discovery mariana trench ocean", "strange underwater anomaly oceanographers"],
        "yt_seeds": ["scariest thing found at the bottom of the ocean", "what happens at the bottom of mariana trench"],
        "rss_urls": ["https://www.livescience.com/feeds/planet-earth"],
        "wiki_hints": ["ocean", "trench", "mariana", "submarine", "abyss", "sea"],
    },
    {
        "id": "cosmic_horror",
        "theme": "COSMOS",
        "badge": "DEEP SPACE",
        "name": "Cosmic Scale & Space Phenomena",
        "news_queries": ["rogue planet black hole terrifying space discovery", "nasa unexplained signal deep space"],
        "yt_seeds": ["what happens if you fall into", "scariest thing discovered in space"],
        "rss_urls": ["https://www.space.com/feeds/all"],
        "wiki_hints": ["black hole", "planet", "nebula", "asteroid", "supernova", "comet"],
    },
    {
        "id": "mega_disasters",
        "theme": "DISASTER",
        "badge": "CRITICAL FAILURE",
        "name": "Engineering Failures & Mega-Disasters",
        "news_queries": ["deepest hole earth engineering disaster", "submersible implosion physics megastructure"],
        "yt_seeds": ["why they sealed the deepest hole", "worst engineering disaster in history"],
        "rss_urls": ["https://www.sciencedaily.com/rss/matter_energy/engineering.xml"],
        "wiki_hints": ["borehole", "dam", "reactor", "implosion", "shipwreck", "collapse"],
    },
    {
        "id": "bizarre_nature",
        "theme": "NATURE",
        "badge": "DEADLY ZONE",
        "name": "Deadliest & Strangest Places on Earth",
        "news_queries": ["deadliest lake river bizarre natural phenomenon", "mysterious glowing cave boiling river"],
        "yt_seeds": ["deadliest place on earth you cant survive", "lake that turns animals into"],
        "rss_urls": ["https://www.livescience.com/feeds/planet-earth"],
        "wiki_hints": ["lake", "volcano", "crater", "desert", "cave", "geyser"],
    },
    {
        "id": "human_body_limits",
        "theme": "BIOLOGY",
        "badge": "HUMAN LIMIT",
        "name": "Extreme Human Body & Survival Limits",
        "news_queries": ["human body survival limit science extreme", "what happens body zero oxygen deep pressure"],
        "yt_seeds": ["what happens to your body after days without", "what happens to your body in deep space"],
        "rss_urls": ["https://www.sciencedaily.com/rss/mind_brain.xml"],
        "wiki_hints": ["decompression", "sleep deprivation", "altitude", "g-force", "starvation"],
    },
    {
        "id": "lost_expeditions",
        "theme": "EXPEDITION",
        "badge": "LOST RECORD",
        "name": "Vanished Expeditions & Ghost Mysteries",
        "news_queries": ["lost ship expedition vanished without trace found", "abandoned arctic station mystery"],
        "yt_seeds": ["expedition that vanished without a trace", "ghost ship found drifting with no crew"],
        "rss_urls": ["https://www.smithsonianmag.com/rss/history/"],
        "wiki_hints": ["expedition", "shipwreck", "vanished", "arctic", "antarctica", "lighthouse"],
    },
    {
        "id": "prehistoric_earth",
        "theme": "PREHISTORIC",
        "badge": "ANCIENT EARTH",
        "name": "Prehistoric Monsters & Lost Earth Eras",
        "news_queries": ["giant prehistoric predator fossil discovered", "ancient earth era before humans extinction"],
        "yt_seeds": ["scariest prehistoric creature that actually existed", "what earth looked like before humans"],
        "rss_urls": ["https://www.livescience.com/feeds/animals"],
        "wiki_hints": ["fossil", "extinction", "asteroid", "megalodon", "dinosaur", "ice age"],
    },
    {
        "id": "extreme_weather_earth",
        "theme": "EARTH",
        "badge": "EXTREME FORCE",
        "name": "Superstorms, Sinkholes & Earth Fury",
        "news_queries": ["giant sinkhole supervolcano rogue wave science", "extreme megatsunami geological event"],
        "yt_seeds": ["biggest rogue wave ever recorded", "what happens if a supervolcano erupts"],
        "rss_urls": ["https://www.sciencedaily.com/rss/earth_climate.xml"],
        "wiki_hints": ["tsunami", "supervolcano", "sinkhole", "earthquake", "caldera", "tornado"],
    },
]

CONTENT_ANGLES = [
    "THE_COUNTDOWN_TRAP: Show second-by-second escalation of a real extreme scenario.",
    "FORBIDDEN_REASON: Reveal the real scientific or terrifying reason a place is sealed.",
    "SCALE_SHOCK: Compare mind-breaking scale, pressure, depth, or size.",
    "BODY_UNDER_EXTREME: Show what physically happens to a human in extreme conditions.",
    "THE_SEALED_MYSTERY: Focus on why experts locked it down and walked away.",
    "HIDDEN_MECHANISM: Expose the invisible natural trigger behind a deadly event.",
    "VANISHED_WITHOUT_TRACE: Focus on the last recorded clue before everything stopped.",
    "PREHISTORIC_NIGHTMARE: Bring an extinct predator or ancient Earth catastrophe to life.",
    "TINY_FLAW_MEGA_DISASTER: Explain how one tiny overlooked detail caused total collapse.",
    "STRANGER_THAN_FICTION: Present a real verified Earth anomaly that defies intuition.",
    "LAST_30_SECONDS: Reconstruct the tense final moments of a real survival crisis.",
    "THE_SILENT_KILLER: Reveal an invisible natural danger with zero warning signs.",
    "IF_IT_HAPPENED_TODAY: Show what would happen right now if this ancient or cosmic event struck.",
    "THE_UNSOLVED_SIGNAL: Highlight a real recorded anomaly instruments still cannot explain.",
    "NATURE_ENGINEERED_TRAP: Show how nature built a deadlier trap than any human invention.",
]

BLOCKED_KEYWORDS = (
    "murder", "serial killer", "homicide", "suicide", "self-harm", "self harm",
    "rape", "sexual", "molest", "gore", "decapitat", "torture", "shooting",
    "massacre", "terrorist", "bombing", "trump", "biden", "election", "senate",
    "gaza", "israel", "ukraine", "putin", "hamas", "crypto", "bitcoin",
    "forex", "kardashian", "celebrity", "divorce", "porn", "onlyfans",
    "naked", "weight loss", "miracle cure", "nfl", "nba", "fifa", "cricket"
)

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "what", "why",
    "how", "into", "you", "your", "are", "was", "were", "have", "has",
    "actually", "really", "happens", "about", "there", "their", "when"
}


def http_get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def is_safe_topic(text):
    low = text.lower()
    if len(low.strip()) < 12:
        return False
    return not any(bad in low for bad in BLOCKED_KEYWORDS)


def tokenize(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) >= 3 and w not in STOPWORDS}


def load_posted_history():
    if not os.path.exists(HISTORY_FILE):
        return [], set(), None
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return [], set(), None

    titles = set()
    last_pillar = None
    items = raw if isinstance(raw, list) else raw.get("topics", raw.get("history", []))
    for entry in items:
        if isinstance(entry, str):
            titles.add(entry.strip().lower())
        elif isinstance(entry, dict):
            t = entry.get("topic") or entry.get("title") or ""
            if t:
                titles.add(t.strip().lower())
            if entry.get("pillar_id"):
                last_pillar = entry.get("pillar_id")
    return raw, titles, last_pillar


def save_posted_history(raw, topic_text, pillar_id):
    if isinstance(raw, list):
        if raw and isinstance(raw[0], dict):
            raw.append({"topic": topic_text, "pillar_id": pillar_id, "ts": datetime.now(timezone.utc).isoformat()})
        else:
            raw.append(topic_text)
    elif isinstance(raw, dict):
        key = "topics" if "topics" in raw else "history"
        lst = raw.setdefault(key, [])
        lst.append(topic_text)
    else:
        raw = [topic_text]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)


def is_duplicate(candidate, posted_titles):
    cand_low = candidate.strip().lower()
    if cand_low in posted_titles:
        return True
    cand_tokens = tokenize(cand_low)
    if not cand_tokens:
        return True
    for old in posted_titles:
        if cand_low in old or old in cand_low:
            return True
        old_tokens = tokenize(old)
        if not old_tokens:
            continue
        overlap = len(cand_tokens & old_tokens) / max(1, min(len(cand_tokens), len(old_tokens)))
        if overlap >= 0.55:
            return True
    return False


def fetch_google_news(query):
    results = []
    try:
        q = urllib.parse.quote_plus(query)
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        xml_data = http_get(url)
        root = ET.fromstring(xml_data)
        for item in root.findall(".//item")[:8]:
            title = (item.findtext("title") or "").strip()
            title = re.sub(r"\s+-\s+[^-]+$", "", title).strip()
            if title and is_safe_topic(title):
                results.append({"title": title, "source": "google_news", "summary": ""})
    except Exception:
        pass
    return results


def fetch_rss_feed(url):
    results = []
    try:
        xml_data = http_get(url)
        root = ET.fromstring(xml_data)
        for item in root.findall(".//item")[:8]:
            title = (item.findtext("title") or "").strip()
            desc = re.sub(r"<[^>]+>", " ", item.findtext("description") or "").strip()
            desc = re.sub(r"\s+", " ", desc)[:260]
            if title and is_safe_topic(title):
                results.append({"title": title, "source": "science_rss", "summary": desc})
    except Exception:
        pass
    return results


def fetch_yt_suggest(seed):
    results = []
    try:
        q = urllib.parse.quote_plus(seed)
        url = f"https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q={q}"
        data = json.loads(http_get(url))
        if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
            for s in data[1][:8]:
                clean = str(s).strip()
                if len(clean.split()) >= 5 and is_safe_topic(clean):
                    results.append({"title": clean.title(), "source": "youtube_search_trend", "summary": ""})
    except Exception:
        pass
    return results


def fetch_wiki_trending(wiki_hints):
    results = []
    for days_ago in (1, 2):
        try:
            dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
            url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{dt:%Y/%m/%d}"
            data = json.loads(http_get(url))
            articles = data.get("items", [{}])[0].get("articles", [])
            for art in articles[:500]:
                raw_title = art.get("article", "")
                if any(raw_title.startswith(p) for p in ("Main_Page", "Special:", "Wikipedia:", "File:", "Portal:", "Deaths_in_")):
                    continue
                clean = raw_title.replace("_", " ").strip()
                low = clean.lower()
                if any(h in low for h in wiki_hints) and is_safe_topic(clean):
                    results.append({"title": clean, "source": "wikipedia_viral_spike", "summary": ""})
                if len(results) >= 6:
                    return results
            if results:
                return results
        except Exception:
            continue
    return results


def fetch_wiki_fact(topic_query):
    try:
        q = urllib.parse.quote_plus(topic_query)
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&srlimit=1&format=json"
        s_data = json.loads(http_get(search_url))
        hits = s_data.get("query", {}).get("search", [])
        if not hits:
            return ""
        page_title = hits[0]["title"].replace(" ", "_")
        sum_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(page_title)}"
        p_data = json.loads(http_get(sum_url))
        extract = (p_data.get("extract") or "").strip()
        return re.sub(r"\s+", " ", extract)[:340]
    except Exception:
        return ""


def collect_live_candidates(pillar, posted_titles):
    pool = []
    for q in pillar["news_queries"]:
        pool.extend(fetch_google_news(q))
    for seed in pillar["yt_seeds"]:
        pool.extend(fetch_yt_suggest(seed))
    for rss in pillar["rss_urls"]:
        pool.extend(fetch_rss_feed(rss))
    pool.extend(fetch_wiki_trending(pillar["wiki_hints"]))

    unique = []
    seen = set()
    for item in pool:
        t_low = item["title"].lower()
        if t_low in seen or is_duplicate(item["title"], posted_titles):
            continue
        seen.add(t_low)
        unique.append(item)
    return unique


def select_with_ollama(candidates, pillar, angle):
    cand_lines = [f"{idx+1}. [{c['source']}] {c['title']}" for idx, c in enumerate(candidates[:18])]
    prompt = "\n".join([
        "You are a Tier-1 Global YouTube Shorts Viral Strategist.",
        f"Pillar: {pillar['name']}",
        f"Required Content Angle: {angle}",
        "Below are REAL live trending items fetched right now:",
        *cand_lines,
        "Task: Pick the SINGLE strongest real topic from the list above that will maximize global swipe-stop and retention.",
        "Rules:",
        "- Keep it grounded in the chosen real item (no fake claims).",
        "- Rewrite the topic into a punchy 6-11 word English curiosity title in Title Case.",
        "- Focus on human survival, mystery, shock, or extreme danger.",
        "- Output valid JSON ONLY with keys: index (int), topic (str), hook_angle (str).",
    ])
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.4, "num_predict": 180},
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    parsed = json.loads(raw.get("response", "{}"))
    topic = str(parsed.get("topic", "")).strip()
    idx = int(parsed.get("index", 1)) - 1
    chosen = candidates[idx] if 0 <= idx < len(candidates) else candidates[0]
    if not topic or not is_safe_topic(topic) or len(topic.split()) < 4:
        raise ValueError("Invalid LLM topic")
    return topic, chosen, str(parsed.get("hook_angle", angle))


def fallback_best_candidate(candidates):
    power_words = {"why", "what", "never", "survive", "trapped", "deepest", "deadliest", "hidden", "vanished", "forbidden", "discovered", "terrifying"}
    scored = []
    for c in candidates:
        words = set(re.findall(r"[a-z]+", c["title"].lower()))
        score = len(words & power_words) * 3
        if c["source"] == "youtube_search_trend":
            score += 4
        elif c["source"] == "wikipedia_viral_spike":
            score += 3
        elif c["source"] == "google_news":
            score += 2
        scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[0][1]
    return best["title"], best


def main():
    raw_history, posted_titles, last_pillar = load_posted_history()
    eligible_pillars = [p for p in PILLARS if p["id"] != last_pillar] or PILLARS
    random.shuffle(eligible_pillars)

    chosen_pillar = None
    candidates = []
    for p in eligible_pillars[:5]:
        found = collect_live_candidates(p, posted_titles)
        if found:
            chosen_pillar = p
            candidates = found
            break

    if not candidates:
        raise RuntimeError("No live candidates fetched from any source.")

    angle = random.choice(CONTENT_ANGLES)
    try:
        final_topic, base_item, hook_angle = select_with_ollama(candidates, chosen_pillar, angle)
    except Exception:
        final_topic, base_item = fallback_best_candidate(candidates)
        hook_angle = angle

    if is_duplicate(final_topic, posted_titles):
        final_topic = base_item["title"]

    fact_summary = base_item.get("summary") or fetch_wiki_fact(base_item["title"]) or fetch_wiki_fact(final_topic)

    out = {
        "theme": chosen_pillar["theme"],
        "topic": final_topic,
        "badge": chosen_pillar["badge"],
        "angle": angle,
        "psych_strategy": hook_angle,
        "fact_summary": fact_summary,
        "pillar": chosen_pillar["name"],
        "pillar_id": chosen_pillar["id"],
        "source_candidate": base_item["title"],
        "source_type": base_item["source"],
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    save_posted_history(raw_history, final_topic, chosen_pillar["id"])
    print(f"[*] Pillar: {chosen_pillar['name']} | Live Candidates: {len(candidates)}", flush=True)
    print(f"[*] Source: {base_item['source']} -> {base_item['title']}", flush=True)
    print(f"[*] Selected Viral Topic: {final_topic}", flush=True)


if __name__ == "__main__":
    main()
