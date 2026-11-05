import os
import sys
import json
import re
import random
import time
import subprocess

# Auto-install google-genai agar mojood na ho
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
    print("[*] Initializing Google GenAI Client...")
    client = genai.Client(api_key=API_KEY)

    categories = [
        "Dark Psychology: Psychological manipulation tactics people use on you daily",
        "Disturbing human brain glitches that science cannot explain",
        "Deep Space Terrors: Black holes drifting silently in our galaxy",
        "Unsolved historical mysteries that sound like science fiction",
        "Subconscious body language cues: How to read anyone like an open book"
    ]
    chosen_category = random.choice(categories)

    # 40-60 seconds (110 to 135 words)
    prompt = f"""
You are a viral YouTube Shorts scriptwriter.
Topic: {chosen_category}

Write a high-retention 45-50 second vertical video script.
Length: between 110 and 135 words.
Structure:
- Hook in the first 3 seconds
- Fast-paced thrilling explanation
- Unexpected ending or loop

Respond ONLY in raw JSON (no markdown ticks):
{{
  "title": "Shocking Catchy Title #Shorts #Facts",
  "text": "Full voiceover narration without brackets or sound cues."
}}
"""

    # Official active Gemini 3 models
    models_to_try = ["gemini-3.8-flash", "gemini-3.8-pro"]
    script_text = ""
    title_text = ""

    for model_name in models_to_try:
        # Har model par 3 attempts (503 high demand ke liye)
        for attempt in range(1, 4):
            try:
                print(f"[*] Calling {model_name} (Attempt {attempt}/3)...")
                interaction = client.interactions.create(
                    model=model_name,
                    input=prompt
                )
                raw_text = interaction.output_text.strip()
                
                match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    title_text = data.get("title", "Shocking Truth #Shorts")
                    script_text = data.get("text") or data.get("script") or ""
                    if script_text:
                        words = len(script_text.split())
                        print(f"[✓] SUCCESS! {model_name} ne {words} words ki script generate kar di!")
                        break
            except Exception as e:
                err_msg = str(e)
                print(f"[!] {model_name} attempt {attempt} failed: {err_msg}")
                # Agar 503 (High demand) aaye to 3 second wait karke retry karein
                if "503" in err_msg or "high demand" in err_msg or "service_unavailable" in err_msg:
                    print("[*] 503 High demand detected. Retrying in 3 seconds...")
                    time.sleep(3)
                else:
                    time.sleep(1)

        if script_text:
            break

    if not script_text:
        print("[X] ERROR: Gemini servers currently busy. Please retry in a few moments.")
        sys.exit(1)

    # current_script.json save karein (Audio script ke sab fields ke sath)
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
    print(f"Duration: ~45-50s ({len(script_text.split())} words)")

if __name__ == "__main__":
    main()
