#!/usr/bin/env python3
"""自我檢查:餵已知好 / 壞樣本,斷言該抓的抓到、該放的放過。無框架,直接跑。"""
from pathlib import Path
from lint import load_rules, scan_lines

terms, patterns = load_rules(Path(__file__).with_name("rules.json"))


def hits(text):
    return {(name, matched) for _, _, _, name, matched, _ in
            scan_lines(text.splitlines(), terms, patterns)}


def hits_cls(text):
    return {(name, matched, cls) for _, _, cls, name, matched, _ in
            scan_lines(text.splitlines(), terms, patterns)}


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    assert cond, name


# 該抓到的
check("大陸用語 代碼", ("大陸用語", "代碼") in hits("這段代碼有問題"))
check("calque 橫切", ("calque", "橫切") in hits("這是橫切旗標"))
check("math symbol", ("math-symbol", "∪") in hits("取 A ∪ B 的結果"))
check("date-slash 警告", ("date-slash", "5/14") in hits("預計 5/14 完成"))

# latin-abbrev 分級:via/i.e./e.g. 是 A,per/vs 降 B
check("via 是 A", ("latin-abbrev", "via", "A") in hits_cls("透過 API via 中介層"))
check("per 降 B", ("latin-abbrev", "per", "B") in hits_cls("per 每筆資料"))
check("vs 降 B", ("latin-abbrev", "vs", "B") in hits_cls("方案甲 vs 方案乙"))

# paren-supplement:全形（含中文補充才報;純英文 gloss / 半形(連結網址)跳過
check("標題中文補充 → 報", ("paren-supplement", "（附帶說明歷程") in hits("## 狀態機（附帶說明歷程）"))
check("內文中文補充 → 報", ("paren-supplement", "（這是內文") in hits("一般內文的括號補充（這是內文）"))
check("Mermaid 標題中文補充 → 報", ("paren-supplement", "（含旗標") in hits("title 車輛狀態（含旗標）"))
check("英文 gloss → 不報", not any(n == "paren-supplement" for n, _ in hits("## 通訊互動模式（Interaction Patterns）")))
check("半形英文縮寫 → 不報", not any(n == "paren-supplement" for n, _ in hits("## 系統狀態機 (FSM)")))
check("markdown 連結中文網址 → 不報", not any(n == "paren-supplement" for n, _ in hits("見 [格式定義](/T3/vehicle-supervision-system/MQTT格式定義)")))

# run-on-list:並列子句擠一句該報,短名詞列舉 / 已是 bullet 放過
check("run-on 並列子句 → 報", any(n == "run-on-list" for n, _ in
      hits("RELEASE_BRAKE 重用消掉相依、空值防呆送出不等回應、走 fallback 記 warn、拆三個獨立 Map。")))
check("短名詞列舉 → 不報", not any(n == "run-on-list" for n, _ in hits("支援 程式碼、資訊、物件、預設 四種")))
check("已是 bullet → 不報", not any(n == "run-on-list" for n, _ in hits("- 消掉相依、空值防呆送出、走 fallback、拆 Map")))
check("兩個子句 → 不報（未達 3 段）", not any(n == "run-on-list" for n, _ in hits("這段消掉了相依、也做了空值防呆。")))

# 不該誤判的
check("純英文行不查 per", ("latin-abbrev", "per") not in hits("results are shown per file"))
check("fenced code 不查", hits("```\n這段代碼\n```") == set())
check("inline code 不查", ("大陸用語", "代碼") not in hits("請看 `代碼` 這個字串"))
check("程式碼 不誤判為 代碼", ("大陸用語", "代碼") not in hits("這段程式碼沒問題"))

print("\n全部通過")
