import os, re, glob, json, subprocess
from PIL import Image, ImageDraw, ImageFont


def find_file(name):
    if os.path.exists(name): return name
    hits = glob.glob(f"/kaggle/input/**/{name}", recursive=True)
    return hits[0] if hits else None


def probe_dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True)
    try: return max(1.0, float(r.stdout.strip()))
    except Exception: return 18.0


def build_ass(srt_path, ass_path):
    power = {"1", "HP", "WAIT", "STOP", "HEADSHOT", "CLUTCH", "IMPOSSIBLE", "LOCK", "WIPE", "TRAP", "KILL", "INSANE", "DEAD", "SHOT"}
    hdr = "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Pop,DejaVu Sans,82,&H00FFFFFF,&H0000D7FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,6,3,2,40,40,340,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    events = []
    if srt_path and os.path.exists(srt_path):
        blocks = open(srt_path, "r", encoding="utf-8").read().strip().split("\n\n")
        for b in blocks:
            lines = b.splitlines()
            if len(lines) < 3 or "-->" not in lines[1]: continue
            st, et = [x.strip().replace(",", ".")[:-1] for x in lines[1].split("-->")]
            words = " ".join(lines[2:]).upper().split()
            styled = []
            for w in words:
                clean = re.sub(r"[^A-Z0-9]", "", w)
                styled.append(f"{{\\c&H00D7FF&}}{w}{{\\c&HFFFFFF&}}" if clean in power else w)
            anim = "{\\fscx80\\fscy80\\t(0,85,\\fscx114\\fscy114)\\t(85,175,\\fscx100\\fscy100)}"
            events.append(f"Dialogue: 0,{st},{et},Pop,,0,0,0,,{anim}{' '.join(styled)}")
    open(ass_path, "w", encoding="utf-8").write(hdr + "\n".join(events))


def make_overlays(badge_text, color_hex):
    r, g, b = int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16)
    hud = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    d = ImageDraw.Draw(hud)
    d.rounded_rectangle([140, 105, 940, 185], radius=24, fill=(12, 14, 20, 205), outline=(r, g, b, 240), width=4)
    try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
    except Exception: font = ImageFont.load_default()
    d.text((540, 145), badge_text[:30], fill=(255, 255, 255, 255), font=font, anchor="mm")
    hud.save("hud_overlay.png")

    ring = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    cx, cy = 540, 860
    rd.ellipse([cx - 145, cy - 145, cx + 145, cy + 145], outline=(255, 45, 45, 235), width=10)
    rd.ellipse([cx - 118, cy - 118, cx + 118, cy + 118], outline=(255, 220, 60, 180), width=3)
    rd.line([(cx - 180, cy), (cx - 125, cy)], fill=(255, 45, 45, 235), width=6)
    rd.line([(cx + 125, cy), (cx + 180, cy)], fill=(255, 45, 45, 235), width=6)
    ring.save("red_ring.png")


def make_portrait_piece(src, ss, dur, pts_mul, extra_vf, out_mp4):
    vf = (f"split=2[bg][fg];[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=22:8,eq=brightness=-0.10[bgb];"
          f"[fg]scale=1080:-2:force_original_aspect_ratio=decrease[fgp];"
          f"[bgb][fgp]overlay=(W-w)/2:(H-h)/2,setpts={pts_mul}*(PTS-STARTPTS){extra_vf},fps=60,setsar=1,format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ss:.2f}", "-t", f"{dur:.2f}", "-i", src, "-an", "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "19", out_mp4], check=True)


def render():
    v_in = find_file("raw_gameplay.mp4")
    a_in = find_file("final_audio.wav")
    j_in = find_file("current_script.json")
    s_in = find_file("subtitles.srt") or find_file("subtitles_en.srt")
    if not v_in or not a_in: raise RuntimeError("Missing raw_gameplay.mp4 or final_audio.wav")

    meta = json.load(open(j_in, "r", encoding="utf-8")) if j_in else {}
    aud_dur = probe_dur(a_in)
    vid_dur = probe_dur(v_in)
    k = max(3.5, min(vid_dur - 1.2, float((meta.get("timeline") or {}).get("kill_at") or vid_dur * 0.72)))
    beats = meta.get("beat_times") or [0.0, aud_dur * 0.18, aud_dur * 0.42, aud_dur * 0.66, aud_dur * 0.85]
    slow_start = float(beats[3]) if len(beats) > 3 else aud_dur * 0.65

    theme_map = {
        "CRIMSON": ("#FF2E43", "eq=contrast=1.12:saturation=1.24"),
        "CYBER": ("#00E5FF", "eq=contrast=1.10:saturation=1.28:gamma_b=1.08"),
        "GOLDEN": ("#FFB800", "eq=contrast=1.10:saturation=1.22:gamma_r=1.06"),
        "ICE": ("#4DD0E1", "eq=contrast=1.12:saturation=1.15:gamma_b=1.10"),
    }
    hex_c, grade_vf = theme_map.get(meta.get("theme", "CRIMSON"), theme_map["CRIMSON"])
    make_overlays(meta.get("hook_badge", "0.25X CLIMAX ANALYSIS"), hex_c)
    build_ass(s_in, "captions.ass")

    p1_dur = max(1.4, float(beats[1]) if len(beats) > 1 else 2.2)
    make_portrait_piece(v_in, max(0.0, k - 0.6), 0.75, round(p1_dur / 0.75, 2), ",rgbashift=rh=9:bv=-9:enable='gte(t,0.9)'", "p1.mp4")

    setup_len = max(2.0, slow_start - p1_dur)
    src_setup_ss = max(0.0, k - 0.8 - setup_len)
    src_setup_take = max(1.5, (k - 0.8) - src_setup_ss)
    make_portrait_piece(v_in, src_setup_ss, src_setup_take, round(setup_len / src_setup_take, 2), "", "p2.mp4")

    rem = max(3.5, aud_dur - p1_dur - setup_len)
    src_hit_take = min(vid_dur - max(0.0, k - 0.8), 1.6)
    shake_vf = ",scale=1200:2133,crop=1080:1920:'(iw-ow)/2+if(between(t,0.4,1.6),28*sin(2*PI*t*18),0)':'(ih-oh)/2+if(between(t,0.4,1.6),28*cos(2*PI*t*16),0)',rgbashift=rh=10:bv=-10:enable='between(t,0.3,0.9)'"
    make_portrait_piece(v_in, max(0.0, k - 0.8), src_hit_take, round((rem + 1.0) / max(0.8, src_hit_take), 2), shake_vf, "p3.mp4")

    open("vlist.txt", "w").write("file 'p1.mp4'\nfile 'p2.mp4'\nfile 'p3.mp4'\n")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "vlist.txt", "-c", "copy", "base_timeline.mp4"], check=True)

    fc = (
        f"[0:v]{grade_vf}[vg];"
        f"[vg][2:v]overlay=0:0[vhud];"
        f"[vhud][3:v]overlay=0:0:enable='between(t,{slow_start:.2f},{min(aud_dur, slow_start+3.2):.2f})'[vring];"
        f"[vring]ass=captions.ass[vcap];"
        f"color=c={hex_c}:s=1080x12:d={aud_dur:.2f}[bar];"
        f"[vcap][bar]overlay=x='-w+(t/{aud_dur:.2f})*w':y=1904:shortest=1[vout]"
    )
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-i", "base_timeline.mp4", "-i", a_in, "-i", "hud_overlay.png", "-i", "red_ring.png",
        "-filter_complex", fc, "-map", "[vout]", "-map", "1:a",
        "-t", f"{aud_dur:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "final_output.mp4"
    ], check=True)
    print(f"[+] $1,000 Editor Render Complete: final_output.mp4 ({probe_dur('final_output.mp4'):.2f}s)")


if __name__ == "__main__":
    render()
