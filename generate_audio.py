import os, json, asyncio, subprocess, requests, edge_tts

HI_CANDIDATES = ["hi-IN-AaravNeural", "hi-IN-ArjunNeural", "hi-IN-MadhurNeural"]
EN_FALLBACK = "en-IN-PrabhatNeural"
BGM_URLS = [
    "https://archive.org/download/DarkTrapBeatNoCopyright/Dark_Trap_Beat.mp3",
    "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Voxel%20Revolution.mp3",
]


def probe_dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True, timeout=15)
    try: return max(0.2, float(r.stdout.strip()))
    except Exception: return 2.5


def fmt_srt(sec):
    ms = max(0, int(round(sec * 1000)))
    h, rem = divmod(ms, 3600000); m, rem = divmod(rem, 60000); s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


async def pick_best_hindi_voice():
    try:
        avail = {v.get("ShortName") for v in await edge_tts.list_voices() if v.get("ShortName")}
        for cand in HI_CANDIDATES:
            if cand in avail:
                print(f"[*] Natural Hindi Voice: {cand}")
                return cand
    except Exception: pass
    return "hi-IN-MadhurNeural"


async def tts_edge(text, voice, rate, out_mp3):
    await edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch="+0Hz").save(out_mp3)


def tts_elevenlabs(text, out_mp3, key):
    vid = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        json={"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.42, "similarity_boost": 0.78, "style": 0.35}},
        timeout=35,
    )
    if r.status_code == 200 and len(r.content) > 1000:
        open(out_mp3, "wb").write(r.content); return True
    return False


def make_sfx():
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=58:duration=0.42", "-af", "afade=t=in:ss=0:d=0.01,afade=t=out:st=0.09:d=0.33,volume=0.85", "-ar", "44100", "-ac", "2", "hit.wav"], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anoisesrc=d=0.22:c=pink", "-af", "bandpass=f=850:w=550,afade=t=in:ss=0:d=0.04,afade=t=out:st=0.07:d=0.15,volume=0.38", "-ar", "44100", "-ac", "2", "whoosh.wav"], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=480:duration=0.26", "-af", "vibrato=f=18:d=0.8,afade=t=in:ss=0:d=0.02,afade=t=out:st=0.08:d=0.18,volume=0.36", "-ar", "44100", "-ac", "2", "rewind.wav"], check=True)


def get_bgm(dur):
    for u in BGM_URLS:
        try:
            r = requests.get(u, timeout=20)
            if r.status_code == 200 and len(r.content) > 80000:
                open("bgm_raw.mp3", "wb").write(r.content)
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", "bgm_raw.mp3", "-t", f"{dur:.2f}", "-ar", "44100", "-ac", "2", "bgm.wav"], check=True)
                return "bgm.wav"
        except Exception: pass
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=55:duration={dur:.2f}", "-af", "tremolo=f=4.5:d=0.5,lowpass=f=220,volume=0.30", "-ar", "44100", "-ac", "2", "bgm.wav"], check=True)
    return "bgm.wav"


def build_audio():
    print("==========================================")
    print("[*] AGENT 4A: NATURAL VOICE + PRO SFX")
    print("==========================================")
    data = json.load(open("current_script.json", "r", encoding="utf-8"))
    segs = data.get("segments") or [{"text": "भाई रुक... ये शॉट कैसे लगा?!", "en": "Wait... how did that shot hit?!", "pace": "fast", "sfx": "hit"}]
    el_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    hi_voice = asyncio.run(pick_best_hindi_voice())

    wavs, srt_entries, cur_t = [], [], 0.0
    rate_map = {"fast": "+10%", "normal": "+6%", "slow": "+0%"}

    for idx, seg in enumerate(segs):
        hi_txt = str(seg.get("text") or "").strip()
        en_txt = str(seg.get("en") or hi_txt).strip()
        rate = rate_map.get(seg.get("pace", "normal"), "+6%")
        mp3_p, wav_p = f"seg_{idx}.mp3", f"seg_{idx}.wav"

        ok = bool(el_key and tts_elevenlabs(hi_txt, mp3_p, el_key))
        if not ok:
            for voice, txt in [(hi_voice, hi_txt), (EN_FALLBACK, en_txt)]:
                try:
                    asyncio.run(tts_edge(txt, voice, rate, mp3_p))
                    if os.path.exists(mp3_p) and os.path.getsize(mp3_p) > 800: ok = True; break
                except Exception as e: print(f"[!] TTS retry ({voice}): {e}")
        if not ok: raise RuntimeError(f"TTS failed for segment {idx}")

        trim = "silenceremove=start_periods=1:start_duration=0:start_threshold=-46dB:stop_periods=-1:stop_duration=0.06:stop_threshold=-46dB," if idx == 0 else "silenceremove=start_periods=1:start_duration=0:start_threshold=-50dB,"
        warm_eq = f"{trim}highpass=f=75,equalizer=f=180:t=q:w=1.2:g=3,equalizer=f=3200:t=q:w=1.5:g=2,alimiter=limit=0.92"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp3_p, "-af", warm_eq, "-ar", "44100", "-ac", "2", wav_p], check=True)
        seg_dur = probe_dur(wav_p)
        wavs.append({"wav": wav_p, "start": cur_t, "dur": seg_dur, "sfx": seg.get("sfx", "whoosh")})

        words = en_txt.split()
        chunks = [" ".join(words[k:k+2]) for k in range(0, len(words), 2)] or [en_txt]
        step = seg_dur / len(chunks)
        for ci, ch in enumerate(chunks):
            srt_entries.append((cur_t + ci * step, cur_t + (ci + 1) * step, ch))
        cur_t += seg_dur

    data["beat_times"] = [round(w["start"], 2) for w in wavs]
    json.dump(data, open("current_script.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    with open("concat_list.txt", "w", encoding="utf-8") as f:
        for w in wavs: f.write(f"file '{w['wav']}'\n")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "concat_list.txt", "-ar", "44100", "-ac", "2", "voice_all.wav"], check=True)

    total_dur = max(12.0, min(32.0, probe_dur("voice_all.wav") + 0.5))
    make_sfx()
    bgm_wav = get_bgm(total_dur)

    sfx_files = {"hit": "hit.wav", "whoosh": "whoosh.wav", "rewind": "rewind.wav"}
    ins, fc, v_labels, in_idx = ["-i", bgm_wav, "-i", "voice_all.wav"], [], ["[1:a]"], 2
    for i, w in enumerate(wavs):
        sfx_f = sfx_files.get(w["sfx"])
        if not sfx_f: continue
        ins += ["-i", sfx_f]
        ms = max(0, int(w["start"] * 1000))
        fc.append(f"[{in_idx}:a]adelay={ms}|{ms}[sf{i}]")
        v_labels.append(f"[sf{i}]"); in_idx += 1

    fc.append(f"{''.join(v_labels)}amix=inputs={len(v_labels)}:duration=first:normalize=0[fg]" if len(v_labels) > 1 else "[1:a]anull[fg]")
    fc.append("[fg]asplit=2[fg_sc][fg_mix]")
    fc.append("[0:a]volume=0.18[bgm_low];[bgm_low][fg_sc]sidechaincompress=threshold=0.03:ratio=8:attack=12:release=180[bgm_duck]")
    fc.append("[fg_mix][bgm_duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=7[out]")
    subprocess.run(["ffmpeg", "-y", "-v", "error"] + ins + ["-filter_complex", ";".join(fc), "-map", "[out]", "-t", f"{total_dur:.2f}", "-ar", "44100", "-ac", "2", "final_audio.wav"], check=True)

    for srt_name in ["subtitles.srt", "subtitles_en.srt"]:
        with open(srt_name, "w", encoding="utf-8") as f:
            for idx, (s_t, e_t, txt) in enumerate(srt_entries, 1):
                f.write(f"{idx}\n{fmt_srt(s_t)} --> {fmt_srt(e_t)}\n{txt}\n\n")

    print(f"[+] Audio Ready: {probe_dur('final_audio.wav'):.2f}s")


if __name__ == "__main__":
    build_audio()
