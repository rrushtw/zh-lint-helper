# zh-lint

中文行文 linter。抓 `~/.claude/CLAUDE.md` §0 裡**機械可判定**的規則,把「每次靠注意力手動掃」的部分 offload 成工具。與 markdownlint 並排跑,不重造它的結構規則。

## 分工哲學

規則分三層,只自動化前兩層:

| 層 | 例 | 這裡做嗎 |
|---|---|---|
| **A 機械可判定** | 大陸用語、Latin 縮寫、數學符號、emoji shortcode | ✅ error(退出碼 1) |
| **B 半判定** | 標題括號、日期斜線、翻譯腔、了解 / 瞭解 | ✅ warn(標疑點,不擋 CI) |
| **C 純語義** | 括號是補充還是合法 gloss、句子自不自然 | ❌ 留給人 review |

只查含中文字的行(擋純英文 / URL / 程式碼誤判);fenced code block 與 inline `` `code` `` 一律遮掉。

## 用法

```sh
./run.sh docs/**/*.md      # 掃檔
./run.sh --test            # 自我檢查
```

宿主不直接跑 python,一律進容器(`python:3.12-slim`,零第三方依賴)。

## 擴充

被糾正到新怪詞 → 在 `rules.json` 的 `terms` 或 `patterns` append 一筆,**不動 `lint.py`**:

```json
{"bad": "落地", "good": "完成 / 上線", "class": "A", "cat": "calque", "note": "2026-XX-XX 被糾正"}
```

- `class`：`A` 高信任(error)、`B` 有誤判風險或語境相關(warn)
- 有 substring 誤判風險(如「新生」撞「新生兒」)一律先放 `B`
