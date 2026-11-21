import gc
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import traceback

os.environ["HF_HOME"] = "/tmp/hf_cache"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

OUT_FILE = "/kaggle/working/final_output.mp4"
TMP_DIR = "/tmp/render_work"
WAN_MODEL = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"


def find_assets_dir():
    for dirpath, _, files in os.walk("/kaggle/input"):
        if "current_script.json" in files and "final_audio.wav" in files:
            return dirpath
    raise FileNotFoundError("Fresh dataset not found in /kaggle/input")


def audio_duration(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
    ], text=True).strip()
    return float(out)


def ensure_ai_packages():
    if importlib.util.find_spec("hf_transfer") and importlib.util.find_spec("ftfy"):
        return
    print("[*] Installing diffusers/Wan2.1 + hf_transfer on Kaggle...", flush=True)
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "-q", "-U",
        "diffusers>=0.32.2", "transformers>=4.49.0", "accelerate>=1.1.1",
        "ftfy", "sentencepiece", "imageio-ffmpeg", "hf_transfer", "safetensors",
    ])


def enable_fast_hf(flag=True):
    if flag:
        try:
            import hf_transfer  # noqa: F401
            os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
            return
        except Exception:
            pass
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"


def generate_all_wan_videos(beats, out_dir):
    import torch
    from diffusers import AutoencoderKLWan, WanPipeline
    from diffusers.utils import export_to_video

    enable_fast_hf(True)
    gpu_name = torch.cuda.get_device_name(0)
    print(f"[*] Loading {WAN_MODEL} on {gpu_name}...", flush=True)
    t0 = time.time()

    try:
        vae = AutoencoderKLWan.from_pretrained(WAN_MODEL, subfolder="vae", torch_dtype=torch.float32)
        pipe = WanPipeline.from_pretrained(WAN_MODEL, vae=vae, torch_dtype=torch.float16)
    except Exception:
        enable_fast_hf(False)
        vae = AutoencoderKLWan.from_pretrained(WAN_MODEL, subfolder="vae", torch_dtype=torch.float32)
        pipe = WanPipeline.from_pretrained(WAN_MODEL, vae=vae, torch_dtype=torch.float16)

    try:
        pipe.vae.enable_tiling()
        pipe.vae.enable_slicing()
    except Exception:
        pass

    seq_mode = False
    pipe.enable_model_cpu_offload()
    print(f"[+] Wan2.1 ready in {time.time() - t0:.1f}s", flush=True)

    neg = "blurry, low quality, text, watermark, subtitles, deformed faces, extra fingers, bright cartoon, static image"
    vid_files = []
    for idx, beat in enumerate(beats):
        raw_p = beat.get("ai_prompt") or beat.get("shot_a") or beat.get("narration") or "deep dark ocean storm"
        prompt = f"{raw_p}, photorealistic 35mm dark cinema, dynamic camera movement, dramatic shadows"
        steps = 22 if idx == 0 else 18
        nframes = 41
        t_clip = time.time()
        print(f"[*] Generating Real AI Video [{idx + 1}/{len(beats)}] (480x832, {nframes}f, {steps}s)...", flush=True)
        try:
            frames = pipe(
                prompt=prompt[:320],
                negative_prompt=neg,
                height=832,
                width=480,
                num_frames=nframes,
                num_inference_steps=steps,
                guidance_scale=5.0,
            ).frames[0]
        except Exception as e:
            if not seq_mode and ("out of memory" in str(e).lower() or "cuda" in str(e).lower()):
                print("[!] VRAM tight -> switching to sequential_cpu_offload and retrying...", flush=True)
                gc.collect()
                torch.cuda.empty_cache()
                pipe.enable_sequential_cpu_offload()
                seq_mode = True
                frames = pipe(
                    prompt=prompt[:320],
                    negative_prompt=neg,
                    height=832,
                    width=480,
                    num_frames=nframes,
                    num_inference_steps=steps,
                    guidance_scale=5.0,
                ).frames[0]
            else:
                traceback.print_exc()
                raise

        out_mp4 = os.path.join(out_dir, f"wan_{idx}.mp4")
        export_to_video(frames, out_mp4, fps=16)
        vid_files.append(out_mp4)
        print(f"[+] Real AI Video [{idx + 1}/{len(beats)}] done in {time.time() - t_clip:.1f}s!", flush=True)

    del pipe, vae
    gc.collect()
    torch.cuda.empty_cache()
    shutil.rmtree("/tmp/hf_cache", ignore_errors=True)
    return vid_files


def pick_font_option():
    for fp in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if os.path.exists(fp):
            return f"fontfile={fp}:"
    return ""


def process_video_beat(src, dur, idx, climax_idx, out_mp4):
    dur_s = max(1.0, dur)
    if idx == 0:
        crop = "crop=1080:1920:x='(iw-ow)/2+12*sin(t*14)':y='(ih-oh)/2+10*cos(t*12)'"
        flash = ":brightness='0.26*between(t,0,0.14)':eval=frame"
    elif idx == climax_idx:
        crop = f"crop=1080:1920:x='(iw-ow)/2+14*sin(t*16)':y='(ih-oh)/2-36*(t/{dur_s:.2f}-0.5)'"
        flash = ":brightness='0.30*between(t,0,0.16)':eval=frame"
    else:
        crop = f"crop=1080:1920:x='(iw-ow)/2+36*(t/{dur_s:.2f}-0.5)':y='(ih-oh)/2-28*(t/{dur_s:.2f}-0.5)'"
        flash = ":brightness=-0.03"

    vf = (
        f"setpts=1.40*PTS,scale=1180:2098:force_original_aspect_ratio=increase:flags=lanczos,"
        f"{crop},eq=contrast=1.14:saturation=0.90{flash},"
        "noise=alls=5:allf=t,unsharp=5:5:0.65:5:5:0.15,fps=30"
    )
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-stream_loop", "-1", "-i", src, "-t", f"{dur:.3f}",
        "-vf", vf, "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "15",
        "-video_track_timescale", "30000", "-pix_fmt", "yuv420p", out_mp4,
    ], check=True)


def main():
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("Kaggle GPU required for Wan2.1 Real Video generation")

    assets = find_assets_dir()
    print(f"[*] Assets dir: {assets} | Files: {sorted(os.listdir(assets))}", flush=True)
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    os.makedirs(TMP_DIR, exist_ok=True)

    with open(os.path.join(assets, "current_script.json"), "r", encoding="utf-8") as f:
        script = json.load(f)
    print(f"[*] Run ID: {script.get('run_id')} | Topic: {script.get('topic')}", flush=True)

    audio_path = os.path.join(assets, "final_audio.wav")
    ass_path = os.path.join(assets, "subtitles.ass")
    srt_path = os.path.join(assets, "subtitles.srt")
    beats = script.get("beats") or []
    beat_times = script.get("beat_times")
    total_dur = float(script.get("total_duration") or audio_duration(audio_path))
    if not beat_times or len(beat_times) != len(beats):
        step = total_dur / max(1, len(beats))
        beat_times = [{"idx": i, "start": i * step, "end": (i + 1) * step} for i in range(len(beats))]

    ensure_ai_packages()
    wan_videos = generate_all_wan_videos(beats, TMP_DIR)

    climax_idx = min(3, len(beats) - 1)
    pieces = []
    for i, bt in enumerate(beat_times):
        bdur = max(1.5, float(bt["end"]) - float(bt["start"]))
        p_out = os.path.join(TMP_DIR, f"piece_{i}.mp4")
        process_video_beat(wan_videos[i], bdur, i, climax_idx, p_out)
        pieces.append(p_out)

    concat_txt = os.path.join(TMP_DIR, "pieces.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for p in pieces:
            f.write(f"file '{p}'\n")
    raw_concat = os.path.join(TMP_DIR, "concat.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", concat_txt, "-c", "copy", raw_concat,
    ], check=True)

    badge = "".join(c for c in str(script.get("hook_badge", "CLASSIFIED")) if c.isalnum() or c in " .,:+-")[:22]
    font_opt = pick_font_option()
    sub_local = os.path.join(TMP_DIR, "subs.ass" if os.path.exists(ass_path) else "subs.srt")
    has_subs = os.path.exists(ass_path) or os.path.exists(srt_path)
    if os.path.exists(ass_path):
        shutil.copyfile(ass_path, sub_local)
    elif os.path.exists(srt_path):
        shutil.copyfile(srt_path, sub_local)

    v_chain = ["vignette=PI/5"]
    if badge:
        v_chain.append("drawbox=x=270:y=105:w=540:h=68:color=black@0.62:t=fill")
        v_chain.append("drawbox=x=270:y=105:w=10:h=68:color=0xFF2B2B:t=fill")
        v_chain.append(f"drawtext={font_opt}text='{badge}':fontcolor=white:fontsize=32:x=(w-text_w)/2:y=124")
    if has_subs:
        esc = sub_local.replace(":", "\\:")
        v_chain.append(f"subtitles={esc}")

    fc = (
        f"[0:v]{','.join(v_chain)}[base];"
        f"[base][1:v]overlay=x='-1080+(t/{total_dur:.2f})*1080':y=0:shortest=1[outv]"
    )

    os.makedirs("/kaggle/working", exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", raw_concat,
        "-f", "lavfi", "-t", f"{total_dur:.2f}", "-i", "color=c=0xFF2222:s=1080x10",
        "-i", audio_path,
        "-filter_complex", fc,
        "-map", "[outv]", "-map", "2:a:0", "-shortest",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", OUT_FILE,
    ], check=True)

    shutil.rmtree(TMP_DIR, ignore_errors=True)
    print(f"[+] 100% Real AI Video Short Complete! {OUT_FILE} ({os.path.getsize(OUT_FILE)/(1024*1024):.2f} MB)", flush=True)


if __name__ == "__main__":
    main()
