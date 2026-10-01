#!/usr/bin/env python3
"""DHC 講解短片生成器：scenes.html + scenes.json → 有粵語旁白、雙語燒入字幕嘅 MP4。

用法：python3 build.py <project_dir>
  project_dir 要有：
    scenes.html  —— 每幕一個 <section class="scene" id="...">，用 #id 切換（見 assets/example）
    scenes.json  —— {"name": "dhc-2min", "lang": "yue" 或 "cmn"（預設 yue）, "voice": {"speed": 0.9, "fx": "radio80s"}（可選）, "html": "../cmn/scenes.html"（可選）, "scenes": [{"id", "min", "zh", "en"}, ...]}
                    min = 最短秒數；zh = 口語粵語旁白；en = 英文字幕（整幕一句）
  可選：voice/<id>.(wav|mp3|m4a) —— 自己錄嘅旁白，優先於 TTS

輸出（寫入 project_dir）：<name>.mp4、<name>.srt、<name>.en.srt、contact.png（每幕一格總覽）

語音來源（逐幕）：錄音 → sherpa-onnx（粵語 vits-cantonese 約 110MB／普通話 vits-melo-tts-zh_en 約 180MB，
離線，首次由 GitHub 下載到 ~/.cache/dhc-video）→ Edge TTS zh-HK（要網絡准許 speech.platform.bing.com）→ espeak-ng yue。
依賴：ffmpeg（有 libass）、pip install sherpa-onnx opencc-python-reimplemented、
apt fonts-wqy-zenhei fonts-arphic-uming（剪報明體）。
"""
import array, asyncio, json, math, os, re, shutil, subprocess, sys, tempfile, wave
from pathlib import Path

CHROME_CANDIDATES = [
    "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell",
    shutil.which("chromium") or "", shutil.which("google-chrome") or "",
]
LEAD = 0.3            # 每幕開始後幾耐先出聲
BG = "0x000000"       # 舊片式淡入淡出黑畫面
FONT = "WenQuanYi Zen Hei"
CACHE = Path.home() / ".cache" / "dhc-video"
REL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
# scenes.json 嘅 "lang"：yue = 粵語（預設），cmn = 普通話。模型字典都係簡體字，所以合成前先轉簡體。
# 聲音效果預設（scenes.json 嘅 voice.fx）。radio80s = 八十年代內地廣播：收窄頻帶、鼻音共鳴、壓縮、
# 播音室回響、帶機轉速微晃、輕微失真，再混入底噪。淨係後製，唔改旁白內容。
FX = {
    None: dict(chain="highpass=f=180,lowpass=f=6500", hiss=0),
    "radio80s": dict(
        chain=("highpass=f=320,lowpass=f=3600,equalizer=f=1200:t=q:w=1.2:g=4,"
               "acompressor=threshold=0.05:ratio=6:attack=5:release=120:makeup=5,"
               "aecho=0.8:0.6:35:0.22,vibrato=f=0.7:d=0.035,asoftclip=type=tanh:threshold=0.6"),
        hiss=0.012),
}
MODELS = {
    "yue": dict(name="vits-cantonese-hf-xiaomaiiwn", onnx="vits-cantonese-hf-xiaomaiiwn.onnx",
                rules=["rule.fst"], dict_dir=False, edge="zh-HK-HiuMaanNeural", espeak="yue"),
    "cmn": dict(name="vits-melo-tts-zh_en", onnx="model.onnx",
                rules=["date.fst", "number.fst", "phone.fst", "new_heteronym.fst"], dict_dir=True,
                edge="zh-CN-XiaoxiaoNeural", espeak="cmn"),
}
_sherpa = {}


def run(*cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout)


def sherpa_tts(lang, text, out, speed=1.0):
    """模型字典係簡體字，繁體字會被跳過唔讀，所以先轉簡體（讀音不變）。"""
    try:
        import sherpa_onnx
        from opencc import OpenCC
        if lang not in _sherpa:
            m = MODELS[lang]
            d = CACHE / m["name"]
            if not d.exists():
                CACHE.mkdir(parents=True, exist_ok=True)
                subprocess.run(f"curl -sL '{REL}{m['name']}.tar.bz2' | tar xj -C '{CACHE}'", shell=True, check=True)
            vits = sherpa_onnx.OfflineTtsVitsModelConfig(
                model=str(d / m["onnx"]), lexicon=str(d / "lexicon.txt"), tokens=str(d / "tokens.txt"),
                dict_dir=str(d / "dict") if m["dict_dir"] else "")
            _sherpa[lang] = (sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(vits=vits, num_threads=4),
                rule_fsts=",".join(str(d / r) for r in m["rules"]))), OpenCC("t2s"))
        engine, cc = _sherpa[lang]
        audio = engine.generate(cc.convert(text), sid=0, speed=speed)
        pcm = array.array("h", (int(max(-1.0, min(1.0, s)) * 32767) for s in audio.samples))
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(audio.sample_rate)
            w.writeframes(pcm.tobytes())
        return True
    except Exception:
        return False


def edge_tts(lang, text, out):
    try:
        import certifi
        if Path("/root/.ccr/ca-bundle.crt").exists():
            certifi.where = lambda: "/root/.ccr/ca-bundle.crt"
        import edge_tts as et
        comm = et.Communicate(text, MODELS[lang]["edge"], proxy=os.environ.get("HTTPS_PROXY"))
        asyncio.run(comm.save(str(out)))
        return out.stat().st_size > 0
    except Exception:
        return False


def tts(proj, lang, sid, text, tmp, speed=1.0):
    for ext in ("wav", "mp3", "m4a"):
        own = proj / "voice" / f"{sid}.{ext}"
        if own.exists():
            return own, "錄音"
    wav = tmp / f"v_{sid}.wav"
    if sherpa_tts(lang, text, wav, speed):
        return wav, f"sherpa-onnx {lang}"
    mp3 = tmp / f"v_{sid}.mp3"
    if edge_tts(lang, text, mp3):
        return mp3, "Edge TTS"
    run("espeak-ng", "-v", MODELS[lang]["espeak"], "-s", "215", "-w", str(wav), text)
    return wav, "espeak-ng"


def ts(t):
    ms = round(t * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def subtitle_chunks(text, start, length):
    """按標點切句，時間按字數比例分配；句末標點唔顯示。"""
    parts = [p.strip() for p in re.split(r"[，。；：、]", text) if p.strip()]
    total = sum(len(p) for p in parts)
    t, out = start, []
    for p in parts:
        d = length * len(p) / total
        out.append((t, t + d, p))
        t += d
    return out


def write_srt(path, rows):
    path.write_text("\n".join(f"{n}\n{ts(a)} --> {ts(b)}\n{s}\n" for n, (a, b, s) in enumerate(rows, 1)),
                    encoding="utf-8")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    proj = Path(sys.argv[1]).resolve()
    cfg = json.loads((proj / "scenes.json").read_text(encoding="utf-8"))
    name, scenes, lang = cfg["name"], cfg["scenes"], cfg.get("lang", "yue")
    voice = cfg.get("voice", {})                 # {"speed": 0.9, "fx": "radio80s"}
    speed, fx = voice.get("speed", 1.0), FX.get(voice.get("fx"), FX[None])
    html = (proj / cfg.get("html", "scenes.html")).resolve()   # 可指去另一個 project 嘅畫面，免重複
    chrome = next(c for c in CHROME_CANDIDATES if c and Path(c).exists())
    tmp = Path(tempfile.mkdtemp())
    srt, srt_en, clips, t0, used = [], [], [], 0.0, set()

    for sc in scenes:
        sid = sc["id"]
        audio, src = tts(proj, lang, sid, sc["zh"], tmp, speed)
        used.add(src)
        a = duration(audio)
        d = round(max(sc["min"], a + LEAD + 0.5), 2)
        png, clip = tmp / f"{sid}.png", tmp / f"c_{sid}.mp4"
        run(chrome, "--headless", "--no-sandbox", "--hide-scrollbars", "--window-size=1920,1080",
            f"--screenshot={png}", f"file://{html}#{sid}")
        run("ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-t", str(d), "-i", str(png), "-i", str(audio),
            "-filter_complex",
            f"[0:v]fade=t=in:st=0:d=0.4:color={BG},fade=t=out:st={d - 0.4}:d=0.4:color={BG},format=yuv420p[v];"
            f"[1:a]adelay={int(LEAD * 1000)}:all=1,aresample=44100,aformat=channel_layouts=stereo,"
            f"{fx['chain']},apad,atrim=0:{d}[s];"
            + (f"anoisesrc=color=pink:amplitude={fx['hiss']}:d={d}:r=44100,aformat=channel_layouts=stereo,"
               f"highpass=f=200,lowpass=f=5000,afade=t=in:d=0.3,afade=t=out:st={d - 0.3}:d=0.3[n];"
               "[s][n]amix=inputs=2:duration=first,volume=2[a]" if fx["hiss"] else "[s]anull[a]"),
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "30",
            "-c:a", "aac", "-b:a", "128k", "-t", str(d), str(clip))
        clips.append(clip)
        srt += subtitle_chunks(sc["zh"], t0 + LEAD, a)
        srt_en.append((t0 + LEAD, t0 + d - 0.3, sc["en"]))
        t0 += d

    zh_srt, en_srt = proj / f"{name}.srt", proj / f"{name}.en.srt"
    write_srt(zh_srt, srt)
    write_srt(en_srt, srt_en)
    (tmp / "list.txt").write_text("".join(f"file '{c}'\n" for c in clips))
    joined = tmp / "joined.mp4"
    run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"), "-c", "copy", str(joined))

    # 舊教育片字幕：中文拉開字距，下面細字英文；畫面先加 VHS 色偏、柔焦、雜訊，再縮到 720p 控制檔案大小
    zh = f"FontName={FONT},FontSize=13,Spacing=3,Outline=1,Shadow=0,BorderStyle=1,MarginV=26"
    en = "FontName=DejaVu Sans,FontSize=8,Outline=1,Shadow=0,BorderStyle=1,MarginV=10"
    vhs = "rgbashift=rh=-3:bh=3,gblur=sigma=0.9,noise=alls=6:allf=t,eq=saturation=0.9:contrast=1.05,scale=1280:720"
    out = proj / f"{name}.mp4"
    run("ffmpeg", "-y", "-i", str(joined), "-vf",
        f"{vhs},subtitles={zh_srt}:force_style='{zh}',subtitles={en_srt}:force_style='{en}'",
        "-c:v", "libx264", "-preset", "slow", "-crf", "27", "-c:a", "copy", "-movflags", "+faststart", str(out))

    # 每幕中段抽一格砌總覽圖：檢查一張圖就睇晒全部幕
    ends = [0.0]
    for c in clips:
        ends.append(ends[-1] + duration(c))
    for i in range(len(clips)):
        run("ffmpeg", "-y", "-ss", str((ends[i] + ends[i + 1]) / 2), "-i", str(out),
            "-frames:v", "1", str(tmp / f"f{i + 1}.png"))
    cols = math.ceil(math.sqrt(len(clips)))
    rows = math.ceil(len(clips) / cols)
    run("ffmpeg", "-y", "-i", str(tmp / "f%d.png"), "-vf", f"scale=640:-1,tile={cols}x{rows}:padding=8:color=gray",
        "-frames:v", "1", str(proj / "contact.png"))

    shutil.rmtree(tmp)
    print(f"語音：{'、'.join(sorted(used))}；總長 {duration(out):.1f} 秒；"
          f"大小 {out.stat().st_size / 1048576:.1f}MB；輸出 {out}")


if __name__ == "__main__":
    main()
