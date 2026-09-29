# -*- coding: utf-8 -*-
"""从汽车之家抓取指定车型的官方外观图，拼成「官方参考图」，作为口碑图 R2 车型比对的基准。

用法：
  python fetch_autohome_refs.py "<车型名>" [输出目录] [最多张数]
  python fetch_autohome_refs.py --series <seriesId> [输出目录] [最多张数]

流程：
  1. 先从 references/汽车之家车型对照.md 查该车型对应的 series ID
  2. 表里没有 -> 走 sou.autohome.com.cn 搜索兜底（结果需人工确认，可能搜错车型）
  3. 抓 https://car.autohome.com.cn/photo/series/<seriesId>/1.html （1 = 车身外观分类）
  4. 正则抽出 CDN 图片 URL，下载并用 Pillow 拼成一张纵向联系图

输出：
  <OUT_DIR>/<车型>.jpg            —— 官方外观图联系图（带编号标签）
  data/autohome_series.json       —— 车型→series ID 缓存，下次直接复用

依赖：Pillow（python3 -m pip install Pillow）
"""
import sys, os, re, json, gzip, zlib, io, urllib.request, urllib.parse

UA_PC = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
MAP_FILE = os.path.join("references", "汽车之家车型对照.md")
CACHE_FILE = os.path.join("data", "autohome_series.json")

W = 520          # 单图目标宽度
PAD = 14
LABEL_H = 26


# ---------- 网络 ----------
def fetch(url, referer=None, timeout=30):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA_PC,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": referer or "https://www.autohome.com.cn/",
    })
    resp = urllib.request.urlopen(req, timeout=timeout)
    data = resp.read()
    enc = (resp.headers.get("Content-Encoding") or "").lower()
    if "gzip" in enc:
        data = gzip.decompress(data)
    elif "deflate" in enc:
        data = zlib.decompress(data, -zlib.MAX_WBITS)
    return data


def decode(data):
    """汽车之家页面 GBK/UTF-8 混杂，逐个试解码"""
    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", errors="ignore")


# ---------- series ID 解析 ----------
def norm(s):
    """归一化：去空格/连字符，用于车型名比对"""
    return re.sub(r"[\s\-_－—]", "", s or "")


def load_series_map():
    """读 references/汽车之家车型对照.md，返回 {归一化车型名: (series_id, 车型页URL, 官方色列表)}"""
    m = {}
    if not os.path.exists(MAP_FILE):
        return m
    text = open(MAP_FILE, encoding="utf-8").read()
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= set("-: "):
            continue
        name, sid = cells[0], cells[1]
        # 表头行跳过（车型列名可能带括号/全角，用 startswith 更稳）
        if norm(name) in ("", "车型") or name.startswith("车型") or name.startswith("---"):
            continue
        url = cells[2] if len(cells) > 2 else ""
        # 官方色支持顿号/中文逗号/英文逗号混合分隔
        colors = [c.strip() for c in re.split(r"[、,，;；]", cells[3]) if c.strip()] if len(cells) > 3 else []
        if sid and sid.strip().isdigit():
            m[norm(name)] = (sid.strip(), url, colors)
    return m


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            return json.load(open(CACHE_FILE, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    json.dump(cache, open(CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def search_series(name):
    """搜索兜底：从搜索结果页里找车型主页链接 www.autohome.com.cn/<id>/"""
    url = "https://sou.autohome.com.cn/zonghe?q=" + urllib.parse.quote(name)
    html = decode(fetch(url))
    # 优先匹配「链接文本里含车型关键词」的那条
    pat = re.compile(r'href="(?:https?:)?//(?:www\.)?autohome\.com\.cn/(\d{3,6})/[^"]*"[^>]*>([^<]{2,40})<')
    cands = pat.findall(html)
    key = norm(name)
    for sid, title in cands:
        if norm(title) in key or key in norm(title) or any(seg and seg in norm(title) for seg in re.split(r"[0-9]", key) if len(seg) >= 2):
            return sid, f"https://www.autohome.com.cn/{sid}/", title
    if cands:
        sid, title = cands[0]
        return sid, f"https://www.autohome.com.cn/{sid}/", title
    raise SystemExit(f"汽车之家搜索不到车型「{name}」，请在 {MAP_FILE} 手工填 series ID")


# ---------- 图片抽取 ----------
def fetch_series_images(sid, limit=12):
    """汽车之家图库 URL 已改版：旧 photo/series/<sid>/1.html 已 404，
    新版为 car.autohome.com.cn/pic/series-<sid>-<spec>-1-1.html（spec 从
    pic/series/<sid>-12-p1.html 或搜索结果的 spec 链接获取），页内图片是
    cardfs/product/ 带尺寸前缀（如 480x360_0_q95_c42_）的缩略图，
    删掉 '<W>x<H>_0_q<Q>_c<C>_' 前缀即还原原图。
    若 spec 未知，先抓 pic/series/<sid>-12-p1.html 找页面里第一个
    series-<sid>-<spec>-1- 外观分类链接作为兜底。"""
    # 兜底：先找 spec（从 -12- 全部图页里抓 series-<sid>-<spec>-1- 链接）
    spec_url = f"https://car.autohome.com.cn/pic/series/{sid}-12-p1.html"
    spec = None
    try:
        nav = decode(fetch(spec_url, referer=f"https://www.autohome.com.cn/{sid}/"))
        m = re.search(r'series-' + sid + r'-(\d+)-1-1\.html', nav)
        if m:
            spec = m.group(1)
    except Exception:
        pass
    if spec:
        url = f"https://car.autohome.com.cn/pic/series-{sid}-{spec}-1-1.html"
    else:
        url = f"https://car.autohome.com.cn/pic/series/{sid}-1-p1.html"
    html = decode(fetch(url, referer=f"https://www.autohome.com.cn/{sid}/"))
    # 匹配 //carN.autoimg.cn/... .jpg（新版缩略图带 <W>x<H>_0_q<Q>_c<C>_ 前缀）
    pat = re.compile(r'//(?:car\d*\.)?autoimg\.cn/[^"\'\s\\<>]+?\.jpg', re.I)
    urls = pat.findall(html)
    out, seen = [], set()
    for u in urls:
        if u.startswith("//"):
            u = "https:" + u
        # 去掉尺寸前缀还原原图（480x360_0_q95_c42_ → 原图）
        u = re.sub(r'/\d{2,4}x\d{2,4}_0_q\d+_c\d+_', '/', u)
        # 过滤小图标（形如 /60x60_ 但非 q95 前缀的残留）与 _t.jpg
        if re.search(r'/(\d{2,3})x(\d{2,3})_', u) and 'cardfs' not in u:
            continue
        if u.endswith("_t.jpg"):
            continue
        if u not in seen:
            seen.add(u)
            out.append(u)
        if len(out) >= limit:
            break
    return out


def get_font(size):
    # 延迟导入：build_sheet 里的 PIL 导入是函数局部作用域，此处取不到全局名
    from PIL import ImageFont
    try:
        return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def build_sheet(imgs, out_path, title):
    from PIL import Image, ImageDraw
    sheets = []
    for i, data in enumerate(imgs, 1):
        try:
            pil = Image.open(io.BytesIO(data)).convert("RGB")
            ratio = W / pil.width
            pil = pil.resize((W, int(pil.height * ratio)))
            sheets.append(pil)
        except Exception as e:
            print(f"  图{i} 解码失败: {e}")
    if not sheets:
        raise SystemExit("没有可用图片，拼图失败")
    total_h = sum(LABEL_H + im.height + PAD for im in sheets)
    sheet = Image.new("RGB", (W + PAD * 2, total_h), (255, 255, 255))
    y = 0
    font = get_font(18)
    draw = ImageDraw.Draw(sheet)
    for idx, im in enumerate(sheets, 1):
        draw.rectangle([PAD, y, PAD + W, y + LABEL_H], fill=(230, 235, 245))
        draw.text((PAD + 6, y + 3), f"官方图{idx}/{len(sheets)}  {title}", fill=(20, 40, 80), font=font)
        y += LABEL_H
        sheet.paste(im, (PAD, y))
        y += im.height + PAD
    sheet.save(out_path, quality=85)
    return len(sheets)


def sanitize(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def main():
    args = sys.argv[1:]
    series = None
    if args and args[0] == "--series":
        if len(args) < 2:
            raise SystemExit("用法：fetch_autohome_refs.py --series <seriesId> [输出目录] [最多张数]")
        series = args[1]
        car_name = f"series{series}"
        rest = args[2:]
    else:
        if not args:
            raise SystemExit("用法：fetch_autohome_refs.py \"<车型名>\" [输出目录] [最多张数]")
        car_name = args[0]
        rest = args[1:]

    OUT_DIR = rest[0] if len(rest) > 0 else "refs"
    limit = int(rest[1]) if len(rest) > 1 else 12

    os.makedirs(OUT_DIR, exist_ok=True)
    cache = load_cache()

    # 1) 解析 series ID
    src = ""
    if series:
        src = "命令行指定"
        page_url = f"https://www.autohome.com.cn/{series}/"
        colors = []
    else:
        smap = load_series_map()
        hit = smap.get(norm(car_name))
        if hit:
            series, page_url, colors = hit
            src = "映射表"
        elif norm(car_name) in cache:
            series, page_url = cache[norm(car_name)], f"https://www.autohome.com.cn/{cache[norm(car_name)]}/"
            colors = []
            src = "缓存"
        else:
            series, page_url, title = search_series(car_name)
            colors = []
            src = f"搜索兜底(匹配到「{title}」，请人工确认车型是否正确)"
            cache[norm(car_name)] = series
            save_cache(cache)

    print(f"车型：{car_name}  series ID：{series}  来源：{src}")
    print(f"车型页：{page_url}")

    # 2) 抓官方外观图
    urls = fetch_series_images(series, limit=limit)
    print(f"解析到 {len(urls)} 张官方外观图，开始下载...")
    if not urls:
        raise SystemExit("未解析到图片 URL，汽车之家页面结构可能已变更，请改用 --series 手动指定或人工下载官方图")

    blobs = []
    for i, u in enumerate(urls, 1):
        try:
            blobs.append(fetch(u, referer=page_url, timeout=30))
            print(f"  [{i}/{len(urls)}] OK")
        except Exception as e:
            print(f"  [{i}/{len(urls)}] 失败: {e}")

    # 3) 拼官方参考图
    out_path = os.path.join(OUT_DIR, f"{sanitize(car_name)}.jpg")
    n = build_sheet(blobs, out_path, car_name)
    print(f"\n完成：{n} 张 → {out_path}")
    print(f"图页：https://car.autohome.com.cn/photo/series/{series}/1.html")
    if colors:
        print(f"官方外观色（仅参考，非 R3 判定依据）：{'、'.join(colors)}")
    else:
        print("官方外观色：映射表未维护（可选，仅供人工参考）")


if __name__ == "__main__":
    main()
