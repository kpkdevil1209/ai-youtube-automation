import asyncio, json, os, re, subprocess
import numpy as np
import soundfile as sf

SCRIPT_FILE = "long_script.json"
OUT_WAV = "long_audio.wav"
OUT_SRT = "long_subtitles.srt"
SR = 24000
MAX_CHARS = 155

def find_kokoro():
    base = os.path.expanduser("~/.cache/kokoro")
    m = os.path.join(base, "kokoro-v1.0.onnx")
    v = os.path.join(base, "voices-v1.0.bin")
    if os.path.exists(m) and os.path.exists(v):
        return m, v
    return None, None

def clean_chunk(t):
    t = re.sub(r"\[[^\]]*\]", " ", str(t or ""))
    t = re.sub(r"[*_`#<>]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def split_chunks(text):
    text = clean_chunk(text)
    if not text:
        return []
    sents = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    for s in sents:
        s = s.strip()
        if not s:
            continue
        if len(s) <= MAX_CHARS:
            chunks.append(s)
            continue
        parts = re.split(r"(?<=[,;:\-])\s+", s)
        buf = ""
        for p in parts:
            if len(buf) + len(p) + 1 <= MAX_CHARS:
                buf = (buf + " " + p).strip()
            else:
                if buf:
                    chunks.append(buf)
                if len(p) <= MAX_CHARS:
                    buf = p
                else:
                    words, cur = p.split(), ""
                    for w in words:
                        if len(cur) + len(w) + 1 <= MAX_CHARS:
                            cur = (cur + " " + w).strip()
                        else:
                            if cur:
                                chunks.append(cur)
                            cur = w
                    buf = cur
        if buf:
            chunks.append(buf)
    return [c for c in chunks if re.search(r"[A-Za-z0-9]", c)]

async def edge_tts_fallback(text, path):
    import edge_tts
    comm = edge_tts.Communicate(text, "en-US-BrianMultilingualNeural", rate="-4%")
    await comm.save(path)

def synth_chunk(kokoro, voice, text, speed):
    text = clean_chunk(text)
    if not re.search(r"[A-Za-z0-9]", text):
        return np.zeros(int(SR * 0.25), dtype=np.float32)
    if kokoro is not None:
        try:
            samples, sr = kokoro.create(text, voice=voice, speed=speed, lang="en-us")
            arr = np.asarray(samples, dtype=np.float32)
            if sr != SR:
                sf.write("_tmp_k.wav", arr, sr)
                subprocess.run(["ffmpeg", "-y", "-i", "_tmp_k.wav", "-ar", str(SR), "-ac", "1", "_tmp_k24.wav"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                arr, _ = sf.read("_tmp_k24.wav", dtype="float32")
            return arr.astype(np.float32)
        except Exception as e:
            print(f"[!] Kokoro chunk fallback: {e}", flush=True)
    mp3_p, wav_p = "_tmp_edge.mp3", "_tmp_edge.wav"
    asyncio.run(edge_tts_fallback(text, mp3_p))
    subprocess.run(["ffmpeg", "-y", "-i", mp3_p, "-ar", str(SR), "-ac", "1", wav_p], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    arr, _ = sf.read(wav_p, dtype="float32")
    return arr.astype(np.float32)

def fmt_srt(sec):
    ms = int(round(max(0.0, sec) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def fmt_yt(sec):
    tot = int(round(max(0.0, sec)))
    h, rem = divmod(tot, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

def make_ambient_bed(total_samples, ch_starts, ch6_start):
    t = np.arange(total_samples, dtype=np.float32) / SR
    sub = 0.45 * np.sin(2.0 * np.pi * 49.0 * t) + 0.30 * np.sin(2.0 * np.pi * 73.5 * t)
    pad = 0.25 * np.sin(2.0 * np.pi * 110.0 * t + 0.4 * np.sin(2.0 * np.pi * 0.08 * t))
    swell = 0.65 + 0.35 * np.sin(2.0 * np.pi * 0.04 * t)
    bed = (sub + pad) * swell * 0.042
    for cs in ch_starts[1:]:
        idx0 = int(cs * SR)
        n_hit = min(int(1.2 * SR), total_samples - idx0)
        if n_hit > 0:
            ht = np.arange(n_hit, dtype=np.float32) / SR
            hit = np.sin(2.0 * np.pi * (65.0 - 25.0 * (ht / 1.2)) * ht) * np.exp(-3.2 * ht) * 0.14
            bed[idx0:idx0 + n_hit] += hit
    if ch6_start is not None:
        drop_a = max(0, int((ch6_start - 2.0) * SR))
        drop_b = min(total_samples, int((ch6_start + 0.1) * SR))
        if drop_b > drop_a:
            bed[drop_a:drop_b] *= 0.04
    fade_n = min(int(2.0 * SR), total_samples)
    bed[:fade_n] *= np.linspace(0.0, 1.0, fade_n, dtype=np.float32)
    bed[-fade_n:] *= np.linspace(1.0, 0.0, fade_n, dtype=np.float32)
    return bed.astype(np.float32)

def two_pass_loudnorm(voice_wav, bed_wav, out_wav):
    mix_wav = "_tmp_long_mix.wav"
    filt = "[0:a]volume=1.0[v];[1:a]volume=1.0[b];[v][b]amix=inputs=2:duration=first:dropout_transition=2[m]"
    subprocess.run(["ffmpeg", "-y", "-i", voice_wav, "-i", bed_wav, "-filter_complex", filt, "-map", "[m]", "-ar", "48000", mix_wav], check=True)
    p1 = subprocess.run(["ffmpeg", "-y", "-i", mix_wav, "-af", "loudnorm=I=-14.0:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    err = p1.stderr.decode("utf-8", errors="ignore")
    stats = json.loads(err[err.rfind("{"):err.rfind("}") + 1])
    af2 = f"loudnorm=I=-14.0:TP=-1.5:LRA=11:measured_I={stats['input_i']}:measured_LRA={stats['input_lra']}:measured_TP={stats['input_tp']}:measured_thresh={stats['input_thresh']}:offset={stats['target_offset']}:linear=true"
    subprocess.run(["ffmpeg", "-y", "-i", mix_wav, "-af", af2, "-ar", "48000", "-ac", "1", out_wav], check=True)
    for f in (mix_wav, voice_wav, bed_wav, "_tmp_k.wav", "_tmp_k24.wav", "_tmp_edge.mp3", "_tmp_edge.wav"):
        if os.path.exists(f):
            os.remove(f)

def main():
    doc = json.load(open(SCRIPT_FILE, encoding="utf-8"))
    m_path, v_path = find_kokoro()
    kokoro, voice = None, "am_michael"
    if m_path:
        from kokoro_onnx import Kokoro
        kokoro = Kokoro(m_path, v_path)
        try:
            voice = 0.65 * kokoro.get_voice_style("am_michael") + 0.35 * kokoro.get_voice_style("am_onyx")
        except Exception:
            voice = "am_michael"

    parts, srt_lines, ch_starts = [], [], []
    cur_sec, srt_idx, ch6_start = 0.0, 1, None

    for ci, ch in enumerate(doc["chapters"]):
        ch_start = cur_sec
        ch_starts.append(ch_start)
        if ch["index"] == 6:
            ch6_start = ch_start
        speed = 1.01 if ch["index"] == 1 else 0.97
        chunks = split_chunks(ch["narration"])
        for c_txt in chunks:
            arr = synth_chunk(kokoro, voice, c_txt, speed)
            dur = len(arr) / SR
            parts.append(arr)
            srt_lines.append(f"{srt_idx}\n{fmt_srt(cur_sec)} --> {fmt_srt(cur_sec + dur)}\n{c_txt}\n\n")
            srt_idx += 1
            cur_sec += dur
            gap = 0.18
            parts.append(np.zeros(int(SR * gap), dtype=np.float32))
            cur_sec += gap
        if ci < len(doc["chapters"]) - 1:
            ch_gap = 1.20 if ch.get("midroll_break_after") else 0.85
            parts.append(np.zeros(int(SR * ch_gap), dtype=np.float32))
            cur_sec += ch_gap
        ch["start_sec"] = round(ch_start, 3)
        ch["end_sec"] = round(cur_sec, 3)
        ch["duration"] = round(cur_sec - ch_start, 3)
        ch["timestamp"] = fmt_yt(ch_start)
        print(f"[*] Chapter {ch['index']} audio: {ch['timestamp']} ({ch['duration']:.1f}s)", flush=True)

    voice_arr = np.concatenate(parts).astype(np.float32)
    bed_arr = make_ambient_bed(len(voice_arr), ch_starts, ch6_start)
    sf.write("_tmp_voice.wav", voice_arr, SR)
    sf.write("_tmp_bed.wav", bed_arr, SR)
    two_pass_loudnorm("_tmp_voice.wav", "_tmp_bed.wav", OUT_WAV)
    open(OUT_SRT, "w", encoding="utf-8").writelines(srt_lines)

    doc["total_duration_sec"] = round(cur_sec, 2)
    doc["chapters_text"] = "\n".join(f"{c['timestamp']} {c['title']}" for c in doc["chapters"])
    json.dump(doc, open(SCRIPT_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"[*] Master {OUT_WAV} ready: {fmt_yt(cur_sec)} ({cur_sec:.1f}s)", flush=True)

if __name__ == "__main__":
    main()
