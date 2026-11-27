import os, sys, re, json, time, glob, shutil, random, subprocess
from pathlib import Path

os.environ["HF_HOME"], os.environ["TOKENIZERS_PARALLELISM"] = "/tmp/hf_cache", "false"
WORK = Path("/kaggle/working")
WORK.mkdir(parents=True, exist_ok=True)
SCRIPT_OUT, AUDIO_OUT = WORK / "current_script.json", Path("/tmp/final_audio.wav")
META_OUT, FINAL_OUT = WORK / "beat_meta.json", WORK / "final_output.mp4"
LEAK_RE = re.compile(
    r"(under\s*\d+\s*chars?|characters?|clicky\s*title|file\s*#?\d*|"
    r"#shorts?|hook_banner|pinned_question|title:|icy\s*cola|and\s+that\s+is\s+why)", re.I
)

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
    t, b = str(d.get("title", "")), str(d.get("hook_banner", ""))
    ls, ss = d.get("lines") or [], d.get("shots") or []
    if LEAK_RE.search(t) or LEAK_RE.search(b) or not (8 <= len(t) <= 48): return "title"
    if not (2 <= len(b.split()) <= 6) or len(ls) != 5 or len(ss) != 10: return "counts"
    tot, seen = 0, set()
    for i, x in enumerate(ls):
        s = str(x).strip(); ws = s.split()
        if LEAK_RE.search(s) or not s.endswith((".", "?", "!")) or not (4 <= len(ws) <= 12):
            return f"line {i+1}"
        if any(len(w) > 16 for w in ws): return f"word {i+1}"
        k = re.sub(r"[^a-z]", "", s.lower())
        if k in seen: return "dup"
        seen.add(k); tot += len(ws)
    if not (30 <= tot <= 46) or any(len(str(x).split()) < 8 for x in ss): return "len"
    return ""

def stage1_script():
    import requests
    tp = find_in("trending_topic.json")
    td = json.load(open(tp, encoding="utf-8")) if tp else {}
    topic = td.get("topic") or "Kola Superdeep Borehole"
    fb = "At 12,262 meters underground in Russia, rock flowed like plastic at 180C."
    facts = re.sub(r"\s+", " ", td.get("fact_summary") or fb).strip()[:1400]
    tdur = round(random.uniform(14.15, 15.85), 2)
    sh("apt-get update -qq && apt-get install -y -qq zstd ffmpeg >/dev/null")
    sh("curl -fsSL https://ollama.com/download/ollama-linux-amd64.tar.zst | zstd -d -c | tar -x -C /usr")
    env = {**os.environ, "OLLAMA_MODELS": "/tmp/olm", "OLLAMA_HOST": "127.0.0.1:11434", "CUDA_VISIBLE_DEVICES": "0"}
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
    def ask(pr, fmt=None, temp=0.65):
        p = {"model": "qwen2.5:14b", "messages": [{"role": "user", "content": pr}], "stream": False, "options": {"temperature": temp, "num_ctx": 4096}}
        if fmt: p["format"] = fmt
        res = requests.post("http://127.0.0.1:11434/api/chat", json=p, timeout=180)
        res.raise_for_status()
        return res.json()["message"]["content"]
    arc = ask(f"Facts on '{topic}': {facts}\nWrite 3 ultra-short lines:\n1. CONTRADICTION HOOK (max 8 words, no answer)\n2. FALSE ASSUMPTION (max 9 words)\n3. SHOCKING TWIST & LOOP TO HOOK (max 12 words)", temp=0.7)
    arr_s, str_s = {"type": "array", "items": {"type": "string"}}, {"type": "string"}
    sch = {"type": "object", "properties": {"title": str_s, "hook_banner": str_s, "lines": arr_s, "shots": arr_s, "pinned_question": str_s, "description": str_s, "tags": arr_s}, "required": ["title", "hook_banner", "lines", "shots", "pinned_question", "description", "tags"]}
    best, err = None, ""
    for _ in range(4):
        try:
            pr = f"Write 15s Short from:\nTOPIC:{topic}\nFACTS:{facts}\nARC:{arc}\n" + (f"FIX:{err}\n" if err else "") + "Rules (never leak rule words):\n- title: 20-42 letters curiosity title (no FILE # or chars)\n- hook_banner: 3-5 bold uppercase words\n- lines: EXACTLY 5 sentences, total 35-41 words, end with '.' or '?'. L1=shock hook, L2=clue, L3=false guess, L4=mind twist, L5=loop back to L1. Ban 'and that is why'.\n- shots: EXACTLY 10 distinct 9:16 35mm documentary prompts (12-18 words each, no text)\n- pinned_question (<95 chars), description (2 lines), tags (6)"
            cand = json.loads(ask(pr, fmt=sch, temp=0.55))
            cand["title"] = clean_title(cand.get("title", ""), topic)
            cand["hook_banner"] = LEAK_RE.sub("", str(cand.get("hook_banner", ""))).strip().upper()[:42]
            err = bad_script(cand)
            if not err: best = cand; break
            if best is None and len(cand.get("lines", [])) == 5 and len(cand.get("shots", [])) == 10: best = cand
        except Exception as e: err = str(e)
    srv.terminate(); shutil.rmtree("/tmp/olm", ignore_errors=True)
    if best is None:
        best = {"title": clean_title("", topic), "hook_banner": "SEALED 12KM DOWN", "lines": ["Why did engineers seal Earth's deepest hole?", "At twelve kilometers down, steel drills struck silence.", "Experts expected dry granite beneath the crust.", "Instead, hot rock flowed like liquid plastic.", "Nobody knows what pressure waits deeper below."], "shots": [f"Cinematic 35mm documentary shot {k+1} of {topic}, dark shadows, analog film grain, moody light" for k in range(10)], "pinned_question": "Would you go down if it reopened?", "description": facts[:260], "tags": ["mystery", "science", "unexplained", "facts"]}
    best.update({"topic": topic, "target_dur": tdur})
    json.dump(best, open(SCRIPT_OUT, "w", encoding="utf-8"), indent=2)
    print("[Stage 1]", best["title"], "| target:", tdur)
    return best

def stage2_audio():
    sh([sys.executable, "-m", "pip", "install", "-q", "uv"])
    uv, venv = shutil.which("uv") or "uv", "/tmp/cb_venv"
    shutil.rmtree(venv, ignore_errors=True)
    sh([uv, "venv", "--python", "3.11", venv])
    py, cu = f"{venv}/bin/python", "https://download.pytorch.org/whl/cu124"
    sh([uv, "pip", "install", "--python", py, "torch==2.6.0", "torchaudio==2.6.0", "--index-url", cu])
    sh([uv, "pip", "install", "--python", py, "--extra-index-url", cu, "setuptools<82", "chatterbox-tts", "soundfile", "numpy", "edge-tts"])
    cb = "\n".join([
        "import os, re, json, asyncio, random, subprocess, numpy as np, soundfile as sf, perth",
        "if getattr(perth, 'PerthImplicitWatermarker', None) is None:",
        "    class _W: apply_watermark = lambda self, w, sample_rate=24000: w",
        "    perth.PerthImplicitWatermarker = _W",
        "from chatterbox.tts import ChatterboxTTS",
        "SR = 24000; d = json.load(open('/kaggle/working/current_script.json'))",
        "lines, td = d['lines'], float(d.get('target_dur', 15.0))",
        "m = ChatterboxTTS.from_pretrained(device='cuda')",
        "trim = lambda y: y if not len(np.where(np.abs(y)>0.008)[0]) else y[max(0,np.where(np.abs(y)>0.008)[0][0]-600):min(len(y),np.where(np.abs(y)>0.008)[0][-1]+1080)]",
        "async def efb(t, p): import edge_tts; await edge_tts.Communicate(t, 'en-US-AndrewMultilingualNeural', rate='+8%').save(p)",
        "cfgs, gaps, segs = [(0.68,0.4),(0.56,0.45),(0.6,0.42),(0.72,0.38),(0.62,0.42)], [0.12,0.09,0.16,0.1,0.0], []",
        "for i, txt in enumerate(lines):",
        r"    cl = re.sub(r'\s+', ' ', txt).strip(); cl = cl if cl.endswith(('.','?','!')) else cl+'.'",
        "    ex, cfg = cfgs[i]; ch = None",
        "    for _ in range(2):",
        "        a = trim(m.generate(text=cl, exaggeration=ex, cfg_weight=cfg, temperature=0.74, repetition_penalty=1.22).squeeze().detach().cpu().numpy().astype(np.float32))",
        "        if 0.8 <= len(a)/SR <= 5.2 and float(np.sqrt(np.mean(a**2))) > 0.008: ch = a; break",
        "    if ch is None:",
        "        asyncio.run(efb(cl, f'/tmp/f{i}.mp3')); subprocess.run(['ffmpeg','-y','-i',f'/tmp/f{i}.mp3','-ar',str(SR),'-ac','1',f'/tmp/f{i}.wav'], check=True)",
        "        ch, _ = sf.read(f'/tmp/f{i}.wav', dtype='float32'); ch = trim(ch)",
        "    segs.append(ch * (0.88 / (float(np.max(np.abs(ch))) or 1.0)))",
        "parts, rt, cur = [], [], 0.0",
        "for i, a in enumerate(segs):",
        "    du = len(a)/SR; rt.append({'text': lines[i], 'start': cur, 'end': cur+du}); parts.append(a); cur += du",
        "    if gaps[i] > 0: parts.append(np.zeros(int(SR*gaps[i]), np.float32)); cur += gaps[i]",
        "sf.write('/tmp/vr.wav', np.concatenate(parts), SR); rdur = sum(len(x) for x in parts)/SR",
        "tp = min(1.16, max(0.92, rdur/td)) if (rdur > 15.85 or rdur < 13.85) else 1.0",
        "af = f'atempo={tp:.4f},highpass=f=75,equalizer=f=145:width_type=o:width=1.4:g=2.5,equalizer=f=4800:width_type=o:width=1.4:g=1.5'",
        "subprocess.run(['ffmpeg','-y','-i','/tmp/vr.wav','-af',af,'-ar','48000','-ac','1','/tmp/veq.wav'], check=True)",
        "veq, sr48 = sf.read('/tmp/veq.wav', dtype='float32'); vdur = len(veq)/sr48",
        "fdur = max(14.05, min(15.95, max(vdur + 0.12, td)))",
        "veq = np.concatenate([veq, np.zeros(int((fdur-vdur)*sr48), np.float32)]) if vdur < fdur else veq[:int(fdur*sr48)]",
        "fdur = len(veq)/sr48; sc = 1.0/tp; timings = [{'text': x['text'], 'start': round(x['start']*sc,3), 'end': round(x['end']*sc,3)} for x in rt]",
        "cuts = [random.uniform(1.32, 1.68) for _ in range(10)]; cs = sum(cuts); cuts = [round(c*fdur/cs, 3) for c in cuts]; cuts[-1] = round(cuts[-1] + fdur - sum(cuts), 3)",
        "t = np.linspace(0, fdur, len(veq), endpoint=False, dtype=np.float32)",
        "drone = (0.045*np.sin(2*np.pi*48*t) + 0.025*np.sin(2*np.pi*96*t)).astype(np.float32); sfx = np.zeros_like(veq); ct = 0.0",
        "for cd in cuts[:-1]:",
        "    ct += cd; p = int(ct*sr48); wl = int(0.18*sr48)",
        "    if p + wl < len(sfx): wt = np.linspace(0,0.18,wl,dtype=np.float32); sfx[p:p+wl] += np.sin(np.pi*wt/0.18)*(0.06*np.random.randn(wl).astype(np.float32)*(0.4+wt*3)+0.12*np.sin(2*np.pi*(65-25*wt/0.18)*wt))",
        "rp, rl = max(0, int((timings[3]['start']-0.55)*sr48)), int(0.55*sr48)",
        "if rp + rl < len(sfx): rt2 = np.linspace(0,0.55,rl,dtype=np.float32); sfx[rp:rp+rl] += (rt2/0.55)**2 * 0.14 * np.sin(2*np.pi*(55+180*(rt2/0.55))*rt2)",
        "sf.write('/tmp/mix.wav', np.clip(veq+drone+sfx, -0.98, 0.98), sr48)",
        "subprocess.run(['ffmpeg','-y','-i','/tmp/mix.wav','-af','loudnorm=I=-14:TP=-1.5:LRA=7','-ar','48000','-ac','2','/tmp/final_audio.wav'], check=True)",
        "ft = lambda s: f'{int(s//3600)}:{int((s%3600)//60):02d}:{s%60:05.2f}'",
        "fh = 'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding'",
        "s1 = 'Style: Pop,DejaVu Sans,70,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,5,2,2,50,50,510,1'",
        "s2 = 'Style: Accent,DejaVu Sans,74,&H0000E5FF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,5,2,2,50,50,510,1'",
        "ass = ['[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 1080', 'PlayResY: 1920', '', '[V4+ Styles]', fh, s1, s2, '', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']",
        "for li, tm in enumerate(timings):",
        "    ws = tm['text'].split(); chs = [' '.join(ws[k:k+2]) for k in range(0, len(ws), 2)]",
        r"    wts = [max(2, len(re.sub(r'[^a-zA-Z]', '', c))) for c in chs]; wsum = sum(wts) or 1; sp = max(0.4, tm['end']-tm['start']); c0 = tm['start']",
        "    for ci, ch in enumerate(chs):",
        "        c1 = min(fdur-0.05, c0 + sp*wts[ci]/wsum); st = 'Accent' if li in (0,3) else 'Pop'",
        r"        ass.append(f'Dialogue: 0,{ft(c0)},{ft(c1)},{st},,0,0,0,,' + r'{\fscx114\fscy114\t(0,75,\fscx100\fscy100)}' + ch.upper()); c0 = c1",
        r"open('/tmp/subtitles.ass','w',encoding='utf-8').write('\n'.join(ass))",
        "json.dump({'total_dur': round(fdur,3), 'cut_durs': cuts, 'timings': timings}, open('/kaggle/working/beat_meta.json','w'), indent=2)",
        "print(f'[Stage 2] Chatterbox {fdur:.2f}s')",
    ])
    open("/tmp/cb.py", "w", encoding="utf-8").write(cb)
    sh([py, "/tmp/cb.py"])
    for p in (venv, "/root/.cache/huggingface", "/tmp/hf_cache"): shutil.rmtree(p, ignore_errors=True)
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
    chk = "import transformers,diffusers,peft,huggingface_hub; assert int(transformers.__version__.split('.')[0])<5"
    if subprocess.run([sys.executable, "-c", chk], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        sh([sys.executable, "-m", "pip", "install", "-q", "--no-cache-dir", "diffusers>=0.32.2", "transformers>=4.49.0,<5.0.0", "peft>=0.14.0", "accelerate>=1.2.0", "huggingface_hub>=0.28.0", "imageio-ffmpeg", "pillow"])
    from huggingface_hub import snapshot_download
    snapshot_download("Wan-AI/Wan2.1-T2V-1.3B-Diffusers", local_dir="/tmp/wan_model")
    open("/tmp/enc.py", "w").write("\n".join([
        "import json, torch; from transformers import UMT5EncoderModel, AutoTokenizer",
        "shots = json.load(open('/kaggle/working/current_script.json'))['shots']",
        "tok = AutoTokenizer.from_pretrained('/tmp/wan_model', subfolder='tokenizer')",
        "enc = UMT5EncoderModel.from_pretrained('/tmp/wan_model', subfolder='text_encoder', torch_dtype=torch.bfloat16).to('cuda:0').eval()",
        "e = lambda t: (lambda x: enc(x.input_ids, attention_mask=x.attention_mask)[0].cpu())(tok([t], padding='max_length', max_length=226, truncation=True, return_tensors='pt').to('cuda:0'))",
        "with torch.no_grad(): pos = [e(s + ', vertical 9:16, 35mm Kodak film, matte documentary, film grain, smooth motion') for s in shots]; neg = e('text, watermark, letters, blurry, distorted, plastic CGI, static')",
        "torch.save({'pos': pos, 'neg': neg}, '/tmp/pe.pt')",
    ]))
    sh([sys.executable, "/tmp/enc.py"])
    def worker(gpu, idxs):
        open(f"/tmp/w{gpu}.py", "w").write("\n".join([
            "import torch; from diffusers import WanPipeline, AutoencoderKLWan",
            "from diffusers.schedulers.scheduling_unipc_multistep import UniPCMultistepScheduler",
            "from diffusers.utils import export_to_video",
            "pe = torch.load('/tmp/pe.pt', map_location='cpu', weights_only=False)",
            "vae = AutoencoderKLWan.from_pretrained('/tmp/wan_model', subfolder='vae', torch_dtype=torch.float32)",
            "pipe = WanPipeline.from_pretrained('/tmp/wan_model', vae=vae, text_encoder=None, tokenizer=None, torch_dtype=torch.float16)",
            "pipe.scheduler.config.flow_shift = 3.0; pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)",
            "pipe.enable_model_cpu_offload(); pipe.vae.enable_tiling(); pipe.vae.enable_slicing(); neg = pe['neg'].to(dtype=torch.float16)",
            f"for i in {idxs}:",
            "    out = pipe(prompt_embeds=pe['pos'][i].to(dtype=torch.float16), negative_prompt_embeds=neg, height=832, width=480, num_frames=25, num_inference_steps=20, guidance_scale=5.5, generator=torch.Generator('cpu').manual_seed(4200+i*17)).frames[0]",
            "    export_to_video(out, f'/tmp/clip_{i}.mp4', fps=16); print(f'Done shot {i}', flush=True)",
        ]))
        return subprocess.Popen([sys.executable, f"/tmp/w{gpu}.py"], env={**os.environ, "CUDA_VISIBLE_DEVICES": str(gpu)}, stdout=open(f"/tmp/w{gpu}.log", "w"), stderr=subprocess.STDOUT)
    ng = len(subprocess.check_output(["nvidia-smi", "-L"]).decode().strip().splitlines())
    procs = [worker(0, [0,2,4,6,8]), worker(1, [1,3,5,7,9])] if ng >= 2 else [worker(0, list(range(10)))]
    if any(p.wait() != 0 for p in procs):
        for g in range(len(procs)): print(f"=== W{g} ===\n" + "\n".join(open(f"/tmp/w{g}.log").read().splitlines()[-35:]))
        raise RuntimeError("GPU worker failed")
    shutil.rmtree("/tmp/wan_model", ignore_errors=True); shutil.rmtree("/tmp/hf_cache", ignore_errors=True)
    segs = []
    for i, d in enumerate(meta["cut_durs"]):
        seg, flp = f"/tmp/seg_{i}.mp4", (",hflip" if i % 2 else "")
        vf = f"setpts={d/1.5625:.4f}*PTS,fps=30,scale='trunc(1080*(1+0.09*t/{d:.3f})/2)*2':'trunc(1920*(1+0.09*t/{d:.3f})/2)*2':eval=frame:flags=lanczos,crop=1080:1920{flp},noise=alls=7:allf=t,unsharp=5:5:0.75:5:5:0.0,eq=contrast=1.08:saturation=1.05:gamma=1.04"
        sh(["ffmpeg", "-y", "-i", f"/tmp/clip_{i}.mp4", "-vf", vf, "-t", f"{d:.3f}", "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p", "-an", seg])
        segs.append(seg)
    open("/tmp/concat.txt", "w").write("\n".join(f"file '{s}'" for s in segs))
    sh(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "/tmp/concat.txt", "-c", "copy", "/tmp/vraw.mp4"])
    make_banner(sdata.get("hook_banner", "UNEXPLAINED SIGNAL"), "/tmp/banner.png")
    fc = "[0:v][1:v]overlay=0:200:enable='between(t,0,2.2)'[v1];[v1]ass=/tmp/subtitles.ass[vo]"
    sh(["ffmpeg", "-y", "-i", "/tmp/vraw.mp4", "-i", "/tmp/banner.png", "-i", str(AUDIO_OUT), "-filter_complex", fc, "-map", "[vo]", "-map", "2:a", "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(FINAL_OUT)])
    print("[Done]", FINAL_OUT)

if __name__ == "__main__":
    s = stage1_script(); m = stage2_audio(); stage3_wan(s, m)
