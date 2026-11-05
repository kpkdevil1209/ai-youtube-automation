import os
import sys
import json
import re
import random
import time
import subprocess

# Auto-install google-genai agar server par na ho
try:
    from google import genai
except ImportError:
    print("[*] Installing google-genai library...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "google-genai"])
    from google import genai

API_KEY = "AQ.Ab8RN6LB1Bd9vV6iYCyd2fDAv_fdVTDloHPUgMIde-_ysfKLSA"
if os.getenv("GEMINI_API_KEY"):
    API_KEY = os.getenv("GEMINI_API_KEY").strip()

def main():
    print("[*] Main Google AI Production Engine initialize ho raha hai...")
    client = genai.Client(api_key=API_KEY)

    categories = [
        "Dark Psychology: Psychological manipulation tactics people use on you daily",
        "Disturbing human brain glitches that science cannot explain",
        "Deep Space Terrors: Black holes drifting silently in our galaxy",
        "Unsolved historical mysteries that sound like science fiction",
        "Subconscious body language cues: How to read anyone like an open book"
    ]
    chosen_category = random.choice(categories)

    # 40-60 seconds (110 se 135 words)
    prompt = f"""
You are a viral YouTube Shorts scriptwriter.
Topic: {chosen_category}

Write a high-retention 45-50 second vertical video script.
Length: between 110 and 135 words (strictly not less than 100 words).
Structure:
- Shocking hook in the first 3 seconds
- Fast-paced explanation with psychological tension
- Unforgettable ending or loop

Respond ONLY in raw valid JSON (no markdown backticks):
{{
  "title": "Shocking Catchy Title #Shorts #Facts",
  "text": "Full voiceover narration script without brackets or sound cues."
}}
"""

    # Main production models jahan load ka masla nahi hota
    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-3.8-flash"]
    script_text = ""
    title_text = ""

    for model_name in models:
        try:
            print(f"[*] Calling Google AI Model: {model_name}...")
            # Official Main Production Method (client.models.generate_content)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            raw_text = response.text.strip()
            
            # JSON Clean Extract
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                title_text = data.get("title", "Shocking Truth #Shorts")
                script_text = data.get("text") or data.get("script") or ""
                if script_text:
                    words = len(script_text.split())
                    print(f"[✓] Google AI ({model_name}) ne {words} words ki 40-60s script bana di!")
                    break
        except Exception as e:
            print(f"[!] {model_name} error: {e}")
            time.sleep(1)

    if not script_text:
        print("[X] ERROR: Script generate nahi ho saki.")
        sys.exit(1)

    # current_script.json save karein (Audio script ke sabhi fields ke sath)
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
    print(f"Length: {len(script_text.split())} words (Duration: ~45-50s)")

if __name__ == "__main__":
    main()
