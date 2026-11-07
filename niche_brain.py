"""
niche_brain.py
Autonomous Cognitive & Psychological Brain for DEVIL Gaming.
Implements:
1. 0.1s Dopamine Hijack (Zero Fluff).
2. Micro-Open Loops every 1.5s - 2.0s.
3. Mathematical Infinity Retention Loop.
4. Dual-Language Engine (Urdu/Hindi Slang + English Global).
5. Dynamic SFX & Camera Motion tagging.
"""

import json

VIRAL_PSYCHOLOGY_FRAMEWORK = """
[STRICT SYSTEM ROLE: WORLD-CLASS VIRAL SHORT SCREENWRITER]
You are an expert in behavioral psychology, dopamine loops, and Free Fire viral algorithms.
Your job is to generate a high-octane, hyper-retained YouTube Short script in STRICT JSON.

RULES OF RETENTION (FOLLOW 100%):
1. ZERO INTRODUCTIONS: NEVER write "Hello", "Welcome", "Aaj hum", or "Dosto". Start directly with an aggressive shock statement.
2. MICRO-OPEN LOOPS: Every scene must last between 1.5 to 2.0 seconds. Each scene must raise an unanswered tension question leading directly into the next scene.
3. THE INFINITY LOOP: The final scene's last sentence must end with an incomplete connector that flows grammatically and seamlessly straight back into Scene 1's opening word!
4. DUAL-LANGUAGE REQUIREMENT:
   - "narration_urdu": Authentic fast gamer slang in Roman Urdu (words like: clutch, one-tap, hacker, scene, banda, garena, headshot, khalaas, OP).
   - "narration_en": Punchy, short English translation for international subtitles.
5. SFX & ACTION TAGGING: Every scene must have a precise SFX trigger and camera motion.
"""

def build_retention_prompt(manifest: dict) -> str:
    daily_short = manifest.get("tasks", {}).get("daily_short", {})
    topic = daily_short.get("topic", "Is DEVIL using secret one-tap config or pure reflexes?")
    title_hook = daily_short.get("suggested_title", "Is DEVIL Using Secret Config?")
    featured_weapon = daily_short.get("featured_weapon", "M1887")
    in_game_tag = manifest.get("in_game_tag", "DEVIL-999")
    channel_name = manifest.get("channel_name", "DEVIL INSANITY")

    prompt = f"""
{VIRAL_PSYCHOLOGY_FRAMEWORK}

[CONTEXT FOR THIS VIDEO]
Channel: {channel_name}
Player Tag: {in_game_tag}
Gun Featured: {featured_weapon}
Topic Angle: {topic}
Title Idea: {title_hook}

Generate an explosive 5-scene Short script. Total duration must be 9 to 10 seconds (5 scenes x 1.8s-2.0s).

OUTPUT STRICT JSON ONLY (No Markdown ticks, no chat, just valid parseable JSON):
{{
  "title_urdu": "Urdu/Hindi viral title (e.g. Kya DEVIL Hacker Hai Ya World Record?)",
  "title_en": "{title_hook}",
  "description_en": "High CTR global description with hashtags #FreeFire #Shorts #DEVIL999 #Clutch",
  "in_game_tag": "{in_game_tag}",
  "infinity_loop_phrase": "Connector connecting scene 5 back to scene 1",
  "scenes": [
    {{
      "scene_num": 1,
      "duration_sec": 1.8,
      "tension_trigger": "Shocking accusation / visual tension",
      "narration_urdu": "Short explosive Urdu line under 7 words",
      "narration_en": "Short English subtitle under 7 words",
      "visual_action": "Fast 1887 crosshair lock and jump",
      "camera_motion": "fast_zoom_in",
      "sfx": "vine_boom"
    }},
    {{
      "scene_num": 2,
      "duration_sec": 1.8,
      "tension_trigger": "Sudden unanswered question",
      "narration_urdu": "Urdu question under 7 words",
      "narration_en": "English subtitle under 7 words",
      "visual_action": "Freeze frame on enemy helmet",
      "camera_motion": "micro_screen_shake",
      "sfx": "bass_drop"
    }},
    {{
      "scene_num": 3,
      "duration_sec": 2.0,
      "tension_trigger": "High stakes proof",
      "narration_urdu": "Urdu line under 8 words",
      "narration_en": "English subtitle under 8 words",
      "visual_action": "Bullet fires, red damage number 550 appears",
      "camera_motion": "slow_motion_snap",
      "sfx": "hitmarker"
    }},
    {{
      "scene_num": 4,
      "duration_sec": 1.8,
      "tension_trigger": "The shocking revelation",
      "narration_urdu": "Urdu line under 7 words",
      "narration_en": "English subtitle under 7 words",
      "visual_action": "Kill feed badge DEVIL-999 pop-up",
      "camera_motion": "flash_transition",
      "sfx": "gun_cock"
    }},
    {{
      "scene_num": 5,
      "duration_sec": 2.0,
      "tension_trigger": "Infinity loop bridge to Scene 1",
      "narration_urdu": "Urdu connector leading back to Scene 1",
      "narration_en": "English connector line",
      "visual_action": "High speed whip pan back to opening frame",
      "camera_motion": "whip_pan",
      "sfx": "whoosh"
    }}
  ]
}}
"""
    return prompt.strip()
