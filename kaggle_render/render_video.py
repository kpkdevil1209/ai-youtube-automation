import os
import sys
import subprocess

# Diffusers aur dependencies ensure karein
subprocess.call("pip install -q --upgrade diffusers transformers accelerate", shell=True)

import json
import urllib.request
import torch
from diffusers import AutoPipelineForText2Image

print("[*] Kaggle NVIDIA T4 GPU Full AI Video Engine Initialized!")
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[*] Compute Device: {device}")

work_dir = "/kaggle/working" if os.path.exists("/kaggle/working") else "."
os.chdir(work_dir)

REPO_RAW = "https://raw.githubusercontent.com/kpkdevil1209/ai-youtube-automation/main"

# Step 1: Script, Voiceover aur Subtitles download karein
print("[*] Downloading assets from GitHub repository...")
urllib.request.urlretrieve(f"{REPO_RAW}/current_script.json", "current_script.json")
urllib.request.urlretrieve(f"{REPO_RAW}/voiceover.mp3", "voiceover.mp3")
urllib.request.urlretrieve(f"{REPO_RAW}/subtitles.srt", "subtitles.srt")

with open("current_script.json", "r") as f:
    script_data = json.load(f)

topic = script_data.get("topic", "Dark Psychology and mystery")
print(f"[*] Video Topic: {topic}")

# Step 2: Audio Duration
cmd = "ffprobe -i voiceover.mp3 -show_entries format=duration -v quiet -of csv=\"p=0\""
duration = float(subprocess.check_output(cmd, shell=True).decode().strip())
print(f"[*] Total Duration: {duration:.2f} seconds")

# Step 3: Fast AI Image Generation Model (SDXL-Turbo)
print("[*] Loading SDXL-Turbo AI Visual Model into T4 GPU VRAM...")
pipe = AutoPipelineForText2Image.from_pretrained(
    "stabilityai/sdxl-turbo", 
    torch_dtype=torch.float16, 
    variant="fp16"
).to(device)

# Step 4: Har scene ke liye AI Visual banayein
num_scenes = max(4, int(duration // 7))
scene_duration = duration / num_scenes
print(f"[*] Generating {num_scenes} Cinematic AI Visuals for the story...")

image_files = []
for i in range(num_scenes):
    prompt = f"Cinematic 8k, vertical 9:16 portrait, dark atmospheric, hyper-realistic, dramatic lighting, {topic}, scene {i+1}"
    print(f"[*] Generating AI Scene {i+1}/{num_scenes}...")
    image = pipe(prompt=prompt, num_inference_steps=2, guidance_scale=0.0).images[0]
    
    image = image.resize((1080, 1920))
    img_path = f"scene_{i}.png"
    image.save(img_path)
    image_files.append(img_path)

# Step 5: FFmpeg se Cinematic Zoom motion aur Subtitles jod kar video banayein
print("[*] Assembling AI Scenes into Full Dynamic Video...")
filter_complex = ""
for i, img in enumerate(image_files):
    filter_complex += f"[{i}:v]zoompan=z='min(zoom+0.0015,1.25)':d={int(scene_duration*25)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920[v{i}];"

inputs = " ".join([f"-loop 1 -t {scene_duration} -i {img}" for img in image_files])
concat_inputs = "".join([f"[v{i}]" for i in range(num_scenes)])
filter_complex += f"{concat_inputs}concat=n={num_scenes}:v=1:a=0[vbg];"
filter_complex += "[vbg]subtitles=subtitles.srt:force_style='FontName=Arial,FontSize=22,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=2,Alignment=2,MarginV=350'[vout]"

render_cmd = f"""
ffmpeg -y {inputs} -i voiceover.mp3 \
-filter_complex "{filter_complex}" \
-map "[vout]" -map {num_scenes}:a \
-t {duration} \
-c:v libx264 -preset fast -pix_fmt yuv420p \
-c:a aac -b:a 192k \
final_output.mp4
"""

subprocess.check_call(render_cmd, shell=True)

if os.path.exists("final_output.mp4") and os.path.getsize("final_output.mp4") > 50000:
    print("[✓] SUCCESS! 100% Full AI Video Generated: final_output.mp4")
else:
    print("[X] ERROR: Video render fail ho gayi!")
    sys.exit(1)
