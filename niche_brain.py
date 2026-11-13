import os
import json
import time
import random
import requests

HISTORY_FILE = "used_topics_history.json"

# 1. SIX PERMANENT CONTENT PILLARS (Frameworks Only - Zero Fixed Topics)
CONTENT_PILLARS = {
    "weapon_drag_physics": {
        "name": "Weapon Mastery & Drag Physics",
        "objective": "Decode headshot drag trajectories, recoil reset timings, and fire-button micro physics.",
        "seed_keywords": ["free fire desert eagle one tap", "free fire m1887 headshot trick", "free fire woodpecker drag", "free fire mp40 recoil"],
        "weapons": ["Desert Eagle", "M1887", "Woodpecker", "MP40", "AWM", "AC80", "UMP", "M1014", "Groza", "SVD", "M500", "Trogon"]
    },
    "hacker_vs_skill_investigation": {
        "name": "Panel vs Pure Mobile Reflex Investigation",
        "objective": "Forensically inspect impossible flicks, smoke shots, and high headshot rates to debate skill vs panel.",
        "seed_keywords": ["free fire impossible headshot", "free fire panel or skill", "free fire fastest handcam", "free fire banned gameplay"],
        "weapons": ["Woodpecker", "M1887", "Desert Eagle", "SVD", "AC80", "AWM"]
    },
    "clutch_psychology": {
        "name": "1v4 Solo vs Squad Clutch IQ",
        "objective": "Break down angle isolation, gloo wall timing, and high-pressure survival under 15 HP.",
        "seed_keywords": ["free fire 1v4 clutch", "free fire solo vs squad", "free fire cs ranked clutch", "free fire grandmaster custom"],
        "weapons": ["M1887", "MP40", "UMP", "M1014", "Desert Eagle", "Trogon"]
    },
    "old_nostalgia_lore": {
        "name": "Old Free Fire Nostalgia & Meta Evolution",
        "objective": "Contrast classic 2018-2020 Free Fire eras, old map zones, and iconic metas with today.",
        "seed_keywords": ["old free fire gameplay", "free fire peak nostalgia", "free fire season 1 montage", "free fire factory fight"],
        "weapons": ["Old M4A1", "M1887", "MP40", "AK47", "Fist", "Scar"]
    },
    "device_sensitivity_meta": {
        "name": "DPI, Touch Sampling & Sensitivity Science",
        "objective": "Analyze low-end vs 120Hz touch physics, crosshair placement height, and button scale secrets.",
        "seed_keywords": ["free fire sensitivity headshot", "free fire dpi settings", "free fire 60fps handcam", "free fire red number settings"],
        "weapons": ["Desert Eagle", "Woodpecker", "M1887", "UMP", "M500"]
    },
    "dark_mysteries_glitches": {
        "name": "Free Fire Dark Mysteries & Server Bugs",
        "objective": "Investigate eerie myths, broken custom rooms, banned accounts, and hidden server anomalies.",
        "seed_keywords": ["free fire glitch gameplay", "free fire mystery moments", "free fire scary custom", "free fire rare clutch"],
        "weapons": ["AWM", "Crossbow", "Scythe", "Woodpecker", "M1887"]
    }
}

# 2. FACTUAL WEAPON DAMAGE & MECHANIC META (For Real Number Alignment)
WEAPON_META = {
    "Desert Eagle": {"head_dmg": "495", "type": "One-Tap Pistol", "mechanic": "U-shape fast drag after foot-level aim"},
    "M1887": {"head_dmg": "550", "type": "2-Shot Shotgun", "mechanic": "Jump-shot or crouch-release chest-up drag"},
    "Woodpecker": {"head_dmg": "372", "type": "Marksman Rifle", "mechanic": "Zero analog movement single-tap reset"},
    "MP40": {"head_dmg": "148", "type": "High-RPM SMG", "mechanic": "Rapid tight vertical flick to lock neck-to-head"},
    "AWM": {"head_dmg": "300", "type": "Bolt Sniper", "mechanic": "Double-sniper quick-switch cancel reload"},
    "AC80": {"head_dmg": "345", "type": "Marksman Rifle", "mechanic": "Second consecutive shot pierces armor multiplier"},
    "UMP": {"head_dmg": "172", "type": "Armor-Piercing SMG", "mechanic": "Mid-range glide drag while strafing"},
    "M1014": {"head_dmg": "550", "type": "Auto Shotgun", "mechanic": "Close-range rotation drag around gloo wall"},
    "Groza": {"head_dmg": "210", "type": "Airdrop AR", "mechanic": "3-burst controlled tap from elevation"},
    "SVD": {"head_dmg": "390", "type": "Airdrop Marksman", "mechanic": "Scope-in instant micro drag on peek"},
    "M500": {"head_dmg": "247", "type": "Scoped Pistol", "mechanic": "Long-range CS round-1 static head lock"},
    "Trogon": {"head_dmg": "480", "type": "Hybrid Shotgun", "mechanic": "Burst-mode corner pre-fire drag"},
    "Old M4A1": {"head_dmg": "175", "type": "Classic AR", "mechanic": "Old tap-fire pacing at Clock Tower"},
    "AK47": {"head_dmg": "195", "type": "High-Recoil AR", "mechanic": "2-bullet burst reset before bloom spreads"},
    "Scar": {"head_dmg": "168", "type": "Balanced AR", "mechanic": "Smooth upward diagonal pull"},
    "Fist": {"head_dmg": "550", "type": "Melee", "mechanic": "Factory roof jump-timing head connect"},
    "Crossbow": {"head_dmg": "350", "type": "Stealth Bow", "mechanic": "Bleed-tick peek behind cover"},
    "Scythe": {"head_dmg": "280", "type": "Melee", "mechanic": "Sprint-jump swing momentum"}
}

# 3. 65 PSYCHOLOGICAL RETENTION STRATEGIES (Hook & Pacing Styles)
PSYCHOLOGY_STRATEGIES = [
    "01_Frame_Zero_Shock", "02_Curiosity_Gap_Question", "03_Panel_Accusation_Debate",
    "04_Forbidden_Pro_Secret", "05_99_Percent_Failure_Bias", "06_Micro_Countdown_Tension",
    "07_Silent_Before_Storm", "08_Real_Damage_Proof_Flex", "09_Enemy_Overconfidence_Punish",
    "10_Zero_HP_Clutch_Anxiety", "11_Nostalgia_Emotional_Trigger", "12_Skill_Gap_Ego_Challenge",
    "13_Millisecond_Reflex_Audit", "14_Myth_Buster_Contradiction", "15_Toxic_Trash_Talk_Karma",
    "16_Impossible_Angle_Reveal", "17_Grandmaster_Gatekeeping", "18_Sound_Cue_Paranoia",
    "19_Gloo_Wall_Mindgame", "20_Fake_Retreat_Bait", "21_Pattern_Interrupt_Shatter",
    "22_Unfinished_Loop_Ending", "23_Comment_War_Polarizer", "24_Device_Disadvantage_Hero",
    "25_Anti_Cheat_Suspense", "26_Speed_vs_Precision_Contrast", "27_Split_Second_Crosshair_Lock",
    "28_Squad_Wipe_Domino_Effect", "29_Last_Bullet_Desperation", "30_Zone_Edge_Ambush",
    "31_Muscle_Memory_Hacking", "32_Touch_Physics_Illusion", "33_Silent_Assassin_Pacing",
    "34_Overturned_1v4_Odds", "35_No_Vest_Survival", "36_Custom_Room_Bet_Stakes",
    "37_Old_Lobby_Grief", "38_Meta_Shift_Warning", "39_Hidden_Hitbox_Mechanic",
    "40_Frame_Skip_Evidence", "41_One_Tap_Dopamine_Drop", "42_Fake_Bot_Disguise_Trap",
    "43_Elevation_Advantage_Rule", "44_Peek_Punishment_Law", "45_Jump_Timing_Prediction",
    "46_DPI_Myth_Exposure", "47_Fire_Button_Scale_Truth", "48_Analog_Freeze_Discipline",
    "49_Rotation_Drag_Geometry", "50_Jiggle_Movement_Bait", "51_Smoke_Blind_Instinct",
    "52_Reload_Cancel_Tempo", "53_360_Gloo_Reflex_Test", "54_Corner_Pre_Aim_Trap",
    "55_Headshot_Ratio_Obsession", "56_Tournament_Clutch_Pressure", "57_Solo_Carry_Burden",
    "58_Lag_Compensation_Trick", "59_Audio_Footstep_Read", "60_Final_Zone_Panic",
    "61_Rivalry_Rematch_Arc", "62_Underdog_Upset_Story", "63_Mechanical_Ceiling_Flex",
    "64_Counter_Meta_Surprise", "65_DEVIL_999_Challenge_Hook"
]

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {"queries": [], "video_ids": [], "titles": [], "last_pillar": ""}

def save_history_entry(query="", video_id="", title="", pillar_id=""):
    history = load_history()
    if query and query not in history["queries"]:
        history["queries"].append(query)
    if video_id and video_id not in history["video_ids"]:
        history["video_ids"].append(video_id)
    if title and title not in history["titles"]:
        history["titles"].append(title)
    if pillar_id:
        history["last_pillar"] = pillar_id
    # Keep file compact (last 200 entries)
    history["queries"] = history["queries"][-200:]
    history["video_ids"] = history["video_ids"][-200:]
    history["titles"] = history["titles"][-200:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def fetch_live_youtube_suggestions(seed_keyword):
    """Fetches real-time trending searches directly from YouTube public autocomplete API."""
    try:
        url = f"https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q={requests.utils.quote(seed_keyword)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            payload = res.json()
            if isinstance(payload, list) and len(payload) > 1 and isinstance(payload[1], list):
                return [s for s in payload[1] if isinstance(s, str) and len(s) > 5]
    except Exception:
        pass
    return []

def fetch_live_reddit_signals():
    """Fetches live community titles from r/freefire and r/freefireclips."""
    signals = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FreeFireTrendScout/2.0"}
    for sub in ["freefire", "freefireclips"]:
        try:
            res = requests.get(f"https://www.reddit.com/r/{sub}/hot.json?limit=15", headers=headers, timeout=8)
            if res.status_code == 200:
                children = res.json().get("data", {}).get("children", [])
                for c in children:
                    t = c.get("data", {}).get("title", "").strip()
                    if t:
                        signals.append(t[:90])
        except Exception:
            continue
    return signals

def scout_live_viral_trend(format_type="short", ollama_url="http://localhost:11434/api/generate"):
    """
    Real-Time Pillar & Trend Scout (Zero Hardcoded Topics):
    Reads 6 Pillars + Live YouTube/Reddit signals + Used History,
    then picks a fresh un-repeated Pillar Blueprint for AI scripting.
    """
    history = load_history()
    used_queries_lower = {q.lower() for q in history.get("queries", [])}
    last_pillar = history.get("last_pillar", "")

    # Rotate pillar so consecutive videos never feel identical
    available_pillars = [k for k in CONTENT_PILLARS.keys() if k != last_pillar] or list(CONTENT_PILLARS.keys())
    pillar_id = random.choice(available_pillars)
    pillar = CONTENT_PILLARS[pillar_id]

    weapon = random.choice(pillar["weapons"])
    weapon_info = WEAPON_META.get(weapon, {"head_dmg": "550", "type": "Weapon", "mechanic": "clean headshot drag"})
    psychology = random.choice(PSYCHOLOGY_STRATEGIES)

    # Pull LIVE trends from YouTube Suggest & Reddit
    seed = random.choice(pillar["seed_keywords"])
    live_yt = fetch_live_youtube_suggestions(seed)
    live_yt_weapon = fetch_live_youtube_suggestions(f"free fire {weapon.lower()} ")
    combined_live_yt = [q for q in (live_yt + live_yt_weapon) if q.lower() not in used_queries_lower]
    live_reddit = fetch_live_reddit_signals()

    # Construct a fresh live search query from real-time signals (no static topic list)
    if combined_live_yt:
        picked_trend = random.choice(combined_live_yt)
        search_query = f"{picked_trend} 60fps" if "60fps" not in picked_trend.lower() else picked_trend
    else:
        search_query = f"{seed} {weapon} 60fps highlights"

    # Build AI prompt context using the Pillar + Live Trend + Psychology
    prompt_context = (
        f"Channel: DEVIL INSANITY (Tag: DEVIL-999) | Format: {format_type.upper()}\n"
        f"Pillar: {pillar['name']} ({pillar['objective']})\n"
        f"Weapon: {weapon} ({weapon_info['type']}, Head Damage: {weapon_info['head_dmg']}, Mechanic: {weapon_info['mechanic']})\n"
        f"Psychological Retention Hook: {psychology}\n"
        f"Live YouTube Trending Searches: {combined_live_yt[:5]}\n"
        f"Live Reddit Community Chatter: {live_reddit[:3]}\n"
        f"Banned Already-Used Queries: {history.get('queries', [])[-15:]}"
    )

    return {
        "pillar_id": pillar_id,
        "pillar_name": pillar["name"],
        "pillar_objective": pillar["objective"],
        "format_type": format_type,
        "weapon": weapon,
        "damage": weapon_info["head_dmg"],
        "weapon_mechanic": weapon_info["mechanic"],
        "psychology_strategy": psychology,
        "search_query": search_query,
        "live_youtube_trends": combined_live_yt[:6],
        "live_reddit_trends": live_reddit[:4],
        "used_queries": history.get("queries", [])[-15:],
        "used_video_ids": history.get("video_ids", []),
        "used_titles": history.get("titles", [])[-15:],
        "prompt_context": prompt_context,
        "player_tag": "DEVIL-999",
        "title": f"{weapon} {pillar['name']} #shorts #freefire"
    }

class NicheBrain:
    def __init__(self):
        self.pillars = CONTENT_PILLARS
        self.weapon_meta = WEAPON_META
        self.strategies = PSYCHOLOGY_STRATEGIES

    def get_daily_trend(self, format_type="short"):
        return scout_live_viral_trend(format_type=format_type)

    def get_pillars_blueprint(self, format_type="short"):
        return scout_live_viral_trend(format_type=format_type)

    def record_used_topic(self, query="", video_id="", title="", pillar_id=""):
        save_history_entry(query=query, video_id=video_id, title=title, pillar_id=pillar_id)

def get_daily_trend(format_type="short"):
    return scout_live_viral_trend(format_type=format_type)

def build_dynamic_prompt(blueprint):
    return blueprint.get("prompt_context", "")

if __name__ == "__main__":
    result = scout_live_viral_trend()
    print(json.dumps(result, indent=2))
