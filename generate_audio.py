import os
import sys
import json
import re
from gtts import gTTS

def main():
    print("[*] Audio generation shuru ho rahi hai...")
    
    if not os.path.exists("current_script.json"):
        print("[ERROR] current_script.json file nahi mili!")
        sys.exit(1)

    with open("current_script.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    # Smart text extraction (chahe script, text ya narration kisi bhi naam se ho)
    script_text = ""
    for key in ["script", "text", "narration", "voiceover", "content"]:
        if data.get(key) and isinstance(data[key], str) and len(data[key].strip()) > 10:
            script_text = data[key].strip()
            break

    if not script_text:
        # Fallback to longest string
        for val in data.values():
            if isinstance(val, str) and len(val) > len(script_text):
                script_text = val

    if not script_text:
        print("[ERROR] Script text bilkul khali hai!")
        sys.exit(1)

    print(f"[✓] Narration text mil gaya ({len(script_text.split())} words):")
    print(f"{script_text[:100]}...")

    # Voiceover MP3 banayein (gTTS se)
    print("[*] Generating voiceover.mp3 using gTTS...")
    tts = gTTS(text=script_text, lang='en', slow=False)
    tts.save("voiceover.mp3")
    print("[✓] voiceover.mp3 kamyabi se save ho gayi!")

    # Subtitles (.srt) generate karein
    print("[*] Generating subtitles.srt...")
    words = script_text.split()
    total_words = len(words)
    # Approx 0.35s per word for natural gTTS pace
    word_duration = 0.35
    chunk_size = 4  # 4 words per subtitle line for Shorts

    srt_lines = []
    idx = 1
    current_time = 0.0

    for i in range(0, total_words, chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        start_time = current_time
        end_time = current_time + (len(chunk.split()) * word_duration)

        def format_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds - int(seconds)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        srt_lines.append(f"{idx}\n{format_time(start_time)} --> {format_time(end_time)}\n{chunk}\n")
        idx += 1
        current_time = end_time

    with open("subtitles.srt", "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))

    print("[✓] subtitles.srt kamyabi se ban gayi!")

if __name__ == "__main__":
    main()
