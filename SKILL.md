---
name: zh-lint
description: 中文行文 linter — 掃 markdown / 程式碼註解，抓 ~/.claude/CLAUDE.md §0 中文行文規範裡機械可判定的規則（大陸用語、calque 英文直譯、Latin 縮寫、數學符號、emoji shortcode、文言、標題括號補充、日期斜線、翻譯腔、字形誤用）。任何「會被別人看到」的中文產出送出前都該過一遍：MR / issue / PR 留言與內文、code review findings、wiki 頁面、對外信件、commit message、docs/**/*.md。與 markdownlint 並排跑（結構規則歸 markdownlint、行文用詞歸這支）。工具在 /home/liu/git/zh-lint，宿主不跑 python，一律進容器。
---

# zh-lint

中文行文 linter。把 CLAUDE.md §0 裡「每次靠注意力手動掃」的用詞規則 offload 成工具——手掃會漏（例：`錨點` 這種 calque 眼睛容易放過，工具不會）。

## 何時用

任何要送出、會被別人看到的中文，送出前掃一遍：

- code review findings、MR / issue / PR 留言與內文
- wiki 頁面、對外信件、commit message
- `docs/**/*.md`

## 用法

**宿主不直接跑 python**（依 CLAUDE.md）。用 repo 內的 `run.sh`（已封好 `python:3.12-slim` 容器）：

```sh
cd /home/liu/git/zh-lint
./run.sh docs/**/*.md      # 掃檔（檔案需在 $PWD 下才會被 mount 進容器）
./run.sh --test            # 自我檢查
```

掃 repo 外的檔（如 scratchpad 草稿）→ 另掛一個 volume：

```sh
docker run --rm -v /home/liu/git/zh-lint:/w -v <草稿目錄>:/data -w /w \
  python:3.12-slim python lint.py /data/<檔名>.md
```

## 判讀輸出

- `[A/error]`（退出碼 1）：高信任黑名單 / regex，近乎零誤判 → **一律修**。
- `[B/warn ]`（不影響退出碼）：語境相關的疑點（如日期斜線可能是分數、`拍板定案` 是慣用語）→ **逐筆判斷**，不無腦改。
- `✓ 無違規` 才算過。

只查含中文字的行，fenced code block 與 inline `` `code` `` 會被遮掉，不會誤判程式碼。純語義層（括號是補充還是合法 gloss、句子自不自然）機器不做，仍要人 review。

## 擴充

被糾正到新怪詞 → 只在 `rules.json` 的 `terms` 或 `patterns` append 一筆，**不動 `lint.py`**：

```json
{"bad": "落地", "good": "完成 / 上線", "class": "A", "cat": "calque", "note": "2026-XX-XX 被糾正"}
```

- `class`：`A` 高信任（error）、`B` 有誤判風險或語境相關（warn）。
- 有 substring 誤判風險（如 `新生` 撞 `新生兒`）一律先放 `B`。
