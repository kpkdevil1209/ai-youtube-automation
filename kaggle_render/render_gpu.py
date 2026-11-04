import os, json, urllib.request
from moviepy.editor import TextClip, AudioFileClip, ColorClip, CompositeVideoClip

base_url = "https://raw.githubusercontent.com/kpkdevil1209/ai-youtube-automation/main/"

print("Downloading latest script and audio from GitHub...")
urllib.request.urlretrieve(base_url + "current_script.json", "current_script.json")
urllib.request.urlretrieve(base_url + "voiceover.mp3", "voiceover.mp3")

script_data = json.load(open("current_script.json", "r", encoding="utf-8"))
title = script_data.get("title", "Viral Fact")
print(f"🎬 GPU Rendering for: {title}")

audio = AudioFileClip("voiceover.mp3")
duration = audio.duration

bg = ColorClip(size=(1080, 1920), color=(12, 14, 28)).set_duration(duration)
txt_clip = TextClip(title.upper(), fontsize=56, color="yellow", font="DejaVu-Sans-Bold", size=(920, None), method="caption", stroke_color="black", stroke_width=3).set_duration(duration).set_position("center")

final_video = CompositeVideoClip([bg, txt_clip]).set_audio(audio)

# GPU acceleration ke sath ultrafast export
final_video.write_videofile("final_viral_video.mp4", fps=30, codec="libx264", audio_codec="aac", preset="ultrafast", threads=4)

print("\n🎉 [SUCCESS] GPU Video rendering completed!")
