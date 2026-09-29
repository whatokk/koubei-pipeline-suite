# 从抓取的 __NEXT_DATA__ JSON 中提取正文文案 + 下载原图
# 每篇输出到 out/<seq>_<昵称>/ : 文案.txt + img_01.jpg ...
import json, os, sys, time, urllib.request, urllib.error, re

WORK = r'D:\项目\汽车之家\核对\下载_20260910'
SNAP = os.path.join(WORK, 'html_snapshots')
OUT = os.path.join(WORK, 'out')
ROWS = json.load(open(os.path.join(WORK, 'data', 'rows.json'), encoding='utf-8'))

UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'

def safe(name):
    return re.sub(r'[\\/:*?"<>|\s]+', '_', str(name)).strip('_')[:40]

def download(url, dest):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Referer': 'https://m.dongchedi.com/',
        'Accept': 'image/avif,image/webp,image/*,*/*;q=0.8',
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    if len(data) < 1024:
        raise ValueError('too small: %d bytes' % len(data))
    with open(dest, 'wb') as f:
        f.write(data)
    return len(data)

def main():
    os.makedirs(OUT, exist_ok=True)
    summary = []
    for row in ROWS:
        seq = row['seq']
        src = os.path.join(SNAP, 'kb_%d.json' % seq)
        if not os.path.exists(src):
            summary.append((seq, row['acct'], 'NO_SNAPSHOT', 0, 0))
            print('[%d] %s -> 缺快照' % (seq, row['acct']))
            continue
        try:
            d = json.load(open(src, encoding='utf-8'))
            ad = d['props']['pageProps']['articleDetail']
        except Exception as e:
            summary.append((seq, row['acct'], 'PARSE_FAIL', 0, 0))
            print('[%d] 解析失败 %s' % (seq, e))
            continue

        title = (ad.get('motor_title') or '').strip()
        if not title:
            title = (ad.get('content') or '').strip()
        imgs = ad.get('image_urls') or []
        prof = ad.get('motor_profile_info') or {}
        car = ad.get('motor_car_info') or {}
        author = prof.get('name') or row['acct']
        series = car.get('series_name') or row['car']

        folder = os.path.join(OUT, '%d_%s' % (seq, safe(author)))
        os.makedirs(folder, exist_ok=True)

        # 文案
        txt = os.path.join(folder, '文案.txt')
        with open(txt, 'w', encoding='utf-8') as f:
            f.write('【序号】%d\n' % seq)
            f.write('【昵称】%s\n' % author)
            f.write('【车型】%s\n' % series)
            f.write('【正文】\n%s\n' % title)
            f.write('\n【图片数】%d\n' % len(imgs))
            f.write('【来源】%s\n' % row['url'])

        # 图片
        okimg = 0
        for i, im in enumerate(imgs):
            u = im.get('url') if isinstance(im, dict) else str(im)
            if not u:
                continue
            ext = '.jpg'
            m = re.search(r'~tplv-[^:]+:([^.?]+)', u)
            if m and '.' in m.group(1):
                ext = '.' + m.group(1).split('.')[-1]
            elif '.png' in u:
                ext = '.png'
            dest = os.path.join(folder, 'img_%02d%s' % (i + 1, ext))
            try:
                sz = download(u, dest)
                okimg += 1
                print('   img%d ok %.0fKB' % (i + 1, sz / 1024))
            except Exception as e:
                print('   img%d FAIL %s' % (i + 1, str(e)[:80]))
            time.sleep(0.4)

        summary.append((seq, author, 'OK' if title else 'NO_TEXT', okimg, len(imgs)))
        print('[%d] %s | 正文%d字 | 图%d/%d' % (seq, author, len(title), okimg, len(imgs)))

    print('\n========== 汇总 ==========')
    tot_img = 0
    for seq, acct, st, oi, ti in summary:
        tot_img += oi
        print('%4d  %-16s %-12s 图 %d/%d' % (seq, acct, st, oi, ti))
    print('合计: %d 篇, 图片 %d 张' % (len(summary), tot_img))
    json.dump(summary, open(os.path.join(WORK, 'data', 'extract_summary.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
