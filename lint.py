#!/usr/bin/env python3
"""中文行文 linter —— 掃 markdown / 程式碼註解,抓 CLAUDE.md §0 裡機械可判定的規則。

分工:
- A 類(error,退出碼 1):純黑名單 / regex,高信任、近乎零誤判。
- B 類(warn,不影響退出碼):需語義判斷的疑點,只標出讓人看。
- 純語義規則(翻譯腔是否自然、括號是補充還是合法 gloss)機器不做,留給人 review。

只查「含中文字的行」——一行擋掉純英文 / URL / 程式碼的誤判;fenced code block 與 inline
`code` 一律遮掉不查。
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


def scan_lines(lines, terms, patterns):
    """回傳 findings:(lineno, col, class, name, matched, suggestion)。lines 為可迭代的原始行。"""
    findings = []
    in_fence = False
    for lineno, raw in enumerate(lines, 1):
        if FENCE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence or not CJK.search(raw):
            continue
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
            m = rx.search(line)
            if m:
                # 遮罩都用等長空白,故 offset 可直接套回原始行取可讀的定位錨
                findings.append((lineno, m.start() + 1, meta["class"],
                                 meta["name"], raw[m.start():m.end()], meta["good"]))
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
        for lineno, col, cls, name, matched, good in scan_lines(lines, terms, patterns):
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
