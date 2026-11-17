# generate_audio.py - Agent 4A: Cinema Voiceover + Micro-SFX + Ducked Phonk + Synced SRT
import os, re, json, asyncio, random, shutil, subprocess, requests, edge_tts

SCRIPT_FILE, OUT_AUDIO, SRT_MAIN, SRT_EN = "current_script.json", "final_audio.wav", "subtitles.srt", "subtitles_en.srt"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
BACKUP_BGM = [
    "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Voxel%20Revolution.mp3",
    "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Rising%20Game.mp3",
    "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Cypher.mp3"
]

def fmt_srt(sec):
    ms = int(round(max(0.0, sec) * 1000))
    h, rem = divmod(ms, 3600000); m, rem = divmod(rem, 60000); s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def clean_tts(txt):
    return re.sub(r"\s+", " ", re.sub(r"[\[\]\(\)\*#_`\"<>]", " ", str(txt or ""))).strip()

def probe_dur(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path], text=True).strip())

async def synth_clip(text, out_mp3, rate="+14%"):
    for voice in ("en-IN-PrabhatNeural", "hi-IN-MadhurNeural"):
        try:
            await edge_tts.Communicate(text, voice, rate=rate).save(out_mp3)
            if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 1000:
                return True
        except Exception:
            await asyncio.sleep(1)
    return False

def make_sfx():
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "aevalsrc=0.75*sin(2*PI*(110*exp(-6*t))*t)*exp(-5*t):d=0.45:s=44100", "-ar", "44100", "-ac", "2", "tmp_aud/hit.wav"], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anoisesrc=c=pink:d=0.30:r=44100", "-af", "bandpass=f=900:w=600,afade=t=in:ss=0:d=0.12,afade=t=out:st=0.12:d=0.18,volume=0.8", "-ar", "44100", "-ac", "2", "tmp_aud/whoosh.wav"], check=True)

def download_bgm(dest="bgm_track.mp3"):
    hdr = {"User-Agent": UA}
    try:
        r = requests.get("https://archive.org/advancedsearch.php", params={"q": "mediatype:audio AND (phonk OR trap OR electronic) AND format:VBR MP3", "fl[]": "identifier", "rows": 12, "output": "json"}, headers=hdr, timeout=10)
        docs = (r.json().get("response") or {}).get("docs") or [] if r.status_code == 200 else []
        random.shuffle(docs)
        for doc in docs[:5]:
            ident = doc.get("identifier")
            if not ident:
                continue
            mr = requests.get(f"https://archive.org/metadata/{ident}", headers=hdr, timeout=10)
            for f in (mr.json().get("files") or []) if mr.status_code == 200 else []:
                nm, sz = f.get("name", ""), int(f.get("size") or 0)
                if nm.lower().endswith(".mp3") and 500_000 < sz < 12_000_000:
                    with requests.get(f"https://archive.org/download/{ident}/{nm}", headers=hdr, stream=True, timeout=25) as ar:
                        if ar.status_code < 400:
                            with open(dest, "wb") as fp:
                                for c in ar.iter_content(131072):
                                    if c: fp.write(c)
                            if os.path.getsize(dest) > 300_000:
                                return dest
    except Exception:
        pass
    for url in random.sample(BACKUP_BGM, len(BACKUP_BGM)):
        try:
            with requests.get(url, headers=hdr, stream=True, timeout=20) as ar:
                if ar.status_code < 400:
                    with open(dest, "wb") as fp:
                        for c in ar.iter_content(131072):
                            if c: fp.write(c)
                    if os.path.getsize(dest) > 200_000:
                        return dest
        except Exception:
            pass
    return None

def split_chunks(text, t0, dur):
    words = text.split()
    if not words: return []
    groups = [" ".join(words[i : i + 3]) for i in range(0, len(words), 3)]
    tot = max(1, sum(len(g) for g in groups))
    out, cur = [], t0
    for g in groups:
        gd = dur * (len(g) / tot)
        out.append((cur, cur + gd, g)); cur += gd
    return out

def main():
    print("\n==========================================")
    print("[*] AGENT 4A: CINEMA VOICE, SFX & BGM")
    print("==========================================")
    if not os.path.exists(SCRIPT_FILE):
        raise FileNotFoundError("current_script.json missing!")
    data = json.load(open(SCRIPT_FILE, "r", encoding="utf-8"))
    scenes = data.get("scenes") or [{"narration": data.get("script", "DEVIL 999 clutch!"), "english_subtitle": data.get("english_script", "DEVIL 999 clutch!")}]

    os.makedirs("tmp_aud", exist_ok=True)
    make_sfx()
    wavs, main_subs, en_subs, cur_t, s_idx, e_idx = [], [], [], 0.0, 1, 1

    for i, sc in enumerate(scenes):
        nar = clean_tts(sc.get("narration") or sc.get("text") or "")
        eng = clean_tts(sc.get("english_subtitle") or nar)
        if not nar: continue
        rate = "+18%" if i == 0 else ("+16%" if i == len(scenes) - 1 else "+12%")
        mp3_p, wav_p = f"tmp_aud/s_{i}.mp3", f"tmp_aud/s_{i}.wav"
        if not asyncio.run(synth_clip(nar, mp3_p, rate=rate)):
            raise RuntimeError(f"TTS failed on scene {i}")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp3_p, "-af", "highpass=f=85,treble=g=3,acompressor=threshold=-16dB:ratio=3,apad=pad_dur=0.10", "-ar", "44100", "-ac", "2", wav_p], check=True)
        sdur = probe_dur(wav_p)
        wavs.append(wav_p)
        for st, en, chunk in split_chunks(nar, cur_t, sdur):
            main_subs.append(f"{s_idx}\n{fmt_srt(st)} --> {fmt_srt(en)}\n{chunk}\n"); s_idx += 1
        en_subs.append(f"{e_idx}\n{fmt_srt(cur_t)} --> {fmt_srt(cur_t + sdur)}\n{eng}\n"); e_idx += 1
        cur_t += sdur

    open("tmp_aud/list.txt", "w").write("\n".join(f"file '{os.path.abspath(w)}'" for w in wavs))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "tmp_aud/list.txt", "-c", "copy", "tmp_aud/voice.wav"], check=True)
    vdur = probe_dur("tmp_aud/voice.wav")
    open(SRT_MAIN, "w", encoding="utf-8").write("\n".join(main_subs))
    open(SRT_EN, "w", encoding="utf-8").write("\n".join(en_subs))

    d_mid, d_w1, d_w2 = int(vdur * 500), int(vdur * 250), int(vdur * 750)
    sfx_fc = (
        f"[1:a]volume=0.55[h0];[1:a]adelay={d_mid}|{d_mid},volume=0.55[h1];"
        f"[2:a]adelay={d_w1}|{d_w1},volume=0.45[w1];[2:a]adelay={d_w2}|{d_w2},volume=0.45[w2];"
        "[0:a][h0][h1][w1][w2]amix=inputs=5:duration=first,volume=2.4[vfx]"
    )
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "tmp_aud/voice.wav", "-i", "tmp_aud/hit.wav", "-i", "tmp_aud/whoosh.wav", "-filter_complex", sfx_fc, "-map", "[vfx]", "-t", f"{vdur:.2f}", "-ar", "44100", "-ac", "2", "tmp_aud/voice_sfx.wav"], check=True)

    bgm = download_bgm()
    if bgm:
        fc = "[1:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=0.30[bgm];[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,asplit=2[v1][v2];[bgm][v1]sidechaincompress=threshold=0.02:ratio=6:attack=40:release=350[duck];[v2][duck]amix=inputs=2:duration=first,volume=1.75[out]"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "tmp_aud/voice_sfx.wav", "-stream_loop", "-1", "-i", bgm, "-filter_complex", fc, "-map", "[out]", "-t", f"{vdur:.2f}", "-ar", "44100", "-ac", "2", OUT_AUDIO], check=True)
    else:
        shutil.copy2("tmp_aud/voice_sfx.wav", OUT_AUDIO)

    shutil.rmtree("tmp_aud", ignore_errors=True)
    print(f"[+] Audio Ready: {OUT_AUDIO} ({probe_dur(OUT_AUDIO):.2f}s) + {SRT_MAIN} + {SRT_EN}")

if __name__ == "__main__":
    main()
