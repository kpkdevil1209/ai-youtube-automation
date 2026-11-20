import asyncio
import json
import os
import re
import subprocess
import wave

SCRIPT_FILE = "current_script.json"
KOKORO_MODEL = os.path.expanduser("~/.cache/kokoro/kokoro-v1.0.onnx")
KOKORO_VOICES = os.path.expanduser("~/.cache/kokoro/voices-v1.0.bin")

DANGER_WORDS = {
    "DEAD", "DEATH", "DIE", "DIES", "ZERO", "NEVER", "STOP", "BLOOD",
    "CRUSH", "BLIND", "VOID", "DARK", "BANNED", "SEALED", "TRAP", "TRAPPED",
    "KILL", "GHOST", "SCREAM", "TERRIFYING", "INSTANT", "EXPLODE", "FINAL",
    "SECONDS", "SECOND", "MINUTES", "METERS", "MILES", "ALONE", "SILENT",
}


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
        samples, sr = kokoro.create(b["narration"], voice=voice, speed=1.08, lang=lang)
        sf.write(raw, samples, sr)
        clean_speech(raw, clean)
        os.remove(raw)
        beat_files.append(clean)
    return beat_files


async def _edge_one(text, voice, out_mp3):
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate="+8%", pitch="-2Hz")
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


def fmt_ass_time(sec):
    cs_tot = int(round(max(0.0, sec) * 100))
    h, rem = divmod(cs_tot, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def style_ass_chunk(chunk):
    tokens = chunk.upper().split()
    styled = []
    highlighted = False
    for t in tokens:
        bare = re.sub(r"[^A-Z0-9]", "", t)
        if bare in DANGER_WORDS or any(c.isdigit() for c in bare):
            styled.append("{\\c&H003B3BFF&}" + t + "{\\c&H00FFFFFF&}")
            highlighted = True
        else:
            styled.append(t)
    if not highlighted and styled:
        styled[-1] = "{\\c&H0000D7FF&}" + styled[-1] + "{\\c&H00FFFFFF&}"
    return "{\\fscx112\\fscy112\\t(0,95,\\fscx100\\fscy100)}" + " ".join(styled)


def build_captions(beats, beat_times):
    srt_entries = []
    ass_events = []
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
            srt_entries.append(f"{idx}\n{fmt_srt_time(t0)} --> {fmt_srt_time(t1)}\n{ch.upper()}\n")
            ass_events.append(f"Dialogue: 0,{fmt_ass_time(t0)},{fmt_ass_time(t1)},Default,,0,0,0,,{style_ass_chunk(ch)}")
            idx += 1

    srt_text = "\n".join(srt_entries)
    for fname in ("subtitles.srt", "subtitles_en.srt"):
        with open(fname, "w", encoding="utf-8") as f:
            f.write(srt_text)

    ass_header = "\n".join([
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,DejaVu Sans,68,&H00FFFFFF,&H0000D7FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,60,60,470,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])
    with open("subtitles.ass", "w", encoding="utf-8") as f:
        f.write(ass_header + "\n" + "\n".join(ass_events) + "\n")


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
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.13", "gap.wav",
    ], check=True)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.32", "drop_gap.wav",
    ], check=True)

    climax_idx = min(4, len(beat_files) - 1)
    beat_times = []
    cursor = 0.0
    concat_inputs = []
    for i, wf in enumerate(beat_files):
        d = wav_duration(wf)
        if i == climax_idx and i > 0:
            concat_inputs.append("drop_gap.wav")
            cursor += 0.32
        start = round(cursor, 3)
        end = round(cursor + d + 0.13, 3)
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
    climax_start = beat_times[climax_idx]["start"]
    drop0 = max(0.5, climax_start - 0.34)
    climax_ms = int(climax_start * 1000)

    drone_expr = "0.45*sin(2*PI*55*t)+0.28*sin(2*PI*82.4*t)+0.18*sin(2*PI*110*t)*sin(2*PI*0.35*t)"
    boom_expr = "sin(2*PI*(95*exp(-3*t))*t)*exp(-4.2*t)"

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", "voice_full.wav",
        "-f", "lavfi", "-t", f"{total_dur:.2f}", "-i", f"aevalsrc={drone_expr}:s=44100",
        "-f", "lavfi", "-t", "1.1", "-i", f"aevalsrc={boom_expr}:s=44100",
        "-f", "lavfi", "-t", "1.1", "-i", f"aevalsrc={boom_expr}:s=44100",
    ]
    fc_parts = [
        "[0:a]apad=pad_dur=0.35,highpass=f=75,equalizer=f=180:width_type=h:width=120:g=3.5,"
        "equalizer=f=3200:width_type=h:width=800:g=2.5,acompressor=threshold=-16dB:ratio=3,volume=1.38[vox]",
        f"[1:a]lowpass=f=220,volume='if(between(t,{drop0:.2f},{climax_start:.2f}),0,0.22)':eval=frame,"
        f"afade=t=in:st=0:d=0.5,afade=t=out:st={total_dur-0.7:.2f}:d=0.7[bgm]",
        "[2:a]volume=0.55[b0]",
        f"[3:a]volume=0.58,adelay={climax_ms}|{climax_ms}[b4]",
    ]
    mix_labels = ["[vox]", "[bgm]", "[b0]", "[b4]"]

    for w_i in range(1, len(beat_times)):
        if w_i == climax_idx:
            continue
        in_idx = 4 + (len(mix_labels) - 4)
        ms = int(max(0.1, beat_times[w_i]["start"] - 0.12) * 1000)
        cmd.extend(["-f", "lavfi", "-t", "0.35", "-i", "anoisesrc=color=pink:sample_rate=44100"])
        lbl = f"[w{w_i}]"
        fc_parts.append(f"[{in_idx}:a]bandpass=f=850:width_type=h:width=500,afade=t=in:d=0.14,afade=t=out:st=0.14:d=0.20,volume=0.24,adelay={ms}|{ms}{lbl}")
        mix_labels.append(lbl)

    fc_parts.append(f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=0,alimiter=limit=0.95[out]")
    cmd.extend(["-filter_complex", ";".join(fc_parts), "-map", "[out]", "-ar", "44100", "-ac", "2", "final_audio.wav"])
    subprocess.run(cmd, check=True)

    build_captions(beats, beat_times)
    data["beat_times"] = beat_times
    data["total_duration"] = round(total_dur, 3)
    with open(SCRIPT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    for tmp in beat_files + ["gap.wav", "drop_gap.wav", "vconcat.txt", "voice_full.wav"]:
        if os.path.exists(tmp):
            os.remove(tmp)
    print(f"[+] Master Audio & Color-Pop ASS Ready: {total_dur:.2f}s | {len(beat_times)} beats!", flush=True)


if __name__ == "__main__":
    main()
