import os
import sys
import json
import re
import time
import random
import google.generativeai as genai

# Aapki API Key yahan direct code mein set hai (Secrets ki zaroorat nahi)
API_KEY = os.getenv("GEMINI_API_KEY") or "AQ.Ab8RN6LB1Bd9vV6iYCyd2fDAv_fdVTDloHPUgMIde-_ysfKLSA"
API_KEY = API_KEY.strip().strip("'").strip('"')

def main():
    print("[*] Gemini API initialize ho rahi hai...")
    genai.configure(api_key=API_KEY)

    # Dynamic Topics List taake har dafa 100% naya aur viral topic bane
    categories = [
        "Dark Psychology tricks people use to manipulate conversations",
        "Disturbing human brain glitches that scientists cannot explain",
        "Creepy historical facts that are rarely talked about",
        "Space mysteries: Terrifying things found beyond our galaxy",
        "Micro-expressions: How to instantly tell if someone is lying to you",
        "The Mandela Effect cases that will make you question reality"
    ]
    chosen_category = random.choice(categories)
    random_id = random.randint(1000, 9999)

    prompt = f"""
You are a viral YouTube Shorts scriptwriter with millions of views.
Category: {chosen_category}
Unique ID: {random_id}

Write an intense, thrilling 25-30 second vertical short video script.
Rule:
1. Output ONLY pure valid JSON. No markdown ticks, no commentary.
2. Structure:
{{
  "title": "Shocking Catchy Title #Shorts #Facts",
  "topic": "{chosen_category}",
  "narration": "Gripping fast-paced narration hook and story. Do not include bracket tags like [music] or [sound]."
}}
"""

    models_to_try = [
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-pro"
    ]

    script_data = None

    for model_name in models_to_try:
        try:
            print(f"[*] Trying model: {model_name}...")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            
            raw_text = response.text.strip()
            # Clean JSON extraction
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if json_match:
                script_data = json.loads(json_match.group(0))
                print(f"[✓] Kamyabi se generate ho gaya model: {model_name} se!")
                break
        except Exception as e:
            print(f"[!] {model_name} se call nahi hui: {e}")

    # Agar kisi network ya token delay ki wajah se API na chale, to unique high-retention generator:
    if not script_data:
        print("[!] API se direct response nahi mila, generating dynamic unique viral script...")
        unique_hooks = [
            ("Did you know your brain secretly tricks you every single day?", "Psychology Fact #Shorts"),
            ("This banned psychological trick was used in ancient Rome.", "Dark History #Shorts"),
            ("Scientists just discovered something unsettling about sleep.", "Sleep Paradox #Shorts")
        ]
        hook, title = random.choice(unique_hooks)
        script_data = {
            "title": title,
            "topic": chosen_category,
            "narration": f"{hook} When someone maintains eye contact for more than six seconds without blinking, their brain releases adrenaline. It either means intense attraction, or extreme aggression. Next time you talk to someone, notice their pupils. If they dilate, their subconscious is fully engaged."
        }

    # Output file current_script.json likhein
    with open("current_script.json", "w", encoding="utf-8") as f:
        json.dump(script_data, f, indent=2, ensure_ascii=False)

    print(f"[✓] Script ready: current_script.json created!")
    print(f"Title: {script_data.get('title')}")
    print(f"Narration: {script_data.get('narration')[:120]}...")

if __name__ == "__main__":
    main()
