import os
import sys
import json
import re
import random
import time
import urllib.request
import urllib.parse
import subprocess

# Auto-install library if missing
try:
    from google import genai
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "google-genai"])
    from google import genai

API_KEY = "AQ.Ab8RN6LB1Bd9vV6iYCyd2fDAv_fdVTDloHPUgMIde-_ysfKLSA"
if os.getenv("GEMINI_API_KEY"):
    API_KEY = os.getenv("GEMINI_API_KEY").strip()

def get_ai_response(prompt):
    """Pehle Google Gemini se live call, agar busy ho to Backup AI se live call"""
    # 1. Try Gemini
    try:
        print("[*] Calling Google Gemini 3.8 Flash...")
        client = genai.Client(api_key=API_KEY)
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt
        )
        raw = response.text.strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        print(f"[!] Gemini temporary error: {e}")

    # 2. Try Backup AI (Live AI without load limits)
    print("[*] Calling Live Backup AI Engine...")
    url = f"https://text.pollinations.ai/{urllib.parse.quote(prompt)}?json=true"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8").strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(raw)

def main():
    categories = [
        "Dark Psychology: Psychological manipulation tactics people use on you daily",
        "Disturbing human brain glitches and illusions science cannot explain",
        "Deep Space Terrors: Black holes drifting silently in our galaxy",
        "Subconscious body language cues: How to read anyone like an open book"
    ]
    chosen_category = random.choice(categories)

    prompt = f"""
You are a viral YouTube Shorts scriptwriter.
Topic: {chosen_category}

Write a captivating 45-second vertical video script between 110 and 135 words.
Respond strictly ONLY in raw JSON format:
{{
  "title": "Shocking Catchy Title #Shorts",
  "script": "Full voiceover narration text without brackets or sound cues."
}}
"""

    data = get_ai_response(prompt)
    if not data or not isinstance(data, dict):
        raise RuntimeError("[ERROR] AI se response nahi mila!")

    # Sirf aur sirf AI ke response se script nikaalein
    script_text = ""
    for k in ["script", "text", "narration", "voiceover", "content", "story"]:
        if data.get(k) and isinstance(data[k], str) and len(data[k].strip()) > 30:
            script_text = data[k].strip()
            break

    if not script_text:
        for val in data.values():
            if isinstance(val, str) and len(val.strip()) > len(script_text):
                script_text = val.strip()

    if not script_text:
        raise RuntimeError("[ERROR] AI response ke andar script text nahi mila!")

    title_text = data.get("title", "Shocking Truth #Shorts")

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

    print(f"[✓] Pure Live AI Script generated ({len(script_text.split())} words)!")
    print(f"Title: {title_text}")
    print(f"Live AI Script Preview: {script_text[:120]}...")

if __name__ == "__main__":
    main()
