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


def load_rules(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    terms = [(t["bad"], t) for t in data.get("terms", [])]
    patterns = [
        (re.compile(p["re"], re.I if p.get("ignorecase") else 0), p)
        for p in data.get("patterns", [])
    ]
    return terms, patterns


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
        for bad, meta in terms:
            idx = line.find(bad)
            if idx >= 0:
                findings.append((lineno, idx + 1, meta["class"],
                                 meta.get("cat", "term"), bad, meta["good"]))
        for rx, meta in patterns:
            m = rx.search(line)
            if m:
                findings.append((lineno, m.start() + 1, meta["class"],
                                 meta["name"], m.group(), meta["good"]))
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
    for f in files:
        if not f.is_file():
            continue
        lines = f.read_text(encoding="utf-8").splitlines()
        for lineno, col, cls, name, matched, good in scan_lines(lines, terms, patterns):
            total += 1
            tag = "error" if cls == "A" else "warn "
            had_error |= cls == "A"
            print(f"{f}:{lineno}:{col}: [{cls}/{tag}] {name}: 「{matched}」→ {good}")

    if total == 0:
        print("✓ 無違規")
    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
