import os, re, sys, json, time, shutil, random, subprocess, urllib.request
from pathlib import Path

P, OUT = Path, "/kaggle/working"
REPO = "kpkdevil1209/ai-youtube-automation"
LEAK_RE = re.compile(r"(under \d+ chars|file #|icy cola|and that is why|did you know|in this video|have you ever)", re.I)
TOPICS = [
    "What happens inside your body if you swallow two tiny magnets", "What happens inside your skull if you pop a danger-triangle pimple",
    "What happens to your arteries if you crack your neck hard", "What happens inside your chest if you hold in a massive sneeze",
    "What happens to your eyeballs if you sleep wearing contact lenses", "Why airplane windows have a tiny pinhole near the bottom",
    "What happens inside your chest if an elevator cable snaps", "Why deep sea divers suddenly hear metallic knocking sounds",
    "What happens to your brain in total zero-sound darkness", "What actually kills you first if you fall into quicksand",
    "What happens inside your lungs seconds after inhaling helium", "How one tiny screw mistake locked a giant bank vault forever",
]

def sh(c, env=None, q=False):
    kw = {"shell": isinstance(c, str), "env": env, "check": True}
    if q: kw["stdout"] = kw["stderr"] = subprocess.DEVNULL
    return subprocess.run(c, **kw)

def dur_of(f):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", f]).decode().strip())

def stage1_script():
    if not shutil.which("ollama"):
        sh("which zstd>/dev/null||(apt-get update -qq&&apt-get install -yq zstd)", q=True)
        sh("curl -fsSL https://ollama.com/download/ollama-linux-amd64.tar.zst -o /tmp/o.zst&&zstd -d -c /tmp/o.zst|tar -x -C /usr&&rm -f /tmp/o.zst")
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": "0"}
    srv = subprocess.Popen(["ollama", "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        try:
            if urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2).status == 200: break
        except Exception: time.sleep(1)
    sh(["ollama", "pull", "qwen2.5:14b"], env=env, q=True)
    topic = random.choice(TOPICS)
    pr = f"Return JSON keys: topic,title,hook,description,pinned_comment,tags,script,visual_prompts. Topic: {topic}. Style: Zack D Films 3D Short. script: 4-5 clinical 2nd-person ('you'/'your') sentences (39-45 words). S1: mid-action visceral hook (NEVER 'Did you know'). Middle: physical chain-reaction. Final: shocking twist looping back to S1. hook: 3-5 uppercase words. title: 'What Happens If You...' or 'Why You Should NEVER...', <=50 chars, no #. description: 1 intriguing sentence, no #. pinned_comment: 1 'new fear unlocked' question. tags: 5 lowercase strings. visual_prompts: 10 3D Pixar medical-CGI scenes with bald 3D dummy; 0=centered danger zoom, even=external wide, odd=glowing X-ray cutaway inside body."
    best, bd = None, 999
    for k in range(4):
        req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=json.dumps({"model": "qwen2.5:14b", "prompt": pr, "stream": False, "format": "json", "options": {"temperature": 0.72}}).encode(), headers={"Content-Type": "application/json"})
        try:
            m = re.search(r"\{.*\}", json.loads(urllib.request.urlopen(req, timeout=180).read())["response"], re.S)
            c = json.loads(m.group(0)) if m else None
            if not c: continue
        except Exception as e: print(f"S1 {k}: {e}"); continue
        scr = re.sub(r"\band that is why\b", "that is how", str(c.get("script", "")).strip(), flags=re.I)
        c["script"] = re.sub(r"\s+", " ", re.sub(LEAK_RE, "", scr)).strip(" ,;-")
        c["visual_prompts"] = [x.get("prompt") or x.get("description") or str(x) if isinstance(x, dict) else str(x) for x in (c.get("visual_prompts") or []) if x]
        wc, you = len(c["script"].split()), bool(re.search(r"\b(you|your)\b", c["script"], re.I))
        print(f"S1 {k}: wc={wc} vp={len(c['visual_prompts'])} you={you}")
        if wc >= 20 and len(c["visual_prompts"]) >= 4:
            d = abs(wc - 42) + (0 if you else 8)
            if d < bd: best, bd = c, d
            if 36 <= wc <= 47 and len(c["visual_prompts"]) >= 8 and you: break
    if not best: raise RuntimeError("Stage 1 script validation failed")
    w = best["script"].split()
    if len(w) > 47: cut = " ".join(w[:46]); p = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?")); best["script"] = cut[:p + 1] if p > 110 else cut.rstrip(".,;:") + "."
    elif len(w) < 35: best["script"] = " ".join((best["script"].rstrip(".!?") + ". Look right back at how this hits your body, because that tiny trigger starts it.").split()[:45]).rstrip(".,;:") + "."
    vp, angs, i = best["visual_prompts"][:10], ["wide shot ", "X-ray cutaway ", "overhead ", "macro close-up "], 0
    while len(vp) < 10: vp.append(angs[i % 4] + vp[i % len(vp)]); i += 1
    best.update({"visual_prompts": vp, "topic": str(best.get("topic") or topic)[:80], "title": re.sub(LEAK_RE, "", str(best.get("title") or topic)).replace("#", "").strip()[:58] or topic[:58], "description": re.sub(LEAK_RE, "", str(best.get("description") or "")).replace("#", "").strip()[:180] or topic, "pinned_comment": re.sub(LEAK_RE, "", str(best.get("pinned_comment") or "")).strip()[:160] or "New fear unlocked? Comment below.", "hook": re.sub(r"[{}\r\n]", "", str(best.get("hook") or "WAIT FOR THE TWIST").upper()[:36]), "tags": best["tags"] if isinstance(best.get("tags"), list) and best["tags"] else ["shorts", "science", "mystery", "facts", "3d"]})
    srv.terminate(); srv.wait(); shutil.rmtree("/root/.ollama", ignore_errors=True); P(f"{OUT}/current_script.json").write_text(json.dumps(best, indent=2)); return best

def stage2_audio(sc):
    uv = shutil.which("uv") or "/root/.local/bin/uv"
    if not os.path.exists(uv): sh("curl -LsSf https://astral.sh/uv/install.sh | sh", q=True)
    ve, py = "/tmp/cb_venv", "/tmp/cb_venv/bin/python"
    if not os.path.exists(py):
        sh([uv, "venv", ve, "--python", "3.11"], q=True); sh([uv, "pip", "install", "--python", py, "numpy>=1.24.0,<2.0.0", "setuptools<82", "wheel"], q=True)
        sh([uv, "pip", "install", "--python", py, "--index-url", "https://download.pytorch.org/whl/cu124", "torch==2.6.0", "torchaudio==2.6.0"], q=True)
        try: sh([uv, "pip", "install", "--python", py, "--no-build-isolation", "chatterbox-tts", "soundfile", "edge-tts"], q=True)
        except Exception:
            sh([uv, "pip", "install", "--python", py, "--no-deps", "chatterbox-tts"], q=True)
            sh([uv, "pip", "install", "--python", py, "transformers==4.46.3", "diffusers==0.29.0", "conformer==0.3.2", "s3tokenizer", "librosa==0.11.0", "pyloudnorm", "resemble-perth", "omegaconf", "einops", "safetensors", "huggingface_hub", "soundfile", "scipy", "edge-tts"], q=True)
    P("/tmp/tts.txt").write_text(sc["script"])
    P("/tmp/cb.py").write_text("\n".join([
        "import os,sys,types,torch,subprocess,soundfile as sf", "os.environ['TRANSFORMERS_ATTN_IMPLEMENTATION']='eager'; torch.manual_seed(42)",
        "if torch.cuda.is_available(): torch.cuda.manual_seed_all(42)", "for n in ('spacy_pkuseg','gradio'):",
        "    if n not in sys.modules: m=types.ModuleType(n); m.pkuseg=lambda *a,**k:None; sys.modules[n]=m",
        "txt=open('/tmp/tts.txt').read().strip()",
        "try:", "    import perth", "    if not getattr(perth,'PerthImplicitWatermarker',None): perth.PerthImplicitWatermarker=type('_P',(),{'apply_watermark':lambda s,w,**k:w})",
        "    from chatterbox.tts import ChatterboxTTS; m=ChatterboxTTS.from_pretrained('cuda'); sf.write('/tmp/vr.wav',m.generate(txt,exaggeration=0.48,cfg_weight=0.52).squeeze().cpu().numpy(),m.sr)",
        "except Exception as e:", "    print('CB fallback:',e)", "    subprocess.run([sys.executable,'-m','edge_tts','--voice','en-US-AndrewMultilingualNeural','--text',txt,'--write-media','/tmp/vr.mp3'],check=True); subprocess.run(['ffmpeg','-y','-i','/tmp/vr.mp3','/tmp/vr.wav'],check=True)",
    ]))
    sh([py, "/tmp/cb.py"]); sh(["ffmpeg", "-y", "-i", "/tmp/vr.wav", "-af", "silenceremove=start_periods=1:start_threshold=-42dB,areverse,silenceremove=start_periods=1:start_threshold=-42dB,areverse", "/tmp/vt.wav"], q=True)
    src = "/tmp/vt.wav" if dur_of("/tmp/vt.wav") >= 2.0 else "/tmp/vr.wav"; d, tgt = dur_of(src), round(random.uniform(14.35, 15.55), 2)
    sh(["ffmpeg", "-y", "-i", src, "-af", f"atempo={max(0.86, min(1.32, d / tgt)):.4f}", "/tmp/vs.wav"], q=True); d2 = dur_of("/tmp/vs.wav")
    if d2 < 14.20: sh(["ffmpeg", "-y", "-i", "/tmp/vs.wav", "-af", f"apad=whole_dur={tgt:.3f}", "-t", f"{tgt:.3f}", "/tmp/voice.wav"], q=True)
    elif d2 > 15.80: sh(["ffmpeg", "-y", "-i", "/tmp/vs.wav", "-af", f"atempo={min(1.45, d2 / tgt):.4f}", "-t", f"{tgt:.3f}", "/tmp/voice.wav"], q=True)
    else: sh(["cp", "/tmp/vs.wav", "/tmp/voice.wav"])
    dur = dur_of("/tmp/voice.wav"); shutil.rmtree(ve, ignore_errors=True); print(f"Audio: raw={d:.2f}s spd={d2:.2f}s final={dur:.2f}s")
    if not (14.05 <= dur <= 15.90): raise RuntimeError(f"Audio dur {dur:.2f}s invalid")
    words, spoken = sc["script"].split(), min(dur, d2)
    wts = [max(1, len(re.findall(r"[aeiouy]+", w.lower()))) + 0.6 + (2.0 if w[-1] in ".!?" else (0.8 if w[-1] in ",;:" else 0.0)) for w in words]
    tot, beats, wt = max(1.0, sum(wts)), [], 0.0
    for i in range(0, len(words), 2): e = min(spoken, wt + spoken * sum(wts[i:i + 2]) / tot); beats.append({"t": round(wt, 3), "e": round(e, 3), "w": " ".join(words[i:i + 2])}); wt = e
    meta = {"dur": round(dur, 3), "cuts": [round(dur * i / 10.0, 3) for i in range(11)], "beats": beats}; P(f"{OUT}/beat_meta.json").write_text(json.dumps(meta, indent=2)); return meta

def load_s34():
    urls = [(f"https://api.github.com/repos/{REPO}/contents/kaggle_render/render_stage34.py", {"Accept": "application/vnd.github.raw"}), (f"https://raw.githubusercontent.com/{REPO}/main/kaggle_render/render_stage34.py?t={int(time.time())}", {})]
    for u, hd in urls:
        try:
            P("/tmp/render_stage34.py").write_bytes(urllib.request.urlopen(urllib.request.Request(u, headers=hd), timeout=20).read()); break
        except Exception as e: print("Fetch s34 retry:", e)
    sys.path.insert(0, "/tmp"); from render_stage34 import stage3_render, stage4_assemble; return stage3_render, stage4_assemble

if __name__ == "__main__":
    sh(["nvidia-smi", "-L"]); s3, s4 = load_s34(); s = stage1_script(); m = stage2_audio(s); s3(s); s4(s, m)
