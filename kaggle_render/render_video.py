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
    power = {"1", "HP", "WAIT", "STOP", "HEADSHOT", "CLUTCH", "IMPOSSIBLE", "LOCK", "WIPE", "TRAP", "KILL", "INSANE", "DEAD", "SHOT", "MISSED", "WHY", "HOW", "RULE", "FRAME"}
    hdr = "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Pop,DejaVu Sans,84,&H00FFFFFF,&H0000D7FF,&H00000000,&H90000000,-1,0,0,0,100,100,2,0,1,7,3,2,45,45,365,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    events = []
    if srt_path and os.path.exists(srt_path):
        for b in open(srt_path, "r", encoding="utf-8").read().strip().split("\n\n"):
            lines = b.splitlines()
            if len(lines) < 3 or "-->" not in lines[1]: continue
            st, et = [x.strip().replace(",", ".")[:-1] for x in lines[1].split("-->")]
            words = " ".join(lines[2:]).upper().split()
            styled = [f"{{\\c&H00D7FF&}}{w}{{\\c&HFFFFFF&}}" if re.sub(r"[^A-Z0-9]", "", w) in power else w for w in words]
            anim = "{\\fscx85\\fscy85\\t(0,75,\\fscx112\\fscy112)\\t(75,160,\\fscx100\\fscy100)}"
            events.append(f"Dialogue: 0,{st},{et},Pop,,0,0,0,,{anim}{' '.join(styled)}")
    open(ass_path, "w", encoding="utf-8").write(hdr + "\n".join(events))


def make_overlays(badge_text, color_hex):
    r, g, b = int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16)
    hud = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    d = ImageDraw.Draw(hud)
    d.rounded_rectangle([190, 118, 890, 184], radius=30, fill=(10, 12, 18, 195), outline=(r, g, b, 235), width=3)
    try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 31)
    except Exception: font = ImageFont.load_default()
    d.text((540, 151), badge_text[:28], fill=(255, 255, 255, 255), font=font, anchor="mm")
    hud.save("hud_overlay.png")

    ring = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    cx, cy = 540, 860
    rd.ellipse([cx - 135, cy - 135, cx + 135, cy + 135], outline=(255, 45, 45, 235), width=9)
    rd.ellipse([cx - 110, cy - 110, cx + 110, cy + 110], outline=(255, 220, 60, 180), width=3)
    rd.line([(cx - 170, cy), (cx - 115, cy)], fill=(255, 45, 45, 235), width=5)
    rd.line([(cx + 115, cy), (cx + 170, cy)], fill=(255, 45, 45, 235), width=5)
    ring.save("red_ring.png")


def make_piece(src, ss, dur, target_dur, extra_vf, out_mp4):
    dur = max(0.3, dur)
    mul = round(target_dur / dur, 4)
    vf = (f"split=2[bg][fg];[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=26:10,eq=brightness=-0.14[bgb];"
          f"[fg]scale=1080:-2:force_original_aspect_ratio=decrease:flags=lanczos,unsharp=5:5:0.75:5:5:0.2[fgp];"
          f"[bgb][fgp]overlay=(W-w)/2:(H-h)/2,setpts={mul}*(PTS-STARTPTS){extra_vf},fps=60,setsar=1,format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ss:.2f}", "-t", f"{dur:.2f}", "-i", src, "-an", "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "13", "-video_track_timescale", "60000", out_mp4], check=True)


def render():
    v_in, a_in = find_file("raw_gameplay.mp4"), find_file("final_audio.wav")
    j_in, s_in = find_file("current_script.json"), find_file("subtitles.srt") or find_file("subtitles_en.srt")
    if not v_in or not a_in: raise RuntimeError("Missing raw_gameplay.mp4 or final_audio.wav")

    meta = json.load(open(j_in, "r", encoding="utf-8")) if j_in else {}
    aud_dur, vid_dur = probe_dur(a_in), probe_dur(v_in)
    k = max(4.0, min(vid_dur - 2.8, float((meta.get("timeline") or {}).get("kill_at") or vid_dur * 0.65)))
    beats = meta.get("beat_times") or [0.0, aud_dur * 0.16, aud_dur * 0.40, aud_dur * 0.62, aud_dur * 0.82]

    theme_map = {
        "CRIMSON": ("#FF2E43", "eq=contrast=1.10:saturation=1.22,vignette=PI/6"),
        "CYBER": ("#00E5FF", "eq=contrast=1.08:saturation=1.25:gamma_b=1.06,vignette=PI/6"),
        "GOLDEN": ("#FFB800", "eq=contrast=1.08:saturation=1.20:gamma_r=1.05,vignette=PI/6"),
        "ICE": ("#4DD0E1", "eq=contrast=1.10:saturation=1.14:gamma_b=1.08,vignette=PI/6"),
    }
    hex_c, grade_vf = theme_map.get(meta.get("theme", "CRIMSON"), theme_map["CRIMSON"])
    make_overlays(meta.get("hook_badge", "WAIT FOR THE TWIST"), hex_c)
    build_ass(s_in, "captions.ass")

    d1 = max(1.4, float(beats[1]) if len(beats) > 1 else 2.0)
    b3 = float(beats[3]) if len(beats) > 3 else aud_dur * 0.62
    d2 = max(3.5, b3 - d1)
    d4 = max(2.6, min(4.2, aud_dur * 0.22))
    d3 = max(2.0, aud_dur - d1 - d2 - d4)

    make_piece(v_in, max(0.0, k - 0.45), 0.75, d1, f",rgbashift=rh=11:bv=-11:enable='gte(t,{max(0.2, d1-0.30):.2f})'", "p1.mp4")

    s2_ss = max(0.0, k - 7.5)
    s2_dur = max(2.0, (k - 0.5) - s2_ss)
    make_piece(v_in, s2_ss, s2_dur, d2, "", "p2.mp4")

    s3_ss = max(0.0, k - 0.5)
    s3_dur = min(1.0, max(0.4, vid_dur - s3_ss - 1.5))
    shake_zoom = f",scale=1240:2204,crop=1080:1920:'(iw-ow)/2+if(between(t,0.3,1.5),28*sin(2*PI*t*18),0)':'(ih-oh)/2+if(between(t,0.3,1.5),28*cos(2*PI*t*16),0)',eq=brightness='0.32*between(t,0.35,0.52)':eval=frame,rgbashift=rh=10:bv=-10:enable='between(t,0.30,0.85)'"
    make_piece(v_in, s3_ss, s3_dur, d3, shake_zoom, "p3.mp4")

    s4_ss = min(vid_dur - 0.6, s3_ss + s3_dur)
    s4_dur = max(0.5, vid_dur - s4_ss)
    make_piece(v_in, s4_ss, s4_dur, d4 + 0.6, "", "p4.mp4")

    open("vlist.txt", "w").write("file 'p1.mp4'\nfile 'p2.mp4'\nfile 'p3.mp4'\nfile 'p4.mp4'\n")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "vlist.txt", "-c", "copy", "base_timeline.mp4"], check=True)

    ring_s, ring_e = d1 + d2, d1 + d2 + d3
    fc = (
        f"[0:v]{grade_vf}[vg];"
        f"[vg][2:v]overlay=0:0[vhud];"
        f"[vhud][3:v]overlay=0:0:enable='between(t,{ring_s:.2f},{ring_e:.2f})'[vring];"
        f"[vring]ass=captions.ass[vcap];"
        f"color=c={hex_c}:s=1080x10:d={aud_dur:.2f}[bar];"
        f"[vcap][bar]overlay=x='-w+(t/{aud_dur:.2f})*w':y=1906:shortest=1[vout]"
    )
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", "base_timeline.mp4", "-i", a_in, "-i", "hud_overlay.png", "-i", "red_ring.png",
        "-filter_complex", fc, "-map", "[vout]", "-map", "1:a", "-t", f"{aud_dur:.2f}",
        "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "final_output.mp4"
    ], check=True)
    print(f"[+] Pro 4-Piece Headshot+3s Render Complete: {probe_dur('final_output.mp4'):.2f}s")


if __name__ == "__main__":
    render()
