import os, re, sys, json, subprocess

VIDEO = sys.argv[1] if len(sys.argv) > 1 else "final_output.mp4"
LEAK_RE = re.compile(r"(under\s*\d+\s*chars?|characters?|file\s*#?\d*|icy\s*cola|and\s+that\s+is\s+why|#shorts?|title:)", re.I)

def ffprobe_info(path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "json", path]
    return json.loads(subprocess.check_output(cmd).decode())

def check_audio(path):
    out = subprocess.check_output(["ffmpeg", "-i", path, "-af", "volumedetect", "-f", "null", "-"], stderr=subprocess.STDOUT).decode("utf-8", "ignore")
    m = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", out)
    return float(m.group(1)) if m else -99.0

def check_brightness_and_motion(path, dur):
    samples = [max(0.2, min(dur - 0.2, dur * r)) for r in (0.12, 0.38, 0.64, 0.88)]
    vals = []
    for ts in samples:
        raw = subprocess.check_output(["ffmpeg", "-ss", f"{ts:.2f}", "-i", path, "-vframes", "1", "-vf", "scale=64:64,format=gray", "-f", "rawvideo", "-"], stderr=subprocess.DEVNULL)
        vals.append(sum(raw) / len(raw) if raw else 0.0)
    return min(vals), sum(vals) / len(vals)

def audit_script():
    if not os.path.exists("current_script.json"):
        raise RuntimeError("QA FAIL: current_script.json missing")
    d = json.load(open("current_script.json", encoding="utf-8"))
    for field in [d.get("title", ""), d.get("hook_banner", "")] + list(d.get("lines") or []):
        if LEAK_RE.search(str(field)):
            raise RuntimeError(f"QA FAIL: Prompt leak or banned text detected: {field}")

def main():
    if not os.path.exists(VIDEO):
        raise RuntimeError(f"QA FAIL: Missing video {VIDEO}")
    audit_script()
    info = ffprobe_info(VIDEO)
    dur = float(info["format"]["duration"])
    if dur < 13.5 or dur > 16.8:
        raise RuntimeError(f"QA FAIL: Duration {dur:.2f}s outside target 14-16s window")
    streams = {s["codec_type"] for s in info.get("streams", [])}
    if "video" not in streams or "audio" not in streams:
        raise RuntimeError(f"QA FAIL: Missing video/audio stream ({streams})")
    mean_db = check_audio(VIDEO)
    if mean_db < -40.0:
        raise RuntimeError(f"QA FAIL: Audio too quiet ({mean_db:.1f} dB)")
    min_b, avg_b = check_brightness_and_motion(VIDEO, dur)
    print(f"[QA] dur={dur:.2f}s | audio={mean_db:.1f} dB | bright_min={min_b:.1f} | bright_avg={avg_b:.1f}")
    if min_b < 5.0:
        raise RuntimeError(f"QA FAIL: Black frame detected (min_b={min_b:.1f})")
    if avg_b < 18.0:
        print("[QA] Moody dark visual detected — applying shadow lift rescue...")
        tmp = VIDEO + ".rescued.mp4"
        subprocess.run(["ffmpeg", "-y", "-i", VIDEO, "-vf", "eq=gamma=1.32:brightness=0.03", "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "copy", tmp], check=True)
        os.replace(tmp, VIDEO)
    print("[QA PASS] Ready for YouTube Upload!")

if __name__ == "__main__":
    main()
