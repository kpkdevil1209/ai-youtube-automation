# qa_guard_agent.py - Agent 5: Final Pre-Upload QA Critic
import os, sys, json, subprocess
from verify_freefire_agent import video_info, quality_scan, ensure_vision, ai_check_frame

def check_audio_loudness(path):
    cmd = ["ffmpeg", "-v", "info", "-i", path, "-af", "volumedetect", "-f", "null", "-"]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in res.stderr.splitlines():
        if "mean_volume:" in line:
            val = float(line.split("mean_volume:")[1].split("dB")[0].strip())
            print(f"[QA Audio] mean_volume={val:.1f} dB")
            return val > -45.0
    return False

def run_qa(path="final_output.mp4"):
    print("\n==========================================")
    print("[*] AGENT 5: FINAL PRE-UPLOAD QA CRITIC")
    print("==========================================")
    if not os.path.exists(path) or os.path.getsize(path) < 400_000:
        raise RuntimeError(f"QA FAIL: {path} missing or too small!")
    w, h, dur = video_info(path)
    if w < 720 or h < 1280 or dur < 10.0:
        raise RuntimeError(f"QA FAIL: Bad final render dimensions/duration ({w}x{h}, {dur:.1f}s)")
    if not check_audio_loudness(path):
        raise RuntimeError("QA FAIL: Rendered audio is silent!")
    ok_q, q_msg = quality_scan(path, dur)
    if not ok_q:
        raise RuntimeError(f"QA FAIL: {q_msg}")
    if ensure_vision():
        r = ai_check_frame(path, dur * 0.50, unload=True)
        print(f"[QA Vision @ 50%] '{r.get('what_is_shown')}' | ff={r.get('is_free_fire')} | sharp={r.get('is_clear_sharp')} | conf={r.get('confidence')}%")
        if not (r.get("is_free_fire") and r.get("is_clear_sharp")):
            raise RuntimeError("QA FAIL: Final render failed visual Free Fire check!")
    print("[+] QA PASSED! Rendered video is verified safe for YouTube upload.\n")

if __name__ == "__main__":
    run_qa(sys.argv[1] if len(sys.argv) > 1 else "final_output.mp4")
