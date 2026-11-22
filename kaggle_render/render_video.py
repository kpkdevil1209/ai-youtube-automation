import os, sys, glob, json, shutil, subprocess, gc
import numpy as np

MODEL = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"
QUAL = "raw National Geographic documentary footage, authentic real-world textures, natural realistic lighting, handheld 35mm film camera, sharp focus, photorealistic"
NEG = "sci-fi, futuristic, cyberpunk, glowing neon, glowing rim light, hologram, laser, CGI render, 3D animation, video game, cartoon, anime, text, watermark, subtitles, logo, blurry, low quality, overexposed, overall gray"

def find_asset(name):
    for d in [".", "/kaggle/input/devil-insanity-assets"] + sorted(glob.glob("/kaggle/input/*")):
        p = os.path.join(d, name)
        if os.path.exists(p): return p
    raise FileNotFoundError(f"Missing asset: {name}")

def load_beats():
    with open(find_asset("current_script.json"), encoding="utf-8") as f: d = json.load(f)
    raw = d.get("beats") or d.get("scenes") or []
    prompts, durs = [], []
    for b in raw:
        vp = b.get("visual_prompt") or b.get("prompt") or b.get("visual") or d.get("topic", "dark ocean abyss documentary") if isinstance(b, dict) else str(b)
        prompts.append(f"{vp.strip()}, {QUAL}")
        durs.append(float(b.get("duration", 4.4)) if isinstance(b, dict) else 4.4)
    if not prompts: prompts, durs = [f"{d.get('topic', 'deep ocean trench')}, {QUAL}"] * 5, [1.0, 4.5, 5.0, 5.5, 4.5]
    return prompts[:6], durs[:6]

def run_worker(gpu_id, idxs_str, local_dir):
    import torch
    from diffusers import AutoencoderKLWan, WanPipeline
    from diffusers.schedulers.scheduling_unipc_multistep import UniPCMultistepScheduler
    from diffusers.utils import export_to_video

    idxs = [int(x) for x in idxs_str.split(",") if x.strip()]
    embeds = torch.load("embeds.pt", map_location="cpu", weights_only=True)
    vae = AutoencoderKLWan.from_pretrained(local_dir, subfolder="vae", torch_dtype=torch.float32)
    pipe = WanPipeline.from_pretrained(local_dir, vae=vae, text_encoder=None, tokenizer=None, torch_dtype=torch.float16)
    pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config, flow_shift=3.0)
    pipe.to("cuda")
    pipe.enable_attention_slicing()

    neg_e = embeds["neg"]
    for i in idxs:
        dt = pipe.transformer.dtype
        pe, ne = embeds["pos"][i].to("cuda", dtype=dt), neg_e.to("cuda", dtype=dt)
        steps = 18 if i in (0, 3) else 15
        frames = pipe(prompt_embeds=pe, negative_prompt_embeds=ne, height=832, width=480, num_frames=25, num_inference_steps=steps, guidance_scale=5.0, generator=torch.Generator("cuda").manual_seed(1042 + i)).frames[0]
        arr = np.array(frames)
        if float(arr.mean()) < 1.5 and float(arr.std()) < 1.5:
            print(f"[!] GPU {gpu_id} clip {i} pure black -> retrying fp32", flush=True)
            pipe.transformer.to(torch.float32)
            frames = pipe(prompt_embeds=pe.to(torch.float32), negative_prompt_embeds=ne.to(torch.float32), height=832, width=480, num_frames=25, num_inference_steps=steps, guidance_scale=5.0, generator=torch.Generator("cuda").manual_seed(2042 + i)).frames[0]
        export_to_video(frames, f"clip_{i}.mp4", fps=16)
        print(f"[*] GPU {gpu_id} rendered clip_{i}.mp4 ({steps} steps)", flush=True)

def encode_all(prompts, local_dir):
    import torch
    from diffusers import WanPipeline
    print("[*] Encoding prompts once in UMT5 bfloat16...", flush=True)
    enc = WanPipeline.from_pretrained(local_dir, transformer=None, vae=None, torch_dtype=torch.bfloat16)
    enc.to("cuda")
    pos_list, neg_e = [], None
    with torch.no_grad():
        for i, p in enumerate(prompts):
            pe, ne = enc.encode_prompt(prompt=p, negative_prompt=NEG, do_classifier_free_guidance=True, max_sequence_length=226, device="cuda")
            if not (torch.isfinite(pe).all() and torch.isfinite(ne).all()):
                enc.to("cpu", dtype=torch.float32)
                pe, ne = enc.encode_prompt(prompt=p, negative_prompt=NEG, do_classifier_free_guidance=True, max_sequence_length=226, device="cpu")
            pos_list.append(pe.cpu().to(torch.float16))
            if neg_e is None: neg_e = ne.cpu().to(torch.float16)
            print(f"[*] Encoded prompt {i+1}/{len(prompts)}", flush=True)
    torch.save({"pos": pos_list, "neg": neg_e}, "embeds.pt")
    del enc
    gc.collect()
    torch.cuda.empty_cache()

def assemble(durs):
    audio_p = find_asset("final_audio.wav")
    shutil.copyfile(find_asset("subtitles.ass"), "subs.ass")
    total = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", audio_p]).decode().strip())
    if len(durs) >= 2:
        d0 = min(1.15, max(0.85, durs[0]))
        rem = max(1.0, total - d0)
        tail_sum = max(0.1, sum(durs[1:]))
        final_durs = [d0] + [rem * (x / tail_sum) for x in durs[1:]]
    else:
        final_durs = [total]
    t_flash = final_durs[0]
    t3 = sum(final_durs[:3]) if len(final_durs) >= 4 else total * 0.55

    cmd = ["ffmpeg", "-y"]
    for i in range(len(final_durs)): cmd += ["-i", f"clip_{i}.mp4"]
    cmd += ["-i", audio_p]
    fc = []
    for i, dur in enumerate(final_durs):
        fc.append(f"[{i}:v]fps=16,setsar=1,split[f{i}][r{i}];[r{i}]reverse,trim=start_frame=1,setpts=PTS-STARTPTS[rv{i}];[f{i}][rv{i}]concat=n=2:v=1:a=0,loop=-1:size=80:start=0,trim=duration={dur:.3f},setpts=PTS-STARTPTS[v{i}]")
    cat_in = "".join(f"[v{i}]" for i in range(len(final_durs)))
    fc.append(f"{cat_in}concat=n={len(final_durs)}:v=1:a=0,scale=1080:1920:flags=lanczos,fps=30,format=yuv420p,eq=brightness='if(between(t,{max(0.0,t_flash-0.06):.3f},{t_flash+0.04:.3f})+between(t,{t3:.3f},{t3+0.10:.3f}),0.28,0)':eval=frame[vmain]")
    fc.append(f"color=c=#DC143C:s=1080x8[bar];[vmain][bar]overlay=x='-w+(t/{total:.3f})*w':y=0:eval=frame:shortest=1,ass=subs.ass[vout]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", f"{len(final_durs)}:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", "final_video.mp4"]
    subprocess.run(cmd, check=True)
    print(f"[*] Assembled final_video.mp4 ({total:.2f}s)", flush=True)

def main():
    if len(sys.argv) >= 5 and sys.argv[1] == "--worker":
        run_worker(sys.argv[2], sys.argv[3], sys.argv[4])
        return
    import torch
    from huggingface_hub import snapshot_download
    prompts, durs = load_beats()
    local_dir = snapshot_download(MODEL)
    encode_all(prompts, local_dir)
    n_gpu = torch.cuda.device_count()
    idxs = list(range(len(prompts)))
    if n_gpu >= 2 and len(idxs) >= 2:
        g0 = [str(i) for i in idxs if i % 2 == 0]
        g1 = [str(i) for i in idxs if i % 2 == 1]
        p0 = subprocess.Popen([sys.executable, __file__, "--worker", "0", ",".join(g0), local_dir], env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"})
        p1 = subprocess.Popen([sys.executable, __file__, "--worker", "1", ",".join(g1), local_dir], env={**os.environ, "CUDA_VISIBLE_DEVICES": "1"})
        if p0.wait() != 0 or p1.wait() != 0: raise RuntimeError("Worker GPU render failed")
    else:
        run_worker("0", ",".join(str(i) for i in idxs), local_dir)
    assemble(durs)

if __name__ == "__main__":
    main()
