import gc
import glob
import json
import os
import shutil
import subprocess
import sys

os.environ["HF_HOME"] = "/tmp/hf_cache"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

OUT_FILE = "/kaggle/working/final_output.mp4"
TMP_DIR = "/tmp/render_work"
MODEL_ID = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"


def find_assets_dir():
    for root in ["/kaggle/input", "/kaggle/working", "."]:
        for dirpath, _, files in os.walk(root):
            if "current_script.json" in files and "final_audio.wav" in files:
                return dirpath
    raise FileNotFoundError("Assets (current_script.json / final_audio.wav) not found")


def audio_duration(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
    ], text=True).strip()
    return float(out)


def ensure_ai_packages():
    try:
        from diffusers import AutoencoderKLWan, WanPipeline  # noqa: F401
        import ftfy  # noqa: F401
        return
    except Exception:
        print("[*] Installing diffusers/WanPipeline dependencies on Kaggle...", flush=True)
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-q", "-U",
            "diffusers>=0.32.2", "transformers>=4.49.0", "accelerate>=1.1.1",
            "ftfy", "sentencepiece", "imageio-ffmpeg",
        ])


def generate_wan_clips(beats, out_dir):
    ai_files = {}
    import torch
    if not torch.cuda.is_available():
        print("[!] No CUDA GPU detected; skipping Wan2.1 and using stock clips.", flush=True)
        return ai_files

    try:
        ensure_ai_packages()
        from diffusers import AutoencoderKLWan, WanPipeline
        from diffusers.utils import export_to_video

        print(f"[*] Loading {MODEL_ID} on {torch.cuda.get_device_name(0)}...", flush=True)
        vae = AutoencoderKLWan.from_pretrained(MODEL_ID, subfolder="vae", torch_dtype=torch.float16)
        pipe = WanPipeline.from_pretrained(MODEL_ID, vae=vae, torch_dtype=torch.float16)
        pipe.enable_model_cpu_offload()

        neg = "blurry, low quality, text, watermark, subtitles, deformed faces, extra fingers, bright cartoon"
        for idx, beat in enumerate(beats):
            if beat.get("visual_mode") != "ai_video":
                continue
            text_src = beat.get("ai_prompt") or beat.get("narration") or "dark deep ocean abyss"
            prompt = text_src + ", photorealistic 35mm dark cinema, moody volumetric lighting, fluid motion"
            print(f"[*] Generating Real AI Video for Beat {idx} (480x832)...", flush=True)
            frames = pipe(
                prompt=prompt[:350],
                negative_prompt=neg,
                height=832,
                width=480,
                num_frames=49,
                num_inference_steps=26,
                guidance_scale=5.0,
            ).frames[0]
            out_mp4 = os.path.join(out_dir, f"ai_{idx}.mp4")
            export_to_video(frames, out_mp4, fps=16)
            ai_files[idx] = out_mp4
            print(f"[+] AI Video Beat {idx} saved!", flush=True)

        del pipe, vae
        gc.collect()
        torch.cuda.empty_cache()
    except Exception as e:
        print(f"[!] Wan2.1 notice (falling back to stock clips): {e}", flush=True)
    finally:
        shutil.rmtree("/tmp/hf_cache", ignore_errors=True)

    return ai_files


def pick_font_option():
    for fp in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if os.path.exists(fp):
            return f"fontfile={fp}:"
    return ""


def main():
    assets = find_assets_dir()
    print(f"[*] Assets dir: {assets}", flush=True)
    print(f"[*] Assets files: {sorted(os.listdir(assets))}", flush=True)
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    os.makedirs(TMP_DIR, exist_ok=True)

    with open(os.path.join(assets, "current_script.json"), "r", encoding="utf-8") as f:
        script = json.load(f)
    print(f"[*] Script keys: {list(script.keys())} | Topic: {script.get('topic')}", flush=True)

    audio_path = os.path.join(assets, "final_audio.wav")
    srt_path = os.path.join(assets, "subtitles.srt")
    beats = script.get("beats") or script.get("segments") or []
    if not beats:
        raise RuntimeError("No beats found in current_script.json (check Step 2/3 or Kaggle dataset sync)")

    beat_times = script.get("beat_times")
    if not beat_times or len(beat_times) != len(beats):
        tot = audio_duration(audio_path)
        step = tot / len(beats)
        beat_times = [{"idx": i, "start": round(i * step, 3), "end": round((i + 1) * step, 3)} for i in range(len(beats))]
        print(f"[!] Computed fallback beat_times ({tot:.2f}s / {len(beats)} beats)", flush=True)

    badge = "".join(c for c in str(script.get("hook_badge", "CLASSIFIED")) if c.isalnum() or c in " .,-")[:24]
    ai_files = generate_wan_clips(beats, TMP_DIR)

    stock_fallback = sorted(glob.glob(os.path.join(assets, "stock_*.mp4")))
    if not stock_fallback and os.path.exists(os.path.join(assets, "raw_gameplay.mp4")):
        stock_fallback = [os.path.join(assets, "raw_gameplay.mp4")]

    piece_paths = []
    for i, (beat, bt) in enumerate(zip(beats, beat_times)):
        dur = max(1.5, float(bt["end"]) - float(bt["start"]))
        src = ai_files.get(i)
        if not src or not os.path.exists(src):
            cand = os.path.join(assets, beat.get("stock_file", f"stock_{i}.mp4"))
            if os.path.exists(cand):
                src = cand
            elif stock_fallback:
                src = stock_fallback[i % len(stock_fallback)]
            else:
                raise FileNotFoundError("No stock or AI video file available for rendering")

        piece = os.path.join(TMP_DIR, f"piece_{i}.mp4")
        slow = "setpts=1.18*PTS," if i in ai_files else ""
        vf = (
            f"{slow}scale=1160:2062:force_original_aspect_ratio=increase:flags=lanczos,"
            "crop=1080:1920:x='(iw-ow)/2+16*sin(t*1.3)':y='(ih-oh)/2+12*cos(t*1.0)',"
            "eq=contrast=1.12:saturation=0.90:brightness=-0.03,unsharp=5:5:0.6:5:5:0.15,fps=30"
        )
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-stream_loop", "-1", "-i", src, "-t", f"{dur:.3f}",
            "-vf", vf, "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "15",
            "-video_track_timescale", "30000", "-pix_fmt", "yuv420p", piece,
        ], check=True)
        piece_paths.append(piece)

    concat_txt = os.path.join(TMP_DIR, "pieces.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for p in piece_paths:
            f.write(f"file '{p}'\n")
    raw_concat = os.path.join(TMP_DIR, "concat.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", concat_txt, "-c", "copy", raw_concat,
    ], check=True)

    srt_local = os.path.join(TMP_DIR, "subs.srt")
    has_srt = os.path.exists(srt_path)
    if has_srt:
        shutil.copyfile(srt_path, srt_local)

    font_opt = pick_font_option()
    filters = ["vignette=PI/5"]
    if badge:
        filters.append("drawbox=x=290:y=115:w=500:h=68:color=black@0.58:t=fill")
        filters.append(f"drawtext={font_opt}text='{badge}':fontcolor=white:fontsize=34:x=(w-text_w)/2:y=134")
    if has_srt:
        esc_srt = srt_local.replace(":", "\\:")
        style = "FontName=DejaVu Sans,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=500,Bold=1"
        filters.append(f"subtitles={esc_srt}:force_style='{style}'")

    os.makedirs("/kaggle/working", exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", raw_concat, "-i", audio_path,
        "-vf", ",".join(filters),
        "-map", "0:v:0", "-map", "1:a:0", "-shortest",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", OUT_FILE,
    ], check=True)

    shutil.rmtree(TMP_DIR, ignore_errors=True)
    print(f"[+] Render complete! {OUT_FILE} ({os.path.getsize(OUT_FILE)/(1024*1024):.2f} MB)", flush=True)


if __name__ == "__main__":
    main()
