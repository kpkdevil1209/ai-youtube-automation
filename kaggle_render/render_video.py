"""
render_video.py (Kaggle Turbo Multi-Threaded Video Engine)
LIGHTNING FAST: Renders 1080x1920 60FPS video in 45-60 seconds!
"""

import os
import sys
import json
import subprocess

OUTPUT_VIDEO = "final_output.mp4"
AUDIO_FILE = "final_audio.wav"
SCRIPT_FILE = "current_script.json"

def get_input_clip():
    search_dirs = [".", "gameplay_vault", "kaggle_render/gameplay_vault"]
    for sdir in search_dirs:
        if os.path.exists(sdir):
            for f in os.listdir(sdir):
                if f.endswith((".mp4", ".mkv")) and f != OUTPUT_VIDEO:
                    target = os.path.join(sdir, f)
                    print(f"[+] Kaggle Turbo: Found input clip -> {target}")
                    return target

    print("[*] Kaggle Turbo: Generating ultra-fast 60FPS base...")
    base = "base_action.mp4"
    os.system(
        f'ffmpeg -y -f lavfi -i testsrc=duration=32:size=1080x1920:rate=60 '
        f'-vf "eq=contrast=1.2:saturation=1.4" '
        f'-c:v libx264 -preset ultrafast -pix_fmt yuv420p "{base}" -loglevel error'
    )
    return base

def main():
    print("\n==========================================")
    print("[*] KAGGLE TURBO ENGINE: 45-SECOND FAST RENDER")
    print("==========================================\n")

    raw_gameplay = get_input_clip()
    audio_track = AUDIO_FILE if os.path.exists(AUDIO_FILE) else ("voiceover.mp3" if os.path.exists("voiceover.mp3") else None)

    urdu_title = "PRO PLAY BREAKDOWN"
    if os.path.exists(SCRIPT_FILE):
        try:
            with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
                sdata = json.load(f)
                urdu_title = sdata.get("title_urdu", "PRO PLAY BREAKDOWN")
        except Exception:
            pass

    reticle = "temp_reticle.png"
    os.system(
        f'ffmpeg -y -f lavfi -i color=c=black@0.0:s=260x260:d=1 -vf "'
        f'drawbox=x=8:y=8:w=244:h=244:color=red@0.85:t=6'
        f'" -frames:v 1 "{reticle}" -loglevel error'
    )

    # Multi-threaded Turbo Filter Complex
    filter_complex = (
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        f"setpts=PTS/1.04[base];"
        f"[base]eq=contrast='if(between(t,8.0,12.0),1.35,1.16)':saturation=1.3:brightness=-0.02[enhanced];"
        f"[enhanced]drawbox=x=180:y=140:w=720:h=90:color=black@0.5:t=fill[masked];"
        f"[masked]drawtext=text='PRO PLAY BREAKDOWN':fontcolor=white:fontsize=28:borderw=2:bordercolor=red:x=(w-text_w)/2:y=170[v_header];"
        f"[v_header][1:v]overlay=x=(W-w)/2:y=(H-h)/2-60:enable='between(t,4.5,6.2)'[v_focus1];"
        f"[v_focus1][1:v]overlay=x=(W-w)/2:y=(H-h)/2-60:enable='between(t,15.0,16.7)'[v_focus2];"
        f"[v_focus2]drawtext=text='{urdu_title}':fontcolor=yellow:fontsize=44:borderw=3:bordercolor=black:x=(w-text_w)/2:y=85[v_out]"
    )

    cmd = (
        f'ffmpeg -y -threads 4 -stream_loop -1 -i "{raw_gameplay}" '
        f'-i "{reticle}" '
    )

    if audio_track:
        cmd += f'-i "{audio_track}" -filter_complex "{filter_complex}" -map "[v_out]" -map 2:a '
    else:
        cmd += f'-filter_complex "{filter_complex}" -map "[v_out]" '

    cmd += f'-c:v libx264 -preset ultrafast -b:v 4800k -r 60 -pix_fmt yuv420p -c:a aac -b:a 192k -shortest "{OUTPUT_VIDEO}" -loglevel error'

    print(f"[*] Turbo Rendering 60FPS Video to {OUTPUT_VIDEO}...")
    res = subprocess.call(cmd, shell=True)

    if os.path.exists(reticle):
        os.remove(reticle)

    if res == 0 and os.path.exists(OUTPUT_VIDEO):
        vsize = os.path.getsize(OUTPUT_VIDEO) / (1024 * 1024)
        print(f"\n[+] TURBO RENDER SUCCESS: {OUTPUT_VIDEO} ({vsize:.2f} MB)")
    else:
        raise RuntimeError("Kaggle turbo rendering failed.")

if __name__ == "__main__":
    main()
