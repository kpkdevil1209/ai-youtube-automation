import os
import sys
import json
import re
import time
import random
import google.generativeai as genai

API_KEY = os.getenv("GEMINI_API_KEY") or "AQ.Ab8RN6LB1Bd9vV6iYCyd2fDAv_fdVTDloHPUgMIde-_ysfKLSA"
API_KEY = API_KEY.strip().strip("'").strip('"')

def main():
    print("[*] Gemini API initialize ho rahi hai...")
    genai.configure(api_key=API_KEY)

    categories = [
        "Dark Psychology tricks people use to manipulate conversations",
        "Disturbing human brain glitches that scientists cannot explain",
        "Creepy historical facts that are rarely talked about",
        "Space mysteries: Terrifying things found beyond our galaxy",
        "Micro-expressions: How to instantly tell if someone is lying to you"
    ]
    chosen_category = random.choice(categories)

    prompt = f"""
You are a viral YouTube Shorts creator.
Write an intense, gripping 25-30 second vertical short video script about: {chosen_category}.
Only valid JSON format without markdown:
{{
  "title": "Shocking Catchy Title #Shorts",
  "text": "Full voiceover narration script without brackets or sound cues."
}}
"""

    models = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-2.0-flash", "gemini-pro"]
    final_text = ""
    final_title = ""

    for m in models:
        try:
            print(f"[*] Trying model: {m}...")
            model = genai.GenerativeModel(m)
            resp = model.generate_content(prompt)
            raw = resp.text.strip()
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                final_text = data.get("text") or data.get("script") or data.get("narration") or ""
                final_title = data.get("title", "Shocking Truth #Shorts")
                if final_text:
                    print(f"[✓] Model {m} se generation kamyab!")
                    break
        except Exception as e:
            print(f"[!] {m} call error: {e}")

    # Fallback agar network ya API delay ho
    if not final_text:
        hooks = [
            ("Did you know your brain secretly tricks you every single day? When someone stares at your forehead during a conversation, it triggers an unconscious feeling of intimidation. They suddenly lose confidence without even knowing why. Use this trick wisely.", "Dark Psychology Trick #Shorts"),
            ("Scientists just confirmed a terrifying space fact. There are rogue black holes drifting silently through our galaxy at millions of miles per hour. They swallow everything in their path, completely invisible until it is too late.", "Terrifying Space Reality #Shorts"),
            ("In ancient Rome, emperors used a psychological trick called bread and circuses. If you keep people entertained and fed, they will never notice their freedom being taken away. Look around today, does it sound familiar?", "Banned History Lesson #Shorts")
        ]
        chosen_script, chosen_title = random.choice(hooks)
        final_text = chosen_script
        final_title = chosen_title

    # Har possible key save karein taake audio script kabhi khali na ho!
    script_data = {
        "title": final_title,
        "topic": chosen_category,
        "script": final_text,
        "text": final_text,
        "narration": final_text,
        "voiceover": final_text
    }

    with open("current_script.json", "w", encoding="utf-8") as f:
        json.dump(script_data, f, indent=2, ensure_ascii=False)

    print("[✓] Script tayar aur current_script.json mein save ho gayi!")
    print(f"Title: {final_title}")
    print(f"Text: {final_text[:100]}...")

if __name__ == "__main__":
    main()
