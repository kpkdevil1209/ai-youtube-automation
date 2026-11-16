# kaggle_render/render_video.py - Pro 9:16 Viral Shorts Editor (Burned Subs + Hook + Color Grade + Audio Mix)
import os, re, json, shutil, subprocess

OUTPUT_VIDEO = "final_output.mp4"

def find_asset(name):
    if os.path.exists(name):
        return name
    if os.path.exists("/kaggle/input"):
        for root, _, files in os.walk("/kaggle/input"):
            if name in files:
                return os.path.join(root, name)
    return None

def probe_json(path):
    cmd = ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path]
    return json.loads(subprocess.check_output(cmd, text=True))

def find_bold_font():
    for root in ("/usr/share/fonts", "/kaggle/input"):
        if os.path.exists(root):
            for r, _, files in os.walk(root):
                for f in files:
                    if "bold" in f.lower() and f.endswith(".ttf"):
                        return os.path.join(r, f)
    return None

def has_subtitles_filter():
    try:
        out = subprocess.check_output(["ffmpeg", "-hide_banner", "-filters"], stderr=subprocess.STDOUT, text=True)
        return " subtitles " in out
    except Exception:
        return False

def wrap_title(txt, width=24):
    words, lines, cur = str(txt or "DEVIL-999 PRO CLUTCH").upper().split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = f"{cur} {w}".strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
        if len(lines) == 2:
            break
    if cur and len(lines) < 2:
        lines.append(cur)
    return "\n".join(lines)[:54]

def main():
    print("\n==========================================")
    print("[*] KAGGLE PRO SHORTS EDITOR (60FPS)")
    print("==========================================\n")

    raw_clip = find_asset("raw_gameplay.mp4")
    audio_file = find_asset("final_audio.wav")
    srt_src = find_asset("subtitles.srt")
    script_src = find_asset("current_script.json")

    if not raw_clip or not os.path.exists(raw_clip):
        raise RuntimeError("FATAL: raw_gameplay.mp4 missing!")
    if not audio_file or not os.path.exists(audio_file):
        raise RuntimeError("FATAL: final_audio.wav missing!")

    vinfo = probe_json(raw_clip)
    v_streams = [s for s in vinfo.get("streams", []) if s.get("codec_type") == "video"]
    a_streams = [s for s in vinfo.get("streams", []) if s.get("codec_type") == "audio"]
    vw = int(v_streams[0].get("width", 1280)) if v_streams else 1280
    vh = int(v_streams[0].get("height", 720)) if v_streams else 720
    vdur = float(vinfo.get("format", {}).get("duration", 30.0))

    ainfo = probe_json(audio_file)
    target_dur = max(10.0, float(ainfo.get("format", {}).get("duration", 28.0)))

    hook_title = "DEVIL-999 INSANE CLUTCH"
    if script_src:
        try:
            sc = json.load(open(script_src, "r", encoding="utf-8"))
            hook_title = sc.get("title") or sc.get("topic") or hook_title
        except Exception:
            pass
    hook_title = re.sub(r"[^\w\s\-!?.,']", "", hook_title).strip()
    open("temp_title.txt", "w", encoding="utf-8").write(wrap_title(hook_title))

    use_subs = False
    if srt_src and os.path.getsize(srt_src) > 10 and has_subtitles_filter():
        shutil.copy2(srt_src, "subs.srt")
        use_subs = True

    font_path = find_bold_font()
    font_opt = f":fontfile={font_path}" if font_path else ""

    if vh > vw:
        fg_chain = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    else:
        fg_chain = "scale=1080:-2"

    v_filter = (
        "[0:v]setpts=PTS-STARTPTS,split=2[vbg][vfg];"
        "[vbg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,eq=brightness=-0.14:saturation=1.25,gblur=sigma=26[bg];"
        f"[vfg]{fg_chain},eq=contrast=1.18:saturation=1.35:brightness=0.02,unsharp=5:5:0.7:5:5:0.0[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,"
        f"drawtext=text='DEVIL-999'{font_opt}:fontsize=36:fontcolor=yellow:box=1:boxcolor=red@0.85:boxborderw=10:x=(w-text_w)/2:y=95,"
        f"drawtext=textfile=temp_title.txt{font_opt}:fontsize=44:fontcolor=white:borderw=4:bordercolor=black:box=1:boxcolor=black@0.55:boxborderw=12:line_spacing=8:x=(w-text_w)/2:y=165"
    )

    if use_subs:
        v_filter += ",subtitles=subs.srt:force_style='FontName=DejaVu Sans,FontSize=20,PrimaryColour=&H0000FFFF&,OutlineColour=&H00000000&,BorderStyle=1,Outline=2.5,Shadow=1,Alignment=2,MarginV=80'"

    v_filter += "[vout]"

    if a_streams:
        a_filter = ";[1:a]aresample=44100,volume=1.0[vo];[0:a]aresample=44100,volume=0.18[sfx];[vo][sfx]amix=inputs=2:duration=first,volume=1.45[aout]"
        a_map = "[aout]"
    else:
        a_filter = ""
        a_map = "1:a"

    cmd = ["ffmpeg", "-y", "-nostdin"]
    if vdur < target_dur:
        cmd += ["-stream_loop", "-1"]
    cmd += [
        "-fflags", "+genpts", "-i", raw_clip, "-i", audio_file,
        "-filter_complex", v_filter + a_filter,
        "-map", "[vout]", "-map", a_map,
        "-t", f"{target_dur:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "60", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", OUTPUT_VIDEO
    ]

    print(f"[*] Rendering {vw}x{vh} -> 1080x1920 60FPS ({target_dur:.1f}s) | Subs={use_subs}")
    subprocess.run(cmd, check=True)
    if not os.path.exists(OUTPUT_VIDEO) or os.path.getsize(OUTPUT_VIDEO) < 50000:
        raise RuntimeError("Output video invalid!")
    print(f"[+] RENDER COMPLETE: {OUTPUT_VIDEO} ({os.path.getsize(OUTPUT_VIDEO)/1048576:.2f} MB)")

if __name__ == "__main__":
    main()
