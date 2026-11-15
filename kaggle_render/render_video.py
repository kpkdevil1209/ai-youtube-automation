import os
import re
import json
import subprocess

OUTPUT_VIDEO = "final_output.mp4"
AUDIO_FILE = "final_audio.wav"
SCRIPT_FILE = "current_script.json"


def candidate_dirs():
    dirs = ["/kaggle/input/devil-insanity-assets", ".", "gameplay_vault", "kaggle_render", "kaggle_render/gameplay_vault"]
    if os.path.isdir("/kaggle/input"):
        for sub in os.listdir("/kaggle/input"):
            p = os.path.join("/kaggle/input", sub)
            if os.path.isdir(p) and p not in dirs:
                dirs.append(p)
    return dirs


def find_file(exact_names=None, exts=None):
    for d in candidate_dirs():
        if not os.path.isdir(d):
            continue
        if exact_names:
            for name in exact_names:
                p = os.path.join(d, name)
                if os.path.isfile(p) and os.path.getsize(p) > 0:
                    return p
        if exts:
            for f in sorted(os.listdir(d)):
                if f.endswith(exts) and f != OUTPUT_VIDEO and not f.startswith("base_"):
                    p = os.path.join(d, f)
                    if os.path.getsize(p) > 10000:
                        return p
    return None


def probe_duration(path, default=32.0):
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
            text=True,
            timeout=15,
        ).strip()
        dur = float(out)
        if 4.0 <= dur <= 3600.0:
            return dur
    except Exception:
        pass
    return default


def main():
    print("\n==========================================")
    print("[*] KAGGLE TURBO ENGINE: 45-SECOND FAST RENDER")
    print("==========================================\n")

    raw_gameplay = find_file(exact_names=["raw_gameplay.mp4"], exts=(".mp4", ".mkv"))
    if not raw_gameplay:
        raise RuntimeError("FATAL: Real gameplay clip missing in Kaggle input/working dirs. Zero fallback enforced!")
    print(f"[+] Kaggle Turbo: Locked real clip -> {raw_gameplay}")

    audio_track = find_file(exact_names=[AUDIO_FILE, "voiceover.mp3"])
    if not audio_track:
        raise RuntimeError("FATAL: Audio track (final_audio.wav) missing in Kaggle input/working dirs.")
    print(f"[+] Kaggle Turbo: Locked audio -> {audio_track}")

    target_dur = probe_duration(audio_track, default=32.0)
    print(f"[+] Target Render Duration: {target_dur:.2f}s")

    urdu_title = "PRO PLAY BREAKDOWN"
    script_path = find_file(exact_names=[SCRIPT_FILE])
    if script_path:
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                sdata = json.load(f)
                raw_t = sdata.get("title_urdu") or sdata.get("title") or urdu_title
                cleaned_t = re.sub(r"[^\x20-\x7E]+", " ", str(raw_t)).strip()
                if cleaned_t:
                    urdu_title = cleaned_t[:46]
        except Exception:
            pass

    title_txt = "temp_title.txt"
    with open(title_txt, "w", encoding="utf-8") as tf:
        tf.write(urdu_title)

    reticle = "temp_reticle.png"
    subprocess.run(
        [
            "ffmpeg", "-y", "-nostdin", "-f", "lavfi", "-i", "color=c=black@0.0:s=260x260:d=1",
            "-vf", "drawbox=x=8:y=8:w=244:h=244:color=red@0.85:t=6",
            "-frames:v", "1", reticle, "-loglevel", "error",
        ],
        check=True,
    )

    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        "setpts=PTS/1.04[base];"
        "[base]eq=contrast='if(between(t,8.0,12.0),1.35,1.16)':saturation=1.3:brightness=-0.02[enhanced];"
        "[enhanced]drawbox=x=180:y=140:w=720:h=90:color=black@0.5:t=fill[masked];"
        "[masked]drawtext=text='PRO PLAY BREAKDOWN':fontcolor=white:fontsize=28:borderw=2:bordercolor=red:x=(w-text_w)/2:y=170[v_header];"
        "[v_header][1:v]overlay=x=(W-w)/2:y=(H-h)/2-60:enable='between(t,4.5,6.2)'[v_focus1];"
        "[v_focus1][1:v]overlay=x=(W-w)/2:y=(H-h)/2-60:enable='between(t,15.0,16.7)'[v_focus2];"
        f"[v_focus2]drawtext=textfile='{title_txt}':fontcolor=yellow:fontsize=38:borderw=3:bordercolor=black:x=(w-text_w)/2:y=85[v_out]"
    )

    cmd = [
        "ffmpeg", "-y", "-nostdin", "-threads", "4",
        "-fflags", "+genpts", "-stream_loop", "-1", "-i", raw_gameplay,
        "-loop", "1", "-i", reticle,
        "-i", audio_track,
        "-filter_complex", filter_complex,
        "-map", "[v_out]", "-map", "2:a",
        "-t", f"{target_dur:.2f}",
        "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "4800k",
        "-r", "60", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        "-loglevel", "error", OUTPUT_VIDEO,
    ]

    print(f"[*] Turbo Rendering 60FPS Video ({target_dur:.2f}s) to {OUTPUT_VIDEO}...")
    proc = subprocess.run(cmd, capture_output=True, text=True)

    for tmp in (reticle, title_txt):
        if os.path.exists(tmp):
            os.remove(tmp)

    if proc.returncode == 0 and os.path.exists(OUTPUT_VIDEO) and os.path.getsize(OUTPUT_VIDEO) > 100000:
        vsize = os.path.getsize(OUTPUT_VIDEO) / (1024 * 1024)
        print(f"\n[+] TURBO RENDER SUCCESS: {OUTPUT_VIDEO} ({vsize:.2f} MB)")
    else:
        print("FFMPEG STDERR:", proc.stderr[-500:] if proc.stderr else "none")
        raise RuntimeError("Kaggle turbo rendering failed.")


if __name__ == "__main__":
    main()
