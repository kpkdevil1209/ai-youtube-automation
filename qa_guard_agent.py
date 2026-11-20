import json
import os
import re
import subprocess
import sys


def probe_video_local(path):
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-show_entries", "format=duration",
        "-of", "json", path,
    ]
    out = subprocess.check_output(cmd, text=True)
    data = json.loads(out)
    streams = data.get("streams") or [{}]
    w = int(streams[0].get("width", 0))
    h = int(streams[0].get("height", 0))
    dur = float((data.get("format") or {}).get("duration", 0.0))
    return w, h, dur


def check_audio_local(path):
    cmd = [
        "ffmpeg", "-hide_banner", "-i", path,
        "-af", "volumedetect", "-vn", "-sn", "-dn", "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    m = re.search(r"max_volume:\s*([-\d.inf]+)\s*dB", proc.stderr)
    if not m or "inf" in m.group(1).lower():
        return -99.0
    return float(m.group(1))


def extract_gray_bytes(path, ts, w=160, h=160):
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{ts:.2f}", "-i", path, "-vframes", "1",
        "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
    ]
    return subprocess.check_output(cmd)


def quality_and_motion(path, dur):
    w, h = 160, 160
    expected = w * h
    points = [min(max(0.3, dur * p), max(0.3, dur - 0.5)) for p in (0.12, 0.30, 0.50, 0.70, 0.88)]
    edges, brights, frames = [], [], []

    for i, ts in enumerate(points, 1):
        raw = extract_gray_bytes(path, ts, w, h)
        if len(raw) < expected:
            continue
        bright = sum(raw[:expected]) / expected
        edge_sum = 0
        for y in range(1, h - 1):
            row = y * w
            for x in range(1, w - 1):
                idx = row + x
                edge_sum += abs(raw[idx + 1] - raw[idx - 1]) + abs(raw[idx + w] - raw[idx - w])
        edge_score = edge_sum / ((w - 2) * (h - 2))
        edges.append(edge_score)
        brights.append(bright)
        frames.append(raw[:expected])
        print(f"[Quality {i}/5 @ {ts:.1f}s] edge={edge_score:.1f} | bright={bright:.1f}", flush=True)

    if len(frames) < 2:
        raise RuntimeError("QA FAIL: Could not decode enough frames")

    diffs = [
        sum(abs(a - b) for a, b in zip(frames[k], frames[k + 1])) / expected
        for k in range(len(frames) - 1)
    ]
    avg_edge = sum(edges) / len(edges)
    avg_bright = sum(brights) / len(brights)
    avg_motion = sum(diffs) / len(diffs)
    print(f"[QA Motion] avg_diff={avg_motion:.2f} | avg_edge={avg_edge:.1f} | avg_bright={avg_bright:.1f}", flush=True)

    if avg_edge < 5.0:
        raise RuntimeError(f"QA FAIL: Blurry or blank render (edge={avg_edge:.1f})")
    if avg_bright < 18.0:
        raise RuntimeError(f"QA FAIL: Too dark or black video (bright={avg_bright:.1f})")
    if avg_motion < 1.5:
        raise RuntimeError(f"QA FAIL: Frozen or static video (motion={avg_motion:.2f})")


def run_qa(target="final_output.mp4"):
    if not os.path.exists(target):
        raise RuntimeError(f"QA FAIL: Missing {target}")
    size_mb = os.path.getsize(target) / (1024 * 1024)
    w, h, dur = probe_video_local(target)
    print(f"[QA Video] {w}x{h} | {dur:.1f}s | {size_mb:.2f} MB", flush=True)
    if w != 1080 or h != 1920:
        raise RuntimeError(f"QA FAIL: Invalid resolution {w}x{h}")
    if dur < 11.0 or dur > 60.0:
        raise RuntimeError(f"QA FAIL: Invalid Shorts duration {dur:.1f}s")
    if size_mb < 0.8:
        raise RuntimeError(f"QA FAIL: File too small ({size_mb:.2f} MB)")

    max_vol = check_audio_local(target)
    print(f"[QA Audio] max_volume={max_vol:.1f} dB", flush=True)
    if max_vol < -45.0:
        raise RuntimeError(f"QA FAIL: Silent or missing audio ({max_vol:.1f} dB)")

    quality_and_motion(target, dur)
    print("[+] QA GUARD PASSED: Ready for YouTube Upload!", flush=True)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "final_output.mp4"
    run_qa(target)
