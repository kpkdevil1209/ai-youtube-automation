import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import requests
from PIL import Image, ImageChops, ImageFilter, ImageStat

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
if not OLLAMA_URL.endswith("/api/chat"):
    OLLAMA_URL = OLLAMA_URL.rstrip("/") + "/api/chat"
VISION_MODEL = os.environ.get("VISION_MODEL", "qwen2.5vl:3b")

QA_SCHEMA = {
    "type": "object",
    "properties": {
        "is_gameplay": {"type": "boolean"},
        "is_corrupted_or_black": {"type": "boolean"},
        "confidence": {"type": "integer"},
        "scene_note": {"type": "string"},
    },
    "required": ["is_gameplay", "is_corrupted_or_black", "confidence", "scene_note"],
}


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


def extract_frame(path, ts, out_jpg, size=384):
    vf = f"scale={size}:{size}:force_original_aspect_ratio=decrease"
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{ts:.2f}", "-i", path, "-vframes", "1",
        "-vf", vf, "-q:v", "4", out_jpg,
    ]
    subprocess.run(cmd, check=True)


def quality_and_motion(path, dur):
    points = [max(0.5, dur * p) for p in (0.12, 0.30, 0.50, 0.70, 0.88)]
    sharps, brights, imgs = [], [], []
    with tempfile.TemporaryDirectory() as tmp:
        for i, ts in enumerate(points, 1):
            jpg = os.path.join(tmp, f"q_{i}.jpg")
            extract_frame(path, ts, jpg, size=480)
            im = Image.open(jpg).convert("L")
            edges = im.filter(ImageFilter.FIND_EDGES)
            sharp = float(ImageStat.Stat(edges).var[0])
            bright = float(ImageStat.Stat(im).mean[0])
            sharps.append(sharp)
            brights.append(bright)
            imgs.append(im.resize((128, 128)))
            print(f"[Quality {i}/5 @ {ts:.1f}s] sharp={sharp:.1f} | bright={bright:.1f}", flush=True)
        diffs = [
            float(ImageStat.Stat(ImageChops.difference(imgs[k], imgs[k + 1])).mean[0])
            for k in range(len(imgs) - 1)
        ]
    avg_sharp = sum(sharps) / len(sharps)
    avg_bright = sum(brights) / len(brights)
    avg_motion = sum(diffs) / len(diffs)
    print(f"[QA Motion] avg_diff={avg_motion:.2f} | avg_sharp={avg_sharp:.1f} | avg_bright={avg_bright:.1f}", flush=True)
    if avg_sharp < 40.0:
        raise RuntimeError(f"QA FAIL: Blurry render (sharp={avg_sharp:.1f})")
    if avg_bright < 18.0:
        raise RuntimeError(f"QA FAIL: Too dark or black video (bright={avg_bright:.1f})")
    if avg_motion < 1.5:
        raise RuntimeError(f"QA FAIL: Frozen or static video (motion={avg_motion:.2f})")


def ask_rendered_qa_frame(path, ts):
    with tempfile.TemporaryDirectory() as tmp:
        jpg = os.path.join(tmp, "v.jpg")
        extract_frame(path, ts, jpg, size=384)
        with open(jpg, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
    prompt = (
        "Analyze this rendered vertical 9:16 mobile gaming Short frame. "
        "Burned-in English captions, top HUD badges, red zoom circles, and dark vignette edges are NORMAL and EXPECTED. "
        "Set is_gameplay=true if it shows shooter or battle-royale gameplay like Free Fire. "
        "Set is_corrupted_or_black=true ONLY if it is a blank black screen, glitch bars, or non-gaming live camera. "
        "Return strict JSON."
    )
    payload = {
        "model": VISION_MODEL,
        "messages": [{"role": "user", "content": prompt, "images": [b64]}],
        "stream": False,
        "format": QA_SCHEMA,
        "keep_alive": "2m",
        "options": {"num_ctx": 2048, "num_predict": 90, "temperature": 0.0},
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=120)
        r.raise_for_status()
        raw = r.json().get("message", {}).get("content", "{}")
        data = json.loads(raw)
        ok = bool(data.get("is_gameplay")) and not bool(data.get("is_corrupted_or_black"))
        conf = int(data.get("confidence", 0))
        note = str(data.get("scene_note", ""))[:80]
        return ok, conf, note
    except Exception as e:
        return False, 0, f"err: {e}"


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

    check_ratios = (0.25, 0.55, 0.40)
    passed = False
    for idx, ratio in enumerate(check_ratios, 1):
        ts = max(0.5, dur * ratio)
        ok, conf, note = ask_rendered_qa_frame(target, ts)
        print(f"[QA Vision {idx}/3 @ {ts:.1f}s] ok={ok} | conf={conf}% | '{note}'", flush=True)
        if ok and conf >= 45:
            passed = True
            if idx == 1 and conf >= 55:
                print("[QA Vision PASS] Fast-passed on frame 1", flush=True)
            break

    if not passed:
        raise RuntimeError("QA FAIL: Rendered frames did not verify as valid gameplay")
    print("[+] QA GUARD PASSED: Ready for YouTube Upload!", flush=True)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "final_output.mp4"
    run_qa(target)
