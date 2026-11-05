import os
import sys
import subprocess
import urllib.request
import shutil

print("[*] Starting Kaggle NVIDIA T4 GPU Video Engine...")

# Working directory Kaggle ki ensure karein
work_dir = "/kaggle/working" if os.path.exists("/kaggle/working") else "."
os.chdir(work_dir)

REPO_RAW = "https://raw.githubusercontent.com/kpkdevil1209/ai-youtube-automation/main"

# Step 1: Voiceover & Subtitles download karein
print("[*] Fetching voiceover and subtitles from repository...")
urllib.request.urlretrieve(f"{REPO_RAW}/voiceover.mp3", "voiceover.mp3")
urllib.request.urlretrieve(f"{REPO_RAW}/subtitles.srt", "subtitles.srt")

# Step 2: Audio duration pata karein
try:
    cmd = "ffprobe -i voiceover.mp3 -show_entries format=duration -v quiet -of csv=\"p=0\""
    duration = float(subprocess.check_output(cmd, shell=True).decode().strip())
except Exception:
    duration = 45.0

print(f"[*] Total Video Duration: {duration:.2f} seconds")

# Step 3: FFmpeg se Native 1080x1920 HD Animated Gradient Video + Voiceover + Subtitles banayein
print("[*] Rendering 1080x1920 HD Video with Voiceover & Subtitles on GPU...")

render_cmd = f"""
ffmpeg -y \
-f lavfi -i "gradients=s=1080x1920:d={duration}:c0=0x0a0a14:c1=0x231342:speed=0.008" \
-i voiceover.mp3 \
-t {duration} \
-vf "subtitles=subtitles.srt:force_style='FontName=Arial,FontSize=22,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=2,Alignment=2,MarginV=350'" \
-c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p \
-c:a aac -b:a 192k \
final_output.mp4
"""

subprocess.check_call(render_cmd, shell=True)

# Step 4: Output verify karein
if os.path.exists("final_output.mp4") and os.path.getsize("final_output.mp4") > 50000:
    size_mb = os.path.getsize("final_output.mp4") / (1024 * 1024)
    print(f"[✓] SUCCESS! final_output.mp4 ready ({size_mb:.2f} MB) in {work_dir}!")
    # Copy to both locations for safety
    if work_dir != ".":
        shutil.copy("final_output.mp4", "/kaggle/working/final_output.mp4")
else:
    print("[X] ERROR: Video render fail ho gayi!")
    sys.exit(1)
