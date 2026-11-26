import asyncio, json, os, re, subprocess
import numpy as np
import soundfile as sf

SR, SCRIPT_FILE = 24000, "current_script.json"
K_DIR = os.path.expanduser("~/.cache/kokoro")
POWER = {"NEVER", "DEAD", "ZERO", "SEALED", "TRAP", "KILLED", "VANISHED", "CRASH", "COLLAPSE", "TOXIC", "BANNED", "SECRET", "DARK", "SECONDS", "STOP", "SURVIVE", "FROZEN", "IMPOSSIBLE", "MISSING"}
_KOKORO, _VOICE = None, None


def get_kokoro():
    global _KOKORO, _VOICE
    if _KOKORO is None:
        m, v = os.path.join(K_DIR, "kokoro-v1.0.onnx"), os.path.join(K_DIR, "voices-v1.0.bin")
        if os.path.exists(m) and os.path.exists(v):
            from kokoro_onnx import Kokoro
            _KOKORO = Kokoro(m, v)
            try:
                _VOICE = 0.65 * _KOKORO.get_voice_style("am_michael") + 0.35 * _KOKORO.get_voice_style("am_onyx")
            except Exception:
                _VOICE = "am_michael"
    return _KOKORO


def trim_sil(y, thr=0.008):
    idx = np.where(np.abs(y) > thr)[0]
    if len(idx) == 0:
        return y
    return y[max(0, idx[0] - int(SR * 0.02)) : min(len(y), idx[-1] + int(SR * 0.04))]


def speak(text, speed=1.07):
    txt = re.sub(r"\s+", " ", re.sub(r"[^\w\s.,?!'%-]", " ", str(text or ""))).strip()
    if not re.search(r"[A-Za-z0-9]", txt):
        return np.zeros(int(SR * 0.50), np.float32)
    k = get_kokoro()
    if k is not None:
        try:
            y, s = k.create(txt[:260], voice=_VOICE, speed=speed, lang="en-us")
            if s != SR:
                y = np.interp(np.linspace(0, len(y), int(len(y) * SR / s)), np.arange(len(y)), y)
            return trim_sil(np.asarray(y, dtype=np.float32))
        except Exception as e:
            print(f"[!] Kokoro fallback ({e}) on: {txt}", flush=True)
    import edge_tts
    asyncio.run(edge_tts.Communicate(txt, "en-US-BrianMultilingualNeural", rate="+8%").save("_tts.mp3"))
    subprocess.run(["ffmpeg", "-y", "-i", "_tts.mp3", "-ar", str(SR), "-ac", "1", "_tts.wav"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    y, _ = sf.read("_tts.wav", dtype="float32")
    for p in ("_tts.mp3", "_tts.wav"):
        if os.path.exists(p):
            os.remove(p)
    return trim_sil(y)


def swept_whoosh(dur=0.26):
    n = int(SR * dur)
    t = np.linspace(0, dur, n, False)
    rng = np.random.default_rng(7)
    noise = np.convolve(rng.standard_normal(n), np.ones(22) / 22.0, mode="same")
    carrier = np.sin(2 * np.pi * (90 + 340 * (t / dur)) * t) * 0.35
    env = np.sin(np.linspace(0, np.pi, n)) ** 1.8
    return ((noise * 0.65 + carrier) * env * 0.14).astype(np.float32)


def sub_thump(dur=0.38, power=0.45):
    t = np.linspace(0, dur, int(SR * dur), False)
    return (np.sin(2 * np.pi * (60.0 - 30.0 * (t / dur)) * t) * np.exp(-t * 7.5) * power).astype(np.float32)


def build_bed(n_samples, climax_t):
    t = np.linspace(0, n_samples / SR, n_samples, False)
    fade = np.minimum(1.0, t / 0.25) * np.minimum(1.0, np.maximum(0.0, (n_samples / SR - t) / 0.30))
    pulse = np.clip(np.sin(2 * np.pi * 1.8 * t), 0, 1) ** 4 * 0.015
    riser = np.clip(1.0 - np.abs(t - (climax_t - 0.12)) / 0.85, 0.0, 1.0)
    bed = np.sin(2 * np.pi * 42 * t) * 0.025 + np.sin(2 * np.pi * 63 * t) * 0.012 + np.sin(2 * np.pi * (78 + 45 * riser) * t) * (riser * 0.04) + pulse
    return (bed * fade).astype(np.float32)


def duck_envelope(voice_track):
    win = int(SR * 0.12)
    amp = np.convolve(np.abs(voice_track), np.ones(win) / win, mode="same")
    return np.where(amp > 0.015, 0.52, 1.0).astype(np.float32)


def ts_ass(t):
    return f"{int(t//3600)}:{int((t%3600)//60):02d}:{int(t%60):02d}.{int((t%1)*100):02d}"


def ts_srt(t):
    return f"{int(t//3600):02d}:{int((t%3600)//60):02d}:{int(t%60):02d},{int((t%1)*1000):03d}"


def color_pop(txt):
    out = []
    for w in txt.split():
        cl = re.sub(r"[^A-Za-z0-9]", "", w).upper()
        if cl in POWER or any(c.isdigit() for c in cl):
            out.append(r"{\c&H0000D7FF&}" + w.upper() + r"{\c&H00FFFFFF&}")
        elif w.endswith(("?", "!")):
            out.append(r"{\c&H003B3BFF&}" + w.upper() + r"{\c&H00FFFFFF&}")
        else:
            out.append(w.upper())
    return r"{\fscx110\fscy110\t(0,85,\fscx100\fscy100)}" + " ".join(out)


def main():
    sc = json.load(open(SCRIPT_FILE, encoding="utf-8"))
    beats = sc["beats"]
    b0 = beats[0]
    hq_txt = b0.get("hook_question") or b0["narration"]
    hq = speak(hq_txt, speed=1.10)
    esc = speak(b0.get("escalation_line", ""), speed=1.08) if b0.get("escalation_line") else np.zeros(0, np.float32)

    v_parts, sfx_events, cues, cur = [sub_thump(0.24, 0.42)[: int(SR * 0.12)]], [], [], 0.12
    v_parts[0] = np.zeros(int(SR * 0.12), np.float32)
    sfx_events.append((0.0, sub_thump(0.28, 0.46)))

    hq_end = cur + len(hq) / SR
    cues.append((cur, hq_end, hq_txt))
    v_parts.append(hq)
    cur = hq_end
    if len(esc) > 0:
        v_parts.append(np.zeros(int(SR * 0.04), np.float32))
        cur += 0.04
        esc_end = cur + len(esc) / SR
        cues.append((cur, esc_end, b0["escalation_line"]))
        v_parts.append(esc)
        cur = esc_end
    beat_times = [[0.0, round(cur, 3)]]

    climax_idx, climax_time = min(3, len(beats) - 1), cur
    for i in range(1, len(beats)):
        gap = 0.24 if i == climax_idx else 0.06
        v_parts.append(np.zeros(int(SR * gap), np.float32))
        cur += gap
        if i == climax_idx:
            climax_time = cur
            sfx_events.append((cur - 0.04, sub_thump(0.45, 0.55)))
        else:
            sfx_events.append((max(0.0, cur - 0.14), swept_whoosh(0.26)))
            sfx_events.append((cur, sub_thump(0.22, 0.30)))
        ntxt = beats[i].get("narration") or sc.get("topic", "Look closely")
        v = speak(ntxt, speed=1.07)
        st, en = cur, cur + len(v) / SR
        cues.append((st, en, ntxt))
        v_parts.append(v)
        beat_times.append([round(st, 3), round(en, 3)])
        cur = en

    v_parts.append(np.zeros(int(SR * 0.08), np.float32))
    voice = np.concatenate(v_parts).astype(np.float32)
    voice_norm = voice * (0.78 / max(0.05, float(np.max(np.abs(voice)))))

    bed = build_bed(len(voice), climax_time) * duck_envelope(voice_norm)
    sfx = np.zeros(len(voice), np.float32)
    for t_ev, clip in sfx_events:
        p = max(0, int(t_ev * SR))
        end = min(len(sfx), p + len(clip))
        if end > p:
            sfx[p:end] += clip[: end - p]

    master = np.tanh((voice_norm + bed + sfx) * 1.05).astype(np.float32)
    sf.write("_raw_short.wav", master, SR, subtype="PCM_16")
    subprocess.run(
        ["ffmpeg", "-y", "-i", "_raw_short.wav", "-af", "loudnorm=I=-14.0:TP=-1.0:LRA=9:linear=true", "-ar", "48000", "final_audio.wav"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    os.remove("_raw_short.wav")
    total_dur = len(master) / SR

    ass = [
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n",
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Cap,DejaVu Sans,70,&H00FFFFFF,&H0000D7FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,6,3,2,48,48,540,1",
        "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    srt, idx_s = [], 1
    for st, en, txt in cues:
        words = txt.split()
        chunks = [" ".join(words[j : j + 2]) for j in range(0, len(words), 2)] or [txt]
        dt = (en - st) / len(chunks)
        for j, ch in enumerate(chunks):
            cs, ce = st + j * dt, st + (j + 1) * dt
            ass.append(f"Dialogue: 1,{ts_ass(cs)},{ts_ass(ce)},Cap,,0,0,0,,{color_pop(ch)}")
            srt.append(f"{idx_s}\n{ts_srt(cs)} --> {ts_srt(ce)}\n{ch}\n")
            idx_s += 1

    open("subtitles.ass", "w", encoding="utf-8").write("\n".join(ass))
    open("subtitles.srt", "w", encoding="utf-8").write("\n".join(srt))
    open("subtitles_en.srt", "w", encoding="utf-8").write("\n".join(srt))
    for i, (st, en) in enumerate(beat_times):
        beats[i]["duration"] = round(max(0.8, en - st), 3)
    sc["beat_times"], sc["climax_time"], sc["total_duration"] = beat_times, round(climax_time, 3), round(total_dur, 3)
    json.dump(sc, open(SCRIPT_FILE, "w", encoding="utf-8"), indent=2)
    print(f"[+] Audio Ready: {total_dur:.2f}s | Speed 1.08x + Ducking + -14 LUFS", flush=True)


if __name__ == "__main__":
    main()
