import json, os, re, subprocess, sys


def probe_streams(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,duration", "-show_entries", "format=duration", "-of", "json", path],
        text=True,
    )
    data = json.loads(out)
    v, a = {}, {}
    for s in data.get("streams") or []:
        if s.get("codec_type") == "video" and not v:
            v = s
        elif s.get("codec_type") == "audio" and not a:
            a = s
    dur = float((data.get("format") or {}).get("duration", 0.0))
    adur = float(a.get("duration") or dur)
    return int(v.get("width", 0)), int(v.get("height", 0)), dur, adur


def check_audio(path):
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "volumedetect", "-vn", "-sn", "-dn", "-f", "null", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    mx = re.search(r"max_volume:\s*([-\d.inf]+)\s*dB", proc.stderr)
    mn = re.search(r"mean_volume:\s*([-\d.inf]+)\s*dB", proc.stderr)
    max_v = -99.0 if (not mx or "inf" in mx.group(1).lower()) else float(mx.group(1))
    mean_v = -99.0 if (not mn or "inf" in mn.group(1).lower()) else float(mn.group(1))
    return max_v, mean_v


def extract_gray(path, ts, w=160, h=160):
    return subprocess.check_output(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{ts:.2f}", "-i", path, "-vframes", "1", "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"])


def measure_metrics(path, dur, label="Quality"):
    w, h = 160, 160
    exp = w * h
    pts = [min(max(0.3, dur * p), max(0.3, dur - 0.5)) for p in (0.12, 0.30, 0.50, 0.70, 0.88)]
    edges, brights, frames = [], [], []
    for i, ts in enumerate(pts, 1):
        raw = extract_gray(path, ts, w, h)
        if len(raw) < exp:
            continue
        br = sum(raw[:exp]) / exp
        es = sum(abs(raw[y * w + x + 1] - raw[y * w + x - 1]) + abs(raw[y * w + x + w] - raw[y * w + x - w]) for y in range(1, h - 1) for x in range(1, w - 1)) / ((w - 2) * (h - 2))
        edges.append(es)
        brights.append(br)
        frames.append(raw[:exp])
        print(f"[{label} {i}/5 @ {ts:.1f}s] edge={es:.1f} | bright={br:.1f}", flush=True)
    if len(frames) < 2:
        raise RuntimeError("QA FAIL: Could not decode enough frames")
    diffs = [sum(abs(a - b) for a, b in zip(frames[k], frames[k + 1])) / exp for k in range(len(frames) - 1)]
    ae, ab, am = sum(edges) / len(edges), sum(brights) / len(brights), sum(diffs) / len(diffs)
    print(f"[QA Motion] diff={am:.2f} | edge={ae:.1f} | avg_bright={ab:.1f} | min_bright={min(brights):.1f}", flush=True)
    return ae, ab, min(brights), am


def lift_dark_video(path):
    tmp = path + ".lifted.mp4"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", path, "-vf", "eq=gamma=1.35:brightness=0.03:contrast=1.04", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", tmp], check=True)
    if os.path.exists(tmp) and os.path.getsize(tmp) > 500000:
        os.replace(tmp, path)


def audit_script():
    if not os.path.exists("current_script.json"):
        return
    d = json.load(open("current_script.json", encoding="utf-8"))
    blob = (d.get("title", "") + " " + " ".join(b.get("narration", "") for b in d.get("beats", []))).lower()
    for bad in ("and that is why", "icy cola"):
        if bad in blob:
            raise RuntimeError(f"QA FAIL: Bad script phrase detected ({bad})")
    if "file #" in d.get("title", "").lower():
        raise RuntimeError("QA FAIL: FILE # label leaked into title")


def run_qa(target="final_output.mp4"):
    if not os.path.exists(target):
        raise RuntimeError(f"QA FAIL: Missing {target}")
    audit_script()
    mb = os.path.getsize(target) / (1024 * 1024)
    w, h, dur, adur = probe_streams(target)
    print(f"[QA Video] {w}x{h} | {dur:.1f}s (audio={adur:.1f}s) | {mb:.2f} MB", flush=True)
    if w != 1080 or h != 1920 or mb < 0.8 or dur < 11.0 or dur > 60.0:
        raise RuntimeError(f"QA FAIL: Invalid format {w}x{h}, {dur:.1f}s, {mb:.2f} MB")
    if abs(dur - adur) > 1.8:
        raise RuntimeError(f"QA FAIL: A/V desync detected (v={dur:.1f}s vs a={adur:.1f}s)")

    max_v, mean_v = check_audio(target)
    print(f"[QA Audio] max={max_v:.1f} dB | mean={mean_v:.1f} dB", flush=True)
    if max_v < -45.0 or mean_v < -55.0:
        raise RuntimeError(f"QA FAIL: Silent audio (max={max_v:.1f}, mean={mean_v:.1f})")

    ae, ab, mb_lum, am = measure_metrics(target, dur, "Quality")
    if ae < 5.5 or am < 1.5 or ab < 6.0 or (ab < 10.0 and ae < 7.0):
        raise RuntimeError(f"QA FAIL: Bad render (edge={ae:.1f}, diff={am:.2f}, bright={ab:.1f})")
    if ab < 18.0 or mb_lum < 4.5:
        print(f"[QA Rescue] Dark scene detected (avg={ab:.1f}, min={mb_lum:.1f}), lifting...", flush=True)
        lift_dark_video(target)
        ae, ab, mb_lum, am = measure_metrics(target, dur, "Rescued")
        if ab < 12.0 or mb_lum < 3.5:
            raise RuntimeError(f"QA FAIL: Still too dark after rescue (avg={ab:.1f}, min={mb_lum:.1f})")
    print("[+] QA GUARD PASSED: Studio-Grade Ready!", flush=True)


if __name__ == "__main__":
    run_qa(sys.argv[1] if len(sys.argv) > 1 else "final_output.mp4")
