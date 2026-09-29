# -*- coding: utf-8 -*-
"""口碑合集批量补写脚本:把「追加句」按篇目标题插入篇末,并自动重算标题字数。

用法:
    1. 在本文件 APPEND 字典里,键 = 篇目标题(不含序号后的字数,如 "2-跨城通勤上班族"),值 = 追加句(40-70字,需衔接该篇最后一个小点主题,避免与已有内容重复)
    2. python append_pieces.py <markdown文件路径>
    3. 脚本自动:按 `## N-标题` 切分 → 命中键的篇在末尾插入追加句 → 重算每篇纯汉字数并更新标题中的 (XXX字)

注意:
    - 追加句必须自然衔接最后一个小点的内容(追加位置在篇末,相当于最后小点的延续),不要另起小点
    - 只补明显不足的篇(<370纯汉字),不追求齐平
    - Windows 下请用本脚本文件方式执行(勿用命令行内联中文,引号/编码会出问题)
"""
import re
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ===== 在此维护追加内容:篇目标题 -> 追加句 =====
APPEND = {
    # 示例:
    # '2-跨城通勤上班族': '买车前担心的充电问题也没成真,家充桩装好之后,晚上插上早上满,从没在外面排过队。',
}

def main():
    if len(sys.argv) < 2:
        print('用法: python append_pieces.py <md路径>')
        sys.exit(1)
    path = sys.argv[1]
    text = open(path, encoding='utf-8').read()

    parts = re.split(r'(?m)(?=^## )', text)
    hit = 0
    out = []
    for seg in parts:
        m = re.match(r'## (\d+)-(.*?)(?:\(\d+字\))?\n', seg)
        if m:
            key = m.group(1) + '-' + m.group(2)
            if key in APPEND:
                seg = seg.rstrip() + '\n\n' + APPEND[key] + '\n'
                hit += 1
        out.append(seg)
    text = ''.join(out)

    # 重算并更新标题字数(纯汉字,不含标点与【】标题)
    segments = re.split(r'(?m)(?=^## )', text)
    out2 = []
    for seg in segments:
        m = re.match(r'(## \d+-[^(]+)\(\d+字\)', seg)
        if m:
            body = seg.split('\n', 1)[1] if '\n' in seg else ''
            body = re.sub(r'【[^】]*】', '', body)
            body = re.sub(r'[\s\u3000，。、；：！？,.;:!?()（）"\'“”‘’\-—]', '', body)
            seg = m.group(1) + f'({len(body)}字)' + seg[len(m.group(0)):]
        out2.append(seg)

    open(path, 'w', encoding='utf-8').write(''.join(out2))
    print(f'完成:补写 {hit} 篇,标题字数已重算')

if __name__ == '__main__':
    main()
