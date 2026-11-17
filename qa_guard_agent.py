import os
import re
import sys
import subprocess
import requests
import verify_freefire_agent as vfa


def check_audio_loudness(path):
    cmd = ["ffmpeg", "-v", "info", "-i", path, "-af", "volumedetect", "-f", "null", "-"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
    m = re.search(r"max_volume:\s*([-\d.]+)\s*dB", p.stderr or "")
    if not m:
        return False, "no audio stream detected"
    vol = float(m.group(1))
    print(f"[QA Audio] max_volume={vol:.1f} dB")
    return (vol > -45.0), f"audio level {vol:.1f} dB"


def run_qa(path="final_output.mp4"):
    if not os.path.exists(path) or os.path.getsize(path) < 500000:
        raise RuntimeError(f"QA FAIL: Missing or tiny rendered file: {path}")

    info = vfa.probe_video(path)
    if not info:
        raise RuntimeError("QA FAIL: ffprobe could not read rendered video")
    w, h, dur = info["width"], info["height"], info["duration"]
    print(f"[QA Video] {w}x{h} | {dur:.1f}s | {os.path.getsize(path)/(1024*1024):.2f} MB")

    if w < 720 or h < 1280:
        raise RuntimeError(f"QA FAIL: Low portrait resolution {w}x{h}")
    if dur < 10.0 or dur > 70.0:
        raise RuntimeError(f"QA FAIL: Invalid Shorts duration {dur:.1f}s")

    a_ok, a_msg = check_audio_loudness(path)
    if not a_ok:
        raise RuntimeError(f"QA FAIL: Silent or broken audio ({a_msg})")

    q_ok, q_msg = vfa.quality_scan(path, dur)
    if not q_ok:
        raise RuntimeError(f"QA FAIL: Visual quality check failed ({q_msg})")

    passes = 0
    for idx, pct in enumerate([0.30, 0.65], 1):
        b64 = vfa.extract_frame_b64(path, max(1.0, dur * pct))
        if not b64:
            continue
        ff_ok, conf, _, scene = vfa.ask_vision_frame(b64)
        print(f"[QA Vision {idx}/2] ff={ff_ok} | conf={conf}% | '{scene}'")
        if ff_ok and conf >= 45:
            passes += 1

    try:
        requests.post("http://127.0.0.1:11434/api/generate", json={"model": "qwen2.5vl:3b", "prompt": "", "keep_alive": 0}, timeout=8)
    except Exception:
        pass

    if passes < 1:
        raise RuntimeError("QA FAIL: Rendered frames did not verify as Free Fire")

    print("[+] QA GUARD PASSED 100% — APPROVED FOR YOUTUBE UPLOAD!")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "final_output.mp4"
    run_qa(target)
