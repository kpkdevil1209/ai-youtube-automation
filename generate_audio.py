# generate_audio.py - AI Voiceover + Auto-Ducked Gaming Music + Synced Pop Subtitles
import os, re, json, time, asyncio, random, shutil, subprocess, requests, edge_tts

SCRIPT_FILE = "current_script.json"
OUT_AUDIO = "final_audio.wav"
SRT_MAIN = "subtitles.srt"
SRT_EN = "subtitles_en.srt"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

BACKUP_BGM = [
    "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Voxel%20Revolution.mp3",
    "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Rising%20Game.mp3",
    "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Cypher.mp3",
    "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Impact%20Moderato.mp3"
]

def fmt_srt(sec):
    ms = int(round(max(0.0, sec) * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def clean_tts(txt):
    t = re.sub(r"[\[\]\(\)\*#_`\"<>]", " ", str(txt or ""))
    return re.sub(r"\s+", " ", t).strip()

def probe_dur(path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
    return float(subprocess.check_output(cmd, text=True).strip())

async def synth_clip(text, out_mp3):
    for voice in ("en-IN-PrabhatNeural", "hi-IN-MadhurNeural"):
        try:
            comm = edge_tts.Communicate(text, voice, rate="+14%")
            await comm.save(out_mp3)
            if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 1000:
                return True
        except Exception:
            await asyncio.sleep(1)
    return False

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
                    url = f"https://archive.org/download/{ident}/{nm}"
                    with requests.get(url, headers=hdr, stream=True, timeout=25) as ar:
                        if ar.status_code < 400:
                            with open(dest, "wb") as fp:
                                for c in ar.iter_content(131072):
                                    if c:
                                        fp.write(c)
                            if os.path.getsize(dest) > 300_000:
                                print(f"[+] BGM Locked (Archive.org): {nm}")
                                return dest
    except Exception:
        pass
    for url in random.sample(BACKUP_BGM, len(BACKUP_BGM)):
        try:
            with requests.get(url, headers=hdr, stream=True, timeout=20) as ar:
                if ar.status_code < 400:
                    with open(dest, "wb") as fp:
                        for c in ar.iter_content(131072):
                            if c:
                                fp.write(c)
                    if os.path.getsize(dest) > 200_000:
                        print(f"[+] BGM Locked (Incompetech): {os.path.basename(url)}")
                        return dest
        except Exception:
            pass
    return None

def split_chunks(text, t0, dur):
    words = text.split()
    if not words:
        return []
    groups = [" ".join(words[i : i + 4]) for i in range(0, len(words), 4)]
    total_ch = max(1, sum(len(g) for g in groups))
    out, cur = [], t0
    for g in groups:
        gd = dur * (len(g) / total_ch)
        out.append((cur, cur + gd, g))
        cur += gd
    return out

def main():
    print("\n==========================================")
    print("[*] AUDIO & SUBTITLE ENGINE: VOICE + BGM")
    print("==========================================")
    if not os.path.exists(SCRIPT_FILE):
        raise FileNotFoundError("current_script.json nahi mila!")
    data = json.load(open(SCRIPT_FILE, "r", encoding="utf-8"))
    scenes = data.get("scenes") or [{"narration": data.get("script", "DEVIL 999 clutch!"), "english_subtitle": data.get("english_script", "DEVIL 999 clutch!")}]

    os.makedirs("tmp_aud", exist_ok=True)
    wav_list, main_subs, en_subs = [], [], []
    cur_t, srt_idx = 0.0, 1

    for i, sc in enumerate(scenes):
        nar = clean_tts(sc.get("narration") or sc.get("text") or "")
        eng = clean_tts(sc.get("english_subtitle") or nar)
        if not nar:
            continue
        mp3_p, wav_p = f"tmp_aud/s_{i}.mp3", f"tmp_aud/s_{i}.wav"
        ok = asyncio.run(synth_clip(nar, mp3_p))
        if not ok:
            raise RuntimeError(f"TTS failed on scene {i}")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp3_p, "-af", "apad=pad_dur=0.12", "-ar", "44100", "-ac", "1", wav_p], check=True)
        sdur = probe_dur(wav_p)
        wav_list.append(wav_p)
        for st, en, chunk in split_chunks(nar, cur_t, sdur):
            main_subs.append(f"{srt_idx}\n{fmt_srt(st)} --> {fmt_srt(en)}\n{chunk}\n")
            en_subs.append(f"{srt_idx}\n{fmt_srt(st)} --> {fmt_srt(en)}\n{eng}\n" if chunk == split_chunks(nar, cur_t, sdur)[0][2] else f"{srt_idx}\n{fmt_srt(st)} --> {fmt_srt(en)}\n{chunk}\n")
            srt_idx += 1
        cur_t += sdur

    if not wav_list:
        raise RuntimeError("No voice segments generated!")

    with open("tmp_aud/list.txt", "w") as f:
        for w in wav_list:
            f.write(f"file '{os.path.abspath(w)}'\n")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "tmp_aud/list.txt", "-c", "copy", "voice_only.wav"], check=True)
    vdur = probe_dur("voice_only.wav")

    with open(SRT_MAIN, "w", encoding="utf-8") as f:
        f.write("\n".join(main_subs))
    with open(SRT_EN, "w", encoding="utf-8") as f:
        f.write("\n".join(en_subs))

    bgm = download_bgm()
    if bgm:
        fc = (
            "[1:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=0.30[bgm];"
            "[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,asplit=2[v1][v2];"
            "[bgm][v1]sidechaincompress=threshold=0.02:ratio=6:attack=40:release=350[duck];"
            "[v2][duck]amix=inputs=2:duration=first,volume=1.75[out]"
        )
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "voice_only.wav", "-stream_loop", "-1", "-i", bgm, "-filter_complex", fc, "-map", "[out]", "-t", f"{vdur:.2f}", "-ar", "44100", "-ac", "2", OUT_AUDIO], check=True)
    else:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "voice_only.wav", "-ar", "44100", "-ac", "2", OUT_AUDIO], check=True)

    shutil.rmtree("tmp_aud", ignore_errors=True)
    print(f"[+] Saved {OUT_AUDIO} ({probe_dur(OUT_AUDIO):.2f}s) + {SRT_MAIN} + {SRT_EN}")

if __name__ == "__main__":
    main()
