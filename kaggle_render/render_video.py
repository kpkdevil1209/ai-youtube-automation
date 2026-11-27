import os, re, gc, json, time, shutil, random, subprocess, urllib.request

OUT = "/kaggle/working"
LEAK_RE = re.compile(
    r"(under \d+ chars|file #|icy cola|and that is why)", re.I
)
TOPICS = [
    "What happens inside your body if you swallow tiny magnets",
    "The 1986 balloon disaster that shut down an entire city",
    "Why airplane windows have a tiny pinhole near the bottom",
    "Why deep sea divers suddenly hear metallic knocking sounds",
    "The weird 1962 trick that kept a trapped miner alive",
    "Why modern skyscrapers sway on purpose during storms",
    "What happens to your brain in total zero-sound darkness",
    "How one tiny screw mistake locked a giant bank vault forever",
]


def sh(cmd, env=None, quiet=False):
    kw = {"shell": isinstance(cmd, str), "env": env, "check": True}
    if quiet:
        kw["stdout"] = subprocess.DEVNULL
        kw["stderr"] = subprocess.DEVNULL
    return subprocess.run(cmd, **kw)


def probe_dur(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
    ])
    return float(out.decode().strip())


def stage1_script():
    if not shutil.which("ollama"):
        sh(
            "which zstd >/dev/null || "
            "(apt-get update -qq && apt-get install -y -qq zstd)",
            quiet=True,
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
        "Style: fast Zack D Films curiosity Short. "
        "script: 3 punchy 5th-grade sentences (28 to 37 words total), "
        "instant 2-second hook and shocking twist at the end. "
        "hook: 3 to 5 uppercase words. "
        "title: intriguing, max 50 chars, no hashtags. "
        "description: 1 short intriguing sentence, no hashtags. "
        "tags: 5 lowercase strings. "
        "visual_prompts: 10 short 3D Pixar cartoon scene prompts."
    )
    best = None
    for k in range(3):
        body = json.dumps({
            "model": "qwen2.5:14b",
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.75},
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
        scr = re.sub(LEAK_RE, "", scr)
        scr = re.sub(r"\s+", " ", scr).strip()
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
            if 24 <= wc <= 42 and len(vp) >= 8:
                break
    if not best:
        raise RuntimeError("Stage 1 script validation failed")
    words = best["script"].split()
    if len(words) > 38:
        cut = " ".join(words[:38])
        p_idx = cut.rfind(".")
        best["script"] = (
            cut[:p_idx + 1] if p_idx > 80 else cut.rstrip(".") + "."
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
    d_txt = re.sub(LEAK_RE, "", str(best.get("description") or ""))
    best["description"] = d_txt.replace("#", "").strip()[:180] or topic
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
        "import os, sys, types, subprocess, soundfile as sf",
        "os.environ['TRANSFORMERS_ATTN_IMPLEMENTATION'] = 'eager'",
        "for n in ('spacy_pkuseg', 'gradio'):",
        "    if n not in sys.modules:",
        "        m = types.ModuleType(n)",
        "        m.pkuseg = lambda *a, **k: None",
        "        sys.modules[n] = m",
        "txt = open('/tmp/tts_txt.txt').read().strip()",
        "try:",
        "    import perth",
        "    if getattr(perth, 'PerthImplicitWatermarker', None) is None:",
        "        class _P:",
        "            def apply_watermark(self, w, **k): return w",
        "        perth.PerthImplicitWatermarker = _P",
        "    from chatterbox.tts import ChatterboxTTS",
        "    m = ChatterboxTTS.from_pretrained('cuda')",
        "    wav = m.generate(txt, exaggeration=0.55, cfg_weight=0.45)",
        "    sf.write('/tmp/voice_raw.wav', wav.squeeze().cpu().numpy(), m.sr)",
        "except Exception as e:",
        "    print('CB fallback edge-tts:', e)",
        "    subprocess.run([",
        "        sys.executable, '-m', 'edge_tts',",
        "        '--voice', 'en-US-AndrewMultilingualNeural',",
        "        '--text', txt, '--write-media', '/tmp/voice_raw.mp3'",
        "    ], check=True)",
        "    subprocess.run([",
        "        'ffmpeg', '-y', '-i', '/tmp/voice_raw.mp3',",
        "        '/tmp/voice_raw.wav'",
        "    ], check=True)",
    ]
    with open("/tmp/tts_txt.txt", "w") as f:
        f.write(sc["script"])
    with open("/tmp/cb_run.py", "w") as f:
        f.write("\n".join(cb_lines))
    sh([py, "/tmp/cb_run.py"])
    sh([
        "ffmpeg", "-y", "-i", "/tmp/voice_raw.wav",
        "-af",
        "silenceremove=start_periods=1:start_threshold=-42dB,"
        "areverse,silenceremove=start_periods=1:start_threshold=-42dB,"
        "areverse",
        "/tmp/voice_trim.wav",
    ], quiet=True)
    src = "/tmp/voice_trim.wav"
    d = probe_dur(src)
    if d < 2.0:
        src = "/tmp/voice_raw.wav"
        d = probe_dur(src)
    tgt = round(random.uniform(14.15, 15.85), 2)
    if 13.95 <= d <= 15.95:
        sh(["cp", src, "/tmp/voice.wav"])
        dur = d
    else:
        spd = max(0.75, min(1.55, d / tgt))
        sh([
            "ffmpeg", "-y", "-i", src,
            "-af", f"atempo={spd:.4f}", "/tmp/voice.wav",
        ], quiet=True)
        dur = probe_dur("/tmp/voice.wav")
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


def stage3_render(sc, meta):
    sh([
        "pip", "install", "-q", "--no-warn-script-location",
        "diffusers>=0.30.0", "transformers>=4.44,<5",
        "accelerate", "safetensors", "imageio[ffmpeg]",
    ])
    from huggingface_hub import hf_hub_download, snapshot_download

    rep = "ByteDance/AnimateDiff-Lightning"
    ckpt = "animatediff_lightning_8step_diffusers.safetensors"
    hf_hub_download(rep, ckpt)
    base_id = "stablediffusionapi/disney-pixar-cartoon"
    try:
        snapshot_download(base_id)
    except Exception:
        base_id = "Lykon/dreamshaper-8"
        snapshot_download(base_id)

    prompts = [
        f"3D Pixar animation style, studio cinematic lighting, "
        f"vivid depth, smooth dynamic action: {p}"
        for p in sc["visual_prompts"][:10]
    ]
    with open("/tmp/prompts.json", "w") as f:
        json.dump(prompts, f)

    w_lines = [
        "import sys, json, torch",
        "from diffusers import (",
        "    AnimateDiffPipeline, MotionAdapter, EulerDiscreteScheduler",
        ")",
        "from diffusers.utils import export_to_video",
        "from huggingface_hub import hf_hub_download",
        "from safetensors.torch import load_file",
        "rep = 'ByteDance/AnimateDiff-Lightning'",
        "ckpt = 'animatediff_lightning_8step_diffusers.safetensors'",
        "ad = MotionAdapter().to('cuda', torch.float16)",
        "ad.load_state_dict(",
        "    load_file(hf_hub_download(rep, ckpt), device='cuda')",
        ")",
        f"pipe = AnimateDiffPipeline.from_pretrained(",
        f"    '{base_id}', motion_adapter=ad, torch_dtype=torch.float16",
        f")",
        "pipe.scheduler = EulerDiscreteScheduler.from_config(",
        "    pipe.scheduler.config, timestep_spacing='trailing',",
        "    beta_schedule='linear'",
        ")",
        "if hasattr(pipe, 'enable_vae_slicing'): pipe.enable_vae_slicing()",
        "if hasattr(pipe, 'enable_attention_slicing'):",
        "    pipe.enable_attention_slicing()",
        "pipe.to('cuda')",
        "prompts = json.load(open('/tmp/prompts.json'))",
        "neg = 'blurry, distorted, deformed, watermark, text, 2d, flat'",
        "s, e = int(sys.argv[1]), int(sys.argv[2])",
        "for i in range(s, e):",
        "    g = torch.Generator('cuda').manual_seed(200 + i)",
        "    with torch.inference_mode():",
        "        fr = pipe(",
        "            prompt=prompts[i], negative_prompt=neg,",
        "            height=768, width=448, num_frames=16,",
        "            num_inference_steps=8, guidance_scale=1.5,",
        "            generator=g",
        "        ).frames[0]",
        "    export_to_video(fr, f'/tmp/c_{i}.mp4', fps=10)",
    ]
    with open("/tmp/w_anim.py", "w") as f:
        f.write("\n".join(w_lines))

    gpus = subprocess.check_output(["nvidia-smi", "-L"]).decode().splitlines()
    if len(gpus) >= 2:
        e0, e1 = os.environ.copy(), os.environ.copy()
        e0["CUDA_VISIBLE_DEVICES"] = "0"
        e1["CUDA_VISIBLE_DEVICES"] = "1"
        l0, l1 = open("/tmp/w0.log", "w"), open("/tmp/w1.log", "w")
        p0 = subprocess.Popen(
            ["python", "/tmp/w_anim.py", "0", "5"], env=e0, stdout=l0, stderr=l0
        )
        p1 = subprocess.Popen(
            ["python", "/tmp/w_anim.py", "5", "10"], env=e1, stdout=l1, stderr=l1
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
        sh(["python", "/tmp/w_anim.py", "0", "10"], env=e0)


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
        "Style: Pop,DejaVu Sans,70,&H0000FFFF,&H00000000,&H80000000,"
        "-1,1,5,2,2,40,40,420,1",
        "Style: Hook,DejaVu Sans,58,&H00FFFFFF,&H000000CC,&H99000000,"
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
        sp = dt / 1.6
        fparts.append(
            f"[{i}:v]setpts={sp:.4f}*PTS,framerate=fps=30,"
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"scale=w=trunc(iw*(1+0.05*t)/2)*2:h=-2:eval=frame,"
            f"crop=1080:1920,trim=duration={dt:.3f},"
            f"setpts=PTS-STARTPTS[v{i}]"
        )
        cats.append(f"[v{i}]")
    fparts.append(
        "".join(cats) + "concat=n=10:v=1:a=0,"
        "eq=contrast=1.07:saturation=1.14,"
        "noise=alls=4:allf=t+u,ass=/tmp/subs.ass,format=yuv420p[vout]"
    )
    fparts.append(
        "[10:a]aresample=44100,dynaudnorm,volume=1.1[va];"
        f"anoisesrc=c=brown:a=0.05:r=44100:d={dur:.2f},"
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
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stderr[-2000:])
        raise RuntimeError("Stage 4 ffmpeg failed")
    if os.path.getsize(f"{OUT}/final_output.mp4") < 100000:
        raise RuntimeError("final_output.mp4 too small")


if __name__ == "__main__":
    sh(["nvidia-smi", "-L"])
    s = stage1_script()
    m = stage2_audio(s)
    stage3_render(s, m)
    stage4_assemble(s, m)
