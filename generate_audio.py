import asyncio
import json
import os
import subprocess
import wave

SCRIPT_FILE = "current_script.json"
KOKORO_MODEL = os.path.expanduser("~/.cache/kokoro/kokoro-v1.0.onnx")
KOKORO_VOICES = os.path.expanduser("~/.cache/kokoro/voices-v1.0.bin")


def wav_duration(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate())


def clean_speech(in_wav, out_wav):
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", in_wav,
        "-af", "silenceremove=start_periods=1:start_threshold=-42dB:start_duration=0.02,aresample=44100",
        "-ac", "1", out_wav,
    ]
    subprocess.run(cmd, check=True)


def synth_kokoro_beats(beats, theme):
    import soundfile as sf
    from kokoro_onnx import Kokoro

    kokoro = Kokoro(KOKORO_MODEL, KOKORO_VOICES)
    use_gb = theme in ("SPACE", "MYSTERY")
    voice = "bm_george" if use_gb else "am_adam"
    lang = "en-gb" if use_gb else "en-us"
    print(f"[*] Kokoro-82M Narrator: {voice} ({lang})", flush=True)

    beat_files = []
    for i, b in enumerate(beats):
        raw = f"tmp_b_{i}.wav"
        clean = f"beat_v_{i}.wav"
        samples, sr = kokoro.create(b["narration"], voice=voice, speed=1.06, lang=lang)
        sf.write(raw, samples, sr)
        clean_speech(raw, clean)
        os.remove(raw)
        beat_files.append(clean)
    return beat_files


async def _edge_one(text, voice, out_mp3):
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate="+6%", pitch="-2Hz")
    await comm.save(out_mp3)


def synth_edge_fallback(beats, theme):
    voice = "en-GB-RyanNeural" if theme in ("SPACE", "MYSTERY") else "en-US-AndrewMultilingualNeural"
    print(f"[!] Fallback Edge-TTS Narrator: {voice}", flush=True)
    beat_files = []
    for i, b in enumerate(beats):
        mp3 = f"tmp_b_{i}.mp3"
        clean = f"beat_v_{i}.wav"
        asyncio.run(_edge_one(b["narration"], voice, mp3))
        clean_speech(mp3, clean)
        os.remove(mp3)
        beat_files.append(clean)
    return beat_files


def fmt_srt_time(sec):
    ms = int(round(max(0.0, sec) * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_subtitles(beats, beat_times):
    entries = []
    idx = 1
    for b, bt in zip(beats, beat_times):
        words = b["narration"].split()
        if not words:
            continue
        chunks = [" ".join(words[k:k + 3]) for k in range(0, len(words), 3)]
        span = max(0.4, (bt["end"] - bt["start"]) - 0.1)
        step = span / len(chunks)
        for j, ch in enumerate(chunks):
            t0 = bt["start"] + j * step
            t1 = min(bt["end"], t0 + step)
            entries.append(f"{idx}\n{fmt_srt_time(t0)} --> {fmt_srt_time(t1)}\n{ch.upper()}\n")
            idx += 1
    srt_text = "\n".join(entries)
    for fname in ("subtitles.srt", "subtitles_en.srt"):
        with open(fname, "w", encoding="utf-8") as f:
            f.write(srt_text)


def main():
    with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    beats = data["beats"]
    theme = data.get("theme", "OCEAN")

    if os.path.exists(KOKORO_MODEL) and os.path.exists(KOKORO_VOICES):
        try:
            beat_files = synth_kokoro_beats(beats, theme)
        except Exception as e:
            print(f"[!] Kokoro error ({e}), using fallback...", flush=True)
            beat_files = synth_edge_fallback(beats, theme)
    else:
        beat_files = synth_edge_fallback(beats, theme)

    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.14", "gap.wav",
    ], check=True)

    beat_times = []
    cursor = 0.0
    concat_inputs = []
    for i, wf in enumerate(beat_files):
        d = wav_duration(wf)
        start = round(cursor, 3)
        end = round(cursor + d + 0.14, 3)
        beat_times.append({"idx": i, "start": start, "end": end})
        concat_inputs.extend([wf, "gap.wav"])
        cursor = end

    with open("vconcat.txt", "w", encoding="utf-8") as f:
        for p in concat_inputs:
            f.write(f"file '{p}'\n")
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", "vconcat.txt", "-c", "copy", "voice_full.wav",
    ], check=True)

    total_dur = max(12.0, wav_duration("voice_full.wav") + 0.35)
    climax_ms = int(beat_times[min(4, len(beat_times) - 1)]["start"] * 1000)

    # Dark ambient sub-drone BGM + opening boom + climax boom + studio voice EQ
    fc = (
        f"[0:a]highpass=f=75,equalizer=f=180:width_type=h:width=120:g=3.5,"
        f"equalizer=f=3200:width_type=h:width=800:g=2.5,acompressor=threshold=-16dB:ratio=3,volume=1.35[vox];"
        f"[1:a]lowpass=f=220,volume=0.22,afade=t=in:st=0:d=0.6,afade=t=out:st={total_dur-0.8:.2f}:d=0.8[bgm];"
        f"[2:a]volume=0.55[b0];"
        f"[3:a]volume=0.55,adelay={climax_ms}|{climax_ms}[b4];"
        f"[vox][bgm][b0][b4]amix=inputs=4:duration=first:dropout_transition=0,alimiter=limit=0.95[out]"
    )
    drone_expr = "0.45*sin(2*PI*55*t)+0.30*sin(2*PI*82.4*t)+0.20*sin(2*PI*110*t)*sin(2*PI*0.35*t)"
    boom_expr = "sin(2*PI*(95*exp(-3*t))*t)*exp(-4.2*t)"

    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", "voice_full.wav",
        "-f", "lavfi", "-t", f"{total_dur:.2f}", "-i", f"aevalsrc={drone_expr}:s=44100",
        "-f", "lavfi", "-t", "1.1", "-i", f"aevalsrc={boom_expr}:s=44100",
        "-f", "lavfi", "-t", "1.1", "-i", f"aevalsrc={boom_expr}:s=44100",
        "-filter_complex", fc, "-map", "[out]", "-ar", "44100", "-ac", "2", "final_audio.wav",
    ], check=True)

    build_subtitles(beats, beat_times)
    data
