#!/usr/bin/env python3
"""
pull_report_narratives.py — 拉取主动基金定期报告「投资策略和运作分析」原文时间线

用法:
  /tmp/pdfenv/bin/python pull_report_narratives.py <fundcode> <start_date> [out_dir]

  <fundcode>   6 位基金代码，如 010624
  <start_date> 现任经理任职起点 YYYY-MM-DD（只取该日期之后的报告）
  [out_dir]    输出目录，默认 /tmp/report_timeline/<fundcode>/

依赖:
  - python3 + pymupdf（建议 venv: /tmp/pdfenv/bin/python，execute_code 沙箱无 fitz）
  - 网络可访问 pdf.dfcfw.com / api.fund.eastmoney.com

输出:
  <out_dir>/<YYYY-MM-DD>.txt  每份定期报告的「运作分析」原文（未找到则写标记）

流程: 东财 F10 公告列表 API → 筛选季度报告+最新中报 → 下载 PDF → pymupdf 提取段落
"""
import json, subprocess, os, sys, time, re, urllib.request

def get_report_list(code, pages=3, per_page=50):
    """东财 F10 公告列表，返回 [{title,id,date}]（定期报告）"""
    reports = []
    for page in range(1, pages + 1):
        url = f"https://api.fund.eastmoney.com/f10/JJGG?fundcode={code}&pageIndex={page}&pageSize={per_page}&type=3"
        req = urllib.request.Request(url, headers={
            "Referer": "https://fundf10.eastmoney.com/",
            "User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read().decode())
            items = d.get("Data") or []
            if not items:
                break
            for x in items:
                t = x.get("TITLE", "")
                if any(k in t for k in ["季度报告", "中期报告", "年度报告"]):
                    reports.append({"title": t, "id": x.get("ID"), "date": x.get("PUBLISHDATEDesc")})
        except Exception as e:
            print(f"page {page} ERR {e}", flush=True)
        time.sleep(0.3)
    seen, uniq = set(), []
    for r in reports:
        if r["id"] not in seen:
            seen.add(r["id"])
            uniq.append(r)
    return sorted(uniq, key=lambda r: r["date"])

def pick_reports(reports, start_date):
    """从 start_date 后取每季度报告 + 最新中报（排除年度报告避免重复）"""
    picks = []
    for r in reports:
        if r["date"] < start_date:
            continue
        t = r["title"]
        if "季度报告" in t and "年度" not in t:
            picks.append(r)
        elif "中期报告" in t and ("2026" in t or "二0二六" in t) and "摘要" not in t:
            picks.append(r)
    return picks

EXTRACTOR = r'''
import fitz, re, sys
path, out = sys.argv[1], sys.argv[2]
doc = fitz.open(path)
full = "\n".join(p.get_text() for p in doc)
best = -1
for m in re.finditer(r"报告期内基金的投资策略和运作分析", full):
    s = m.start()
    line = full[s:s+80].split("\n")[0]
    if "……" in line or "...." in line:
        continue  # 目录行
    if s > best:
        best = s
if best == -1:
    idx = full.find("报告期内基金的运作分析")
    best = idx if idx > 0 else -1
if best == -1:
    open(out, "w").write("【未找到运作分析段】")
    sys.exit(0)
seg = full[best:]
ends = []
for m in ["4.5", "报告期内基金的业绩表现", "5. 投资组合", "§5"]:
    i = seg.find(m, 100)
    if i > 0:
        ends.append(i)
cut = min(ends) if ends else min(len(seg), 4000)
text = re.sub(r"[ \t]+", " ", seg[:cut].strip())
text = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9，。、；：""''（）()%％\-+./\n\s]", "", text)
open(out, "w").write(text)
'''

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    code, start_date = sys.argv[1], sys.argv[2]
    out_dir = sys.argv[3] if len(sys.argv) > 3 else f"/tmp/report_timeline/{code}"
    os.makedirs(out_dir, exist_ok=True)
    pdf_dir = f"/tmp/report_pdf"
    os.makedirs(pdf_dir, exist_ok=True)
    ext_path = "/tmp/extract_narrative.py"
    if not os.path.exists(ext_path):
        open(ext_path, "w").write(EXTRACTOR)

    reports = get_report_list(code)
    picks = pick_reports(reports, start_date)
    print(f"{code}: 共 {len(reports)} 份定期报告, 筛选 {len(picks)} 份", flush=True)
    for r in picks:
        print(f"  {r['date']} | {r['title'][:40]}", flush=True)

    for r in picks:
        out = f"{out_dir}/{r['date']}.txt"
        pdf = f"{pdf_dir}/{code}_{r['date']}.pdf"
        if os.path.exists(out) and os.path.getsize(out) > 50 and os.path.exists(pdf):
            continue
        url = f"https://pdf.dfcfw.com/pdf/H2_{r['id']}_1.pdf"
        ok = False
        for attempt in range(3):
            subprocess.run(["curl", "-sL", "--max-time", "45", "-H", "User-Agent: Mozilla/5.0",
                            "-o", pdf, url], capture_output=True, text=True)
            if os.path.exists(pdf) and os.path.getsize(pdf) > 30000:
                ok = True
                break
            time.sleep(1.5)
        if not ok:
            open(out, "w").write("【下载失败】")
            print(f"{r['date']} 下载失败", flush=True)
            continue
        subprocess.run([sys.executable, ext_path, pdf, out], capture_output=True, text=True)
        print(f"  ✅ {r['date']} ({os.path.getsize(out)}B)", flush=True)
        time.sleep(0.4)
    print("完成", flush=True)

if __name__ == "__main__":
    main()