# kaggle_render/render_video.py - Agent 4B: Viral Shorts Visual Director
import os, re, json, hashlib, subprocess

OUTPUT_VIDEO = "final_output.mp4"
POWER_WORDS = {"HEADSHOT", "DEVIL", "1HP", "HACKER", "CLUTCH", "AWM", "M1887", "PRO", "ONE", "TAP", "KILL", "SHOCK", "SECRET", "LEGIT", "BUSTED", "IMPOSSIBLE"}
THEMES = [
    {"name": "CRIMSON", "bar": "0xFF2E4C", "box": "red@0.88", "ass_hi": "&H0000FFFF&", "eq": "contrast=1.18:saturation=1.35:brightness=0.02"},
    {"name": "CYBER",   "bar": "0x00F5FF", "box": "purple@0.85", "ass_hi": "&H00FFFF00&", "eq": "contrast=1.20:saturation=1.42:brightness=0.01"},
    {"name": "GOLDEN",  "bar": "0xFFD700", "box": "darkorange@0.88", "ass_hi": "&H0033FF66&", "eq": "contrast=1.16:saturation=1.32:brightness=0.03"},
    {"name": "ICE",     "bar": "0x38BDF8", "box": "navy@0.88", "ass_hi": "&H0000FFFF&", "eq": "contrast=1.22:saturation=1.28:brightness=0.02"}
]

def find_asset(name):
    if os.path.exists(name): return name
    for r, _, fs in (os.walk("/kaggle/input") if os.path.exists("/kaggle/input") else []):
        if name in fs: return os.path.join(r, name)
    return None

def probe_json(path):
    return json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path], text=True))

def find_bold_font():
    for root in ("/usr/share/fonts", "/kaggle/input"):
        if os.path.exists(root):
            for r, _, fs in os.walk(root):
                for f in fs:
                    if "bold" in f.lower() and f.endswith(".ttf"):
                        return os.path.join(r, f)
    return None

def srt_to_ass_time(t):
    h, m, s_ms = t.strip().split(":")
    s, ms = s_ms.split(",")
    return f"{int(h)}:{m}:{s}.{ms[:2]}"

def build_pop_ass(srt_path, ass_path, hi_col):
    raw = open(srt_path, "r", encoding="utf-8").read().strip().split("\n\n")
    head = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Pop,DejaVu Sans,68,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,1,0,1,5,2,2,40,40,260,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = []
    for blk in raw:
        parts = blk.strip().splitlines()
        if len(parts) < 3 or "-->" not in parts[1]: continue
        st, en = [srt_to_ass_time(x) for x in parts[1].split("-->")]
        words = " ".join(parts[2:]).upper().split()
        styled = []
        for w in words:
            clean = re.sub(r"[^A-Z0-9]", "", w)
            styled.append(f"{{\\c{hi_col}}}{w}{{\\c&H00FFFFFF&}}" if clean in POWER_WORDS else w)
        anim = "{\\fscx75\\fscy75\\t(0,95,1.4,\\fscx116\\fscy116)\\t(95,190,1,\\fscx100\\fscy100)}"
        lines.append(f"Dialogue: 0,{st},{en},Pop,,0,0,0,,{anim}{' '.join(styled)}")
    open(ass_path, "w", encoding="utf-8").write(head + "\n".join(lines) + "\n")
    return len(lines) > 0

def wrap_title(txt, width=22):
    words, lines, cur = str(txt or "DEVIL-999 PRO CLUTCH").upper().split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width: cur = f"{cur} {w}".strip()
        else:
            if cur: lines.append(cur)
            cur = w
        if len(lines) == 2: break
    if cur and len(lines) < 2: lines.append(cur)
    return "\n".join(lines)[:50]

def main():
    print("\n==========================================")
    print("[*] AGENT 4B: KAGGLE VIRAL SHORTS DIRECTOR")
    print("==========================================\n")
    raw_clip, audio_file = find_asset("raw_gameplay.mp4"), find_asset("final_audio.wav")
    srt_src, script_src = find_asset("subtitles.srt"), find_asset("current_script.json")
    if not raw_clip or not audio_file:
        raise RuntimeError("FATAL: raw_gameplay.mp4 ya final_audio.wav missing!")

    vi = probe_json(raw_clip)
    vs = [s for s in vi.get("streams", []) if s.get("codec_type") == "video"]
    aus = [s for s in vi.get("streams", []) if s.get("codec_type") == "audio"]
    vw, vh = int(vs[0].get("width", 1280)), int(vs[0].get("height", 720))
    vdur = float(vi.get("format", {}).get("duration", 30.0))
    target_dur = max(10.0, float(probe_json(audio_file).get("format", {}).get("duration", 28.0)))

    sc = json.load(open(script_src, "r", encoding="utf-8")) if script_src else {}
    hook_title = re.sub(r"[^\w\s\-!?.,']", "", sc.get("title") or sc.get("topic") or "DEVIL-999 CLUTCH").strip()
    badge_txt = re.sub(r"[^A-Z0-9\s\-]", "", str(sc.get("viral_format") or "DEVIL-999").upper()).strip() or "DEVIL-999"
    theme = THEMES[int(hashlib.md5(hook_title.encode()).hexdigest(), 16) % len(THEMES)]

    open("temp_title.txt", "w", encoding="utf-8").write(wrap_title(hook_title))
    open("temp_badge.txt", "w", encoding="utf-8").write(f"DEVIL-999 | {badge_txt}"[:28])
    use_ass = bool(srt_src and os.path.getsize(srt_src) > 10 and build_pop_ass(srt_src, "captions.ass", theme["ass_hi"]))
    fp = find_bold_font()
    fopt = f":fontfile={fp}" if fp else ""

    fg_chain = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" if vh > vw else "scale=1080:-2"
    mid = target_dur * 0.50
    v_fc = (
        f"[0:v]setpts=PTS-STARTPTS,split=2[vbg][vfg];"
        f"[vbg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,eq=brightness=-0.16:saturation=1.25,gblur=sigma=28[bg];"
        f"[vfg]{fg_chain},eq={theme['eq']},eq=brightness=0.28:enable='between(t,0.03,0.11)+between(t,{mid:.2f},{mid+0.08:.2f})',unsharp=5:5:0.7:5:5:0.0[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,"
        f"drawtext=textfile=temp_badge.txt{fopt}:fontsize=34:fontcolor=yellow:box=1:boxcolor={theme['box']}:boxborderw=10:x=(w-text_w)/2:y=95,"
        f"drawtext=textfile=temp_title.txt{fopt}:fontsize=44:fontcolor=white:borderw=4:bordercolor=black:box=1:boxcolor=black@0.58:boxborderw=12:line_spacing=8:x=(w-text_w)/2:y=165[vtxt];"
        f"color=c={theme['bar']}:s=1080x10:d={target_dur:.2f}[bar];"
        f"[vtxt][bar]overlay=x='-w+(t/{target_dur:.2f})*w':y=1910:shortest=1"
    )
    if use_ass:
        v_fc += ",ass=captions.ass"
    v_fc += "[vout]"

    a_fc = ";[1:a]aresample=44100,volume=1.0[vo];[0:a]aresample=44100,volume=0.16[sfx];[vo][sfx]amix=inputs=2:duration=first,volume=1.45[aout]" if aus else ""
    a_map = "[aout]" if aus else "1:a"

    cmd = ["ffmpeg", "-y", "-nostdin"] + (["-stream_loop", "-1"] if vdur < target_dur else []) + [
        "-fflags", "+genpts", "-i", raw_clip, "-i", audio_file,
        "-filter_complex", v_fc + a_fc, "-map", "[vout]", "-map", a_map, "-t", f"{target_dur:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "60", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", OUTPUT_VIDEO
    ]
    print(f"[*] Theme: {theme['name']} | {vw}x{vh} -> 1080x1920 60FPS ({target_dur:.1f}s)")
    subprocess.run(cmd, check=True)
    print(f"[+] RENDER COMPLETE: {OUTPUT_VIDEO} ({os.path.getsize(OUTPUT_VIDEO)/1048576:.2f} MB)")

if __name__ == "__main__":
    main()
