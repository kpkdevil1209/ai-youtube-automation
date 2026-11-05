import os
import sys
import json
import re
import random
from google import genai

API_KEY = "AQ.Ab8RN6LB1Bd9vV6iYCyd2fDAv_fdVTDloHPUgMIde-_ysfKLSA"
if os.getenv("GEMINI_API_KEY"):
    API_KEY = os.getenv("GEMINI_API_KEY").strip()

def main():
    print("[*] Official Google GenAI Interactions Client initialize ho raha hai...")
    client = genai.Client(api_key=API_KEY)

    categories = [
        "Dark Psychology: Psychological manipulation tactics people use on you daily",
        "Disturbing human brain glitches and illusions that scientists cannot explain",
        "Deep Space Terrors: Black holes and rogue planets drifting silently",
        "Unsolved historical mysteries that sound like science fiction",
        "Subconscious body language cues: How to read anyone like an open book"
    ]
    chosen_category = random.choice(categories)

    # 40-60 seconds ke liye 110-130 words ka strict rule
    prompt = f"""
You are a viral YouTube Shorts creator specializing in high-retention content.
Topic Category: {chosen_category}

Write a captivating, thrilling, fast-paced vertical video script.
Length Requirement:
- Duration MUST be between 40 and 55 seconds when read aloud.
- Word count MUST be between 110 and 135 words (do not make it shorter than 100 words).
- Hook the audience in the first 3 seconds.
- Create suspense in the middle, and an unexpected twist or infinite loop at the end.

Strictly respond ONLY with valid raw JSON (no markdown ticks, no extra text):
{{
  "title": "Shocking Catchy Title #Shorts #Facts",
  "text": "Full voiceover narration text. Do not include bracketed cues like [music] or (whispers). Just pure spoken words."
}}
"""

    models_to_try = ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
    script_text = ""
    title_text = ""

    for model_name in models_to_try:
        try:
            print(f"[*] Calling Gemini Model: {model_name}...")
            interaction = client.interactions.create(
                model=model_name,
                input=prompt
            )
            raw_text = interaction.output_text.strip()
            
            # JSON Clean extraction
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                title_text = data.get("title", "Shocking Truth #Shorts")
                script_text = data.get("text") or data.get("script") or ""
                if script_text and len(script_text.split()) >= 80:
                    print(f"[✓] Gemini Model {model_name} se {len(script_text.split())} words ki 40-60s script tayar!")
                    break
        except Exception as e:
            print(f"[!] Model {model_name} error: {e}")

    if not script_text:
        print("[X] ERROR: Gemini API call fail hui! Google Cloud / AI Studio project status check karein.")
        sys.exit(1)

    # current_script.json save karein
    script_data = {
        "title": title_text,
        "topic": chosen_category,
        "script": script_text,
        "text": script_text,
        "narration": script_text,
        "voiceover": script_text,
        "word_count": len(script_text.split())
    }

    with open("current_script.json", "w", encoding="utf-8") as f:
        json.dump(script_data, f, indent=2, ensure_ascii=False)

    print(f"[✓] 40-60 second ki video script current_script.json mein save ho gayi!")
    print(f"Title: {title_text}")
    print(f"Total Words: {len(script_text.split())} (Expected time: ~45-50 seconds)")

if __name__ == "__main__":
    main()
