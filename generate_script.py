import os
import sys
import json
import re
import time
import random
import google.generativeai as genai

def get_best_model():
    """Aapki API key se active aur compatible model dhoondta hai taake 404 na aaye"""
    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
    except Exception as e:
        print(f"[!] Models list karne mein masla: {e}")

    # Flash aur Fast models ko tarjeeh dein
    preferences = [
        "models/gemini-1.5-flash-latest",
        "models/gemini-1.5-flash",
        "models/gemini-2.0-flash",
        "models/gemini-1.5-pro-latest",
        "models/gemini-1.5-pro",
        "models/gemini-pro"
    ]

    for pref in preferences:
        if pref in available_models:
            print(f"[✓] Active model mil gaya: {pref}")
            return pref

    # Agar list mein se koi match na ho lekin koi aur available ho
    if available_models:
        print(f"[✓] Alternate available model: {available_models[0]}")
        return available_models[0]

    # Default fallback to standard name
    return "gemini-1.5-flash-latest"

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[X] ERROR: GEMINI_API_KEY GitHub Secrets mein nahi mili!")
        sys.exit(1)

    genai.configure(api_key=api_key)

    chosen_model_name = get_best_model()
    print(f"[*] Initializing {chosen_model_name}...")
    model = genai.GenerativeModel(chosen_model_name)

    # Random category aur seed taake topic har dafa 100% naya aur viral ho
    categories = [
        "Dark Psychology & Manipulation Tricks People Use on You",
        "Disturbing Historical Facts School Never Taught You",
        "Mind-Blowing Space & Black Hole Paradoxes",
        "Human Body Secrets & Brain Glitches",
        "Bizarre Unexplained Mysteries & Real Life Glitches"
    ]
    chosen_category = random.choice(categories)
    unique_seed = int(time.time())

    prompt = f"""
You are an expert YouTube Shorts creator with millions of views.
Category: {chosen_category}
Random Seed: {unique_seed}

Write a viral, fast-paced 25 to 30 second vertical short video script.
It MUST hook the viewer in the first 2 seconds.

Strict Output Rules:
1. Respond ONLY with valid JSON.
2. Do not use markdown backticks like ```json.
3. Exactly this JSON structure:
{{
  "title": "Shocking Catchy Title #Shorts",
  "topic": "Brief topic name",
  "narration": "Full spoken voiceover text without any sound effect tags or brackets. Make it exciting, clear, and gripping for text-to-speech."
}}
"""

    print(f"[*] Generating viral script for category: {chosen_category}...")
    response = model.generate_content(prompt)
    raw_text = response.text.strip()

    # JSON extract karein
    json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
    if json_match:
        clean_json_str = json_match.group(0)
    else:
        clean_json_str = raw_text

    data = json.loads(clean_json_str)

    # current_script.json save karein
    output_filename = "current_script.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[✓] Script kamyabi se generate ho gayi!")
    print(f"Title: {data.get('title')}")
    print(f"Narration: {data.get('narration')[:100]}...")

if __name__ == "__main__":
    main()
