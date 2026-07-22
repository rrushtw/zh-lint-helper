#!/usr/bin/env python3
"""自我檢查:餵已知好 / 壞樣本,斷言該抓的抓到、該放的放過。無框架,直接跑。"""
from pathlib import Path
from lint import load_rules, scan_lines

terms, patterns = load_rules(Path(__file__).with_name("rules.json"))


def hits(text):
    return {(name, matched) for _, _, _, name, matched, _ in
            scan_lines(text.splitlines(), terms, patterns)}


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    assert cond, name


# 該抓到的
check("大陸用語 代碼", ("大陸用語", "代碼") in hits("這段代碼有問題"))
check("calque 橫切", ("calque", "橫切") in hits("這是橫切旗標"))
check("math symbol", ("math-symbol", "∪") in hits("取 A ∪ B 的結果"))
check("latin per (含中文行)", ("latin-abbrev", "per") in hits("per 每筆資料"))
check("date-slash 警告", ("date-slash", "5/14") in hits("預計 5/14 完成"))
check("heading-paren 警告", any(n == "heading-paren" for n, _ in hits("## 系統狀態機(FSM)")))

# 不該誤判的
check("純英文行不查 per", ("latin-abbrev", "per") not in hits("results are shown per file"))
check("fenced code 不查", hits("```\n這段代碼\n```") == set())
check("inline code 不查", ("大陸用語", "代碼") not in hits("請看 `代碼` 這個字串"))
check("程式碼 不誤判為 代碼", ("大陸用語", "代碼") not in hits("這段程式碼沒問題"))

print("\n全部通過")
