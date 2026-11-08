"""
transformative_clipper.py
Phase 3: Cognitive Dual-Mode Free Fire Video Transformer.
Mode 1: REACTION_MODE (Breakdown / Mythbusters / Other's gameplay)
        -> Masks original HUD & name cleanly. NO fake branding. Clean analytical look.
Mode 2: OWNERSHIP_MODE (DEVIL's own gameplay / AI generated action)
        -> Overlays DEVIL-999 Free Fire Kill Badge.
        -> Injects Bouncing Red Damage Numbers (550 / 1100 HEADSHOT) with Free Fire float physics.
"""

import os
import json
import random
import subprocess

SCRIPT_DATA_PATH = "current_script.json"
AUDIO_TRACK_PATH = "final_audio.wav"
OUTPUT_VIDEO_PATH = "final_output.mp4"
DEFAULT_GAMEPLAY_DIR = "gameplay_vault"

def run_cmd(cmd: str):
    print(f"[*] Executing: {cmd}")
    res = subprocess.call(cmd, shell=True)
    if res != 0:
        print(f"[!] Warning: Command returned code {res}")
    return res

def determine_video_mode(script_data: dict) -> str:
    topic = script_data.get("title", "").lower() + " " + script_data.get("title_urdu", "").lower()
    reaction_keywords = ["hacker", "exposed", "kya ye", "spectate", "myth", "inspect", "config"]

    for kw in reaction_keywords:
        if kw in topic:
            print("[+] Cognitive Brain: Detected Breakdown/Reaction Topic -> ACTIVATING REACTION_MODE (Clean HUD Mask, No Tag).")
            return "REACTION_MODE"

    print("[+] Cognitive Brain: Detected Showcase/Own Montage Topic -> ACTIVATING OWNERSHIP_MODE (DEVIL-999 Tag + Red Numbers).")
    return "OWNERSHIP_MODE"

def ensure_gameplay_clip() -> str:
    os.makedirs(DEFAULT_GAMEPLAY_DIR, exist_ok=True)
    clips = [
        os.path.join(DEFAULT_GAMEPLAY_DIR, f)
        for f in os.listdir(DEFAULT_GAMEPLAY_DIR)
        if f.endswith((".mp4", ".mkv", ".mov"))
    ]
    if clips:
        chosen = random.choice(clips)
        print(f"[+] Using vault gameplay clip: {chosen}")
        return chosen

    procedural_path = os.path.join(DEFAULT_GAMEPLAY_DIR, "base_action.mp4")
    if not os.path.exists(procedural_path):
        print("[*] Synthesizing 60FPS procedural action base...")
        cmd = (
            f'ffmpeg -y -f lavfi -i testsrc=duration=26:size=1080x1920:rate=60 '
            f'-vf "eq=contrast=1.2:saturation=1.4,noise=alls=15:allf=t+u" '
            f'-c:v libx264 -pix_fmt yuv420p "{procedural_path}" -loglevel error'
        )
        run_cmd(cmd)
    return procedural_path

def create_kill_badge_png(tag_name: str, output_png: str):
    cmd = (
        f'ffmpeg -y -f lavfi -i color=c=black@0.0:s=560x110:d=1 -vf "'
        f'drawbox=x=10:y=10:w=540:h=90:color=red@0.85:t=fill,'
        f'drawbox=x=10:y=10:w=540:h=90:color=gold@0.95:t=4,'
        f'drawtext=text=\'{tag_name} 💥 M1887 🎯 ENEMY\':fontcolor=white:fontsize=30:x=(w-text_w)/2:y=(h-text_h)/2'
        f'" -frames:v 1 "{output_png}" -loglevel error'
    )
    run_cmd(cmd)

def create_floating_red_damage_png(output_png: str):
    cmd = (
        f'ffmpeg -y -f lavfi -i color=c=black@0.0:s=420x180:d=1 -vf "'
        f'drawtext=text=\'550\':fontcolor=red:fontsize=84:borderw=5:bordercolor=yellow:x=(w-text_w)/2:y=20,'
        f'drawtext=text=\'HEADSHOT!\':fontcolor=yellow:fontsize=28:borderw=3:bordercolor=black:x=(w-text_w)/2:y=120'
        f'" -frames:v 1 "{output_png}" -loglevel error'
    )
    run_cmd(cmd)

def build_transformative_video():
    print("\n==========================================")
    print("[*] PHASE 3: COGNITIVE GAMEPLAY TRANSFORMER")
    print("==========================================")

    script_data = {}
    if os.path.exists(SCRIPT_DATA_PATH):
        try:
            with open(SCRIPT_DATA_PATH, "r", encoding="utf-8") as f:
                script_data = json.load(f)
        except Exception:
            pass

    in_game_tag = script_data.get("in_game_tag", "DEVIL-999")
    urdu_title = script_data.get("title_urdu", "DEVIL HEADSHOT GOD")
    mode = determine_video_mode(script_data)

    raw_gameplay = ensure_gameplay_clip()
    audio_track = AUDIO_TRACK_PATH if os.path.exists(AUDIO_TRACK_PATH) else "voiceover.mp3"

    base_filter = (
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        f"setpts=PTS/1.05,"
        f"eq=contrast=1.18:saturation=1.35:brightness=-0.02"
    )

    if mode == "REACTION_MODE":
        print("[*] Compiling REACTION_MODE: Clean Masking of original HUD...")
        filter_complex = (
            f"{base_filter}[bg];"
            f"[bg]drawbox=x=180:y=140:w=720:h=90:color=black@0.4:t=fill[masked];"
            f"[masked]drawtext=text='ANALYSIS: PURE SKILL OR CONFIG?':fontcolor=white:fontsize=34:borderw=3:bordercolor=red:x=(w-text_w)/2:y=165[v_tag];"
            f"[v_tag]drawtext=text='{urdu_title}':fontcolor=yellow:fontsize=44:borderw=3:bordercolor=black:x=(w-text_w)/2:y=80[v_out]"
        )
        cmd = (
            f'ffmpeg -y -stream_loop -1 -i "{raw_gameplay}" '
            f'-i "{audio_track}" '
            f'-filter_complex "{filter_complex}" '
            f'-map "[v_out]" -map 1:a '
            f'-c:v libx264 -preset veryfast -b:v 4500k -r 60 -pix_fmt yuv420p '
            f'-c:a aac -b:a 192k -shortest "{OUTPUT_VIDEO_PATH}" -loglevel error'
        )
    else:
        print("[*] Compiling OWNERSHIP_MODE: Injecting DEVIL-999 Badge & 550 Red Damage...")
        kill_badge_png = "kill_badge.png"
        damage_png = "damage_headshot.png"
        create_kill_badge_png(in_game_tag, kill_badge_png)
        create_floating_red_damage_png(damage_png)

        filter_complex = (
            f"{base_filter}[bg];"
            f"[bg][1:v]overlay=x=260:y=180:enable='between(t,3.5,8.5)'[v_badge];"
            f"[v_badge][2:v]overlay=x=(W-w)/2:y='(H-h)/2-100-25*(t-5.0)':enable='between(t,5.0,7.0)'[v_dmg];"
            f"[v_dmg]drawtext=text='{urdu_title}':fontcolor=yellow:fontsize=46:borderw=3:bordercolor=black:x=(w-text_w)/2:y=90[v_out]"
        )
        cmd = (
            f'ffmpeg -y -stream_loop -1 -i "{raw_gameplay}" '
            f'-i "{kill_badge_png}" '
            f'-i "{damage_png}" '
            f'-i "{audio_track}" '
            f'-filter_complex "{filter_complex}" '
            f'-map "[v_out]" -map 3:a '
            f'-c:v libx264 -preset veryfast -b:v 4500k -r 60 -pix_fmt yuv420p '
            f'-c:a aac -b:a 192k -shortest "{OUTPUT_VIDEO_PATH}" -loglevel error'
        )

    res = run_cmd(cmd)
    if res == 0 and os.path.exists(OUTPUT_VIDEO_PATH):
        vsize = os.path.getsize(OUTPUT_VIDEO_PATH) / (1024 * 1024)
        print(f"[+] PHASE 3 SUCCESS: Output File: {OUTPUT_VIDEO_PATH} ({vsize:.2f} MB)")
    else:
        raise RuntimeError("Phase 3 video render failed.")

if __name__ == "__main__":
    build_transformative_video()
