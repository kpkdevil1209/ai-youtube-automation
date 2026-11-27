import os, re, gc, json, time, shutil, random, subprocess, urllib.request

OUT = "/kaggle/working"
LEAK_RE = re.compile(
    r"(under \d+ chars|file #|icy cola|and that is why)", re.I
)
TOPICS = [
    "Why airplane windows have a tiny pinhole near the bottom",
    "The 1986 balloon launch disaster that paralyzed Cleveland",
    "What happens inside your body if you swallow a magnet",
    "Why deep sea divers hear strange metallic knocking sounds",
    "The silent 1962 survival trick that saved a trapped miner",
    "Why modern skyscrapers sway on purpose during storms",
    "How one tiny screw mistake locked an entire vault forever",
    "Why astronauts lose their sense of up and down in dark rooms",
]


def sh(cmd, env=None, quiet=False):
    kw = {"shell": isinstance(cmd, str), "env": env, "check": True}
    if quiet:
        kw["stdout"] = subprocess.DEVNULL
        kw["stderr"] = subprocess.DEVNULL
    return subprocess.run(cmd, **kw)


def stage1_script():
    if not shutil.which("ollama"):
        sh(
            "which zstd >/dev/null || "
            "(apt-get update -qq && apt-get install -y -qq zstd)"
        )
        sh(
            "curl -fsSL https://ollama.com/download/"
            "ollama-linux-amd64.tar.zst -o /tmp/olm.zst"
        )
        sh("zstd -d -c /tmp/olm.zst | tar -x -C /usr")
        sh("rm -f /tmp/olm.zst")
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "0"
    srv = subprocess.Popen(
        ["ollama", "serve"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        try:
            r = urllib.request.urlopen(
                "http://127.0.0.1:11434/api/tags", timeout=2
            )
            if r.status == 200:
                break
        except Exception:
            time.sleep(1)
    sh(["ollama", "pull", "qwen2.5:14b"], env=env, quiet=True)
    topic = random.choice(TOPICS)
    prompt = (
        "Return JSON with keys: topic, title, hook, description, "
        "tags, script, visual_prompts. "
        f"Topic: {topic}. "
        "Keep script short: 3 punchy sentences (30 to 40 words total), "
        "instant 2-second hook and shocking twist at the end. "
        "hook: 3 to 5 uppercase words. "
        "title: intriguing, max 50 chars, no hashtags. "
        "tags: 5 lowercase strings. "
        "visual_prompts: list of 10 short 3D CGI scene strings."
    )
    best = None
    for k in range(3):
        body = json.dumps({
            "model": "qwen2.5:14b",
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.7},
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            raw = json.loads(
                urllib.request.urlopen(req, timeout=180).read()
            )["response"]
            m = re.search(r"\{.*\}", raw, re.S)
            if not m:
                continue
            cand = json.loads(m.group(0))
        except Exception as e:
            print(f"S1 parse err {k}: {e}")
            continue
        scr = str(cand.get("script", "")).strip()
        scr = re.sub(r"\band that is why\b", "that is how", scr, flags=re.I)
        scr = re.sub(r"\s+", " ", scr)
        cand["script"] = scr
        vp = cand.get("visual_prompts") or []
        vp = [
            x.get("prompt") or x.get("description") or str(x)
            if isinstance(x, dict) else str(x)
            for x in vp if x
        ]
        cand["visual_prompts"] = vp
        wc = len(scr.split())
        print(f"S1 try {k}: wc={wc} vp={len(vp)}")
        if wc >= 15 and len(vp) >= 3:
            best = cand
            if 24 <= wc <= 46 and len(vp) >= 8:
                break
    if not best:
        raise RuntimeError("Stage 1 script validation failed")
    words = best["script"].split()
    if len(words) > 42:
        cut = " ".join(words[:42])
        p_idx = cut.rfind(".")
        best["script"] = (
            cut[:p_idx + 1] if p_idx > 90 else cut.rstrip(".") + "."
        )
    vp = best["visual_prompts"][:10]
    angs = ["wide angle ", "close-up ", "dramatic overhead ", "low angle "]
    idx = 0
    while len(vp) < 10:
        vp.append(angs[idx % 4] + vp[idx % len(vp)])
        idx += 1
    best["visual_prompts"] = vp
    best["topic"] = str(best.get("topic") or topic)[:80]
    t = re.sub(LEAK_RE, "", str(best.get("title") or topic))
    best["title"] = t.replace("#", "").strip()[:58] or topic[:58]
    hk = str(best.get("hook") or "WAIT FOR THE END").upper()[:36]
    best["hook"] = re.sub(r"[{}\r\n]", "", hk)
    if not isinstance(best.get("tags"), list) or not best["tags"]:
        best["tags"] = ["shorts", "science", "mystery", "facts", "3d"]
    srv.terminate()
    srv.wait()
    shutil.rmtree("/root/.ollama", ignore_errors=True)
    with open(f"{OUT}/current_script.json", "w") as f:
        json.dump(best, f, indent=2)
    return best


def stage2_audio(sc):
    uv = shutil.which("uv") or "/root/.local/bin/uv"
    if not os.path.exists(uv):
        sh("curl -LsSf https://astral.sh/uv/install.sh | sh", quiet=True)
    ve = "/tmp/cb_venv"
    py = f"{ve}/bin/python"
    if not os.path.exists(py):
        sh([uv, "venv", ve, "--python", "3.11"], quiet=True)
        sh([
            uv, "pip", "install", "--python", py,
            "numpy>=1.24.0,<2.0.0", "setuptools<82", "wheel",
        ], quiet=True)
        sh([
            uv, "pip", "install", "--python", py,
            "--index-url", "https://download.pytorch.org/whl/cu124",
            "torch==2.6.0", "torchaudio==2.6.0",
        ], quiet=True)
        try:
            sh([
                uv, "pip", "install", "--python", py,
                "--no-build-isolation",
                "chatterbox-tts", "soundfile", "edge-tts",
            ], quiet=True)
        except Exception:
            sh([
                uv, "pip", "install", "--python", py, "--no-deps",
                "chatterbox-tts",
            ], quiet=True)
            sh([
                uv, "pip", "install", "--python", py,
                "transformers==4.46.3", "diffusers==0.29.0",
                "conformer==0.3.2", "s3tokenizer", "librosa==0.11.0",
                "pyloudnorm", "resemble-perth", "omegaconf", "einops",
                "safetensors", "huggingface_hub", "soundfile",
                "scipy", "edge-tts",
            ], quiet=True)
    cb_lines = [
        "import os, sys, types, soundfile as sf",
        "os.environ['TRANSFORMERS_ATTN_IMPLEMENTATION'] = 'eager'",
        "for n in ('spacy_pkuseg', 'gradio'):",
        "    if n not in sys.modules:",
        "        m = types.ModuleType(n)",
        "        m.pkuseg = lambda *a, **k: None",
        "        sys.modules[n] = m",
        "import perth",
        "if getattr(perth, 'PerthImplicitWatermarker', None) is None:",
        "    class _P:",
        "        def apply_watermark(self, w, **k): return w",
        "    perth.PerthImplicitWatermarker = _P",
        "from chatterbox.tts import ChatterboxTTS",
        "txt = open('/tmp/tts_txt.txt').read().strip()",
        "m = ChatterboxTTS.from_pretrained('cuda')",
        "wav = m.generate(txt, exaggeration=0.55, cfg_weight=0.45)",
        "sf.write('/tmp/voice_raw.wav', wav.squeeze().cpu().numpy(), m.sr)",
    ]
    with open("/tmp/tts_txt.txt", "w") as f:
        f.write(sc["script"])
    with open("/tmp/cb_run.py", "w") as f:
        f.write("\n".join(cb_lines))
    sh([py, "/tmp/cb_run.py"])
    sh([
        "ffmpeg", "-y", "-i", "/tmp/voice_raw.wav",
        "-af", "silenceremove=start_periods=1:start_threshold=-42dB",
        "/tmp/voice_trim.wav",
    ], quiet=True)
    src = "/tmp/voice_trim.wav"
    d = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", src,
    ]).decode().strip())
    if d < 2.0:
        src = "/tmp/voice_raw.wav"
        d = float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", src,
        ]).decode().strip())
    tgt = round(random.uniform(14.15, 15.85), 2)
    if 13.95 <= d <= 15.95:
        sh(["cp", src, "/tmp/voice.wav"])
        dur = d
    else:
        spd = max(0.80, min(1.30, d / tgt))
        sh([
            "ffmpeg", "-y", "-i", src,
            "-af", f"atempo={spd:.4f}", "/tmp/voice.wav",
        ], quiet=True)
        dur = float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", "/tmp/voice.wav",
        ]).decode().strip())
    shutil.rmtree(ve, ignore_errors=True)
    words = sc["script"].split()
    cuts = [round(dur * i / 10.0, 3) for i in range(11)]
    beats = []
    wt = 0.0
    step = dur / max(1, len(words))
    for i in range(0, len(words), 2):
        chunk = " ".join(words[i:i + 2])
        end = min(dur, (i + 2) * step)
        beats.append({"t": round(wt, 3), "e": round(end, 3), "w": chunk})
        wt = end
    meta = {"dur": round(dur, 3), "cuts": cuts, "beats": beats}
    with open(f"{OUT}/beat_meta.json", "w") as f:
        json.dump(meta, f, indent=2)
    return meta


def stage3_wan(sc, meta):
    sh([
        "pip", "install", "-q", "diffusers>=0.32.2",
        "transformers>=4.49,<5", "accelerate", "ftfy",
        "sentencepiece", "imageio[ffmpeg]",
    ], quiet=True)
    import torch
    from huggingface_hub import snapshot_download
    from transformers import AutoTokenizer, UMT5EncoderModel
    from diffusers import WanPipeline

    mid = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"
    snapshot_download(mid)
    prompts = [
        f"Stylized 3D Pixar-like CGI cinematic scene, dramatic "
        f"volumetric lighting, dynamic camera motion: {p}"
        for p in sc["visual_prompts"][:10]
    ]
    neg = (
        "blurry, static, watermark, text, subtitle, distorted, "
        "overexposed, low quality"
    )
    tok = AutoTokenizer.from_pretrained(mid, subfolder="tokenizer")
    te = UMT5EncoderModel.from_pretrained(
        mid, subfolder="text_encoder", torch_dtype=torch.bfloat16
    ).to("cuda:0")
    ep = WanPipeline(
        tokenizer=tok, text_encoder=te,
        vae=None, scheduler=None, transformer=None,
    )
    with torch.no_grad():
        embs = [
            tuple(x.cpu() for x in ep.encode_prompt(
                p, neg, True, device="cuda:0"
            ))
            for p in prompts
        ]
    torch.save(embs, "/tmp/embs.pt")
    del ep, te, tok, embs
    gc.collect()
    torch.cuda.empty_cache()

    w_lines = [
        "import sys, torch, torch.nn.functional as F",
        "from diffusers import (",
        "    AutoencoderKLWan, WanPipeline,",
        "    WanTransformer3DModel, UniPCMultistepScheduler",
        ")",
        "from diffusers.utils import export_to_video",
        "_sd = F.scaled_dot_product_attention",
        "def _cs(q, k, v, attn_mask=None, dropout_p=0.0,",
        "        is_causal=False, **kw):",
        "    if attn_mask is not None or is_causal or q.shape[-2] <= 512:",
        "        return _sd(q, k, v, attn_mask, dropout_p, is_causal, **kw)",
        "    out = [",
        "        _sd(q[..., i:i+512, :], k, v, None, dropout_p, False, **kw)",
        "        for i in range(0, q.shape[-2], 512)",
        "    ]",
        "    return torch.cat(out, dim=-2)",
        "F.scaled_dot_product_attention = _cs",
        "mid = 'Wan-AI/Wan2.1-T2V-1.3B-Diffusers'",
        "vae = AutoencoderKLWan.from_pretrained(",
        "    mid, subfolder='vae', torch_dtype=torch.float32",
        ")",
        "tr = WanTransformer3DModel.from_pretrained(",
        "    mid, subfolder='transformer', torch_dtype=torch.bfloat16",
        ")",
        "sch = UniPCMultistepScheduler.from_pretrained(",
        "    mid, subfolder='scheduler'",
        ")",
        "sch = UniPCMultistepScheduler.from_config(sch.config, flow_shift=3.0)",
        "pipe = WanPipeline(",
        "    tokenizer=None, text_encoder=None,",
        "    vae=vae, scheduler=sch, transformer=tr",
        ")",
        "pipe.text_encoder = type('D', (), {'dtype': torch.bfloat16})()",
        "pipe.vae.enable_tiling()",
        "pipe.vae.enable_slicing()",
        "pipe.to('cuda')",
        "embs = torch.load('/tmp/embs.pt', map_location='cpu',",
        "                  weights_only=True)",
        "s, e = int(sys.argv[1]), int(sys.argv[2])",
        "for i in range(s, e):",
        "    pe, ne = embs[i]",
        "    g = torch.Generator('cuda').manual_seed(100 + i)",
        "    with torch.no_grad():",
        "        fr = pipe(",
        "            prompt_embeds=pe.to('cuda'),",
        "            negative_prompt_embeds=ne.to('cuda'),",
        "            height=832, width=480, num_frames=25,",
        "            num_inference_steps=20, guidance_scale=5.0,",
        "            generator=g",
        "        ).frames[0]",
        "    export_to_video(fr, f'/tmp/c_{i}.mp4', fps=16)",
    ]
    with open("/tmp/w_wan.py", "w") as f:
        f.write("\n".join(w_lines))

    gpus = subprocess.check_output(["nvidia-smi", "-L"]).decode().splitlines()
    if len(gpus) >= 2:
        e0, e1 = os.environ.copy(), os.environ.copy()
        e0["CUDA_VISIBLE_DEVICES"] = "0"
        e1["CUDA_VISIBLE_DEVICES"] = "1"
        l0, l1 = open("/tmp/w0.log", "w"), open("/tmp/w1.log", "w")
        p0 = subprocess.Popen(
            ["python", "/tmp/w_wan.py", "0", "5"], env=e0, stdout=l0, stderr=l0
        )
        p1 = subprocess.Popen(
            ["python", "/tmp/w_wan.py", "5", "10"], env=e1, stdout=l1, stderr=l1
        )
        rc0, rc1 = p0.wait(), p1.wait()
        l0.close()
        l1.close()
        if rc0 != 0 or rc1 != 0:
            print("=== W0 ===", *open("/tmp/w0.log").readlines()[-40:])
            print("=== W1 ===", *open("/tmp/w1.log").readlines()[-40:])
            raise RuntimeError("GPU worker failed")
    else:
        e0 = os.environ.copy()
        e0["CUDA_VISIBLE_DEVICES"] = "0"
        sh(["python", "/tmp/w_wan.py", "0", "10"], env=e0)


def fmt_t(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s - h * 3600 - m * 60
    return f"{h}:{m:02d}:{sec:05.2f}"


def stage4_assemble(sc, meta):
    dur = meta["dur"]
    cuts = meta["cuts"]
    ass = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, "
        "OutlineColour, BackColour, Bold, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Pop,Arial,74,&H0000FFFF,&H00000000,&H80000000,"
        "-1,1,5,2,2,40,40,420,1",
        "Style: Hook,Arial,64,&H00FFFFFF,&H000000CC,&H99000000,"
        "-1,3,6,0,8,50,50,240,1",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, "
        "MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 1,0:00:00.00,0:00:02.20,Hook,,0,0,0,,{sc['hook']}",
    ]
    for b in meta["beats"]:
        t0, t1 = fmt_t(b["t"]), fmt_t(b["e"])
        txt = b["w"].replace("{", "").replace("}", "").upper()
        ass.append(
            f"Dialogue: 0,{t0},{t1},Pop,,0,0,0,,"
            "{\\fscx92\\fscy92\\t(0,90,\\fscx108\\fscy108)}" + txt
        )
    with open("/tmp/subs.ass", "w") as f:
        f.write("\n".join(ass))

    ins, fparts, cats = [], [], []
    for i in range(10):
        ins.extend(["-i", f"/tmp/c_{i}.mp4"])
        dt = max(0.8, cuts[i + 1] - cuts[i])
        sp = dt / 1.5625
        fparts.append(
            f"[{i}:v]setpts={sp:.4f}*PTS,fps=30,"
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"scale=w=trunc(iw*(1+0.05*t)/2)*2:h=-2:eval=frame,"
            f"crop=1080:1920,trim=duration={dt:.3f},"
            f"setpts=PTS-STARTPTS[v{i}]"
        )
        cats.append(f"[v{i}]")
    fparts.append(
        "".join(cats) + "concat=n=10:v=1:a=0,"
        "eq=contrast=1.06:saturation=1.12,"
        "noise=alls=4:allf=t+u,ass=/tmp/subs.ass,format=yuv420p[vout]"
    )
    fparts.append(
        "[10:a]dynaudnorm,volume=1.1[va];"
        f"anoisesrc=color=brown:d={dur:.2f}:a=0.05,"
        "lowpass=f=105[bg];"
        "[va][bg]amix=inputs=2:duration=first[aout]"
    )
    cmd = (
        ["ffmpeg", "-y"] + ins + ["-i", "/tmp/voice.wav"]
        + ["-filter_complex", ";".join(fparts)]
        + ["-map", "[vout]", "-map", "[aout]", "-t", f"{dur:.3f}"]
        + ["-c:v", "libx264", "-preset", "fast", "-crf", "20"]
        + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
        + [f"{OUT}/final_output.mp4"]
    )
    sh(cmd, quiet=True)
    if os.path.getsize(f"{OUT}/final_output.mp4") < 100000:
        raise RuntimeError("final_output.mp4 too small")


if __name__ == "__main__":
    s = stage1_script()
    m = stage2_audio(s)
    stage3_wan(s, m)
    stage4_assemble(s, m)
