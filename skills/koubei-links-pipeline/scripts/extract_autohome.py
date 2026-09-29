#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汽车之家口碑详情页（k.autohome.com.cn/detail/view_*.html）结构化提取。

直连 HTTP 即可（无需登录态），输出 data/autohome_extracted.json
字段：url / nickname / series / spec / title / pub_date / dims{7项} / avg / text
"""
import gzip
import json
import os
import re
import sys
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

DIM_ORDER = ["空间", "驾驶感受", "续航", "外观", "内饰", "价格政策", "智能化"]
# 价格政策 在折算 5 分制平均分时按「性价比」口径参与


def fetch(url, cache_dir):
    """下载页面（带本地缓存）"""
    os.makedirs(cache_dir, exist_ok=True)
    key = re.search(r"view_(view_)?([0-9a-z]+)\.html", url)
    key = key.group(2) if key else re.sub(r"\W+", "_", url)[-40:]
    path = os.path.join(cache_dir, key + ".html")
    if os.path.exists(path) and os.path.getsize(path) > 20000:
        return open(path, encoding="utf-8", errors="ignore").read()
    # 移动版 share_ 链接 → 转 PC view_
    u = url
    if "/share_" in u:
        u = u.replace("k.m.autohome.com.cn/detail/share_",
                      "k.autohome.com.cn/detail/view_")
    req = urllib.request.Request(u, headers={
        "User-Agent": UA,
        "Accept-Encoding": "gzip",
        "Referer": "https://k.autohome.com.cn/",
    })
    with urllib.request.urlopen(req, timeout=40) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
    t = data.decode("utf-8", "ignore")
    open(path, "w", encoding="utf-8").write(t)
    return t


def text_of(html, tag="p"):
    return re.sub(r"\s+", " ", html).strip()


def extract(html, url):
    out = {"url": url}

    # 标题
    m = re.search(r'<h1 class="title">(.*?)</h1>', html, re.S)
    out["title"] = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

    # 车系 / 配置
    m = re.search(r'class="main-series"\s*>(.*?)</span>', html, re.S)
    out["series"] = m.group(1).strip() if m else ""
    m = re.search(r'class="main-spec"\s*>(.*?)</span>', html, re.S)
    out["spec"] = m.group(1).strip() if m else ""

    # 昵称：<title> 里 "… _昵称_口碑_汽车之家"
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    out["nickname"] = ""
    if m:
        parts = m.group(1).split("_")
        if len(parts) >= 3:
            out["nickname"] = parts[-3].strip()

    # 发布日期：timeline 里的 YYYY-MM-DD 首次发表
    m = re.search(r"(\d{4}-\d{2}-\d{2})\s*首次发表", html)
    if not m:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", html)
    out["pub_date"] = m.group(1) if m else ""

    # 分项评分
    dims = {}
    for m in re.finditer(
            r"<h1>([^<]{1,10}?)\s*<div class=\"athm-star\">.*?star-num\">([\d.]+)<",
            html, re.S):
        name = m.group(1).strip()
        if name in DIM_ORDER:
            dims[name] = float(m.group(2))
    out["dims"] = dims

    vals = [dims[d] for d in DIM_ORDER if d in dims]
    out["avg"] = round(sum(vals) / len(vals), 2) if vals else None
    # 官方口径总分（懂车帝口径 5 分制 → 两位小数，供表格「评分」列参考）
    out["score5"] = out["avg"]

    # 正文：按小点拼接
    body = []
    for m in re.finditer(
            r"<h1>([^<]{1,10}?)\s*<div class=\"athm-star\">.*?star-num\">[\d.]+</span>\s*</h1>\s*<p class=\"kb-item-msg\">(.*?)</p>",
            html, re.S):
        name = m.group(1).strip()
        txt = re.sub(r"<[^>]+>", "", m.group(2))
        txt = re.sub(r"\s+", " ", txt).strip()
        if txt:
            body.append(f"【{name}】{txt}")
    out["text"] = "\n".join(body)

    # 购买时间 / 行驶里程等附加信息（尽力提取，缺失留空）
    m = re.search(r'<div class="key">(.*?)</div>\s*<div class="name">购买时间</div>', html, re.S)
    out["buy_time"] = re.sub(r"\s+", "", m.group(1)) if m else ""
    m = re.search(r'<div class="key">(.*?)</div>\s*<div class="name">行驶里程</div>', html, re.S)
    out["mileage"] = re.sub(r"\s+", "", m.group(1)) if m else ""

    # 图片 URL
    imgs = re.findall(r'<img[^>]+src="(//[^"]*?autoimg\.cn/[^"]+\.(?:jpg|jpeg|png))"', html)
    out["img_count_raw"] = len(imgs)
    return out


def main():
    urls_file = sys.argv[1] if len(sys.argv) > 1 else "data/urls_new.txt"
    out_file = sys.argv[2] if len(sys.argv) > 2 else "data/autohome_extracted.json"
    urls = [l.strip() for l in open(urls_file, encoding="utf-8") if l.strip()]
    res = []
    for i, u in enumerate(urls, 1):
        try:
            html = fetch(u, "html_snapshots")
            d = extract(html, u)
            res.append(d)
            print(f"[{i}/{len(urls)}] OK {d['nickname']} | {d['series']} {d['spec']} | "
                  f"{d['pub_date']} | avg={d['avg']} dims={d['dims']} | text={len(d['text'])}字")
            sys.stdout.flush()
        except Exception as e:
            print(f"[{i}/{len(urls)}] FAIL {u} :: {type(e).__name__} {e}")
            res.append({"url": u, "error": f"{type(e).__name__}: {e}"})
    json.dump(res, open(out_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("SAVED", out_file, len(res))


if __name__ == "__main__":
    main()
