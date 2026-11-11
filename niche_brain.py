"""
niche_brain.py (Version 5.0)
Autonomous 6-Pillar Trend Scout & 7-Stage Extended Script Architecture.
Calibrated for 28s - 34s high-retention YouTube Shorts.
"""

import json
from datetime import date

WEAPONS_META = {
    "Desert Eagle": {"headshot_dmg": "495", "type": "one_tap"},
    "M1887": {"headshot_dmg": "550", "type": "shotgun_burst"},
    "Woodpecker": {"headshot_dmg": "380", "type": "ar_tap"},
    "AWM": {"headshot_dmg": "1100", "type": "sniper_kill"},
    "MP40": {"headshot_dmg": "138", "type": "smg_laser"},
    "M1014": {"headshot_dmg": "240", "type": "shotgun_close"}
}

CONTENT_PILLARS = [
    {
        "category": "Spectating Suspicious Pro Highlights",
        "search_query": "free fire 1v4 clutch highlights 60fps",
        "hook_template": "Is This {weapon} Player Using Panel or Pure Reflexes?"
    },
    {
        "category": "Instant Karma on Toxic Emote Spammer",
        "search_query": "free fire toxic emote karma one tap headshot",
        "hook_template": "He Emoted Too Early... Then {weapon} Did This!"
    },
    {
        "category": "Grandmaster Tournament Impossible Moments",
        "search_query": "free fire grandmaster solo vs squad clutch",
        "hook_template": "When Squad Died and Player Had 1 HP Left with {weapon}..."
    },
    {
        "category": "Fastest Finger Speed Handcam Breakdown",
        "search_query": "free fire fastest m1887 one tap handcam",
        "hook_template": "The Secret {weapon} Drag Angle That Never Misses Head!"
    }
]

def scout_live_viral_trend() -> dict:
    today_num = date.today().timetuple().tm_yday
    pillar = CONTENT_PILLARS[today_num % len(CONTENT_PILLARS)]
    weapons_keys = list(WEAPONS_META.keys())
    weapon = weapons_keys[(today_num * 2) % len(weapons_keys)]
    meta = WEAPONS_META[weapon]
    hook = pillar["hook_template"].format(weapon=weapon)

    return {
        "pillar": pillar["category"],
        "weapon": weapon,
        "headshot_dmg": meta["headshot_dmg"],
        "hook": hook,
        "search_query": f"{weapon} {pillar['search_query']}"
    }

def build_retention_prompt(manifest: dict) -> str:
    trend = scout_live_viral_trend()
    channel_name = manifest.get("channel_name", "DEVIL INSANITY")
    target_sec = manifest.get("tasks", {}).get("daily_short", {}).get("target_duration_sec", 29.5)

    prompt = f"""Write an explosive 7-scene Free Fire YouTube Short script in STRICT JSON.
Channel: {channel_name} | Target Duration: ~{target_sec}s
Topic: {trend['hook']} | Weapon: {trend['weapon']}

RULES:
1. No greetings. Start directly with controversy/shock.
2. Exactly 7 sequential scenes matching 28s-34s duration.
3. Scene 7 ends with a phrase connecting seamlessly back into Scene 1's opening.
4. "narration_urdu": Roman Urdu gamer slang (under 7 words per scene).
5. "narration_en": Short English subtitle (under 7 words per scene).

OUTPUT STRICT JSON ONLY:
{{
  "title_urdu": "{trend['hook']}",
  "title_en": "{trend['hook']}",
  "description_en": "{trend['hook']} #FreeFire #Shorts #FFHighlights #Gaming",
  "featured_weapon": "{trend['weapon']}",
  "headshot_dmg": "{trend['headshot_dmg']}",
  "search_query": "{trend['search_query']}",
  "infinity_loop_connector": "Bridge phrase from scene 7 back to scene 1",
  "scenes": [
    {{"scene_num": 1, "duration_sec": 4.0, "narration_urdu": "Shocking accusation hook line", "narration_en": "English subtitle line", "subtitle_en": "HOOK ACCUSATION", "sfx": "vine_boom"}},
    {{"scene_num": 2, "duration_sec": 4.0, "narration_urdu": "Enemy movement tension line", "narration_en": "English subtitle line", "subtitle_en": "ENEMY RUSHING", "sfx": "bass_drop"}},
    {{"scene_num": 3, "duration_sec": 4.2, "narration_urdu": "Editorial freeze sawal line", "narration_en": "English subtitle line", "subtitle_en": "WAIT FOR THIS", "sfx": "whoosh"}},
    {{"scene_num": 4, "duration_sec": 4.2, "narration_urdu": "Bullet fire real damage moment", "narration_en": "English subtitle line", "subtitle_en": "BULLET CONNECTS", "sfx": "hitmarker"}},
    {{"scene_num": 5, "duration_sec": 4.2, "narration_urdu": "In-game damage analysis line", "narration_en": "English subtitle line", "subtitle_en": "REAL DAMAGE POPUP", "sfx": "gun_cock"}},
    {{"scene_num": 6, "duration_sec": 4.2, "narration_urdu": "Final clutch wipe reaction", "narration_en": "English subtitle line", "subtitle_en": "CLUTCH COMPLETE", "sfx": "bass_explosion"}},
    {{"scene_num": 7, "duration_sec": 4.0, "narration_urdu": "Loop phrase leading to Scene 1", "narration_en": "Loop subtitle line", "subtitle_en": "LOOP TO START", "sfx": "whoosh"}}
  ]
}}"""
    return prompt.strip()
