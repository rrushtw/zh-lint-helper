#!/usr/bin/env python3
"""中文行文 linter —— 掃 markdown / 程式碼註解,抓 CLAUDE.md §0 裡機械可判定的規則。

分工:
- A 類(error,退出碼 1):純黑名單 / regex,高信任、近乎零誤判。
- B 類(warn,不影響退出碼):需語義判斷的疑點,只標出讓人看。
- 純語義規則(翻譯腔是否自然、括號是補充還是合法 gloss)機器不做,留給人 review。

只查「含中文字的行」——一行擋掉純英文 / URL / 程式碼的誤判;fenced code block 與 inline
`code` 一律遮掉不查。程式檔案(`.js` / `.py` 等)先切出註解再套規則,見 COMMENT_SYNTAX。
"""
import json
import re
import sys
from pathlib import Path

CJK = re.compile(r"[一-鿿]")
FENCE = re.compile(r"^\s*```")
INLINE_CODE = re.compile(r"`[^`]*`")
# markdown 連結目標:URL 與 anchor 不是行文,中文 anchor 不該計入句長 / 並列段
LINK_DEST = re.compile(r"\]\([^)\s]*\)")
# 行首的 blockquote 與 list 標記。遮成等長空白後 LIST 三規則的行首排除不再命中,
# bullet 與 callout 內文一樣受 run-on / long-sentence 檢查——§0 要的是「拆 bullet / sub-list」,
# 長句落在 bullet 或 callout 框裡同樣該拆。heading 與表格列不遮,維持原本不查。
LEAD_MARKER = re.compile(r"^\s*(?:>\s*)*(?:(?:[-*+]|\d+[.)])\s+)?")
# checkbox 例外(§0:checkbox 不拆):保留標記讓規則的行首排除繼續生效。
CHECKBOX = re.compile(r"^\s*(?:>\s*)*(?:[-*+]|\d+[.)])\s+\[[ xX]\]")

# 程式檔案的註解語法。key 是副檔名,不在表內的一律照 markdown 走(行為與先前相同)。
# 刻意不收 `.yml` / `.conf`:YAML 的 plain scalar 沒有引號,收進來會把中文值當程式碼漏掉。
# - line:行註解標記
# - blocks:區塊註解的(起,迄)配對,依序比對
# - quotes:字串引號,字串字面值整段不當行文掃
# - cont:區塊註解有 `*` 續行標記(JSDoc),要連標記一起遮掉
_C = {"line": "#", "blocks": [], "quotes": ['"', "'"], "cont": False}
_JS = {"line": "//", "blocks": [("/*", "*/")], "quotes": ['"', "'", "`"], "cont": True}
_PY = {"line": "#", "blocks": [('"""', '"""'), ("'''", "'''")],
       "quotes": ['"', "'"], "cont": False}
COMMENT_SYNTAX = {
    ".js": _JS, ".mjs": _JS, ".cjs": _JS, ".jsx": _JS, ".ts": _JS, ".tsx": _JS,
    ".py": _PY,
    ".sh": _C, ".env": _C,
}
# JSDoc 續行的 ` * `:遮掉才讓註解內的 `- ` 落在行首,LIST 三規則照 markdown 處理。
JSDOC_CONT = re.compile(r"^\s*\*+[ \t]?")
# JSDoc tag 的型別與參數名段不是行文(`@param {string} stationId 站點` 只有「站點」是)。
# 第三段只在不含中文時才遮,`@returns {Object} 回傳值` 的中文說明才不會被吃掉。
JSDOC_TAG = re.compile(r"^[ \t]*@\w+[ \t]*(?:\{[^}]*\}[ \t]*)?(?:(?![^\s]*[一-鿿])\S+[ \t]*)?")
# 只在 JSDoc 描述首行報的規則:程式註解內文的括號多半是合法 gloss 或 cross-ref,
# 全報等於每行都要人逐筆判。markdown 不套這層,行為不變。
HEADING_ONLY = frozenset({"paren-supplement"})


def load_rules(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    terms = [(t["bad"], t) for t in data.get("terms", [])]
    patterns = [
        (re.compile(p["re"], re.I if p.get("ignorecase") else 0), p)
        for p in data.get("patterns", [])
    ]
    return terms, patterns


def find_outside(line, bad, allow):
    """第一個不被 allow 詞包住的 bad 位置,沒有則 -1。

    allow 是「這個壞詞合法出現在裡面」的較長詞,例如「施工」的「施工規範」——
    甲方文件正式名稱，引用時照原名不改。
    """
    spans = []
    for a in allow:
        start = 0
        while (i := line.find(a, start)) >= 0:
            spans.append((i, i + len(a)))
            start = i + 1
    start = 0
    while (i := line.find(bad, start)) >= 0:
        if not any(s <= i and i + len(bad) <= e for s, e in spans):
            return i
        start = i + 1
    return -1


def mask_source(lines, syn):
    """程式檔案 → (只留註解內文的行, 各行要略過的規則)。

    - 程式碼本體與字串字面值換等長空白:行號與欄位不變,含中文的字串字面值不當行文掃
      - 字串是給人看的訊息,但句長與標點的判準與註解內文不同,要掃得另開規則類別
    - 註解標記與 JSDoc 續行的 `*` 一併遮掉:註解內的 `- ` 因此落在行首
    - `paren-supplement` 只留在 JSDoc 描述首行,其餘行略過
    - 已知天花板:跨行的 JS template literal 當不到字串,那行的中文會被當註解掃
    """
    out, skips = [], {}
    block = None          # 區塊註解未結束時存它的結束標記,跨行保留
    desc_pending = False  # 剛開 `/**`,還沒遇到第一行內文
    for lineno, raw in enumerate(lines, 1):
        keep = [False] * len(raw)
        quote = None
        i = 0
        while i < len(raw):
            if block:
                if raw.startswith(block, i):
                    i += len(block)
                    block = None
                else:
                    keep[i] = True
                    i += 1
            elif quote:
                if raw[i] == "\\":
                    i += 2
                elif raw.startswith(quote, i):
                    i += len(quote)
                    quote = None
                else:
                    i += 1
            elif syn["line"] and raw.startswith(syn["line"], i):
                for j in range(i + len(syn["line"]), len(raw)):
                    keep[j] = True
                i = len(raw)
            elif pair := next((p for p in syn["blocks"] if raw.startswith(p[0], i)), None):
                block = pair[1]
                desc_pending = raw.startswith("/**", i)
                i += len(pair[0])
            elif q := next((x for x in syn["quotes"] if raw.startswith(x, i)), None):
                quote = q
                i += len(q)
            else:
                i += 1
        line = "".join(c if keep[k] else " " for k, c in enumerate(raw))
        if syn["cont"]:
            line = JSDOC_CONT.sub(lambda m: " " * len(m.group()), line, count=1)
        heading = False
        if desc_pending and line.strip():
            # 首行就是 tag 表示這段沒有描述,一樣消耗掉 pending
            heading = not line.lstrip().startswith("@")
            desc_pending = False
        line = JSDOC_TAG.sub(lambda m: " " * len(m.group()), line, count=1)
        if not heading:
            skips[lineno] = HEADING_ONLY
        out.append(line)
    return out, skips


def scan_lines(lines, terms, patterns, skips=None):
    """回傳 findings:(lineno, col, class, name, matched, suggestion)。lines 為可迭代的原始行。

    skips:lineno → 該行要略過的規則名稱集合,由 mask_source 產生;markdown 傳 None。
    """
    findings = []
    in_fence = False
    for lineno, raw in enumerate(lines, 1):
        if FENCE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence or not CJK.search(raw):
            continue
        skip = skips.get(lineno, ()) if skips else ()
        # 遮掉 inline code,用等長空白保留欄位位置
        line = INLINE_CODE.sub(lambda m: " " * len(m.group()), raw)
        line = LINK_DEST.sub(lambda m: " " * len(m.group()), line)
        if not CHECKBOX.match(line):
            line = LEAD_MARKER.sub(lambda m: " " * len(m.group()), line, count=1)
        for bad, meta in terms:
            idx = find_outside(line, bad, meta.get("allow", []))
            if idx >= 0:
                findings.append((lineno, idx + 1, meta["class"],
                                 meta.get("cat", "term"), bad, meta["good"]))
        for rx, meta in patterns:
            if meta["name"] in skip:
                continue
            m = rx.search(line)
            if m:
                # 整句規則從行首起算,定位錨要跳過遮掉的縮排與標記才看得出命中哪一句。
                # 跳掉幾個字就往後多取幾個字,定位錨的寬度不因縮排深淺而變。
                start = m.start()
                while start < len(line) and line[start] == " ":
                    start += 1
                end = m.end() + (start - m.start())
                # 遮罩都用等長空白,故 offset 可直接套回原始行取可讀的定位錨
                findings.append((lineno, start + 1, meta["class"],
                                 meta["name"], raw[start:end], meta["good"]))
    return findings


def main(argv):
    rules_path = Path(__file__).with_name("rules.json")
    terms, patterns = load_rules(rules_path)
    files = [Path(a) for a in argv]
    if not files:
        print("用法: python lint.py <file.md> [more files...]", file=sys.stderr)
        return 2

    had_error = False
    total = 0
    missing = [f for f in files if not f.is_file()]
    if missing:
        # 靜默跳過會讓打錯路徑的掃描印出「✓ 無違規」——假綠燈比漏抓更糟。
        for f in missing:
            print(f"找不到檔案: {f}", file=sys.stderr)
        return 2

    for f in files:
        lines = f.read_text(encoding="utf-8").splitlines()
        skips = None
        if syn := COMMENT_SYNTAX.get(f.suffix.lower()):
            lines, skips = mask_source(lines, syn)
        for lineno, col, cls, name, matched, good in scan_lines(lines, terms, patterns, skips):
            total += 1
            tag = "error" if cls == "A" else "warn "
            had_error |= cls == "A"
            # 整句規則(long-sentence / run-on-sentence)的 matched 是一長段,截短當定位錨
            shown = matched if len(matched) <= 24 else matched[:24] + "…"
            print(f"{f}:{lineno}:{col}: [{cls}/{tag}] {name}: 「{shown}」→ {good}")

    if total == 0:
        print("✓ 無違規")
    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
