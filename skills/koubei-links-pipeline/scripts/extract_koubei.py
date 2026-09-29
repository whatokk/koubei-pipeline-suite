# -*- coding: utf-8 -*-
"""从已下载的口碑 HTML 快照中提取标题/评分/发布日期。
输入：HTML 目录（文件名形如 01_账号_车型.html，seq 取前两位）
输出：data/extracted.json [{seq, acct, car, title, score, date, raw}]
用法：python extract_koubei.py [HTML目录] [输出json路径]
"""
import sys, os, re, json, glob, datetime

SRC = sys.argv[1] if len(sys.argv) > 1 else "html_snapshots"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join("data", "extracted.json")

def extract_title(motor_title, title_tag):
    """标题 = 正文第一句，去掉开头的【xxx】标记；备选 title 标签去'_懂车帝'"""
    if motor_title:
        cleaned = re.sub(r'^(?:【[^】]*】[\s]*)+', '', motor_title)
        first = re.split(r'[。]', cleaned)[0]
        first = re.sub(r'\s+', ' ', first).strip()
        if first:
            return first
    if title_tag:
        t = re.sub(r'_懂车帝$', '', title_tag.strip())
        return re.sub(r'\s+', ' ', t).strip()
    return ""

def main():
    rows = []
    files = sorted(glob.glob(os.path.join(SRC, "*.html")))
    for fp in files:
        base = os.path.basename(fp)
        seq = int(base[:2])
        html = open(fp, encoding="utf-8").read()
        # title 标签
        m_title = re.search(r'<title>(.*?)</title>', html, re.S)
        title_tag = m_title.group(1).strip() if m_title else ""
        # __NEXT_DATA__
        mj = re.search(r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', html, re.S)
        ad = None
        score = None
        date = None
        if mj:
            try:
                data = json.loads(mj.group(1))
                ad = data["props"]["pageProps"]["articleDetail"]
            except Exception as e:
                ad = None
        if ad:
            cv = ad.get("car_view") or {}
            if cv.get("score") is not None:
                score = f"{cv['score'] / 100:.2f}"  # 整数→两位小数
            cpt = ad.get("content_publish_time")
            if cpt:
                date = datetime.datetime.fromtimestamp(int(cpt)).strftime("%Y-%m-%d")
            title = extract_title(ad.get("motor_title", ""), title_tag)
        else:
            title = re.sub(r'_懂车帝$', '', title_tag) if title_tag else ""

        # 从文件名解析账号/车型
        parts = base[:-5].split("_", 2)
        acct = parts[1] if len(parts) > 1 else ""
        car = parts[2] if len(parts) > 2 else ""

        rows.append({
            "seq": seq, "acct": acct, "car": car,
            "title": title, "score": score, "date": date,
        })
        print(f"{seq:02d} | {car} | 评分={score} | {date} | {title[:30]}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n提取完成 {len(rows)} 条 → {OUT}")

if __name__ == "__main__":
    main()
