import gc
import json
import os
import shutil
import subprocess
import sys
import time

os.environ["HF_HOME"] = "/tmp/hf_cache"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

OUT_FILE = "/kaggle/working/final_output.mp4"
TMP_DIR = "/tmp/render_work"
SDXL_BASE = "stabilityai/stable-diffusion-xl-base-1.0"
SDXL_LIGHTNING = "ByteDance/SDXL-Lightning"
SDXL_TURBO = "stabilityai/sdxl-turbo"
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
    try:
        from diffusers import AutoencoderKLWan, WanPipeline, StableDiffusionXLPipeline  # noqa: F401
        import ftfy  # noqa: F401
        import hf_transfer  # noqa: F401
        return
    except Exception:
        print("[*] Installing diffusers/Wan/SDXL + hf_transfer on Kaggle...", flush=True)
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


def generate_sdxl_scenes(beats, out_dir):
    import torch
    from diffusers import EulerDiscreteScheduler, StableDiffusionXLPipeline, UNet2DConditionModel, AutoPipelineForText2Image
    from huggingface_hub import hf_hub_download
    from safetensors.torch import load_file

    enable_fast_hf(True)
    scene_map = {}
    t0 = time.time()
    use_turbo = False
    try:
        print("[*] Loading SDXL-Lightning 4-step...", flush=True)
        unet = UNet2DConditionModel.from_config(SDXL_BASE, subfolder="unet").to("cuda", torch.float16)
        ckpt = hf_hub_download(SDXL_LIGHTNING, "sdxl_lightning_4step_unet.safetensors")
        unet.load_state_dict(load_file(ckpt, device="cuda"))
        pipe = StableDiffusionXLPipeline.from_pretrained(SDXL_BASE, unet=unet, torch_dtype=torch.float16, variant="fp16").to("cuda")
        pipe.scheduler = EulerDiscreteScheduler.from_config(pipe.scheduler.config, timestep_spacing="trailing")
    except Exception as e:
        print(f"[!] SDXL-Lightning fallback to SDXL-Turbo ({e})", flush=True)
        use_turbo = True
        pipe = AutoPipelineForText2Image.from_pretrained(SDXL_TURBO, torch_dtype=torch.float16, variant="fp16").to("cuda")

    neg = "text, watermark, subtitles, cartoon, bright cheerful, deformed fingers, blurry"
    w, h = (576, 1024) if use_turbo else (768, 1344)
    for i, beat in enumerate(beats):
        for tag, key in (("a", "shot_a"), ("b", "shot_b")):
            raw_p = beat.get(key) or beat.get("narration") or "dark deep ocean mystery"
            prompt = f"{raw_p}, 35mm dark cinema documentary still, dramatic moody shadows, volumetric light, ultra realistic"
            img = pipe(prompt=prompt[:300], negative_prompt=neg, width=w, height=h, num_inference_steps=4, guidance_scale=0.0).images[0]
            out_png = os.path.join(out_dir, f"scene_{i}_{tag}.png")
            img.save(out_png)
            scene_map[(i, tag)] = out_png

    print(f"[+] Generated {len(scene_map)} unique HD AI scenes in {time.time()-t0:.1f}s!", flush=True)
    del pipe
    gc.collect()
    torch.cuda.empty_cache()
    shutil.rmtree("/tmp/hf_cache", ignore_errors=True)
    return scene_map


def generate_wan_hook(beat0, out_dir):
    import torch
    from diffusers import AutoencoderKLWan, WanPipeline
    from diffusers.utils import export_to_video

    enable_fast_hf(True)
    t0 = time.time()
    try:
        print(f"[*] Loading {WAN_MODEL} on {torch.cuda.get_device_name(0)}...", flush=True)
        vae = AutoencoderKLWan.from_pretrained(WAN_MODEL, subfolder="vae", torch_dtype=torch.float16)
        pipe = WanPipeline.from_pretrained(WAN_MODEL, vae=vae, torch_dtype=torch.float16)
        pipe.enable_model_cpu_offload()
        prompt = (beat0.get("shot_a") or beat0["narration"]) + ", photorealistic 35mm dark cinema, fluid camera motion, volumetric shadows"
        neg = "blurry, low quality, text, watermark, subtitles, deformed faces, extra fingers, bright cartoon"
        frames = pipe(prompt=prompt[:320], negative_prompt=neg, height=832, width=480, num_frames=33, num_inference_steps=18, guidance_scale=5.0).frames[0]
        out_mp4 = os.path.join(out_dir, "ai_hook.mp4")
        export_to_video(frames, out_mp4, fps=16)
        print(f"[+] Hero AI Video Hook saved in {time.time()-t0:.1f}s!", flush=True)
        del pipe, vae
        gc.collect()
        torch.cuda.empty_cache()
        return out_mp4
    except Exception as e:
        print(f"[!] Wan2.1 hook skipped ({e}); using SDXL motion hook.", flush=True)
        return None
    finally:
        shutil.rmtree("/tmp/hf_cache", ignore_errors=True)


def pick_font_option():
    for fp in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if os.path.exists(fp):
            return f"fontfile={fp}:"
    return ""


def make_motion_piece(src, dur, is_video, sub_idx, is_climax, out_mp4):
    motions = [
        "crop=1080:1920:x='(iw-ow)/2+48*(t/{D}-0.5)':y='(ih-oh)/2-36*(t/{D}-0.5)'",
        "crop=1080:1920:x='(iw-ow)/2-48*(t/{D}-0.5)':y='(ih-oh)/2+40*(t/{D}-0.5)'",
        "crop=1080:1920:x='(iw-ow)/2+10*sin(t*12)':y='(ih-oh)/2-44*(t/{D}-0.5)+8*cos(t*10)'",
        "crop=1080:1920:x='(iw-ow)/2-40*(t/{D}-0.5)':y='(ih-oh)/2-36*(t/{D}-0.5)'",
    ]
    crop_expr = motions[sub_idx % 4].replace("{D}", f"{max(0.5, dur):.3f}")
    flash = ":brightness='0.28*between(t,0,0.16)':eval=frame" if is_climax else ":brightness=-0.03"
    slow = "setpts=1.35*PTS," if is_video else ""
    vf = (
        f"{slow}scale=1220:2168:force_original_aspect_ratio=increase:flags=lanczos,"
        f"{crop_expr},eq=contrast=1.14:saturation=0.88{flash},"
        "noise=alls=6:allf=t,unsharp=5:5:0.6:5:5:0.15,fps=30"
    )
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if is_video:
        cmd.extend(["-stream_loop", "-1", "-i", src])
    else:
        cmd.extend(["-loop", "1", "-framerate", "30", "-i", src])
    cmd.extend([
        "-t", f"{dur:.3f}", "-vf", vf, "-an",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "15",
        "-video_track_timescale", "30000", "-pix_fmt", "yuv420p", out_mp4,
    ])
    subprocess.run(cmd, check=True)


def main():
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("Kaggle GPU required for Full-AI Cinema generation")

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
    scene_map = generate_sdxl_scenes(beats, TMP_DIR)
    hook_mp4 = generate_wan_hook(beats[0], TMP_DIR)

    pieces = []
    sub_idx = 0
    for i, bt in enumerate(beat_times):
        bdur = max(1.2, float(bt["end"]) - float(bt["start"]))
        half1 = round(bdur * 0.50, 3)
        half2 = round(max(0.6, bdur - half1), 3)

        p1 = os.path.join(TMP_DIR, f"p_{i}_a.mp4")
        use_vid = (i == 0 and hook_mp4 and os.path.exists(hook_mp4))
        src1 = hook_mp4 if use_vid else scene_map[(i, "a")]
        make_motion_piece(src1, half1, use_vid, sub_idx, i == 4, p1)
        pieces.append(p1)
        sub_idx += 1

        p2 = os.path.join(TMP_DIR, f"p_{i}_b.mp4")
        make_motion_piece(scene_map[(i, "b")], half2, False, sub_idx, False, p2)
        pieces.append(p2)
        sub_idx += 1

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
    print(f"[+] V3 Cinema Render Complete! {OUT_FILE} ({os.path.getsize(OUT_FILE)/(1024*1024):.2f} MB)", flush=True)


if __name__ == "__main__":
    main()
