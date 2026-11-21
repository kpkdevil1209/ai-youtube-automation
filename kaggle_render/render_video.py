import os, sys, gc, glob, json, time, shutil, subprocess, importlib.util

os.environ["HF_HOME"] = "/tmp/hf_cache"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

if importlib.util.find_spec("hf_transfer") is None or importlib.util.find_spec("diffusers") is None:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "diffusers", "transformers", "accelerate", "hf_transfer", "sentencepiece", "ftfy"], check=True)

import numpy as np
import torch
from transformers import UMT5EncoderModel
from diffusers import AutoencoderKLWan, WanPipeline
from diffusers.utils import export_to_video

torch.backends.cuda.matmul.allow_tf32 = True
MID = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"
NEG = "pitch black, dark empty screen, blurry, static photo, watermark, text, subtitles, deformed face, extra fingers, cartoon"
QUAL = ", vivid dramatic lighting, glowing rim light, 35mm IMAX documentary cinematography, high contrast, rich colors, crisp focus"

def find_assets():
    for root in ("/kaggle/input", "/kaggle/working"):
        for dp, _, fs in os.walk(root):
            if "current_script.json" in fs and "final_audio.wav" in fs: return dp
    raise RuntimeError("Assets not found in /kaggle/input")

def probe_dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", p]).decode().strip())

def encode_all_prompts(prompts):
    te = UMT5EncoderModel.from_pretrained(MID, subfolder="text_encoder", torch_dtype=torch.bfloat16)
    vae = AutoencoderKLWan.from_pretrained(MID, subfolder="vae", torch_dtype=torch.float32)
    pipe = WanPipeline.from_pretrained(MID, text_encoder=te, vae=vae, torch_dtype=torch.float16)
    embeds = []
    try:
        try:
            pipe.text_encoder.to("cuda:0")
            dev = "cuda:0"
        except Exception:
            pipe.text_encoder.to("cpu")
            dev = "cpu"
        with torch.inference_mode():
            for p in prompts:
                pe, npe = pipe.encode_prompt(prompt=p + QUAL, negative_prompt=NEG, do_classifier_free_guidance=True, device=dev)
                if not torch.isfinite(pe).all() or not torch.isfinite(npe).all():
                    raise RuntimeError("Non-finite prompt embeddings")
                embeds.append((pe.cpu().float(), npe.cpu().float()))
        torch.save(embeds, "/tmp/embeds.pt")
        print(f"[+] All 5 prompts encoded on {dev}!", flush=True)
    finally:
        del pipe, te, vae; gc.collect(); torch.cuda.empty_cache()

def is_black(frames):
    arr = np.asarray(frames[0], dtype=np.float32)
    return (arr.mean() < 0.03) if arr.max() <= 1.5 else (arr.mean() < 8.0)

def render_indices(indices, prompts, base_seed):
    vae = AutoencoderKLWan.from_pretrained(MID, subfolder="vae", torch_dtype=torch.float32)
    embeds = torch.load("/tmp/embeds.pt", map_location="cpu")
    pipe = WanPipeline.from_pretrained(MID, text_encoder=None, tokenizer=None, vae=vae, torch_dtype=torch.float16)
    pipe.vae.enable_tiling(); pipe.vae.enable_slicing()
    dtype_tr = torch.float16
    try: pipe.to("cuda")
    except Exception: pipe.enable_model_cpu_offload()

    for i in indices:
        steps = 18 if i == 0 else 15
        print(f"[*] GPU Rendering Beat {i} (480x832, 25f, {steps} steps)...", flush=True)
        g = torch.Generator(device="cpu").manual_seed(base_seed + i * 7)
        pe, npe = embeds[i][0].to("cuda", dtype=dtype_tr), embeds[i][1].to("cuda", dtype=dtype_tr)
        try:
            with torch.inference_mode():
                fr = pipe(prompt_embeds=pe, negative_prompt_embeds=npe, height=832, width=480, num_frames=25, num_inference_steps=steps, guidance_scale=5.0, generator=g).frames[0]
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache(); gc.collect(); pipe.enable_sequential_cpu_offload()
            with torch.inference_mode():
                fr = pipe(prompt_embeds=pe, negative_prompt_embeds=npe, height=832, width=480, num_frames=25, num_inference_steps=steps, guidance_scale=5.0, generator=g).frames[0]
        if is_black(fr):
            print(f"[!] Black output Beat {i} -> switching to fp32...", flush=True)
            dtype_tr = torch.float32
            pipe.transformer.to(dtype=torch.float32); pipe.enable_model_cpu_offload()
            torch.cuda.empty_cache(); gc.collect()
            pe, npe = embeds[i][0].to("cuda", dtype=torch.float32), embeds[i][1].to("cuda", dtype=torch.float32)
            with torch.inference_mode():
                fr = pipe(prompt_embeds=pe, negative_prompt_embeds=npe, height=832, width=480, num_frames=25, num_inference_steps=steps, guidance_scale=5.0, generator=torch.Generator(device="cpu").manual_seed(base_seed + i * 7)).frames[0]
            if is_black(fr): raise RuntimeError(f"Beat {i} rendered black even in fp32")
        print(f"[+] Beat {i} raw luma={float(np.asarray(fr[0], dtype=np.float32).mean()):.3f}", flush=True)
        export_to_video(fr, f"/tmp/raw_{i}.mp4", fps=16)
        torch.cuda.empty_cache(); gc.collect()
    del pipe, vae; gc.collect(); torch.cuda.empty_cache()

def prep_beat(raw_mp4, out_mp4, dur, idx):
    loop_f = f"[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0,loop=loop=3:size=60:start=0,trim=duration={dur:.3f},setpts=PTS-STARTPTS"
    if idx == 0:
        mv = "scale=1280:2275:flags=lanczos,crop=1080:1920:x='(iw-1080)/2+16*sin(t*24)+20*sin(t*1.6)':y='(ih-1920)/2+14*cos(t*20)'"
        gr = "eq=brightness='if(lt(t,0.12),0.14*(1-t/0.12),if(between(t,1.00,1.10),0.18,0.02))':contrast=1.15:saturation=1.22:eval=frame,unsharp=5:5:0.8:5:5:0.0,noise=alls=3:allf=t+u"
    elif idx == 3:
        mv = "scale=1220:2168:flags=lanczos,crop=1080:1920:x='(iw-1080)/2+28*sin(t*1.4)':y='(ih-1920)/2+16*cos(t*1.1)'"
        gr = "eq=brightness='if(lt(t,0.18),0.22*(1-t/0.18),0.02)':contrast=1.14:saturation=1.20:eval=frame,unsharp=5:5:0.75:5:5:0.0,noise=alls=3:allf=t+u"
    else:
        sx = 28 if idx % 2 else -28
        mv = f"scale=1200:2133:flags=lanczos,crop=1080:1920:x='(iw-1080)/2+{sx}*sin(t*1.2)':y='(ih-1920)/2+14*cos(t*0.9)'"
        gr = "eq=contrast=1.12:saturation=1.18:brightness=0.02,unsharp=5:5:0.75:5:5:0.0,noise=alls=3:allf=t+u"
    subprocess.run(["ffmpeg", "-y", "-i", raw_mp4, "-filter_complex", f"{loop_f},{mv},{gr},fps=24,format=yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "18", out_mp4], check=True)

def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        render_indices([int(x) for x in sys.argv[2].split(",")], json.load(open("/tmp/prompts.json", encoding="utf-8")), int(sys.argv[3]))
        return

    t0 = time.time()
    assets = find_assets()
    sc = json.load(open(os.path.join(assets, "current_script.json"), encoding="utf-8"))
    wav, ass_src = os.path.join(assets, "final_audio.wav"), os.path.join(assets, "subtitles.ass")
    total_dur = float(sc.get("total_duration") or probe_dur(wav))
    bt = sc.get("beat_times") or [[i * (total_dur / len(sc["beats"])), (i + 1) * (total_dur / len(sc["beats"]))] for i in range(len(sc["beats"]))]
    prompts = [b["ai_prompt"] for b in sc["beats"]]
    json.dump(prompts, open("/tmp/prompts.json", "w", encoding="utf-8"))
    base_seed = int(time.time()) % 90000

    encode_all_prompts(prompts)
    n_gpus = torch.cuda.device_count()
    print(f"[*] Detected {n_gpus} GPU(s)", flush=True)
    if n_gpus >= 2:
        p0 = subprocess.Popen([sys.executable, __file__, "--worker", "0,1,2", str(base_seed)], env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"})
        p1 = subprocess.Popen([sys.executable, __file__, "--worker", "3,4", str(base_seed)], env={**os.environ, "CUDA_VISIBLE_DEVICES": "1"})
        if p0.wait() != 0 or p1.wait() != 0: raise RuntimeError("Dual-GPU worker failed")
    else:
        render_indices(list(range(len(prompts))), prompts, base_seed)

    clips = []
    for i in range(len(prompts)):
        dur = max(1.6, (bt[i+1][0] - bt[i][0]) if i + 1 < len(bt) else (total_dur - bt[i][0]))
        prep_beat(f"/tmp/raw_{i}.mp4", f"/tmp/clip_{i}.mp4", dur, i)
        clips.append(f"/tmp/clip_{i}.mp4")

    shutil.rmtree("/tmp/hf_cache", ignore_errors=True)
    open("/tmp/list.txt", "w").write("\n".join(f"file '{c}'" for c in clips))
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "/tmp/list.txt", "-c", "copy", "/tmp/joined.mp4"], check=True)
    shutil.copyfile(ass_src, "render_subs.ass")
    vf = f"subtitles=render_subs.ass,drawbox=x=0:y=0:w='iw*min(1,t/{total_dur:.3f})':h=10:color=#E50914@0.95:t=fill"
    subprocess.run(["ffmpeg", "-y", "-i", "/tmp/joined.mp4", "-i", wav, "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-c:a", "aac", "-b:a", "192k", "-shortest", "final_output.mp4"], check=True)
    for f in glob.glob("/tmp/raw_*.mp4") + glob.glob("/tmp/clip_*.mp4") + ["/tmp/joined.mp4", "/tmp/embeds.pt", "/tmp/prompts.json", "render_subs.ass"]:
        if os.path.exists(f): os.remove(f)
    print(f"[+] Rendered 10/10 Video in {(time.time()-t0)/60:.1f} min!", flush=True)

if __name__ == "__main__":
    main()
