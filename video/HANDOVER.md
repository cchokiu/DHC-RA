# Handover：用 ElevenLabs 配粵語旁白，Krea 補畫面（喺屋企部電腦做）

寫於手機雲端 session。雲端環境連唔到 `krea.ai`、`elevenlabs.io`（網絡政策擋咗），所以呢份係俾屋企部電腦嘅 Claude Code 執行嘅工作單。**雲端 session 冇試過下面任何 API 呼叫**，所有 API 細節都要喺屋企對返最新官方文件。

## 點開始

```
git fetch origin claude/dhc-video-storyboard
git checkout claude/dhc-video-storyboard
claude        # 然後講：Read video/HANDOVER.md and execute it. Stop at each decision gate.
```

API key 只放環境變數（`ELEVENLABS_API_KEY`、`KREA_API_KEY`），**唔好寫入任何檔案或 commit**。

## 更新：之後新增嘅版本（先睇呢段）

寫 handover 之後，雲端 session 又加咗：

- `video/cmn/`：普通話版（離線 sherpa 語音），`scenes.json` 有 `"lang": "cmn"`。
- `video/cmn80s/`：普通話＋八十年代內地廣播風，`voice: {"speed": 0.95, "fx": "radio80s"}`，畫面共用 `video/cmn/scenes.html`（`"html"` 欄）。
- `build.py` 嘅 `tts()` 而家係 `tts(proj, lang, sid, text, tmp, speed)`；語音後製 `FX["radio80s"]` 係 ffmpeg，**同語音來源無關**，所以 ElevenLabs 出嘅音檔都可以套用。

**建議次序**：普通話版比粵語版更適合先試 ElevenLabs，因為普通話係佢支援最穩陣嘅中文。
1. 先做 `video/cmn/`（普通話）：測試聲、緩存、出片。
2. 再試 `video/` 粵語版，過咗上面「關口 A」先做。
3. `cmn80s`：ElevenLabs 聲＋`radio80s` 後製；ElevenLabs 自己嘅聲音風格唔一定似舊廣播，後製參數可再調。
4. 每個版本分開 `voice_cache/`（或者 cache key 已含 text/model/voice，咁就唔會撞）。

## 現況（已完成）

- 一條 127 秒、14 幕嘅 DHC 講解片：`video/dhc-2min.mp4`，舊香港教育片風格，粵語旁白用離線 sherpa-onnx（機械味重，所以要升級），中英字幕燒入。
- 內容同旁白全部喺 `video/scenes.json`（每幕 `id`、`min`、`zh`、`en`），畫面喺 `video/scenes.html`。
- 生成腳本：`.claude/skills/dhc-video/scripts/build.py <project_dir>`，用法同「已知陷阱」見 `.claude/skills/dhc-video/SKILL.md`，**先讀呢份**。內容規則（來源編號、推論標示、剪報唔偽造、未核實內容唔寫）亦喺度，唔好違反。
- 幕 ID 次序：`s1 s2 news s3 s4 bp1 bp2 s5 bp3 s6 bp4 bp5 s7 s8`。
- 用家想要：低 token、低成本；用 ElevenLabs 配音，Krea 用嚟整畫面。

## 目標

1. 每幕旁白改用 ElevenLabs，聽落係自然嘅**香港廣東話**。
2. 可選：用 Krea 為少數幾幕加動態畫面，唔係全片。
3. 保持一個指令出片，音檔要緩存，唔好重複燒額度。

## Task 0：屋企電腦環境（用家係 Mac，先確認）

`build.py` 係喺 Linux 寫嘅，喺 Mac 要改幾樣：

- `CHROME_CANDIDATES` 加 `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`；`--headless` 用 `--headless=new`，截圖指令要試一次確認。
- 字體：`FONT = "WenQuanYi Zen Hei"` 同 `scenes.html` 嘅 `font-family` 要加 Mac 有嘅繁體字（例如 `PingFang HK`、`Noto Sans CJK TC`）。剪報明體 `AR PL UMing TW` 可換 `Songti TC` 或 `PMingLiU`。
- ffmpeg 要有 libass：跑 `ffmpeg -filters | grep subtitles` 確認；冇就 `brew install ffmpeg`（要包含 libass 嘅版本）。
- `sherpa-onnx`、`opencc`：只係後備語音，唔裝都得，但 `build.py` 入面嘅 import 已經包咗 try/except。
- 用 `contact.png` 檢查字幕有冇撞畫面、字有冇變方格，Mac 同 Linux 渲染可能唔同。

做完 Task 0，先用現有語音出一次片，確認畫面同字幕冇壞，**先至接 API**。

## Task 1：ElevenLabs 粵語旁白

**決策關口 A（必須先做，幾毛錢內完成）：測試粵語質素。**
雲端搜尋結果顯示 ElevenLabs 嘅 Cantonese 支援唔明確：`yue` 語言代碼見於語音轉文字，而文字轉語音官方頁面主打 Mandarin，要親身測試。

1. 喺 Voice Library 搜尋標明 Hong Kong／Cantonese 嘅聲，揀 2–3 把候選。
2. 用 `video/scenes.json` 嘅第一句同最長嗰句（`bp3` 或 `s6`）各生成一次，模型試 `eleven_v3` 同 `eleven_multilingual_v2`，唔好一開始就生成全片。
3. 用家自己聽：讀音啱唔啱粵語（唔係普通話口音）、「嘅、咗、喺、佢、哋」呢類口語字有冇讀啱、數字（「二零一七年」）。
4. 如果冇一把聲達標，**停低問用家**，唔好硬做。後備方案：ElevenLabs 配普通話稿（要將 `zh` 寫成普通話），或者用家自己錄音放入 `voice/`，或者保留現有 sherpa 粵語。

**實作（過咗關口 A 先做）：**

- 喺 `build.py` 嘅 `tts()` 加一個來源，次序：自己錄音 → ElevenLabs（有 `ELEVENLABS_API_KEY` 先用）→ sherpa → Edge TTS → espeak。
- API 大致係 `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`，header `xi-api-key`，body 有 `text`、`model_id`、`voice_settings`，返回 mp3。以最新官方文件為準，包括 `language_code` 同輸出格式參數。
- **緩存**：音檔存喺 `video/voice_cache/`，檔名用 `sha1(voice_id + model_id + text)`。文字冇改就唔重新生成，重跑 `build.py` 唔會再扣額度。`voice_cache/` 要放入 `.gitignore`，唔好 commit。
- 失敗要有清晰提示（401 = key 錯；quota 用完），然後退返用 sherpa，唔好令整個出片失敗。
- 每幕長度仍然係 `max(min, 旁白長度 + 0.8)`，換聲之後全片長度會變，出片後報告總長。
- 全片旁白大約幾多字，換算大約幾多 credits，**先報用家同意再全片生成**。

## Task 2：Krea（可選，成本較高，要用家同意）

Krea 係畫面工具，**搵唔到佢有廣東話配音功能**，所以只負責畫面。

- 搜尋結果顯示 Krea 有 Video API：base URL `https://api.krea.ai`，Bearer token 認證，有 image-to-video（例如 `/generate/video/kling/kling-2.5`，參數有 `start_image`、`prompt`、`duration`、`aspect_ratio`）。**全部要對返 https://www.krea.ai/docs/developers/introduction.md 確認**，同埋睇清楚每次生成嘅收費。
- 建議做法：用 `contact.png` 或單幕截圖作 `start_image`，做幾秒微動畫（輕微推近、點線流動），再同旁白合成。只揀 1–2 幕（例如 `s1` 標題、`bp3` 系統圖），唔好全片。
- 風格要保持舊香港教育片：深藍底、米白字，唔好令 AI 影片生成新嘅字或者改咗圖入面嘅字，**圖入面嘅數字同中文一定要同 `scenes.html` 一致**，如果 Krea 輸出令字變形，就唔用。
- **決策關口 B**：先生成一條 3–5 秒測試片，用家睇過同意先擴大。預算、幕數同用家確認。
- 輸出剪輯入 ffmpeg 流程：每幕如果有 `video/krea/<id>.mp4`，就用佢代替靜態截圖，長度要夠，唔夠就 `-stream_loop` 或者放慢，**唔好改變旁白同字幕嘅時間**。
- 影片檔放 `video/krea/`，唔好 commit 大檔（30MB 上限同 repo 歷史），只 commit 腳本。

## 驗收

- [ ] 旁白係粵語（用家聽過），冇漏字、冇讀錯數字同年份
- [ ] 重跑 `build.py` 用緩存，唔會再扣 ElevenLabs credits
- [ ] 全片 120–130 秒，字幕冇撞畫面，`contact.png` 檢查過
- [ ] `.mp4` 細於 30MB（要傳俾用家同上載）
- [ ] 冇 API key 進入 git（`git log -p | grep -i key` 檢查）
- [ ] 更新 `.claude/skills/dhc-video/SKILL.md`：加入 ElevenLabs 來源、緩存、Mac 注意事項同今次踩到嘅陷阱

## 慳 token 守則（沿用）

- 唔好讀 `index.html`（82 萬字節）；內容問題先問用家。
- 每幕唔好逐張截圖檢查，只睇 `contact.png`，有問題先 crop 該幕。
- API 先用最短文字測試，過咗關口先全片生成。

## 完成後

commit 到 `claude/dhc-video-storyboard`（唔好直接推 `main`），再報告：用咗邊把聲、邊個模型、總長、檔案大小、用咗幾多 credits。
