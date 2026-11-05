import os
import sys
import subprocess
import urllib.request
import json

print("[*] Kaggle NVIDIA T4 GPU Video Renderer shuru ho raha hai...")

REPO_RAW = "https://raw.githubusercontent.com/kpkdevil1209/ai-youtube-automation/main"

# Step 1: Latest Voiceover aur Subtitles download karein
print("[*] Voiceover aur Subtitles fetch kiye ja rahe hain...")
try:
    urllib.request.urlretrieve(f"{REPO_RAW}/voiceover.mp3", "voiceover.mp3")
    print("[✓] voiceover.mp3 download ho gaya!")
except Exception as e:
    print(f"[!] voiceover download error: {e}")

try:
    urllib.request.urlretrieve(f"{REPO_RAW}/subtitles.srt", "subtitles.srt")
    print("[✓] subtitles.srt download ho gaya!")
except Exception as e:
    print(f"[!] subtitles download error: {e}")

# Step 2: Audio ki duration pata karein
def get_audio_duration():
    try:
        cmd = "ffprobe -i voiceover.mp3 -show_entries format=duration -v quiet -of csv=\"p=0\""
        out = subprocess.check_output(cmd, shell=True).decode().strip()
        return float(out)
    except:
        return 45.0

duration = get_audio_duration()
print(f"[*] Total Video Duration: {duration} seconds")

# Step 3: High-Quality Vertical HD Background Video (Dark / Cinematic Aesthetic)
BG_URL = "https://assets.mixkit.co/videos/preview/mixkit-stars-in-space-1610-large.mp4"
print("[*] HD Background video download ho rahi hai...")
urllib.request.urlretrieve(BG_URL, "background.mp4")

# Step 4: FFmpeg se 1080x1920 Vertical Short Video Render karein (With Audio & Captions)
print("[*] NVIDIA T4 GPU par video render ho rahi hai...")
render_cmd = f"""
ffmpeg -y -stream_loop -1 -i background.mp4 -i voiceover.mp3 \
-t {duration} \
-vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,subtitles=subtitles.srt:force_style='FontName=Arial,FontSize=20,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=2,Alignment=2,MarginV=300'" \
-c:v libx264 -preset fast -crf 22 -c:a aac -b:a 192k \
final_output.mp4
"""

subprocess.check_call(render_cmd, shell=True)

# Step 5: Verify Final Output
if os.path.exists("final_output.mp4") and os.path.getsize("final_output.mp4") > 1000:
    size_mb = os.path.getsize("final_output.mp4") / (1024 * 1024)
    print(f"[✓] SUCCESS! final_output.mp4 tayar ho gayi hai ({size_mb:.2f} MB)!")
else:
    print("[X] ERROR: Video render nahi ho saki.")
    sys.exit(1)
