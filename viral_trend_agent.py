import json
import os
import random
from datetime import datetime, timezone

HISTORY_FILE = "posted_history.json"
OUT_FILE = "trending_topic.json"

TOPIC_POOL = [
    {"theme": "OCEAN", "topic": "What Happens To Your Body 3000 Meters Under The Ocean", "angle": "crush pressure and total darkness", "badge": "3,000M DEEP"},
    {"theme": "OCEAN", "topic": "Why Divers Never Enter The Blue Hole Past 100 Meters", "angle": "nitrogen narcosis and sunken bones", "badge": "DEADLY DEPTH"},
    {"theme": "OCEAN", "topic": "The Terrifying 1997 Bloop Sound Recorded Under Antarctica", "angle": "ultrasonic ocean roar mystery", "badge": "1997 ANOMALY"},
    {"theme": "OCEAN", "topic": "Point Nemo: The Loneliest And Creepiest Spot In The Ocean", "angle": "spacecraft graveyard 1600 miles from land", "badge": "POINT NEMO"},
    {"theme": "SPACE", "topic": "What Happens Inside A Black Hole In Your Final 3 Seconds", "angle": "spaghettification and frozen time", "badge": "EVENT HORIZON"},
    {"theme": "SPACE", "topic": "The 1977 Wow Signal From Deep Space We Still Cannot Explain", "angle": "72 second alien radio burst", "badge": "1977 SIGNAL"},
    {"theme": "SPACE", "topic": "Rogue Planets Floating Alone In Pitch Black Space", "angle": "sunless frozen worlds drifting silently", "badge": "ROGUE WORLDS"},
    {"theme": "SPACE", "topic": "The Bootes Void: A Pitch Black Hole 330 Million Light Years Wide", "angle": "missing galaxies cosmic dread", "badge": "COSMIC VOID"},
    {"theme": "SURVIVAL", "topic": "Why Climbers Never Rescue Bodies Above 8000 Meters On Everest", "angle": "the death zone oxygen starvation", "badge": "8,000M DEATH ZONE"},
    {"theme": "SURVIVAL", "topic": "Why Explorers Sealed Nutty Putty Cave Forever With Concrete", "angle": "tight underground tunnel tragedy", "badge": "SEALED FOREVER"},
    {"theme": "SURVIVAL", "topic": "The Impossible 100 Foot Rogue Wave Sailors Swore Was A Myth", "angle": "wall of ocean water breaking steel ships", "badge": "100FT WALL"},
    {"theme": "SURVIVAL", "topic": "Deep Sea Saturation Diving: Why One Valve Mistake Is Instant", "angle": "explosive decompression physics", "badge": "SATURATION DIVE"},
    {"theme": "MYSTERY", "topic": "The Ship Found Drifting With Zero Crew And Warm Coffee Still On Table", "angle": "Mary Celeste ghost ship mystery", "badge": "GHOST VESSEL"},
    {"theme": "MYSTERY", "topic": "Dyatlov Pass: Why Nine Experienced Hikers Cut Their Own Tent", "angle": "frozen mountain panic mystery", "badge": "1959 INCIDENT"},
    {"theme": "MYSTERY", "topic": "The Forbidden Island Nobody Is Allowed Within 5 Miles Of", "angle": "untouched island guarded by patrol", "badge": "NO ENTRY ZONE"},
    {"theme": "MYSTERY", "topic": "The Mysterious Shortwave Radio Stations Broadcasting For 50 Years", "angle": "UVB-76 buzzer cold war mystery", "badge": "SHORTWAVE GHOST"},
]


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def pick_topic():
    history = load_history()
    used_topics = {str(x.get("topic", "")).lower() for x in history[-40:]}
    candidates = [t for t in TOPIC_POOL if t["topic"].lower() not in used_topics]
    if not candidates:
        candidates = TOPIC_POOL[:]
    choice = random.choice(candidates)
    payload = {
        "theme": choice["theme"],
        "topic": choice["topic"],
        "angle": choice["angle"],
        "badge": choice["badge"],
        "picked_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    history.append({"topic": choice["topic"], "picked_at": payload["picked_at"]})
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[-100:], f, indent=2)
    print(f"[+] Trend Scout Locked [{choice['theme']}]: {choice['topic']}", flush=True)


if __name__ == "__main__":
    pick_topic()
