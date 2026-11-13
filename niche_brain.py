import os
import json
import random
import time

class NicheBrain:
    def __init__(self):
        # 6 Permanent Strategic Content Pillars (Frameworks, Not Fixed Topics)
        self.pillars = {
            "weapon_drag_physics": {
                "name": "Weapon Mastery & Drag Physics",
                "core_objective": "Explain headshot angles, recoil reset, drag speeds, and fire button placement.",
                "weapons": ["Desert Eagle", "M1887", "Woodpecker", "MP40", "AWM", "AC80", "UMP", "M1014", "Charge Buster", "Groza"],
                "situations": ["1v1 Close Range", "Mid-Range Drag", "Jumping Enemy", "Gloo Wall Peek", "Running Target"],
                "emotional_angles": ["Secret setting grandmasters hide", "Impossible angle discovery", "Why 99% players fail this drag"]
            },
            "hacker_vs_skill_investigation": {
                "name": "Hacker Controversy & Panel vs Skill",
                "core_objective": "Analyze whether an insane shot or movement was done via paid panel or 120Hz pure mobile reflexes.",
                "weapons": ["Woodpecker", "M1887", "Desert Eagle", "SVD", "M500"],
                "situations": ["Smoke Headshot", "Blind Gloo Wall Penetration", "180 Degree Flick", "Zero Recoil Spray"],
                "emotional_angles": ["Garena anti-cheat dilemma", "Panel expose", "Is this player human?"]
            },
            "clutch_psychology": {
                "name": "1v4 Solo vs Squad Clutch Formulas",
                "core_objective": "Deconstruct high-IQ positioning, angle isolation, and 10 HP survival clutch moments.",
                "weapons": ["M1887", "MP40", "Desert Eagle", "UMP", "Grenade + Shotgun"],
                "situations": ["1 vs 4 Custom Room", "Grandmaster Final Zone", "Rush Attack Defense", "CS Ranked Decider"],
                "emotional_angles": ["When your whole squad dies", "Calm nerves under pressure", "Outplaying toxic trash talkers"]
            },
            "nostalgia_and_lore": {
                "name": "Old Free Fire Nostalgia & Evolution",
                "core_objective": "Compare old golden days of Free Fire with modern meta and remember iconic moments.",
                "weapons": ["Old M4A1", "Old Double M1887", "Old MP40 Bunny", "Old AK47 Dragon"],
                "situations": ["Old Factory Roof Fist Fight", "Old Peak Tower Rush", "Season 1 Sakura Lobby", "Bermuda Bridge Camp"],
                "emotional_angles": ["Before Free Fire became pay to win", "The sadness of deleted features", "Why old days were pure emotion"]
            },
            "secret_settings_meta": {
                "name": "Secret DPI, Sensitivity & Button Physics",
                "core_objective": "Reveal device-level optimizations and fire button micro-adjustments.",
                "weapons": ["Desert Eagle", "Woodpecker", "M1887"],
                "situations": ["Low-End Phone Smoothness", "120Hz Touch Sampling", "Zero Lag Trick", "Perfect Drag Sensitivity"],
                "emotional_angles": ["The setting phone companies hide", "Instant headshot boost", "Device secret"]
            },
            "dark_game_mysteries": {
                "name": "Dark Free Fire Lore & Glitches",
                "core_objective": "Unravel creepy, mysterious, or game-breaking server bugs and haunted IDs.",
                "weapons": ["AWM", "Scythe", "Crossbow"],
                "situations": ["Banned Invisible Room", "Negative Diamond Bug", "Ghost Player in Match", "Deleted Map Area"],
                "emotional_angles": ["Garena tried to delete this", "Creepiest glitch ever recorded", "Player vanished"]
            }
        }

        self.history_file = "used_topics_history.json"

    def get_pillars_prompt(self):
        """Builds a comprehensive guide prompt for the AI to generate a brand new topic."""
        pillar_key = random.choice(list(self.pillars.keys()))
        selected = self.pillars[pillar_key]

        weapon = random.choice(selected["weapons"])
        situation = random.choice(selected["situations"])
        angle = random.choice(selected["emotional_angles"])

        # Avoid repetition by feeding previously used queries
        recent_queries = self._get_recent_history()

        prompt = f"""
You are the Lead Content Director for DEVIL INSANITY (DEVIL-999), a top-tier Free Fire gaming channel.
Your task: Invent a 100% BRAND NEW, viral, high-retention YouTube Short topic based on this pillar:

PILLAR: {selected['name']}
OBJECTIVE: {selected['core_objective']}
FOCUS WEAPON: {weapon}
SITUATION: {situation}
EMOTIONAL HOOK ANGLE: {angle}

STRICT RULE: Do NOT copy any of these recently used queries:
{json.dumps(recent_queries[-10:], indent=2)}

OUTPUT FORMAT ONLY (JSON):
{{
  "pillar_id": "{pillar_key}",
  "title": "A high-CTR title under 55 characters with #shorts #freefire",
  "search_query": "A realistic YouTube search query to find high quality 60fps real gameplay clip for this topic (e.g. '{weapon} free fire clutch highlights 60fps')",
  "weapon": "{weapon}",
  "estimated_damage": "e.g. 550 or 495 or 372",
  "story_hook": "First 3-second Urdu hook line to stop scrolling instantly",
  "story_body": "Main advice or dramatic breakdown in Urdu (1-2 sentences)",
  "story_climax": "Reaction to the headshot or clutch moment in Urdu",
  "story_outro": "Call to action or challenge to comments in Urdu"
}}
"""
        return prompt, pillar_key, weapon, situation, angle

    def record_used_topic(self, query):
        """Saves query so it is never repeated."""
        history = self._get_recent_history()
        history.append({"query": query, "timestamp": time.time()})
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

    def _get_recent_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def generate_combinatorial_topic(self, pillar_key, weapon, situation, angle):
        """Dynamic synthesis engine if local LLM is slow or offline."""
        modifiers = ["Crazy", "Impossible", "Secret", "God Level", "Unreal", "120Hz Fast"]
        mod = random.choice(modifiers)
        
        title = f"{mod} {weapon} {situation}! ({angle[:25]}) #shorts #freefire"
        search_query = f"{weapon} free fire {situation.lower()} highlights 60fps"
        
        # Ensure search query is completely fresh
        salt = random.randint(10, 99)
        if random.random() > 0.5:
            search_query += f" montage"

        damage_map = {
            "Desert Eagle": "495", "M1887": "550", "Woodpecker": "372",
            "MP40": "148", "AWM": "300", "AC80": "345", "UMP": "172", "M1014": "550"
        }

        return {
            "pillar_id": pillar_key,
            "title": title,
            "search_query": search_query,
            "weapon": weapon,
            "estimated_damage": damage_map.get(weapon, "550"),
            "story_hook": f"Agar tumhara {weapon} se one tap nahi lagta to ye secret angle miss mat karna.",
            "story_body": f"Jab enemy {situation} mein ho to screen ko hamesha U-drag karo.",
            "story_climax": f"Ye shot dekho! Pure red numbers connect hue hain.",
            "story_outro": "Comment mein apna favorite gun batao aur DEVIL-999 ko follow karo."
        }

if __name__ == "__main__":
    b = NicheBrain()
    prompt, p, w, s, a = b.get_pillars_prompt()
    print("[*] Generated Prompt for AI:")
    print(prompt)
