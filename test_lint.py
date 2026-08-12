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

# 工地隱喻:動工 / 完工 是 A;動手 / 施工 有本義或正式名稱例外故降 B
check("工地隱喻 動工 是 A", ("工地隱喻", "動工", "A") in hits_cls("下週開始動工"))
check("工地隱喻 完工 是 A", ("工地隱喻", "完工", "A") in hits_cls("預計月底完工"))
check("工地隱喻 動手 降 B", ("工地隱喻", "動手", "B") in hits_cls("## 動手順序"))
check("工地隱喻 施工 降 B", ("工地隱喻", "施工", "B") in hits_cls("照施工順序做"))
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
check("bullet 內短名詞列舉 → 不報", not any(n == "run-on-list" for n, _ in hits("- 消掉相依、空值防呆送出、走 fallback、拆 Map")))
check("bullet 內並列子句 → 報", any(n == "run-on-list" for n, _ in
      hits("- RELEASE_BRAKE 重用消掉相依、空值防呆送出不等回應、走 fallback 記 warn、拆三個獨立 Map。")))
check("兩個子句 → 不報（未達 3 段）", not any(n == "run-on-list" for n, _ in hits("這段消掉了相依、也做了空值防呆。")))

check("純英文識別字列舉 → 不報", not any(n == "run-on-list" for n, _ in
      hits("- 本頁的 topic、payload、cadence、retain 旗標與判定門檻由 ICL 先行定義")))
check("連結 URL 的中文 anchor 不計句長 → 不報", not any(n == "long-sentence" for n, _ in
      hits("- Agent 展開 task 後透傳至 ADS（[agent-ads-mqtt §2.1](/T3/interfaces/agent-ads-mqtt#h-21-導航任務-navigate)），ADS 依此識別碼自查內建站點資料庫取得精準停靠姿態")))

# run-on-sentence:一句 3+ 個實質子句(，／；分隔)該報,短子句 / 引言句 / bullet 放過
check("三子句擠一句 → 報", any(n == "run-on-sentence" for n, _ in
      hits("先確認欄位型別對不對再說，接著看邊界條件有沒有處理好，最後跑一次整合測試確認。")))
check("兩子句 → 不報", not any(n == "run-on-sentence" for n, _ in
      hits("先確認欄位型別對不對再說，接著看邊界條件有沒有處理好。")))
check("短子句 → 不報", not any(n == "run-on-sentence" for n, _ in hits("這樣改，那樣改，都可以。")))
check("行尾冒號的引言句 → 不報", not any(n == "run-on-sentence" for n, _ in
      hits("類別內部的成員應嚴格按照以下順序排列，並建議使用註解標題區隔，以利閱讀：")))
check("run-on-sentence 在 bullet 內 → 報", any(n == "run-on-sentence" for n, _ in
      hits("- 先確認欄位型別對不對再說，接著看邊界條件有沒有處理好，最後跑一次整合測試確認。")))
check("run-on-sentence 在 sub-bullet 內 → 報", any(n == "run-on-sentence" for n, _ in
      hits("    - 先確認欄位型別對不對再說，接著看邊界條件有沒有處理好，最後跑一次整合測試確認。")))
check("run-on-sentence checkbox → 不報", not any(n == "run-on-sentence" for n, _ in
      hits("- [ ] 先確認欄位型別對不對再說，接著看邊界條件有沒有處理好，最後跑一次整合測試確認。")))

# long-sentence:單句 30+ 中文字該報,英文 / 網址不計字
check("單句超長 → 報", any(n == "long-sentence" for n, _ in
      hits("這個規則之所以要放進工具裡是因為每次靠注意力手動掃都會漏掉幾條而且漏的還都是同一類。")))
check("兩短句 → 不報", not any(n == "long-sentence" for n, _ in
      hits("這段改得不錯。邊界條件也都有處理到。")))
check("長網址不計字 → 不報", not any(n == "long-sentence" for n, _ in
      hits("詳見 https://gitlab.itriadv.co/u2/t3/host/-/merge_requests/62#note_9525 這條留言。")))
check("long-sentence 在 bullet 內 → 報", any(n == "long-sentence" for n, _ in
      hits("- 這個規則之所以要放進工具裡是因為每次靠注意力手動掃都會漏掉幾條而且漏的還都是同一類。")))
check("long-sentence 在 blockquote 的 bullet 內 → 報", any(n == "long-sentence" for n, _ in
      hits("> - 這個規則之所以要放進工具裡是因為每次靠注意力手動掃都會漏掉幾條而且漏的還都是同一類。")))
check("long-sentence 在 blockquote 純內文 → 報", any(n == "long-sentence" for n, _ in
      hits("> 這個規則之所以要放進工具裡是因為每次靠注意力手動掃都會漏掉幾條而且漏的還都是同一類。")))
check("long-sentence checkbox → 不報", not any(n == "long-sentence" for n, _ in
      hits("- [x] 這個規則之所以要放進工具裡是因為每次靠注意力手動掃都會漏掉幾條而且漏的還都是同一類。")))
check("bullet 短句 → 不報", not any(n == "long-sentence" for n, _ in
      hits("- 這段改得不錯。邊界條件也都有處理到。")))
check("表格列長句 → 不報", not any(n == "long-sentence" for n, _ in
      hits("| 說明 | 這個規則之所以要放進工具裡是因為每次靠注意力手動掃都會漏掉幾條而且漏的還都是同一類 |")))

# halfwidth-comma:緊貼 CJK 的半形逗號該報,英數之間放行
check("中文後半形逗號 → 報", ("halfwidth-comma", ",", "A") in hits_cls("這幾個判斷都對,方向抓得很好"))
check("半形逗號後接中文 → 報", ("halfwidth-comma", ",", "A") in hits_cls("Howie,超速這兩張 MR"))
check("英文之間半形逗號 → 不報", not any(n == "halfwidth-comma" for n, _ in hits("支援 MINOR, MAJOR, CRITICAL 三級")))
check("數字之間半形逗號 → 不報", not any(n == "halfwidth-comma" for n, _ in hits("總共 1,000 筆資料")))
check("inline code 內逗號 → 不報", not any(n == "halfwidth-comma" for n, _ in hits("看 `a,b` 這段跟後面的中文")))

# halfwidth-colon:緊貼 CJK 的半形冒號該報;全形 / 半形後加空格 / 數字兩側放行
check("中文後緊貼半形冒號 → 報", ("halfwidth-colon", ":", "A") in hits_cls("先說結論:車端分級"))
check("半形冒號後接中文 → 報", ("halfwidth-colon", ":", "A") in hits_cls("MR:超速這兩張"))
check("半形冒號後有空格 → 不報", not any(n == "halfwidth-colon" for n, _ in hits("先說結論: 車端分級")))
check("全形冒號 → 不報", not any(n == "halfwidth-colon" for n, _ in hits("先說結論：車端分級")))
check("時間 10:30 → 不報", not any(n == "halfwidth-colon" for n, _ in hits("預計 10:30 出發")))
check("行號 a.js:129 → 不報", not any(n == "halfwidth-colon" for n, _ in hits("看 a.js:129 這行")))
check("比例 2:1 → 不報", not any(n == "halfwidth-colon" for n, _ in hits("男女比例 2:1 偏高")))

# halfwidth-semicolon:緊貼 CJK 的半形分號該報,英數之間放行
check("中文後半形分號 → 報", ("halfwidth-semicolon", ";", "A") in hits_cls("已確認;方向抓得很好"))
check("半形分號後接中文 → 報", ("halfwidth-semicolon", ";", "A") in hits_cls("方案甲;方案乙"))
check("中文分號即使後接空格 → 報", ("halfwidth-semicolon", ";", "A") in hits_cls("這是中文; 後面還有"))
check("英文分號後接空格 → 不報", not any(n == "halfwidth-semicolon" for n, _ in hits("這段 a; b 是程式碼")))
check("英文分號無空格 → 報", ("halfwidth-semicolon", ";", "A") in hits_cls("這段 a;b 是程式碼"))
check("數字之間半形分號 → 報", ("halfwidth-semicolon", ";", "A") in hits_cls("總共 1;2 兩筆"))

# 落地：工程直譯動詞該抓(B)，正常詞放過
check("落地 動詞 → 報 B", ("自創縮語", "落地", "B") in hits_cls("導航參數一路落地到資料庫"))
check("首版落地 → 報 B", ("自創縮語", "落地", "B") in hits_cls("本期先完成首版落地"))
check("落地窗 → 仍會命中(B 靠人判)", ("自創縮語", "落地", "B") in hits_cls("客廳有一整面落地窗"))

# allow：壞詞被合法長詞包住時放行，落在長詞外仍要報
check("施工規範 → 不報", not any(n == "工地隱喻" for n, _ in hits("以施工規範附錄三為準")))
check("施工規範同行另有裸施工 → 報", ("工地隱喻", "施工", "B") in hits_cls("施工規範寫的施工順序要改"))
check("裸施工 → 仍報", ("工地隱喻", "施工", "B") in hits_cls("先確認施工順序再開工"))
check("無 allow 的詞不受影響", ("自創縮語", "落地", "B") in hits_cls("首版落地了"))

# 不該誤判的
check("純英文行不查 per", ("latin-abbrev", "per") not in hits("results are shown per file"))
check("fenced code 不查", hits("```\n這段代碼\n```") == set())
check("inline code 不查", ("大陸用語", "代碼") not in hits("請看 `代碼` 這個字串"))
check("程式碼 不誤判為 代碼", ("大陸用語", "代碼") not in hits("這段程式碼沒問題"))

print("\n全部通過")
