import os, sys, json, time, shutil, subprocess, gc, textwrap

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.environ["HF_HOME"] = "/tmp/hf_cache"
os.environ["TMPDIR"] = "/tmp"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

MODEL = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"
QUAL = "raw National Geographic documentary footage, authentic real-world textures, natural realistic lighting, handheld 35mm film camera, sharp focus, photorealistic"
NEG = "sci-fi, futuristic, cyberpunk, glowing neon, hologram, laser, CGI render, 3D animation, video game, cartoon, anime, text, watermark, subtitles, logo, blurry, low quality, overexposed, overall gray"


def ensure_packages():
    chk = "from diffusers import AutoencoderKLWan, WanPipeline; from diffusers.utils import export_to_video; import transformers, accelerate, peft, imageio_ffmpeg, PIL, numpy, torch"
    if subprocess.run([sys.executable, "-c", chk], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        return
    print("[*] Syncing diffusers/transformers/peft/pillow stack...", flush=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "--upgrade", "--no-cache-dir", "diffusers", "transformers", "accelerate", "peft", "huggingface_hub", "ftfy", "imageio-ffmpeg", "pillow", "numpy"],
        check=True,
    )
    if subprocess.run([sys.executable, "-c", chk], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "--no-cache-dir", "transformers>=4.49.0,<5.0.0", "diffusers>=0.32.2", "peft>=0.14.0", "accelerate", "huggingface_hub", "ftfy", "imageio-ffmpeg", "pillow"],
            check=True,
        )
    subprocess.run([sys.executable, "-c", chk], check=True)


def find_asset(name):
    for d in (".", "/kaggle/working"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    for dp, _, fns in os.walk("/kaggle/input"):
        if name in fns:
            return os.path.join(dp, name)
    raise FileNotFoundError(f"Missing {name}")


def load_beats():
    d = json.load(open(find_asset("current_script.json"), encoding="utf-8"))
    raw = d.get("beats") or d.get("scenes") or []
    prompts, durs = [], []
    for b in raw:
        vp = (b.get("visual_prompt") or b.get("ai_prompt") or b.get("prompt") or d.get("topic", "dark ocean abyss documentary")) if isinstance(b, dict) else str(b)
        prompts.append(f"{vp.strip()}, {QUAL}")
        durs.append(float(b.get("duration", 3.4)) if isinstance(b, dict) else 3.4)
    if not prompts:
        prompts, durs = [f"{d.get('topic', 'deep ocean trench')}, {QUAL}"] * 5, [1.8, 3.5, 3.6, 3.8, 3.4]
    headline = d.get("hook_headline") or (raw[0].get("hook_question") if raw and isinstance(raw[0], dict) else "") or d.get("title", "")
    return prompts[:6], durs[:6], str(headline).strip().upper()


def make_hook_banner(headline, out_png):
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    if not headline:
        img.save(out_png, "PNG")
        return
    font = ImageFont.load_default()
    for fp in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if os.path.exists(fp):
            font = ImageFont.truetype(fp, 54)
            break
    lines = textwrap.wrap(headline, width=20)[:3]
    lh = 66
    bh = len(lines) * lh + 48
    by0, by1 = 230, 230 + bh
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([64, by0, 1016, by1], radius=18, fill=(8, 12, 22, 212), outline=(250, 204, 21, 210), width=3)
    draw.rectangle([64, by0 + 16, 76, by1 - 16], fill=(220, 38, 38, 255))
    y = by0 + 24
    for idx, ln in enumerate(lines):
        col = (250, 204, 21, 255) if idx == len(lines) - 1 else (255, 255, 255, 255)
        draw.text((104, y + 3), ln, font=font, fill=(0, 0, 0, 230))
        draw.text((100, y), ln, font=font, fill=col)
        y += lh
    img.save(out_png, "PNG")


def install_chunked_sdpa(chunk_size=512):
    import torch, torch.nn.functional as F

    orig_sdpa = F.scaled_dot_product_attention
    if getattr(orig_sdpa, "_is_chunked", False):
        return

    def chunked_sdpa(query, key, value, attn_mask=None, dropout_p=0.0, is_causal=False, scale=None, enable_gqa=False, **kwargs):
        kw = dict(kwargs)
        if enable_gqa:
            kw["enable_gqa"] = enable_gqa
        if query.is_cuda and query.ndim == 4 and query.dtype != torch.float16 and attn_mask is None and not is_causal and query.shape[-2] > chunk_size:
            return torch.cat([orig_sdpa(query[:, :, i : i + chunk_size, :], key, value, attn_mask=None, dropout_p=dropout_p, is_causal=False, scale=scale, **kw) for i in range(0, query.shape[-2], chunk_size)], dim=-2)
        return orig_sdpa(query, key, value, attn_mask=attn_mask, dropout_p=dropout_p, is_causal=is_causal, scale=scale, **kw)

    chunked_sdpa._is_chunked = True
    F.scaled_dot_product_attention = chunked_sdpa
    torch.nn.functional.scaled_dot_product_attention = chunked_sdpa


def encode_sub(local_dir):
    import torch
    from diffusers import WanPipeline

    prompts, _, _ = load_beats()
    print("[*] Encoding prompts in UMT5 bfloat16...", flush=True)
    enc = WanPipeline.from_pretrained(local_dir, transformer=None, vae=None, torch_dtype=torch.bfloat16)
    try:
        enc.text_encoder.set_input_embeddings(enc.text_encoder.get_input_embeddings())
    except Exception:
        pass
    enc.enable_sequential_cpu_offload()
    pos_list, neg_e = [], None
    with torch.no_grad():
        for i, p in enumerate(prompts):
            pe, ne = enc.encode_prompt(prompt=p, negative_prompt=NEG, do_classifier_free_guidance=True, max_sequence_length=226, device="cuda")
            pos_list.append(pe.cpu().to(torch.bfloat16))
            if neg_e is None:
                neg_e = ne.cpu().to(torch.bfloat16)
            print(f"[*] Encoded {i+1}/{len(prompts)}", flush=True)
    torch.save({"pos": pos_list, "neg": neg_e}, "embeds.pt")


def make_pipe(local_dir, dtype):
    import torch
    from diffusers import AutoencoderKLWan, WanPipeline
    from diffusers.schedulers.scheduling_unipc_multistep import UniPCMultistepScheduler

    install_chunked_sdpa(512)
    vae = AutoencoderKLWan.from_pretrained(local_dir, subfolder="vae", torch_dtype=torch.float32)
    for fn in ("enable_tiling", "enable_slicing"):
        try:
            getattr(vae, fn)()
        except Exception:
            pass
    pipe = WanPipeline.from_pretrained(local_dir, vae=vae, text_encoder=None, tokenizer=None, torch_dtype=dtype)
    pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config, flow_shift=3.0)
    pipe.set_progress_bar_config(disable=True)
    pipe.enable_model_cpu_offload()
    return pipe


def run_worker(gpu_id, idxs_str, local_dir):
    import numpy as np, torch
    from diffusers.utils import export_to_video

    idxs = [int(x) for x in idxs_str.split(",") if x.strip()]
    embeds = torch.load("embeds.pt", map_location="cpu", weights_only=True)
    pipe = make_pipe(local_dir, torch.bfloat16)
    neg_e = embeds["neg"]
    for i in idxs:
        steps = 16 if i in (0, 3) else 14
        pe, ne = embeds["pos"][i].to("cuda", dtype=torch.bfloat16), neg_e.to("cuda", dtype=torch.bfloat16)
        frames = pipe(prompt_embeds=pe, negative_prompt_embeds=ne, height=832, width=480, num_frames=21, num_inference_steps=steps, guidance_scale=5.0, generator=torch.Generator("cuda").manual_seed(1042 + i)).frames[0]
        arr = np.array(frames)
        print(f"[*] GPU {gpu_id} clip {i} mean={arr.mean():.2f}", flush=True)
        export_to_video(frames, f"clip_{i}.mp4", fps=16)
        del frames, arr, pe, ne
        gc.collect()
        torch.cuda.empty_cache()


def assemble(durs, headline):
    audio_p = find_asset("final_audio.wav")
    shutil.copyfile(find_asset("subtitles.ass"), "subs.ass")
    make_hook_banner(headline, "hook_banner.png")
    total = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", audio_p]).decode().strip())

    if len(durs) >= 2:
        d0 = min(2.2, max(1.4, durs[0]))
        rem = max(1.0, total - d0)
        final_durs = [d0] + [rem * (x / max(0.1, sum(durs[1:]))) for x in durs[1:]]
    else:
        final_durs = [total]

    n_clips = len(final_durs)
    cmd = ["ffmpeg", "-y"]
    for i in range(n_clips):
        cmd += ["-i", f"clip_{i}.mp4"]
    cmd += ["-i", audio_p, "-loop", "1", "-t", "2.40", "-i", "hook_banner.png"]

    fc, segs = [], []
    for i, dur in enumerate(final_durs):
        fc.append(f"[{i}:v]fps=16,setsar=1,split[f{i}][r{i}];[r{i}]reverse,trim=start_frame=1,setpts=PTS-STARTPTS[rv{i}];[f{i}][rv{i}]concat=n=2:v=1:a=0,loop=-1:size=80:start=0,trim=duration={dur:.3f},setpts=PTS-STARTPTS[b{i}]")
        if dur >= 1.5:
            da = round(dur * 0.50, 3)
            fc.append(f"[b{i}]split[sa{i}][sb{i}]")
            if i % 2 == 0:
                fc.append(f"[sa{i}]trim=0:{da:.3f},setpts=PTS-STARTPTS,scale=1080:1920:flags=lanczos,fps=30,setsar=1,format=yuv420p[p{i}a]")
                fc.append(f"[sb{i}]trim={da:.3f}:{dur:.3f},setpts=PTS-STARTPTS,crop=iw*0.86:ih*0.86,scale=1080:1920:flags=lanczos,fps=30,setsar=1,format=yuv420p[p{i}b]")
            else:
                fc.append(f"[sa{i}]trim=0:{da:.3f},setpts=PTS-STARTPTS,crop=iw*0.86:ih*0.86,scale=1080:1920:flags=lanczos,fps=30,setsar=1,format=yuv420p[p{i}a]")
                fc.append(f"[sb{i}]trim={da:.3f}:{dur:.3f},setpts=PTS-STARTPTS,hflip,scale=1080:1920:flags=lanczos,fps=30,setsar=1,format=yuv420p[p{i}b]")
            segs.extend([f"[p{i}a]", f"[p{i}b]"])
        else:
            fc.append(f"[b{i}]scale=1080:1920:flags=lanczos,fps=30,setsar=1,format=yuv420p[p{i}a]")
            segs.append(f"[p{i}a]")

    fc.append(f"{''.join(segs)}concat=n={len(segs)}:v=1:a=0,unsharp=5:5:0.75:5:5:0.0,eq=gamma=1.06:contrast=1.05:saturation=1.06[vmain]")
    fc.append(f"[{n_clips+1}:v]format=rgba,fade=t=in:st=0.0:d=0.10:alpha=1,fade=t=out:st=2.05:d=0.25:alpha=1[hban]")
    fc.append(f"color=c=#DC143C:s=1080x8[bar];[vmain][bar]overlay=x='-w+(t/{total:.3f})*w':y=0:eval=frame:shortest=1[vbar];[vbar][hban]overlay=0:0:enable='between(t,0.0,2.30)',ass=subs.ass[vout]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", f"{n_clips}:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", "final_video.mp4"]
    subprocess.run(cmd, check=True)
    print(f"[*] Assembled final_video.mp4 ({total:.2f}s)", flush=True)


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--encode":
        encode_sub(sys.argv[2])
        return
    if len(sys.argv) >= 5 and sys.argv[1] == "--worker":
        run_worker(sys.argv[2], sys.argv[3], sys.argv[4])
        return

    ensure_packages()
    import torch
    from huggingface_hub import snapshot_download

    prompts, durs, headline = load_beats()
    local_dir = snapshot_download(MODEL)
    subprocess.run([sys.executable, __file__, "--encode", local_dir], check=True)
    idxs = list(range(len(prompts)))
    if torch.cuda.device_count() >= 2 and len(idxs) >= 2:
        g0, g1 = [str(i) for i in idxs if i % 2 == 0], [str(i) for i in idxs if i % 2 == 1]
        with open("w0.log", "w") as f0, open("w1.log", "w") as f1:
            p0 = subprocess.Popen([sys.executable, __file__, "--worker", "0", ",".join(g0), local_dir], env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"}, stdout=f0, stderr=subprocess.STDOUT)
            p1 = subprocess.Popen([sys.executable, __file__, "--worker", "1", ",".join(g1), local_dir], env={**os.environ, "CUDA_VISIBLE_DEVICES": "1"}, stdout=f1, stderr=subprocess.STDOUT)
            p0.wait(), p1.wait()
        if p0.returncode != 0 or p1.returncode != 0:
            raise RuntimeError("Worker GPU render failed")
    else:
        run_worker("0", ",".join(str(i) for i in idxs), local_dir)
    assemble(durs, headline)


if __name__ == "__main__":
    main()
