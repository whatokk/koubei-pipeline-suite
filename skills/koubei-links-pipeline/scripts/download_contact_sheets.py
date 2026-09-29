# -*- coding: utf-8 -*-
"""下载口碑页图片并拼成联系图，供视觉核实（车身/内饰/人物）。
输入：HTML 目录（文件名 01_账号_车型.html）
输出：sheets/<seq>.jpg（每页一张纵向联系图，带编号标签）
依赖：Pillow（python3 -m pip install Pillow）
用法：python download_contact_sheets.py [HTML目录] [输出目录]
"""
import sys, os, re, json, glob, urllib.request, io
from PIL import Image, ImageDraw, ImageFont

SRC = sys.argv[1] if len(sys.argv) > 1 else "html_snapshots"
OUT = sys.argv[2] if len(sys.argv) > 2 else "sheets"

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
W = 520          # 单图目标宽度
PAD = 14
LABEL_H = 26

def get_font(size):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size)
    except Exception:
        return ImageFont.load_default()

def download(url, fn):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://m.dongchedi.com/"})
    data = urllib.request.urlopen(req, timeout=30).read()
    open(fn, "wb").write(data)

def main():
    os.makedirs(OUT, exist_ok=True)
    files = sorted(glob.glob(os.path.join(SRC, "*.html")))
    total_imgs = 0
    for fp in files:
        seq = os.path.basename(fp).split("_")[0]   # 兼容 2/3 位序号
        html = open(fp, encoding="utf-8").read()
        mj = re.search(r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', html, re.S)
        if not mj:
            continue
        ad = json.loads(mj.group(1))["props"]["pageProps"]["articleDetail"]
        imgs = ad.get("image_urls") or []
        if not imgs:
            continue
        # 下载到内存
        sheets = []
        for i, im in enumerate(imgs, 1):
            url = im.get("url")
            if not url:
                continue
            try:
                data = None
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://m.dongchedi.com/"})
                data = urllib.request.urlopen(req, timeout=30).read()
                pil = Image.open(io.BytesIO(data)).convert("RGB")
                ratio = W / pil.width
                pil = pil.resize((W, int(pil.height * ratio)))
                sheets.append(pil)
                total_imgs += 1
            except Exception as e:
                print(f"  [{seq}] 图{i}失败: {e}")
        if not sheets:
            continue
        # 纵向拼接 + 编号
        total_h = sum(LABEL_H + im.height + PAD for im in sheets)
        sheet = Image.new("RGB", (W + PAD * 2, total_h), (255, 255, 255))
        y = 0
        font = get_font(18)
        draw = ImageDraw.Draw(sheet)
        for idx, im in enumerate(sheets, 1):
            draw.rectangle([PAD, y, PAD + W, y + LABEL_H], fill=(230, 235, 245))
            draw.text((PAD + 6, y + 3), f"图{idx}/{len(sheets)}", fill=(20, 40, 80), font=font)
            y += LABEL_H
            sheet.paste(im, (PAD, y))
            y += im.height + PAD
        out = os.path.join(OUT, f"{seq}.jpg")
        sheet.save(out, quality=85)
        print(f"{seq}: {len(sheets)} 张 → {out}")
    print(f"\n完成，共下载 {total_imgs} 张图片")

if __name__ == "__main__":
    main()
