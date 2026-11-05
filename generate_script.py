import os
import sys
import json
import re
import random
import subprocess

# Agar google-genai install na ho to khud install karein
try:
    from google import genai
except ImportError:
    print("[*] google-genai library install ho rahi hai...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "google-genai"])
    from google import genai

API_KEY = "AQ.Ab8RN6LB1Bd9vV6iYCyd2fDAv_fdVTDloHPUgMIde-_ysfKLSA"
if os.getenv("GEMINI_API_KEY"):
    API_KEY = os.getenv("GEMINI_API_KEY").strip()

def main():
    print("[*] Google GenAI Client initialize ho raha hai...")
    client = genai.Client(api_key=API_KEY)

    categories = [
        "Dark Psychology: Hidden manipulation tactics people use on you daily",
        "Disturbing human brain glitches and illusions that scientists cannot explain",
        "Deep Space Terrors: Black holes and rogue planets drifting silently",
        "Unsolved historical mysteries that sound like science fiction",
        "Subconscious body language cues: How to read anyone like an open book"
    ]
    chosen_category = random.choice(categories)

    # 40-60 seconds (110-135 words)
    prompt = f"""
You are a viral YouTube Shorts scriptwriter.
Topic: {chosen_category}

Write a captivating 45-second vertical video script.
Length: between 110 and 135 words.
Structure:
- Intense hook in first 3 seconds
- Fast-paced explanation with psychological tension
- Unforgettable ending or loop

Respond ONLY in raw JSON (no markdown backticks):
{{
  "title": "Shocking Catchy Title #Shorts #Facts",
  "text": "Full voiceover narration without brackets or sound cues."
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
            
            # JSON clean extraction
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                title_text = data.get("title", "Shocking Truth #Shorts")
                script_text = data.get("text") or data.get("script") or ""
                if script_text:
                    words = len(script_text.split())
                    print(f"[✓] Gemini Model {model_name} se {words} words ki 40-60s script ban gayi!")
                    break
        except Exception as e:
            print(f"[!] Model {model_name} error: {e}")

    if not script_text:
        print("[X] ERROR: Gemini response nahi mila. API key check karein.")
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

    print(f"[✓] Script kamyabi se current_script.json mein save ho gayi!")
    print(f"Title: {title_text}")
    print(f"Words: {len(script_text.split())} (Duration: ~45-50s)")

if __name__ == "__main__":
    main()
