import json
import os
import random
from datetime import datetime, timezone

HISTORY_FILE = "posted_history.json"
OUT_FILE = "trending_topic.json"

PSYCH_STRATEGIES = [
    "IMMEDIATE_SURVIVAL_THREAT: Open with an exact countdown or biological failure happening in seconds.",
    "FORBIDDEN_ZONE_CURIOSITY: Open with why governments or scientists banned humans from entering.",
    "SENSORY_PARADOX: Open with something that feels impossible or contradicts common sense.",
    "DECLASSIFIED_RECORDING: Open as if leaking a chilling real-world log or sonar anomaly.",
    "LOSS_AVERSION_WARNING: Open telling the viewer what tiny mistake guarantees instant disaster.",
    "BODY_HORROR_SCIENCE: Focus on the exact physical terrifying effect on human lungs, eyes, or brain.",
    "UNSOLVED_EVIDENCE: Highlight one haunting physical object left behind with no explanation.",
    "COSMIC_INSIGNIFICANCE: Contrast human scale against colossal, terrifying forces.",
    "FALSE_SAFETY_ILLUSION: Start calm for 1 second, then violently shatter what feels safe.",
    "DEBATE_TRIGGER: Frame an eerie scientific mystery that splits experts 50/50.",
]

TOPIC_POOL = [
    {"theme": "OCEAN", "topic": "What Happens To Your Body 3000 Meters Under The Ocean", "angle": "crush pressure and pitch darkness", "badge": "DEPTH: 3,000M"},
    {"theme": "OCEAN", "topic": "Why Divers Never Enter The Blue Hole Past 100 Meters", "angle": "nitrogen narcosis and sunken bones", "badge": "OXYGEN: CRITICAL"},
    {"theme": "OCEAN", "topic": "The Terrifying 1997 Bloop Sound Recorded Under Antarctica", "angle": "ultrasonic roar louder than whales", "badge": "SONAR: CLASSIFIED"},
    {"theme": "OCEAN", "topic": "Point Nemo: The Loneliest And Creepiest Place In The Ocean", "angle": "1600 miles from any human land", "badge": "1,600 MI TO LAND"},
    {"theme": "OCEAN", "topic": "Why Giant Squid Have Eyes The Size Of Dinner Plates", "angle": "hunting monsters in pitch black abyss", "badge": "ABYSSAL ZONE"},
    {"theme": "SPACE", "topic": "What Happens Inside A Black Hole In Your Final 3 Seconds", "angle": "spaghettification and frozen time", "badge": "EVENT HORIZON"},
    {"theme": "SPACE", "topic": "The 1977 Wow Signal From Deep Space Still Unexplained", "angle": "72 second alien radio burst", "badge": "1977 SIGNAL"},
    {"theme": "SPACE", "topic": "Rogue Planets Floating Alone In Pitch Black Space", "angle": "sunless frozen worlds drifting silently", "badge": "TEMP: -240C"},
    {"theme": "SPACE", "topic": "The Bootes Void: A Black Hole In Space 330 Million Light Years Wide", "angle": "2000 missing galaxies", "badge": "ZERO GALAXIES"},
    {"theme": "SPACE", "topic": "What Happens If A Rogue Magnetar Passes Near Earth", "angle": "magnetic field tearing atoms apart", "badge": "RADIATION: EXTREME"},
    {"theme": "SURVIVAL", "topic": "Why Climbers Never Rescue Bodies Above 8000 Meters On Everest", "angle": "the death zone oxygen starvation", "badge": "ALT: 8,000M"},
    {"theme": "SURVIVAL", "topic": "Why Explorers Sealed Nutty Putty Cave Forever With Concrete", "angle": "upside down underground trap", "badge": "SEALED FOREVER"},
    {"theme": "SURVIVAL", "topic": "The Impossible 100 Foot Rogue Wave Sailors Swore Was A Myth", "angle": "wall of ocean water snapping steel", "badge": "WAVE: 100 FEET"},
    {"theme": "SURVIVAL", "topic": "Deep Sea Saturation Diving: Why One Valve Mistake Is Instant", "angle": "explosive pressure physics", "badge": "PRESSURE: 30 ATM"},
    {"theme": "SURVIVAL", "topic": "Why You Cannot Scream In A Vacuum Chamber Suit Failure", "angle": "boiling saliva at zero pressure", "badge": "PRESSURE: 0 PSI"},
    {"theme": "MYSTERY", "topic": "The Ship Found Drifting With Zero Crew And Warm Coffee On Table", "angle": "Mary Celeste ghost vessel", "badge": "CREW: ZERO"},
    {"theme": "MYSTERY", "topic": "Dyatlov Pass: Why Nine Hikers Cut Their Own Tent In Freezing Night", "angle": "subzero panic mystery", "badge": "1959 INCIDENT"},
    {"theme": "MYSTERY", "topic": "The Forbidden Island Nobody Is Allowed Within 5 Miles Of", "angle": "guarded untouched island mystery", "badge": "RESTRICTED ZONE"},
    {"theme": "MYSTERY", "topic": "The Shortwave Radio Station Buzzing Nonstop For 50 Years", "angle": "UVB-76 cold war buzzer", "badge": "FREQ: 4625 KHZ"},
    {"theme": "MYSTERY", "topic": "The Submersible Door Mystery Inside The Mariana Trench", "angle": "unexplained metallic knocking 7 miles down", "badge": "10,900M DEEP"},
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
    strategy = random.choice(PSYCH_STRATEGIES)
    payload = {
        "theme": choice["theme"],
        "topic": choice["topic"],
        "angle": choice["angle"],
        "badge": choice["badge"],
        "psych_strategy": strategy,
        "picked_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    history.append({"topic": choice["topic"], "picked_at": payload["picked_at"]})
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[-100:], f, indent=2)
    print(f"[+] Trend Scout [{choice['theme']}]: {choice['topic']}", flush=True)
    print(f"[+] Psych Strategy: {strategy[:60]}...", flush=True)


if __name__ == "__main__":
    pick_topic()
