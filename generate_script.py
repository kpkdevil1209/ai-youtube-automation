import os
import sys
import json
import re
import random
import time
import urllib.request
import urllib.parse
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

def get_script_from_backup_ai(topic):
    """Zero-Load Free AI Engine (Real AI, No API key needed, Never gets 503)"""
    print("[*] Switching to High-Speed Backup AI Engine (Zero Load Error)...")
    prompt = (
        f"You are a viral YouTube Shorts writer. Write an intense, thrilling 45-second vertical script about: {topic}. "
        "Strict rule: length MUST be between 110 and 130 words. Hook in 3s, tension in middle, loop at end. "
        "Respond ONLY with raw JSON: {\"title\": \"Catchy Title #Shorts\", \"text\": \"Full narration text without brackets\"}"
    )
    
    # High-speed AI endpoint
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://text.pollinations.ai/{encoded_prompt}?json=true"
    
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    
    with urllib.request.urlopen(req, timeout=25) as resp:
        raw_text = resp.read().decode("utf-8").strip()
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(raw_text)

def main():
    categories = [
        "Dark Psychology: Psychological manipulation tactics people use on you daily",
        "Disturbing human brain glitches and illusions science cannot explain",
        "Deep Space Terrors: Black holes drifting silently in our galaxy",
        "Unsolved historical mysteries that sound like science fiction",
        "Subconscious body language cues: How to read anyone like an open book"
    ]
    chosen_category = random.choice(categories)

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

    script_text = ""
    title_text = ""

    # Engine 1: Google Gemini Model 3.8
    try:
        print("[*] Engine 1: Calling Google Gemini (gemini-3.8-flash)...")
        client = genai.Client(api_key=API_KEY)
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt
        )
        raw_text = response.text.strip()
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            title_text = data.get("title", "Shocking Truth #Shorts")
            script_text = data.get("text") or data.get("script") or ""
            if script_text:
                print(f"[✓] Google Gemini se {len(script_text.split())} words ki script ban gayi!")
    except Exception as e:
        print(f"[!] Google Gemini busy ya load error: {e}")

    # Engine 2: Agar Gemini busy ho to Backup AI se foran lein
    if not script_text:
        try:
            data = get_script_from_backup_ai(chosen_category)
            title_text = data.get("title", "Mind-Blowing Truth #Shorts")
            script_text = data.get("text") or data.get("script") or ""
            if script_text:
                print(f"[✓] Backup AI Engine se {len(script_text.split())} words ki live fresh script ban gayi!")
        except Exception as e2:
            print(f"[!] Backup AI error: {e2}")

    # Final Check
    if not script_text:
        print("[X] ERROR: Dono AI engines fail ho gaye.")
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

    print(f"[✓] Final Script current_script.json mein tayar ho gayi!")
    print(f"Title: {title_text}")
    print(f"Total Words: {len(script_text.split())} (Duration: ~45-50 seconds)")

if __name__ == "__main__":
    main()
