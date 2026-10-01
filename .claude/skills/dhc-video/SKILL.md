---
name: dhc-video
description: Make short explainer / tutorial videos (MP4) about Hong Kong District Health Centres (地區康健中心, DHC) or the DHC fieldbook site — Cantonese narration, burned-in bilingual subtitles, retro Hong Kong educational-film look, restaged "news clipping" scenes, all generated offline at low token cost. Use this whenever the user asks for a DHC video, 短片, 教學片, 講解片, 影片, 旁白, 字幕, 剪報 or wants to extend, restyle, re-voice or shorten an existing DHC video, even if they do not say "skill" or name the tools.
---

# DHC 講解短片

由手冊事實 → 分鏡 → `scenes.html` + `scenes.json` → 一個腳本出片。成個流程設計成少工具呼叫、少讀檔，因為用家好在意 token 成本。

## 檔案

- `scripts/build.py <project_dir>`：截圖、粵語 TTS、字幕、VHS 效果、合成、總覽圖，一次過做晒。開頭 docstring 有完整說明。
- `assets/example/`：已完成嘅兩分鐘版（14 幕）。新片由佢複製開始改，唔好由零寫。
  - `scenes.html`：每幕一個 `<section class="scene" id="...">`，CSS 已有舊教育片色調同各種版式（時間線、數字卡、樞紐圖、四欄分工、剪報、公式、架構圖、推論卡）。
  - `scenes.json`：`{"name", "scenes": [{"id", "min", "zh", "en"}]}`，次序就係播放次序。

## 流程

1. **攞內容，唔好讀成份 `index.html`**（約 82 萬字節）。用 `grep -n` 搵需要嘅章節，或者用用家貼嘅文字。
2. **寫旁白同分鏡**：直接改 `scenes.json` 同 `scenes.html`。要跟以下規則：
   - 每個數字、年份都要對得返手冊入面「引用事實」，畫面右下角用 `.src` 標來源編號，例如 `[5][12]`。
   - 手冊用「看來」「或許」寫嘅句子係推論，影片要放喺 `.infcard` 加「推」字，旁白保留弱化語氣。
   - 唔寫手冊標明未核實嘅嘢，例如督導委員會中期文件、開支分項、社署分工文件、現行合約條款同法案結果。
   - 結尾要講明「以上全屬政府自述，並非獨立評估」。
   - 合約金額只可以寫成「3 年總額」，唔好令人誤以為係每年開支。
   - **剪報唔可以偽造真報紙**：只可以用公報事實重新排版，註明「示意重製，內容據官方公報整理，非原文影像」，唔好用報紙名稱或者報頭。標題係自己撰寫，唔好扮係原文。如果用家有權使用真剪報掃描，可以放圖代替。
3. **計時長**：sherpa 語音大約每秒讀 6 個字。所以每幕旁白字數大約係 6 × 目標秒數，`min` 就設為目標秒數。實際長度係 `max(min, 旁白長度 + 0.8)`，所以想縮短全片，要刪旁白，淨係改 `min` 冇用。
4. **出片**：`python3 scripts/build.py <project_dir>`。
5. **檢查**：只睇 `contact.png` 一張圖。有問題就用 ffmpeg crop 出嗰一兩幕再睇，唔好逐幕截圖。
6. **交付**：commit 去非預設 branch 再 push。`SendUserFile` 上限係 30MB，腳本預設輸出 720p、crf 27，一般兩分鐘大約 3.5MB。

## 已知陷阱（今次個案踩過）

- **Edge TTS 同 HuggingFace 可能被雲端環境網絡擋**；GitHub release 一般下載到。所以 sherpa-onnx 係預設語音。如果要用 Edge TTS，用家要喺環境設定開放 `speech.platform.bing.com`。
- **sherpa 粵語模型字典係簡體字**：繁體字會被靜靜咁跳過唔讀。腳本已經用 OpenCC 轉簡體；如果旁白有生僻字，留意 stderr 嘅 `OOV`。
- **冇 Python Playwright**：腳本直接用 Chromium headless 嘅 `--screenshot`。
- **字型**：要裝 `WenQuanYi Zen Hei`（字幕同介面）同 `AR PL UMing TW`（剪報明體）；冇嘅話用 apt 裝 `fonts-wqy-zenhei fonts-arphic-uming`。
- **燒入字幕會佔畫面底部大約 200px**：畫面內容唔好放喺底部；`.cap` 要設 `bottom:260px` 或以上。
- **方框入面嘅小字會爆框**：長嘅副標要加闊方框（例如 `width:400px`），同時要調返 SVG 連線嘅端點。
- **雜訊會令影片難壓縮**：1080p 加 `noise=alls=9` 出咗 36MB，所以而家縮到 720p、`alls=6`、crf 27。
- **唔好 commit 大檔**：如果已經推咗而 branch 係自己開又未有 PR，可以 amend 再 `--force-with-lease`；別人嘅 branch 就唔好咁做。
- **模型**：腳本會將約 110MB 嘅模型存喺 `~/.cache/dhc-video`，唔會放入 repo。

## 想改風格

- **色調**：改 `scenes.html` 開頭 `:root` 嘅變數，深藍底 `#16256a`、米白字 `#f4edd4`、黃色重點 `#ffd866`、青色點 `#8fd3c6`。
- **VHS 效果**：改 `build.py` 入面嘅 `vhs` 字串，包括色偏、柔焦、雜訊同解像度。
- **雙語字幕**：中文樣式改 `zh`，英文樣式改 `en`。想淨係要中文字幕，就刪走最後合成嗰度第二個 `subtitles` filter。
- **換聲**：將錄音放喺 `<project>/voice/<id>.m4a`，會優先使用。
- **普通話版**：`scenes.json` 加 `"lang": "cmn"`，`zh` 改寫成書面普通話稿（用繁體字，聽落係普通話）。`scenes.html` 要複製一份，將畫面上嘅粵語字（點解、點樣、唔係、嘅）改成普通話寫法。例子喺 `video/cmn/`。
- **懷舊廣播聲**：`scenes.json` 加 `"voice": {"speed": 0.95, "fx": "radio80s"}`。`radio80s` 係 ffmpeg 後製（收窄頻帶、鼻音共鳴、壓縮、回響、轉速微晃、失真、底噪），唔改語音來源，所以粵語、普通話都用得。想用同一套畫面，就加 `"html": "../cmn/scenes.html"`。稿件可以加「各位聽眾，現在播送……」同「謝謝收聽」呢類播音腔開結語。例子喺 `video/cmn80s/`。後製係模擬音色，唔係真人播音員；想更似真，仍然要靠真人錄音或高質素 TTS 加呢個 effect。普通話模型 `vits-melo-tts-zh_en` 約 180MB，同樣首次自動下載；Mandarin 稿比粵語稿長，全片大約長 5–10%。
