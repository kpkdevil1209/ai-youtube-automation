import os, re, json, asyncio, subprocess, numpy as np, soundfile as sf

SR, SCRIPT_FILE = 24000, "current_script.json"
K_DIR = os.path.expanduser("~/.cache/kokoro")
POWER = {"NEVER", "DEAD", "ZERO", "SEALED", "TRAP", "KILLED", "VANISHED", "CRASH", "COLLAPSE", "TOXIC", "BANNED", "SECRET", "DARK", "SECONDS", "STOP", "SURVIVE", "FROZEN"}
_KOKORO = None

def get_kokoro():
    global _KOKORO
    if _KOKORO is None:
        m, v = os.path.join(K_DIR, "kokoro-v1.0.onnx"), os.path.join(K_DIR, "voices-v1.0.bin")
        if os.path.exists(m) and os.path.exists(v):
            from kokoro_onnx import Kokoro
            _KOKORO = Kokoro(m, v)
    return _KOKORO

def trim_sil(y, thr=0.008):
    idx = np.where(np.abs(y) > thr)[0]
    if len(idx) == 0: return y
    return y[max(0, idx[0] - int(SR * 0.03)):min(len(y), idx[-1] + int(SR * 0.05))]

def speak(text, speed=0.95):
    k = get_kokoro()
    if k is not None:
        y, s = k.create(text, voice="am_adam", speed=speed, lang="en-us")
        if s != SR: y = np.interp(np.linspace(0, len(y), int(len(y) * SR / s)), np.arange(len(y)), y)
        return trim_sil(np.asarray(y, dtype=np.float32))
    import edge_tts
    asyncio.run(edge_tts.Communicate(text, "en-US-AndrewNeural", rate="-4%").save("_tts.mp3"))
    subprocess.run(["ffmpeg", "-y", "-i", "_tts.mp3", "-ar", str(SR), "-ac", "1", "_tts.wav"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    y, _ = sf.read("_tts.wav", dtype="float32")
    return trim_sil(y)

def sonic_stamp():
    t = np.linspace(0, 0.20, int(SR * 0.20), False)
    y = (np.sin(2 * np.pi * (56 - 22 * (t / 0.20)) * t) * np.exp(-t * 11) * 0.65 + np.sin(2 * np.pi * 890 * t) * np.exp(-t * 22) * 0.32).astype(np.float32)
    y[-240:] *= np.linspace(1, 0, 240)
    return y

def tension_bed(dur):
    t = np.linspace(0, dur, int(SR * dur), False)
    pulse = np.clip(np.sin(2 * np.pi * 2.2 * t), 0, 1) ** 3
    return (np.sin(2 * np.pi * (44 + 14 * (t / max(0.1, dur))) * t) * (0.04 + 0.05 * pulse)).astype(np.float32)

def whoosh(dur=0.24):
    n = int(SR * dur)
    return (np.convolve(np.random.randn(n), np.ones(12) / 12, mode="same") * (np.sin(np.linspace(0, np.pi, n)) ** 1.6) * 0.16).astype(np.float32)

def sub_boom(dur=0.50):
    t = np.linspace(0, dur, int(SR * dur), False)
    return (np.sin(2 * np.pi * (54 - 24 * (t / dur)) * t) * np.exp(-t * 6.5) * 0.58).astype(np.float32)

def lock_click():
    t = np.linspace(0, 0.06, int(SR * 0.06), False)
    return (np.sin(2 * np.pi * 1650 * t) * np.exp(-t * 85) * 0.30).astype(np.float32)

def ts_ass(t): return f"{int(t//3600)}:{int((t%3600)//60):02d}:{int(t%60):02d}.{int((t%1)*100):02d}"
def ts_srt(t): return f"{int(t//3600):02d}:{int((t%3600)//60):02d}:{int(t%60):02d},{int((t%1)*1000):03d}"

def color_pop(txt):
    out = []
    for w in txt.split():
        cl = re.sub(r"[^A-Za-z0-9]", "", w).upper()
        if cl in POWER or any(c.isdigit() for c in cl): out.append(r"{\c&H0000D7FF&}" + w.upper() + r"{\c&H00FFFFFF&}")
        elif cl.endswith(("?", "!")): out.append(r"{\c&H003B3BFF&}" + w.upper() + r"{\c&H00FFFFFF&}")
        else: out.append(w.upper())
    return " ".join(out)

def main():
    sc = json.load(open(SCRIPT_FILE, encoding="utf-8"))
    beats = sc["beats"]
    b0 = beats[0]
    hq = speak(b0.get("hook_question", b0["narration"]), speed=1.03)
    esc = speak(b0.get("escalation_line", ""), speed=0.98) if b0.get("escalation_line") else np.zeros(0, np.float32)

    parts, cues, cur = [sonic_stamp()], [], 0.20
    hq_end = cur + len(hq) / SR
    cues.append((cur, hq_end, b0.get("hook_question", b0["narration"])))
    parts.append(hq); cur = hq_end
    if len(esc) > 0:
        parts.append(np.zeros(int(SR * 0.04), np.float32)); cur += 0.04
        esc_end = cur + len(esc) / SR
        cues.append((cur, esc_end, b0["escalation_line"]))
        parts.append(esc); cur = esc_end
    b0_end = cur
    beat_times = [[0.0, round(b0_end, 3)]]

    climax_idx, climax_time = min(3, len(beats) - 1), b0_end
    for i in range(1, len(beats)):
        gap = 0.32 if i == climax_idx else 0.06
        parts.append(np.zeros(int(SR * gap), np.float32)); cur += gap
        if i == climax_idx: climax_time = cur
        v = speak(beats[i]["narration"], speed=0.95)
        st, en = cur, cur + len(v) / SR
        cues.append((st, en, beats[i]["narration"]))
        parts.append(v); beat_times.append([round(st, 3), round(en, 3)]); cur = en

    parts.append(np.zeros(int(SR * 0.08), np.float32))
    master = np.concatenate(parts).astype(np.float32)
    bed = tension_bed(min(2.6, b0_end))
    master[:len(bed)] += bed
    lc = lock_click(); idx_lc = int(min(2.40, b0_end) * SR)
    if idx_lc + len(lc) < len(master): master[idx_lc:idx_lc+len(lc)] += lc
    for i in range(1, len(beat_times)):
        t_cut = beat_times[i][0]
        if i == climax_idx:
            bm = sub_boom(); p = int(t_cut * SR)
            if p + len(bm) < len(master): master[p:p+len(bm)] += bm
        else:
            wh = whoosh(); p = max(0, int((t_cut - 0.12) * SR))
            if p + len(wh) < len(master): master[p:p+len(wh)] += wh

    master = master * (0.92 / float(np.max(np.abs(master)) or 1.0))
    sf.write("final_audio.wav", master, SR, subtype="PCM_16")
    total_dur = len(master) / SR

    ass = [
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n",
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Flash,Arial Black,88,&H0000D7FF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,6,2,5,40,40,40,1",
        "Style: Stamp,Arial,34,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,1,0,1,3,1,7,40,40,40,1",
        "Style: Egg,Arial,28,&H00FFD800,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,3,1,9,40,40,40,1",
        "Style: Cap,Arial Black,68,&H00FFFFFF,&H0000D7FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,45,45,510,1",
        "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 2,{ts_ass(0.12)},{ts_ass(0.95)},Flash,,0,0,0,,{{\\an5\\pos(540,700)\\fad(80,100)}}{b0.get('hook_flash_words', 'EXPLAIN THIS')}",
        f"Dialogue: 2,{ts_ass(min(2.40, b0_end))},{ts_ass(total_dur)},Stamp,,0,0,0,,{{\\an7\\pos(48,88)\\fad(180,0)}}{{\\c&H003B3BFF&}}{sc.get('channel_signature','DEVIL ARCHIVE')}  {{\\c&H00FFFFFF&}}|  {sc.get('case_label','FILE #001')}",
        f"Dialogue: 2,{ts_ass(total_dur*0.50)},{ts_ass(total_dur*0.50+0.80)},Egg,,0,0,0,,{{\\an9\\pos(1032,165)\\fad(100,100)}}[ANOMALY: {sc.get('easter_egg_code','X-014')}]",
    ]
    srt, idx_s = [], 1
    for st, en, txt in cues:
        words = txt.split()
        chunks = [" ".join(words[j:j+3]) for j in range(0, len(words), 3)] or [txt]
        dt = (en - st) / len(chunks)
        for j, ch in enumerate(chunks):
            cs, ce = st + j * dt, st + (j + 1) * dt
            ass.append(f"Dialogue: 1,{ts_ass(cs)},{ts_ass(ce)},Cap,,0,0,0,,{color_pop(ch)}")
            srt.append(f"{idx_s}\n{ts_srt(cs)} --> {ts_srt(ce)}\n{ch}\n"); idx_s += 1

    open("subtitles.ass", "w", encoding="utf-8").write("\n".join(ass))
    open("subtitles.srt", "w", encoding="utf-8").write("\n".join(srt))
    open("subtitles_en.srt", "w", encoding="utf-8").write("\n".join(srt))
    sc["beat_times"], sc["climax_time"], sc["total_duration"] = beat_times, round(climax_time, 3), round(total_dur, 3)
    json.dump(sc, open(SCRIPT_FILE, "w", encoding="utf-8"), indent=2)
    print(f"[+] Audio Ready: {total_dur:.2f}s | Stamp@2.40s | Climax@{climax_time:.2f}s", flush=True)

if __name__ == "__main__":
    main()
