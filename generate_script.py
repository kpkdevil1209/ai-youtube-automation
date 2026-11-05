import os
import sys
import json
import re
import random
import time
import subprocess
import urllib.request

def ensure_ollama_and_llama():
    """GitHub runner par Ollama aur Meta Llama 3.2 model set karta hai"""
    # 1. Install Ollama agar na ho
    if subprocess.call(["which", "ollama"]) != 0:
        print("[*] Installing Ollama Engine...")
        subprocess.check_call("curl -fsSL https://ollama.com/install.sh | sh", shell=True)

    # 2. Start Ollama Background Service
    print("[*] Starting Local AI Service...")
    subprocess.Popen(["ollama", "serve"])
    time.sleep(3)

    # 3. Download Meta's Llama 3.2 3B (Viral Creative Writing King)
    print("[*] Pulling Meta Llama-3.2 (3B) Model (~2.0 GB)...")
    subprocess.check_call(["ollama", "pull", "llama3.2:3b"])

def query_llama(prompt):
    """Meta Llama 3.2 se native JSON script generate karta hai"""
    url = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": "llama3.2:3b",
        "prompt": prompt,
        "stream": False,
        "format": "json"  # Built-in strict JSON mode
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    with urllib.request.urlopen(req, timeout=90) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        raw_json = result.get("response", "{}")
        return json.loads(raw_json)

def main():
    ensure_ollama_and_llama()

    categories = [
        "Dark Psychology: Manipulation tactics people secretly use in conversations",
        "Disturbing human brain glitches and illusions science cannot explain",
        "Deep Space Terrors: Rogue black holes drifting silently across galaxies",
        "Subconscious body language cues: How to read anyone like an open book"
    ]
    chosen_category = random.choice(categories)

    prompt = f"""
You are a viral YouTube Shorts scriptwriter with millions of views.
Category: {chosen_category}

Write a gripping, high-retention 45-second vertical video script between 110 and 130 words.
Rules:
- First sentence must be an irresistible psychological hook.
- Fast pacing with continuous suspense in the middle.
- End with a mind-bending question or infinite loop.
- No sound cues like [whisper] or [music]. Just spoken words.

Respond in valid JSON format with keys:
"title": "Shocking Catchy Title #Shorts",
"script": "Full voiceover narration text"
"""

    print("[*] Generating viral script using Meta Llama 3.2 (3B)...")
    data = query_llama(prompt)

    title_text = data.get("title", "Shocking Truth #Shorts")
    script_text = data.get("script") or data.get("text") or ""

    if not script_text:
        print("[ERROR] Model ne script text create nahi kiya!")
        sys.exit(1)

    # current_script.json save karein
    script_data = {
        "title": title_text,
        "topic": chosen_category,
        "script": script_text,
        "text": script_text,
        "narration": script_text,
        "voiceover": script_text,
        "word_count": len(script_text.split()),
        "ai_engine": "Meta-Llama-3.2-3B"
    }

    with open("current_script.json", "w", encoding="utf-8") as f:
        json.dump(script_data, f, indent=2, ensure_ascii=False)

    print(f"[✓] SUCCESS! Meta Llama 3.2 ne super-viral script generate kar di!")
    print(f"Title: {title_text}")
    print(f"Word Count: {len(script_text.split())} words (~45s voiceover)")
    print(f"Preview: {script_text[:120]}...")

if __name__ == "__main__":
    main()
