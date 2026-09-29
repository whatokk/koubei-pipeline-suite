# -*- coding: utf-8 -*-
"""口碑合集结构/字数/小点分布校验脚本。

用法:
    python check_koubei.py <markdown文件路径> [--min 370] [--max 470]

输出:
    1. 每车型分节与篇数
    2. 每篇纯汉字数(不含标点与【小点】标题)、平均值、中位数、越界篇
    3. 小点数量分布(应为 2点/3点为主,不应出现5点以上)
    4. 同篇重复小点标题(如两个【最满意】)
    5. 标题字数标注与实际是否一致

编码:Windows 下需以 UTF-8 输出,脚本已处理。
"""
import re
import sys
import io
import statistics
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def hanzi(s):
    s = re.sub(r'【[^】]*】', '', s)
    s = re.sub(r'[\s\u3000，。、；：！？,.;:!?()（）"\'“”‘’\-—]', '', s)
    return len(s)

def main():
    if len(sys.argv) < 2:
        print('用法: python check_koubei.py <md路径> [--min 370] [--max 470]')
        sys.exit(1)
    path = sys.argv[1]
    min_w = 370
    max_w = 470
    if '--min' in sys.argv:
        min_w = int(sys.argv[sys.argv.index('--min') + 1])
    if '--max' in sys.argv:
        max_w = int(sys.argv[sys.argv.index('--max') + 1])

    text = open(path, encoding='utf-8').read()

    # 1. 车型分节(兼容单车型文件:只有一个 # 标题时直接统计全部 ## 篇目)
    sections = re.split(r'\n(?=# )', text)
    h1_sections = [s for s in sections if s.startswith('# ')]
    print('== 车型分节 ==')
    total = 0
    if len(h1_sections) <= 1:
        total = len(re.findall(r'\n## \d+', text))
        print(f'  (单车型文件) 共{total}篇')
    else:
        for sec in sections[1:]:
            car = sec.split('\n')[0]
            n = len(re.findall(r'\n## \d+', sec))
            total += n
            print(f'  {car} -> {n}篇')
        print(f'  总篇数: {total}')

    # 2. 每篇字数
    parts = re.split(r'\n(?=## )', text)[1:]
    print(f'\n== 字数(纯汉字, 标准 {min_w}-{max_w}) ==')
    sizes = []
    issues = []
    for p in parts:
        lines = p.split('\n')
        title = lines[0].strip()
        body = hanzi('\n'.join(lines[1:]))
        sizes.append(body)
        flag = ' <<太短' if body < min_w else (' >>太长' if body > max_w else '')
        if flag:
            issues.append((body, title, flag))
        # 标题字数标注核对
        m = re.match(r'## \d+-[^(]+\((\d+)字\)', title)
        if m and int(m.group(1)) != body:
            print(f'  [字数标注不符] {title}: 标{m.group(1)}实际{body}')
    sizes.sort()
    print(f'  最短{sizes[0]} 最长{sizes[-1]} 中位{sizes[len(sizes)//2]} 平均{round(statistics.mean(sizes))}')
    if issues:
        print('  越界篇:')
        for body, title, flag in sorted(issues):
            print(f'    {body:4d} {title}{flag}')
    else:
        print('  全部达标')

    # 3. 小点数量分布(2026-08-05 规则更新:每篇1~8个 + 纯正文段混排)
    cnts = [len(re.findall(r'【([^】]+)】', p)) for p in parts]
    dist = dict(sorted(Counter(cnts).items()))
    print(f'\n== 小点数量分布(1~8个/篇) == {dist}')
    over = [p for p in parts if len(re.findall(r'【([^】]+)】', p)) > 8]
    if over:
        print('  !! 存在单篇8个以上小点,违反「每篇1~8个」规则')
        for p in over:
            print('    ', p.split('\n')[0])
    # 纯正文段计数(无【】标题的段落,开头购车背景句不计)
    plain = []
    for p in parts:
        paras = [pp.strip() for pp in p.split('\n\n') if pp.strip() and not pp.strip().startswith('##')]
        n_plain = sum(1 for pp in paras if not pp.startswith('【') and len(pp) > 20)
        plain.append(n_plain)
    pdist = dict(sorted(Counter(plain).items()))
    print(f'== 纯正文段数量分布(0~2段/篇) == {pdist}')
    for p, n in zip(parts, plain):
        if n > 2:
            print(f'  !! {p.split(chr(10))[0]}: 纯正文段{n}段(应≤2)')

    # 4. 重复小点标题
    print('\n== 重复小点标题检查 ==')
    dup = False
    for p in parts:
        pts = re.findall(r'【([^】]+)】', p)
        seen = Counter(pts)
        for k, v in seen.items():
            if v > 1:
                dup = True
                print(f'  !! {p.split(chr(10))[0]}: 【{k}】出现{v}次')
    if not dup:
        print('  无重复')

if __name__ == '__main__':
    main()
