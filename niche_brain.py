"""
niche_brain.py
Autonomous Cognitive & Psychological Brain for DEVIL Gaming.
Implements:
1. The 0.1-second dopamine hook (No greetings / Zero fluff).
2. Micro-Open Loops every 1.5s - 2.0s.
3. Subconscious Infinity Retention Loop.
4. Dual-Language Engine (Urdu/Hindi Pro Gamer Voiceover + English Global Voiceover).
5. Dynamic Word-by-Word Subtitle Timing Engine.
"""

VIRAL_PSYCHOLOGY_FRAMEWORK = """
[STRICT SYSTEM ROLE: WORLD-CLASS VIRAL SHORT SCREENWRITER & HUMAN PSYCHOLOGIST]
You write hyper-addictive, ultra-viral Free Fire YouTube Shorts scripts.
Your target is 150%+ audience retention.

MANDATORY RULES:
1. ZERO GREETINGS: NEVER write "Hello", "Welcome", "Dosto", or "Aaj hum". The first word must punch the viewer in the face with controversy or a high-stakes question.
2. MICRO-OPEN LOOPS (1.5s - 2.0s): Every single scene MUST end with an unanswered curiosity hook that forces the human brain to watch the next 2 seconds.
3. POLARIZATION TRIGGER: Create subtle controversy (e.g. "Did he use config or is he a god?", "99% of players are doing this wrong").
4. THE INFINITY LOOP: The final sentence in Scene 5 MUST be a bridge phrase that seamlessly grammar-connects straight back into Scene 1's very first word!
5. DUAL-LANGUAGE REQUIREMENT:
   - "narration_urdu": Authentic fast gamer slang in Roman Urdu (words: clutch, one-tap, hacker, scene, banda, garena, headshot, khalaas, OP).
   - "narration_en": Punchy, energetic international gaming voiceover line (under 8 words per scene).
   - "subtitle_en": Word-by-word synchronized English subtitle.
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

[INPUT CONTEXT]
Channel: {channel_name}
Player Tag: {in_game_tag}
Featured Weapon: {featured_weapon}
Topic Angle: {topic}
Title Idea: {title_hook}

Generate an explosive 5-scene Short script. Total duration must be 9 to 10 seconds (5 scenes x 1.8s-2.0s).

OUTPUT STRICT JSON ONLY (No markdown ticks, no preamble, only valid JSON):
{{
  "title_urdu": "Shocking Urdu/Hindi title",
  "title_en": "{title_hook}",
  "description_en": "High CTR global description with hashtags #FreeFire #Shorts #DEVIL999 #Clutch",
  "in_game_tag": "{in_game_tag}",
  "infinity_loop_connector": "The exact bridge phrase connecting Scene 5 back to Scene 1",
  "scenes": [
    {{
      "scene_num": 1,
      "duration_sec": 1.8,
      "tension_trigger": "Explosive controversy / shock accusation",
      "narration_urdu": "Punched Urdu line under 7 words",
      "narration_en": "Punchy English voiceover line under 7 words",
      "subtitle_en": "ALL CAPS SHORT SUBTITLE",
      "visual_action": "Fast 1887 crosshair lock and jump",
      "camera_motion": "fast_zoom_in",
      "sfx": "vine_boom"
    }},
    {{
      "scene_num": 2,
      "duration_sec": 1.8,
      "tension_trigger": "Garena / Inspection tension",
      "narration_urdu": "Urdu question or mystery under 7 words",
      "narration_en": "English mystery line under 7 words",
      "subtitle_en": "ALL CAPS SHORT SUBTITLE",
      "visual_action": "Freeze frame on enemy helmet",
      "camera_motion": "micro_screen_shake",
      "sfx": "bass_drop"
    }},
    {{
      "scene_num": 3,
      "duration_sec": 2.0,
      "tension_trigger": "Red number damage proof",
      "narration_urdu": "Urdu proof line under 8 words",
      "narration_en": "English proof line under 8 words",
      "subtitle_en": "ALL CAPS SHORT SUBTITLE",
      "visual_action": "Bullet connects, red damage 550 appears",
      "camera_motion": "slow_motion_snap",
      "sfx": "hitmarker"
    }},
    {{
      "scene_num": 4,
      "duration_sec": 1.8,
      "tension_trigger": "DEVIL signature clutch moment",
      "narration_urdu": "Urdu clutch line under 7 words",
      "narration_en": "English clutch line under 7 words",
      "subtitle_en": "ALL CAPS SHORT SUBTITLE",
      "visual_action": "Kill feed badge DEVIL-999 pop-up",
      "camera_motion": "flash_transition",
      "sfx": "gun_cock"
    }},
    {{
      "scene_num": 5,
      "duration_sec": 2.0,
      "tension_trigger": "Infinity loop bridge leading back to Scene 1",
      "narration_urdu": "Incomplete Urdu phrase connecting to Scene 1",
      "narration_en": "Incomplete English bridge phrase connecting to Scene 1",
      "subtitle_en": "ALL CAPS SHORT SUBTITLE",
      "visual_action": "Fast whip pan leading straight to opening frame",
      "camera_motion": "whip_pan",
      "sfx": "whoosh"
    }}
  ]
}}
"""
    return prompt.strip()
