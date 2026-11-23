import os, sys, json, time, gc, shutil, textwrap, subprocess

os.environ["HF_HOME"] = "/tmp/hf_cache"
os.environ["TMPDIR"] = "/tmp"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

MODEL_ID = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"
WORK_DIR = "/tmp/work_long"
OUT_DIR = "/kaggle/working"


def ensure_packages():
    try:
        import PIL, numpy, torch, transformers, accelerate, ftfy  # noqa: F401
        from diffusers import WanPipeline, AutoencoderKLWan  # noqa: F401
    except Exception:
        print("[*] Installing diffusers/ftfy/pillow...", flush=True)
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "--upgrade", "diffusers", "transformers", "accelerate", "ftfy", "pillow", "numpy"],
            check=True,
        )


def run_cmd(cmd, desc="cmd"):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(f"{desc} failed:\n{p.stderr.decode('utf-8', 'ignore')[-900:]}")
    return p


def find_input(name):
    for root in ("/kaggle/input", "."):
        if os.path.exists(root):
            for cur, _, files in os.walk(root):
                if name in files:
                    return os.path.join(cur, name)
    return None


def probe_dur(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path])
    return float(out.decode("utf-8").strip())


def install_chunked_sdpa(chunk_size=512):
    import torch.nn.functional as F, torch

    orig = F.scaled_dot_product_attention

    def chunked(q, k, v, attn_mask=None, dropout_p=0.0, is_causal=False, scale=None, **kw):
        if scale is not None:
            kw["scale"] = scale
        ql = q.shape[-2]
        if ql <= chunk_size or is_causal or (attn_mask is not None and attn_mask.shape[-2] not in (1, ql)):
            return orig(q, k, v, attn_mask=attn_mask, dropout_p=dropout_p, is_causal=is_causal, **kw)
        outs = []
        for i in range(0, ql, chunk_size):
            ms = None if attn_mask is None else (attn_mask if attn_mask.shape[-2] == 1 else attn_mask[..., i : i + chunk_size, :])
            outs.append(orig(q[..., i : i + chunk_size, :], k, v, attn_mask=ms, dropout_p=dropout_p, is_causal=False, **kw))
        return torch.cat(outs, dim=-2)

    F.scaled_dot_product_attention = chunked


def save_np_video(arr, out_mp4, fps=16):
    import numpy as np

    u8 = np.ascontiguousarray((np.clip(arr, 0.0, 1.0) * 255.0).astype(np.uint8))
    luma = float(u8.mean())
    if luma < 2.5:
        return False, luma
    _, h, w, _ = u8.shape
    tmp = out_mp4 + ".tmp.mp4"
    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p", tmp]
    p = subprocess.run(cmd, input=u8.tobytes(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 5000:
        raise RuntimeError(f"Save failed: {p.stderr.decode('utf-8', 'ignore')[-400:]}")
    os.replace(tmp, out_mp4)
    return True, luma


def worker_main(gpu_idx, job_file):
    import torch
    from diffusers import AutoencoderKLWan, WanPipeline

    jobs = json.load(open(job_file, "r", encoding="utf-8"))
    if not jobs:
        return
    install_chunked_sdpa(512)
    vae = AutoencoderKLWan.from_pretrained(MODEL_ID, subfolder="vae", torch_dtype=torch.float32)
    pipe = WanPipeline.from_pretrained(MODEL_ID, vae=vae, torch_dtype=torch.bfloat16).to("cuda")
    neg = "static image, frozen frame, blurry, distorted anatomy, text, watermark, subtitle, logo, overexposed, shaky, low quality, cartoon"
    tail = ", cinematic 8k documentary cinematography, anamorphic lens, atmospheric depth, subtle slow camera motion, moody volumetric lighting"

    for i, job in enumerate(jobs, 1):
        out_p = job["out_mp4"]
        if os.path.exists(out_p) and os.path.getsize(out_p) > 10240:
            print(f"[GPU {gpu_idx}] [{i}/{len(jobs)}] Cached {os.path.basename(out_p)}", flush=True)
            continue
        t0 = time.time()
        ok = False
        for att in range(2):
            gen = torch.Generator(device="cuda").manual_seed(int(job["seed"]) + att * 777)
            out = pipe(prompt=job["prompt"].strip() + tail, negative_prompt=neg, height=480, width=832, num_frames=21, num_inference_steps=int(job["steps"]), guidance_scale=5.2, generator=gen, output_type="np")
            arr = out.frames[0]
            ok, luma = save_np_video(arr, out_p, 16)
            del out, arr
            gc.collect()
            torch.cuda.empty_cache()
            if ok:
                print(f"[GPU {gpu_idx}] [{i}/{len(jobs)}] {os.path.basename(out_p)} (luma={luma:.1f}, {time.time()-t0:.1f}s)", flush=True)
                break
        if not ok:
            raise RuntimeError(f"Dark clip failure: {out_p}")


def load_font(size):
    from PIL import ImageFont

    for fp in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()


def make_overlays(hud_png, card_png, ch_num, ch_title):
    from PIL import Image, ImageDraw

    hud = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hud)
    hd.rounded_rectangle([1525, 42, 1872, 92], radius=8, fill=(10, 15, 24, 170), outline=(56, 189, 248, 120), width=2)
    hd.ellipse([1543, 60, 1557, 74], fill=(239, 68, 68, 240))
    hd.text((1569, 56), f"SILENT SIGNAL  //  CH {ch_num:02d}", font=load_font(20), fill=(226, 232, 240, 235))
    hud.save(hud_png, "PNG")

    card = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    txt = (ch_title or f"Part {ch_num}").strip()
    if len(txt) > 48:
        txt = txt[:45].rstrip() + "..."
    cd.rounded_rectangle([80, 845, 1040, 990], radius=10, fill=(8, 12, 20, 205), outline=(56, 189, 248, 150), width=2)
    cd.rectangle([80, 857, 88, 978], fill=(56, 189, 248, 255))
    cd.text((110, 865), f"DOSSIER CHAPTER {ch_num:02d}", font=load_font(24), fill=(56, 189, 248, 255))
    cd.text((110, 903), txt.upper(), font=load_font(44), fill=(248, 250, 252, 255))
    card.save(card_png, "PNG")


def make_thumbnail(hero_clip, alt_clip, thumb_text, out_jpg, tmp_dir):
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

    src = hero_clip if os.path.exists(hero_clip) else alt_clip
    raw_png = os.path.join(tmp_dir, "thumb_raw.png")
    run_cmd(["ffmpeg", "-y", "-ss", "0.60", "-i", src, "-vframes", "1", raw_png], "Thumb frame")
    base = Image.open(raw_png).convert("RGB").resize((1280, 720), Image.Resampling.LANCZOS)
    base = ImageEnhance.Color(ImageEnhance.Contrast(base).enhance(1.22)).enhance(1.12).filter(ImageFilter.SHARPEN)
    ov = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for x in range(1280):
        od.line([(x, 0), (x, 720)], fill=(5, 9, 16, int(max(30, min(225, 225 - (x / 920.0) * 195)))))
    od.rectangle([18, 18, 1262, 702], outline=(56, 189, 248, 190), width=5)
    comp = Image.alpha_composite(base.convert("RGBA"), ov)
    d = ImageDraw.Draw(comp)
    d.rounded_rectangle([54, 52, 345, 100], radius=6, fill=(220, 38, 38, 235))
    d.text((70, 62), "SILENT SIGNAL", font=load_font(26), fill=(255, 255, 255, 255))
    lines = textwrap.wrap((thumb_text or "CLASSIFIED FILE").strip().upper(), width=14)[:3]
    f_big = load_font(92 if len(lines) <= 2 else 78)
    y, step = (210, 112) if len(lines) <= 2 else (170, 96)
    for idx, line in enumerate(lines):
        col = (250, 204, 21, 255) if idx == len(lines) - 1 else (255, 255, 255, 255)
        d.text((62, y + 6), line, font=f_big, fill=(0, 0, 0, 240))
        d.text((56, y), line, font=f_big, fill=col)
        y += step
    comp.convert("RGB").save(out_jpg, "JPEG", quality=95)


def build_hd_clip(raw_mp4, hd_mp4):
    if os.path.exists(hd_mp4) and os.path.getsize(hd_mp4) > 20000:
        return
    vf = "[0:v]split=2[f][r];[r]trim=start_frame=1:end_frame=20,setpts=PTS-STARTPTS,reverse[rv];[f][rv]concat=n=2:v=1:a=0,setpts=1.32*PTS,framerate=fps=30,scale=1920:1080:flags=lanczos,unsharp=5:5:0.7:5:5:0.0,colorbalance=rs=-0.04:gs=0.01:bs=0.06:rm=-0.02:bm=0.04,eq=contrast=1.06:saturation=0.90,vignette=PI/4.2,noise=alls=3:allf=t,format=yuv420p[v]"
    run_cmd(["ffmpeg", "-y", "-i", raw_mp4, "-filter_complex", vf, "-map", "[v]", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "15", "-pix_fmt", "yuv420p", hd_mp4], "HD clip")


def build_half(hd_clips, beat_dur, alt, out_mp4):
    xd, trs = 0.40, ["fade", "dissolve", "smoothleft", "fade"]
    inp, ch = [], []
    fx = "crop=iw*0.88:ih*0.88,scale=1920:1080:flags=lanczos,hflip,colorbalance=rs=0.03:gs=0.0:bs=-0.03," if alt else ""
    for i, cp in enumerate(hd_clips):
        inp.extend(["-i", cp])
        ch.append(f"[{i}:v]loop=loop=-1:size=160:start=0,trim=duration={beat_dur:.3f},setpts=PTS-STARTPTS,fps=30,{fx}format=yuv420p[b{i}]")
    prev = "b0"
    for j in range(1, 5):
        nxt = f"x{j}" if j < 4 else "vh"
        ch.append(f"[{prev}][b{j}]xfade=transition={trs[(j-1)%len(trs)]}:duration={xd:.2f}:offset={j*beat_dur-j*xd:.3f}[{nxt}]")
        prev = nxt
    hlen = 5.0 * beat_dur - 4.0 * xd
    run_cmd(["ffmpeg", "-y"] + inp + ["-filter_complex", ";".join(ch), "-map", "[vh]", "-t", f"{hlen:.3f}", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "15", "-pix_fmt", "yuv420p", out_mp4], "Half seg")
    return hlen


def build_chapter(idx, ch_dur, ch_title, hd_clips, v_enc, tmp_dir, out_mp4):
    xd = 0.40
    beat = (ch_dur + 9.0 * xd) / 10.0
    ha, hb = os.path.join(tmp_dir, f"c{idx}_a.mp4"), os.path.join(tmp_dir, f"c{idx}_b.mp4")
    la = build_half(hd_clips, beat, False, ha)
    build_half(hd_clips, beat, True, hb)
    hud_png, card_png = os.path.join(tmp_dir, f"hud_{idx}.png"), os.path.join(tmp_dir, f"card_{idx}.png")
    make_overlays(hud_png, card_png, idx + 1, ch_title)
    fc = (
        f"[0:v][1:v]xfade=transition=dissolve:duration={xd:.2f}:offset={max(0.5, la-xd):.3f},trim=duration={ch_dur:.3f},setpts=PTS-STARTPTS[base];"
        "[2:v]format=rgba[hud];[3:v]format=rgba,fade=t=in:st=0.2:d=0.45:alpha=1,fade=t=out:st=4.9:d=0.55:alpha=1[card];"
        "[base][hud]overlay=0:0:shortest=1[v1];[v1][card]overlay=0:0:enable='between(t,0.15,5.55)',format=yuv420p[vout]"
    )
    cmd = ["ffmpeg", "-y", "-i", ha, "-i", hb, "-loop", "1", "-t", f"{ch_dur:.3f}", "-i", hud_png, "-loop", "1", "-t", "5.60", "-i", card_png, "-filter_complex", fc, "-map", "[vout]", "-r", "30", "-t", f"{ch_dur:.3f}", "-video_track_timescale", "90000"] + v_enc + [out_mp4]
    run_cmd(cmd, f"Chapter {idx+1}")
    for p in (ha, hb):
        if os.path.exists(p):
            os.remove(p)


def coordinator_main():
    import torch
    from diffusers import AutoencoderKLWan, WanPipeline

    sp, ap = find_input("long_script.json"), find_input("long_audio.wav")
    if not sp or not ap:
        raise FileNotFoundError(f"Missing inputs script={sp} audio={ap}")
    meta = json.load(open(sp, "r", encoding="utf-8"))
    chapters = meta.get("chapters", [])
    total_dur = probe_dur(ap)

    for d in ("clips", "fx", "chapters"):
        os.makedirs(os.path.join(WORK_DIR, d), exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    _ = AutoencoderKLWan.from_pretrained(MODEL_ID, subfolder="vae", torch_dtype=torch.float32)
    _ = WanPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16)
    del _
    gc.collect()

    all_jobs, ch_map = [], []
    for ci, ch in enumerate(chapters):
        sc = [s for s in ch.get("scenes", []) if isinstance(s, str) and s.strip()]
        hero = (ch.get("hero_prompt") or "").strip()
        pr = ([hero] + sc[:4]) if (ch.get("hero_motion") and hero) else sc[:5]
        while len(pr) < 5:
            pr.append(hero or (pr[-1] if pr else "dark atmospheric classified facility"))
        c_files = []
        for si, p_txt in enumerate(pr[:5]):
            out_c = os.path.join(WORK_DIR, "clips", f"ch{ci:02d}_s{si:02d}.mp4")
            all_jobs.append({"out_mp4": out_c, "prompt": p_txt, "steps": 14 if (ci in (0, 5, 6) and si == 0) else 12, "seed": 4200 + ci * 100 + si * 13})
            c_files.append(out_c)
        ch_map.append(c_files)

    if torch.cuda.device_count() >= 2:
        jf0, jf1 = os.path.join(WORK_DIR, "j0.json"), os.path.join(WORK_DIR, "j1.json")
        json.dump(all_jobs[0::2], open(jf0, "w"))
        json.dump(all_jobs[1::2], open(jf1, "w"))
        p0 = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--worker", "0", jf0], env=dict(os.environ, CUDA_VISIBLE_DEVICES="0"))
        p1 = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--worker", "1", jf1], env=dict(os.environ, CUDA_VISIBLE_DEVICES="1"))
        p0.wait(), p1.wait()
    else:
        jf = os.path.join(WORK_DIR, "js.json")
        json.dump(all_jobs, open(jf, "w"))
        run_cmd([sys.executable, os.path.abspath(__file__), "--worker", "0", jf], "Single GPU")

    miss = [j for j in all_jobs if not os.path.exists(j["out_mp4"]) or os.path.getsize(j["out_mp4"]) < 10240]
    if miss:
        jfr = os.path.join(WORK_DIR, "jr.json")
        json.dump(miss, open(jfr, "w"))
        run_cmd([sys.executable, os.path.abspath(__file__), "--worker", "0", jfr], "Retry missing")

    hd_map = []
    for ci, raws in enumerate(ch_map):
        hds = []
        for si, rp in enumerate(raws):
            hp = os.path.join(WORK_DIR, "fx", f"ch{ci:02d}_s{si:02d}_hd.mp4")
            build_hd_clip(rp, hp)
            hds.append(hp)
        hd_map.append(hds)

    nv = subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1", "-c:v", "h264_nvenc", "-f", "null", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    v_enc = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "20", "-pix_fmt", "yuv420p"] if nv.returncode == 0 else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p"]

    raw_d = [max(20.0, float(c.get("duration") or (float(c.get("end_sec", 0)) - float(c.get("start_sec", 0))))) for c in chapters]
    ratio = total_dur / max(1.0, sum(raw_d))
    durs = [d * ratio for d in raw_d]
    durs[-1] += total_dur - sum(durs)

    ch_mp4s = []
    for ci, ch in enumerate(chapters):
        out_c = os.path.join(WORK_DIR, "chapters", f"ch_{ci:02d}.mp4")
        print(f"[*] Mastering Chapter {ci+1}/{len(chapters)} ({durs[ci]:.2f}s)...", flush=True)
        build_chapter(ci, durs[ci], ch.get("title") or ch.get("chapter_title") or f"Part {ci+1}", hd_map[ci], v_enc, os.path.join(WORK_DIR, "chapters"), out_c)
        ch_mp4s.append(out_c)

    ctxt = os.path.join(WORK_DIR, "concat.txt")
    with open(ctxt, "w", encoding="utf-8") as f:
        for cp in ch_mp4s:
            f.write(f"file '{cp}'\n")
    v_only = os.path.join(WORK_DIR, "v_master.mp4")
    run_cmd(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", ctxt, "-c", "copy", v_only], "Concat")

    final_mp4 = os.path.join(OUT_DIR, "long_final.mp4")
    run_cmd(["ffmpeg", "-y", "-i", v_only, "-i", ap, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-shortest", final_mp4], "Mux")
    make_thumbnail(ch_map[0][0], ch_map[min(5, len(ch_map) - 1)][0], meta.get("thumbnail_text") or meta.get("hook_text") or chapters[0].get("title"), os.path.join(OUT_DIR, "thumbnail.jpg"), WORK_DIR)
    shutil.rmtree(WORK_DIR, ignore_errors=True)
    print(f"[DONE] long_final.mp4 ({os.path.getsize(final_mp4)/(1024*1024):.1f} MB) & thumbnail.jpg ready!", flush=True)


if __name__ == "__main__":
    ensure_packages()
    if len(sys.argv) >= 4 and sys.argv[1] == "--worker":
        worker_main(int(sys.argv[2]), sys.argv[3])
    else:
        coordinator_main()
