import json, os, sys
from gtts import gTTS

script_file = "current_script.json"
if not os.path.exists(script_file):
    print("\n[ERROR] current_script.json nahi mili! Pehle generate_script.py run karein.")
    sys.exit(1)

script_data = json.load(open(script_file, "r", encoding="utf-8"))
text = script_data.get("script_text", "").strip()

if not text:
    print("\n[ERROR] Script text khali hai!")
    sys.exit(1)

print("1. Generating Voiceover with gTTS...")
tts = gTTS(text=text, lang="en", slow=False)
tts.save("voiceover.mp3")
print("✓ voiceover.mp3 generated successfully!")

print("2. Generating Synchronized Subtitles (subtitles.srt)...")
sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
if not sentences:
    sentences = [text]

# Speaking speed approx 2.5 words per second
total_est_seconds = max(5.0, len(text.split()) / 2.5)
duration_per_sent = total_est_seconds / len(sentences)

srt_entries = []
for idx, sent in enumerate(sentences, 1):
    start = (idx - 1) * duration_per_sent
    end = idx * duration_per_sent
    s_m, s_s = divmod(int(start), 60)
    e_m, e_s = divmod(int(end), 60)
    s_ms = int((start - int(start)) * 1000)
    e_ms = int((end - int(end)) * 1000)
    start_ts = f"00:{s_m:02d}:{s_s:02d},{s_ms:03d}"
    end_ts = f"00:{e_m:02d}:{e_s:02d},{e_ms:03d}"
    srt_entries.append(f"{idx}\n{start_ts} --> {end_ts}\n{sent}\n")

with open("subtitles.srt", "w", encoding="utf-8") as f:
    f.write("\n".join(srt_entries))

print("✓ subtitles.srt generated successfully with proper timings!")
print("\n🎉 [SUCCESS] Audio and Subtitles ready for Video Creation!")
