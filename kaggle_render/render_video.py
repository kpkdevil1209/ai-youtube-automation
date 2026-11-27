import os, sys, re, json, time, glob, shutil, random, subprocess
from pathlib import Path

os.environ["HF_HOME"] = "/tmp/hf_cache"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
WORK = Path("/kaggle/working")
WORK.mkdir(parents=True, exist_ok=True)
SCRIPT_OUT, AUDIO_OUT, ASS_OUT, META_OUT, FINAL_OUT = WORK / "current_script.json", Path("/tmp/final_audio.wav"), Path("/tmp/subtitles.ass"), WORK / "beat_meta.json", WORK / "final_output.mp4"
LEAK_RE = re.compile(r"(under\s*\d+\s*chars?|characters?|clicky\s*title|file\s*#?\d*|#shorts?|hook_banner|pinned_question|title:|icy\s*cola|and\s+that\s+is\s+why)", re.I)

def sh(cmd, env=None):
    return subprocess.run(cmd, shell=isinstance(cmd, str), env=env, check=True)

def find_in(name):
    hits = glob.glob(f"/kaggle/input/**/{name}", recursive=True)
    return hits[0] if hits else (name if os.path.exists(name) else None)

def clean_title(raw, fb):
    t = re.sub(r"\s+", " ", LEAK_RE.sub("", str(raw or "")).strip(" -:|\"'()[]")).strip()
    if 10 <= len(t) <= 48: return t
    ws = [w for w in re.findall(r"[A-Za-z0-9'-]+", fb) if len(w) > 1][:5]
    return ("Why " + " ".join(ws) + " Stuns Experts")[:48]

def bad_script(d):
    if not isinstance(d, dict): return "not dict"
    t, b, ls, ss = str(d.get("title", "")), str(d.get("hook_banner", "")), d.get("lines") or [], d.get("shots") or []
    if LEAK_RE.search(t) or LEAK_RE.search(b) or not (8 <= len(t) <= 48): return "bad title/banner"
    if not (2 <= len(b.split()) <= 6) or len(ls) != 5 or len(ss) != 10: return "bad counts"
    tot, seen = 0, set()
    for i, x in enumerate(ls):
        s = str(x).strip(); ws = s.split()
        if LEAK_RE.search(s) or not s.endswith((".", "?", "!")) or not (4 <= len(ws) <= 12) or any(len(w) > 16 for w in ws): return f"bad line {i+1}"
        k = re.sub(r"[^a-z]", "", s.lower())
        if k in seen: return "dup line"
        seen.add(k); tot += len(ws)
    if not (30 <= tot <= 46) or any(len(str(x).split()) < 8 for x in ss): return f"words={tot}/shots"
    return ""

def stage1_script():
    import requests
    td = json.load(open(find_in("trending_topic.json"), encoding="utf-8")) if find_in("trending_topic.json") else {}
    topic = td.get("topic") or "Kola Superdeep Borehole"
    facts = re.sub(r"\s+", " ", td.get("fact_summary") or "At 12,262 meters underground in Russia, solid granite flowed like plastic at 180C and unexpected water appeared.").strip()[:1400]
    target_dur = round(random.uniform(14.15, 15.85), 2)
    sh("apt-get update -qq && apt-get install -y -qq zstd ffmpeg >/dev/null")
    sh("curl -fsSL https://ollama.com/download/ollama-linux-amd64.tar.zst | zstd -d -c | tar -x -C /usr")
    env = {**os.environ, "OLLAMA_MODELS": "/tmp/ollama_models", "OLLAMA_HOST": "127.0.0.1:11434", "CUDA_VISIBLE_DEVICES": "0"}
    srv = subprocess.Popen(["ollama", "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(25):
        try:
            if requests.get("http://127.0.0.1:11434/api/tags", timeout=2).status_code == 200: break
        except Exception: time.sleep(1)
    for r in range(3):
        try: sh(["ollama", "pull", "qwen2.5:14b"], env=env); break
        except Exception:
            if r == 2: raise
            time.sleep(5)
    def ask(prompt, fmt=None, temp=0.65):
        p = {"model": "qwen2.5:14b", "messages": [{"role": "user", "content": prompt}], "stream": False, "options": {"temperature": temp, "num_ctx": 4096}}
        if fmt: p["format"] = fmt
        r = requests.post("http://127.0.0.1:11434/api/chat", json=p, timeout=180); r.raise_for_status()
        return r.json()["message"]["content"]
    outline = ask(f"You are an elite mystery Shorts writer.\nFacts on '{topic}': {facts}\nWrite 3 ultra-short points:\n1. CONTRADICTION HOOK (max 8 words, no answer)\n2. FALSE ASSUMPTION (max 9 words)\n3. REAL SHOCKING TWIST & LOOP BACK TO HOOK (max 12 words)", temp=0.7)
    schema = {"type": "object", "properties": {"title": {"type": "string"}, "hook_banner": {"type": "string"}, "lines": {"type": "array", "items": {"type": "string"}}, "shots": {"type": "array", "items": {"type": "string"}}, "pinned_question": {"type": "string"}, "description": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}}, "required": ["title", "hook_banner", "lines", "shots", "pinned_question", "description", "tags"]}
    best, err = None, ""
    for _ in range(4):
        try:
            cand = json.loads(ask(f"Write a viral 15s Short from:\nTOPIC: {topic}\nFACTS: {facts}\nARC:\n{outline}\n" + (f"FIX: {err}\n" if err else "") + "Rules (never copy rule words into output):\n- title: 20-42 letters curiosity title (never mention chars or FILE #)\n- hook_banner: 3-5 bold uppercase words\n- lines: EXACTLY 5 simple spoken sentences, total 35-41 words, each ending in '.' or '?'. Line 1=unanswered shock hook, Line 2=clue, Line 3=false assumption, Line 4=mind-twist reveal, Line 5=haunting loop back to Line 1. Ban 'and that is why'.\n- shots: EXACTLY 10 distinct 9:16 classic 35mm documentary prompts (2 cuts/line, 12-18 words each, zero text in visuals)\n- pinned_question (<95 chars), description (2 factual sentences), tags (6 words)", fmt=schema, temp=0.55))
            cand["title"] = clean_title(cand.get("title", ""), topic)
            cand["hook_banner"] = LEAK_RE.sub("", str(cand.get("hook_banner", ""))).strip().upper()[:42]
            err = bad_script(cand)
            if not err: best = cand; break
            if best is None and len(cand.get("lines", [])) == 5 and len(cand.get("shots", [])) == 10: best = cand
        except Exception as e: err = str(e)
    srv.terminate(); shutil.rmtree("/tmp/ollama_models", ignore_errors=True)
    if best is None:
        best = {"title": clean_title("", topic), "hook_banner": "SEALED 12KM UNDERGROUND", "lines": ["Why did engineers suddenly seal Earth's deepest hole?", "At twelve kilometers down, steel drills struck boiling silence.", "Geologists expected dry solid granite beneath the crust.", "Instead, crushed rock flowed like plastic in trapped water.", "Nobody knows what pressure awaits any deeper below."], "shots": ["Extreme close-up rusted drill shaft descending into dark subterranean abyss, 35mm film", "Wide aerial abandoned Arctic concrete tower in heavy fog, archival film grain", "Glowing red molten rock fractures deep underground, thermal shimmer, matte shadows", "Macro analog pressure gauge needle shaking violently in dim red studio light", "Dark fractured ancient granite cavern lit by single narrow flashlight beam", "Water droplets seeping from superheated black rock deep underground, macro lens", "Warped shimmering stone bending under extreme subterranean pressure, dark documentary", "Heavy iron hatch welded shut with flying orange sparks over concrete shaft", "Rusted steel padlock frozen on chain fence in Arctic snowstorm, 35mm", "Vertigo shot looking straight down endless pitch black vertical shaft"], "pinned_question": "Would you go down if they reopened it?", "description": facts[:260], "tags": ["mystery", "science", "deep earth", "unexplained", "documentary", "facts"]}
    best.update({"topic": topic, "target_dur": target_dur})
    json.dump(best, open(SCRIPT_OUT, "w", encoding="utf-8"), indent=2)
    print("[Stage 1]", best["title"], "| target:", target_dur)
    return best

def stage2_audio(sdata):
    sh([sys.executable, "-m", "pip", "install", "-q", "uv"])
    uv, venv = shutil.which("uv") or "uv", "/tmp/cb_venv"
    shutil.rmtree(venv, ignore_errors=True)
    sh([uv, "venv", "--python", "3.11", venv])
    py = f"{venv}/bin/python"
    sh([uv, "pip", "install", "--python", py, "torch==2.6.0", "torchaudio==2.6.0", "--index-url", "https://download.pytorch.org/whl/cu124"])
    sh([uv, "pip", "install", "--python", py, "--extra-index-url", "https://download.pytorch.org/whl/cu124", "setuptools<82", "chatterbox-tts", "soundfile", "numpy", "edge-tts"])
    cb = "\n".join([
        "import os, re, json, asyncio, random, subprocess, numpy as np, soundfile as sf, perth",
        "if getattr(perth, 'PerthImplicitWatermarker', None) is None:",
        "    class _W: apply_watermark = lambda self, w, sample_rate=24000: w",
        "    perth.PerthImplicitWatermarker = _W",
        "from chatterbox.tts import ChatterboxTTS",
        "SR = 24000; d = json.load(open('/kaggle/working/current_script.json')); lines = d['lines']; td = float(d.get('target_dur', 15.0))",
        "m = ChatterboxTTS.from_pretrained(device='cuda')",
        "def trim(y, t=0.008):",
        "    idx = np.where(np.abs(y) > t)[0]",
        "    return y if not len(idx) else y[max(0, idx[0]-600):min(len(y), idx[-1]+1080)]",
        "async def efb(t, p): import edge_tts; await edge_tts.Communicate(t, 'en-US-AndrewMultilingualNeural', rate='+8%').save(p)",
        "cfgs, gaps, segs = [(0.68,0.40),(0.56,0.45),(0.60,0.42),(0.72,0.38),(0.62,0.42)], [0.12,0.09,0.16,0.10,0.0], []",
        "for i, txt in enumerate(lines):",
        r"    cl = re.sub(r'\s+', ' ', txt).strip(); cl = cl if cl.endswith(('.', '?', '!')) else cl + '.'",
        "    ex, cfg = cfgs[i]; ch = None",
        "    for _ in range(2):",
        "        arr = trim(m.generate(text=cl, exaggeration=ex, cfg_weight=cfg, temperature=0.74, repetition_penalty=1.22).squeeze().detach().cpu().numpy().astype(np.float32))",
        "        if 0.8 <= len(arr)/SR <= 5.2 and float(np.sqrt(np.mean(arr**2))) > 0.008: ch = arr; break",
        "    if ch is None:",
        "        asyncio.run(efb(cl, f'/tmp/fb{i}.mp3')); subprocess.run(['ffmpeg','-y','-i',f'/tmp/fb{i}.mp3','-ar',str(SR),'-ac','1',f'/tmp/fb{i}.wav'], check=True)",
        "        ch, _ = sf.read(f'/tmp/fb{i}.wav', dtype='float32'); ch = trim(ch)",
        "    pk = float(np.max(np.abs(ch))) or 1.0; segs.append(ch * (0.88 / pk))",
        "parts, rt, cur = [], [], 0.0",
        "for i, a in enumerate(segs):",
        "    du = len(a)/SR; rt.append({'text': lines[i], 'start': cur, 'end': cur+du}); parts.append(a); cur += du",
        "    if gaps[i] > 0: parts.append(np.zeros(int(SR*gaps[i]), np.float32)); cur += gaps[i]",
        "sf.write('/tmp/vr.wav', np.concatenate(parts), SR); rdur = sum(len(x) for x in parts)/SR",
        "tp = min(1.16, max(0.92, rdur/td)) if (rdur > 15.85 or rdur < 13.85) else 1.0",
        "subprocess.run(['ffmpeg','-y','-i','/tmp/vr.wav','-af',f'atempo={tp:.4f},highpass=f=75,equalizer=f=145:width_type=o:width=1.4:g=2.5,equalizer=f=4800:width_type=o:width=1.4:g=1.5','-ar','48000','-ac','1','/tmp/veq.wav'], check=True)",
        "veq, sr48 = sf.read('/tmp/veq.wav', dtype='float32'); vdur = len(veq)/sr48",
        "fdur = max(14.05, min(15.95, max(vdur + 0.12, td)))",
        "veq = np.concatenate([veq, np.zeros(int((fdur-vdur)*sr48), np.float32)]) if vdur < fdur else veq[:int(fdur*sr48)]",
        "fdur = len(veq)/sr48; sc = 1.0/tp; timings = [{'text': x['text'], 'start': round(x['start']*sc,3), 'end': round(x['end']*sc,3)} for x in rt]",
        "cuts = [random.uniform(1.32, 1.68) for _ in range(10)]; cs = sum(cuts); cuts = [round(c*fdur/cs, 3) for c in cuts]; cuts[-1] = round(cuts[-1] + fdur - sum(cuts), 3)",
        "t = np.linspace(0, fdur, len(veq), endpoint=False, dtype=np.float32)",
        "drone = (0.045*np.sin(2*np.pi*48*t) + 0.025*np.sin(2*np.pi*96*t)).astype(np.float32); sfx = np.zeros_like(veq); ct = 0.0",
        "for cd in cuts[:-1]:",
        "    ct += cd; p = int(ct*sr48); wl = int(0.18*sr48)",
        "    if p + wl < len(sfx):",
        "        wt = np.linspace(0, 0.18, wl, dtype=np.float32)",
        "        sfx[p:p+wl] += np.sin(np.pi*wt/0.18) * (0.06*np.random.randn(wl).astype(np.float32)*(0.4+wt*3) + 0.12*np.sin(2*np.pi*(65-25*wt/0.18)*wt))",
        "rp, rl = max(0, int((timings[3]['start']-0.55)*sr48)), int(0.55*sr48)",
        "if rp + rl < len(sfx): rt2 = np.linspace(0, 0.55, rl, dtype=np.float32); sfx[rp:rp+rl] += (rt2/0.55)**2 * 0.14 * np.sin(2*np.pi*(55+180*(rt2/0.55))*rt2)",
        "sf.write('/tmp/mix.wav', np.clip(veq+drone+sfx, -0.98, 0.98), sr48)",
        "subprocess.run(['ffmpeg','-y','-i','/tmp/mix.wav','-af','loudnorm=I=-14:TP=-1.5:LRA=7','-ar','48000','-ac','2','/tmp/final_audio.wav'], check=True)",
        "ft = lambda s: f'{int(s//3600)}:{int((s%3600)//60):02d}:{s%60:05.2f}'",
        "ass = ['[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 1080', 'PlayResY: 1920', '', '[V4+ Styles]', 'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding', 'Style: Pop,DejaVu Sans,70,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,5,2,2,50,50,510,1', 'Style: Accent,DejaVu Sans,74,&H0000E5FF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,5,2,2,50,50,510,1', '', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']",
        "for li, tm in enumerate(timings):",
        "    ws = tm['text'].split(); chs = [' '.join(ws[k:k+2]) for k in range(0, len(ws), 2)]",
        r"    wts = [max(2, len(re.sub(r'[^a-zA-Z]', '', c))) for c in chs]; wsum = sum(wts) or 1; sp = max(0.4, tm['end']-tm['start']); c0 = tm['start']",
        "    for ci, ch in enumerate(chs):",
        "        c1 = min(fdur-0.05, c0 + sp*wts[ci]/wsum); st = 'Accent' if li in (0,3) else 'Pop'",
        r"        ass.append(f'Dialogue: 0,{ft(c0)},{ft(c1)},{st},,0,0,0,,' + r'{\fscx114\fscy114\t(0,75,\fscx100\fscy100)}' + ch.upper()); c0 = c1",
        r"open('/tmp/subtitles.ass','w',encoding='utf-8').write('\n'.join(ass))",
        "json.dump({'total_dur': round(fdur,3), 'cut_durs': cuts, 'timings': timings}, open('/kaggle/working/beat_meta.json','w'), indent=2)",
        "print(f'[Stage 2] Chatterbox locked at {fdur:.2f}s across {len(cuts)} cuts')",
    ])
    open("/tmp/cb.py", "w", encoding="utf-8").write(cb)
    sh([py, "/tmp/cb.py"])
    shutil.rmtree(venv, ignore_errors=True); shutil.rmtree("/root/.cache/huggingface", ignore_errors=True); shutil.rmtree("/tmp/hf_cache", ignore_errors=True)
    return json.load(open(META_OUT, encoding="utf-8"))

def make_banner(text, outp):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (1080, 260), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle([60, 20, 1020, 240], radius=34, fill=(10, 14, 22, 215), outline=(255, 215, 0, 235), width=5)
    fp = next((p for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"] if os.path.exists(p)), None)
    font = ImageFont.truetype(fp, 58) if fp else ImageFont.load_default()
    lines, cur = [], ""
    for w in text.split():
        if len((cur + " " + w).strip()) > 20 and cur: lines.append(cur); cur = w
        else: cur = (cur + " " + w).strip()
    if cur: lines.append(cur)
    lines = lines[:2]; y0 = 72 if len(lines) == 2 else 95
    for i, ln in enumerate(lines):
        tw = d.textbbox((0, 0), ln, font=font)[2]
        d.text(((1080 - tw) // 2, y0 + i * 74), ln, font=font, fill=(255, 220, 40, 255) if i == 0 else (255, 255, 255, 255))
    img.save(outp)

def stage3_wan(sdata, meta):
    if subprocess.run([sys.executable, "-c", "import transformers,diffusers,peft,huggingface_hub; assert int(transformers.__version__.split('.')[0])<5"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        sh([sys.executable, "-m", "pip", "install", "-q", "--no-cache-dir", "diffusers>=0.32.2", "transformers>=4.49.0,<5.0.0", "peft>=0.14.0", "accelerate>=1.2.0", "huggingface_hub>=0.28.0", "imageio-ffmpeg", "pillow"])
    from huggingface_hub import snapshot_download
    snapshot_download("Wan-AI/Wan2.1-T2V-1.3B-Diffusers", local_dir="/tmp/wan_model")
    open("/tmp/enc.py", "w").write("\n".join([
        "import json, torch; from transformers import UMT5EncoderModel, AutoTokenizer",
        "shots = json.load(open('/kaggle/working/current_script.json'))['shots']",
        "tok = AutoTokenizer.from_pretrained('/tmp/wan_model', subfolder='tokenizer')",
        "enc = UMT5EncoderModel.from_pretrained('/tmp/wan_model', subfolder='text_encoder', torch_dtype=torch.bfloat16).to('cuda:0').eval()",
        "def e(t): x = tok([t], padding='max_length', max_length=226, truncation=True, return_tensors='pt').to('cuda:0'); return enc(x.input_ids, attention_mask=x.attention_mask)[0].cpu()",
        "with torch.no_grad(): pos = [e(s + ', vertical 9:16, classic 35mm Kodak film, matte documentary, chiaroscuro shadows, subtle film grain, smooth motion') for s in shots]; neg = e('text, watermark, letters, blurry, distorted, plastic CGI, neon, static')",
        "torch.save({'pos': pos, 'neg': neg}, '/tmp/pe.pt')",
    ]))
    sh([sys.executable, "/tmp/enc.py"])
    def worker(gpu, idxs):
        open(f"/tmp/w{gpu}.py", "w").write("\n".join([
            "import torch",
            "from diffusers import WanPipeline, AutoencoderKLWan",
            "from diffusers.schedulers.scheduling_unipc_multistep import UniPCMultistepScheduler",
            "from diffusers.utils import export_to_video",
            "pe = torch.load('/tmp/pe.pt', map_location='cpu', weights_only=False)",
            "vae = AutoencoderKLWan.from_pretrained('/tmp/wan_model', subfolder='vae', torch_dtype=torch.float32)",
            "pipe = WanPipeline.from_pretrained('/tmp/wan_model', vae=vae, text_encoder=None, tokenizer=None, torch_dtype=torch.float16)",
            "pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config, flow_shift=3.0)",
            "pipe.enable_model_cpu_offload(); pipe.vae.enable_tiling(); pipe.vae.enable_slicing(); neg = pe['neg'].to(dtype=torch.float16)",
            f"for i in {idxs}:",
            "    out = pipe(prompt_embeds=pe['pos'][i].to(dtype=torch.float16), negative_prompt_embeds=neg, height=832, width=480, num_frames=25, num_inference_steps=20, guidance_scale=5.5, generator=torch.Generator('cpu').manual_seed(4200+i*17)).frames[0]",
            "    export_to_video(out, f'/tmp/clip_{i}.mp4', fps=16)",
            "    print(f'[GPU] Done shot {i}', flush=True)",
        ]))
        env = {**os.environ, "CUDA_VISIBLE_DEVICES": str(gpu)}
        return subprocess.Popen([sys.executable, f"/tmp/w{gpu}.py"], env=env, stdout=open(f"/tmp/w{gpu}.log", "w"), stderr=subprocess.STDOUT)
    import torch
    if torch.cuda.device_count() >= 2:
        p0, p1 = worker(0, [0, 2, 4, 6, 8]), worker(1, [1, 3, 5, 7, 9])
        if p0.wait() != 0 or p1.wait() != 0:
            for g in (0, 1):
                if os.path.exists(f"/tmp/w{g}.log"): print(f"=== W{g} LOG ===\n" + "\n".join(open(f"/tmp/w{g}.log").read().splitlines()[-35:]))
            raise RuntimeError("GPU worker failed")
    else:
        if worker(0, list(range(10))).wait() != 0:
            print("=== W0 LOG ===\n" + "\n".join(open("/tmp/w0.log").read().splitlines()[-35:]))
            raise RuntimeError("GPU 0 worker failed")
    shutil.rmtree("/tmp/wan_model", ignore_errors=True); shutil.rmtree("/tmp/hf_cache", ignore_errors=True)
    segs = []
    for i, d in enumerate(meta["cut_durs"]):
        seg = f"/tmp/seg_{i}.mp4"; flp = ",hflip" if i % 2 else ""
        vf = f"setpts={d/1.5625:.4f}*PTS,fps=30,scale='trunc(1080*(1+0.09*t/{d:.3f})/2)*2':'trunc(1920*(1+0.09*t/{d:.3f})/2)*2':eval=frame:flags=lanczos,crop=1080:1920{flp},noise=alls=7:allf=t,unsharp=5:5:0.75:5:5:0.0,eq=contrast=1.08:saturation=1.05:gamma=1.04"
        sh(["ffmpeg", "-y", "-i", f"/tmp/clip_{i}.mp4", "-vf", vf, "-t", f"{d:.3f}", "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p", "-an", seg])
        segs.append(seg)
    open("/tmp/concat.txt", "w").write("\n".join(f"file '{s}'" for s in segs))
    sh(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "/tmp/concat.txt", "-c", "copy", "/tmp/vraw.mp4"])
    make_banner(sdata.get("hook_banner", "UNEXPLAINED SIGNAL"), "/tmp/banner.png")
    sh(["ffmpeg", "-y", "-i", "/tmp/vraw.mp4", "-
