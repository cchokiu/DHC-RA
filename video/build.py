#!/usr/bin/env python3
"""由 scenes.html + narration.txt 生成有廣東話旁白同燒入字幕嘅 dhc-1min.mp4。

語音來源（逐幕揀，優先次序）：
  1. voice/s<N>.(wav|mp3|m4a) —— 自己錄嘅旁白
  2. sherpa-onnx vits-cantonese —— 離線神經網絡粵語女聲，首次自動由 GitHub 下載模型（約 110MB）到 models/
  3. Edge TTS zh-HK-HiuMaanNeural —— 需要網絡可以連到 speech.platform.bing.com
  4. espeak-ng yue —— 離線、機械聲，只作示範
每幕長度 = max(原定秒數, 旁白長度 + 0.8 秒)。
依賴：pip install sherpa-onnx opencc-python-reimplemented
"""
import array, asyncio, os, re, shutil, subprocess, sys, tempfile, wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHROME = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell"
BASE_DUR = [5, 8, 10, 5, 6, 10, 4, 4]
LEAD = 0.3  # 每幕開始後幾耐先出聲
BG = "0xfbfaf7"
FONT = "WenQuanYi Zen Hei"


def run(*cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout)


MODEL = HERE / "models" / "vits-cantonese-hf-xiaomaiiwn"
MODEL_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
             "vits-cantonese-hf-xiaomaiiwn.tar.bz2")
_sherpa = None


def sherpa_tts(text, out):
    """模型字典係簡體字，所以先轉簡體再合成（讀音不變）。"""
    global _sherpa
    try:
        import sherpa_onnx
        from opencc import OpenCC
        if _sherpa is None:
            if not MODEL.exists():
                MODEL.parent.mkdir(exist_ok=True)
                subprocess.run(f"curl -sL '{MODEL_URL}' | tar xj -C '{MODEL.parent}'", shell=True, check=True)
            vits = sherpa_onnx.OfflineTtsVitsModelConfig(
                model=str(MODEL / f"{MODEL.name}.onnx"), lexicon=str(MODEL / "lexicon.txt"),
                tokens=str(MODEL / "tokens.txt"))
            _sherpa = (sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(vits=vits, num_threads=4),
                rule_fsts=str(MODEL / "rule.fst"))), OpenCC("t2s"))
        engine, cc = _sherpa
        audio = engine.generate(cc.convert(text), sid=0, speed=1.0)
        pcm = array.array("h", (int(max(-1.0, min(1.0, s)) * 32767) for s in audio.samples))
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(audio.sample_rate)
            w.writeframes(pcm.tobytes())
        return True
    except Exception:
        return False


def edge_tts(text, out):
    try:
        import certifi
        certifi.where = lambda: "/root/.ccr/ca-bundle.crt"
        import edge_tts as et
        comm = et.Communicate(text, "zh-HK-HiuMaanNeural", proxy=os.environ.get("HTTPS_PROXY"))
        asyncio.run(comm.save(str(out)))
        return out.stat().st_size > 0
    except Exception:
        return False


def tts(i, text, tmp):
    for ext in ("wav", "mp3", "m4a"):
        own = HERE / "voice" / f"s{i}.{ext}"
        if own.exists():
            return own, "錄音"
    wav = tmp / f"v{i}.wav"
    if sherpa_tts(text, wav):
        return wav, "sherpa-onnx 粵語"
    mp3 = tmp / f"v{i}.mp3"
    if edge_tts(text, mp3):
        return mp3, "Edge TTS"
    run("espeak-ng", "-v", "yue", "-s", "215", "-w", str(wav), text)
    return wav, "espeak-ng"


def ts(t):
    ms = round(t * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def subtitle_chunks(text, start, length):
    """按標點切句，時間按字數比例分配；句末標點唔顯示。"""
    parts = [p for p in re.split(r"[，。；：、]", text) if p.strip()]
    total = sum(len(p) for p in parts)
    t, out = start, []
    for p in parts:
        d = length * len(p) / total
        out.append((t, t + d, p.strip()))
        t += d
    return out


def main():
    lines = [l.strip() for l in (HERE / "narration.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == len(BASE_DUR), "narration.txt 要有 8 行"
    tmp = Path(tempfile.mkdtemp())
    srt, clips, t0, used = [], [], 0.0, set()

    for i, text in enumerate(lines, 1):
        audio, src = tts(i, text, tmp)
        used.add(src)
        a = duration(audio)
        d = round(max(BASE_DUR[i - 1], a + LEAD + 0.5), 2)
        png, clip = tmp / f"s{i}.png", tmp / f"c{i}.mp4"
        run(CHROME, "--headless", "--no-sandbox", "--hide-scrollbars", "--window-size=1920,1080",
            f"--screenshot={png}", f"file://{HERE}/scenes.html#s{i}")
        run("ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-t", str(d), "-i", str(png), "-i", str(audio),
            "-filter_complex",
            f"[0:v]fade=t=in:st=0:d=0.4:color={BG},fade=t=out:st={d - 0.4}:d=0.4:color={BG},format=yuv420p[v];"
            f"[1:a]adelay={int(LEAD * 1000)}:all=1,aresample=44100,aformat=channel_layouts=stereo,apad,atrim=0:{d}[a]",
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "30",
            "-c:a", "aac", "-b:a", "128k", "-t", str(d), str(clip))
        clips.append(clip)
        srt += subtitle_chunks(text, t0 + LEAD, a)
        t0 += d

    (HERE / "dhc-1min.srt").write_text(
        "\n".join(f"{n}\n{ts(a)} --> {ts(b)}\n{s}\n" for n, (a, b, s) in enumerate(srt, 1)), encoding="utf-8")
    (tmp / "list.txt").write_text("".join(f"file '{c}'\n" for c in clips))
    joined = tmp / "joined.mp4"
    run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"), "-c", "copy", str(joined))

    style = (f"FontName={FONT},FontSize=15,PrimaryColour=&H00FFFFFF,BackColour=&H66000000,"
             "BorderStyle=4,Outline=6,Shadow=0,MarginV=22")
    run("ffmpeg", "-y", "-i", str(joined), "-vf",
        f"subtitles={HERE / 'dhc-1min.srt'}:force_style='{style}'",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "copy",
        "-movflags", "+faststart", str(HERE / "dhc-1min.mp4"))

    # 每幕中段各抽一格，砌成總覽圖檢查字幕位置
    ends = [0.0]
    for c in clips:
        ends.append(ends[-1] + duration(c))
    for i in range(8):
        run("ffmpeg", "-y", "-ss", str((ends[i] + ends[i + 1]) / 2), "-i", str(HERE / "dhc-1min.mp4"),
            "-frames:v", "1", str(tmp / f"f{i + 1}.png"))
    run("ffmpeg", "-y", "-i", str(tmp / "f%d.png"), "-vf", "scale=640:-1,tile=4x2:padding=8:color=gray",
        "-frames:v", "1", str(HERE / "contact.png"))

    shutil.rmtree(tmp)
    print(f"語音：{'、'.join(sorted(used))}；總長 {duration(HERE / 'dhc-1min.mp4'):.1f} 秒")


if __name__ == "__main__":
    sys.exit(main())
