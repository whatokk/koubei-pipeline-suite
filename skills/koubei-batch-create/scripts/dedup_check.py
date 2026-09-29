#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
口碑交叉去重校验脚本（跨篇 n-gram 重复检测 + 字数/小点统计）

用途：一批同车型口碑写完后，检出「篇与篇之间」的重复片段，定位雷同来源。
用法：
    python dedup_check.py <口碑目录>            # 默认 10 字级
    python dedup_check.py <口碑目录> 12         # 指定 n（字级）

判读：
    - 有重叠篇对 = 0   → 达标
    - 出现重叠 → 按片段原文回到两篇里，把那一处换措辞（同事实换说法，不要删信息）
    - 高频雷同来源就三类：①小点开头套话 ②数字套话 ③提车句

同事实换措辞示例（这几组是实测有效的）：
    车宽   ：「车宽1995mm」/「车身一米九九宽」/「一米九九的车宽」/「宽一米九九」
    CLTC   ：「CLTC标675公里」/「标称675公里」/「官方675公里」/「表上写着675公里」/「标的675公里」
    方盒子 ：「方盒子加封闭前脸」/「方方正正的封闭前脸」/「四方的前脸」/「方正的车身配封闭前脸」
    高阶智驾：「天神之眼B我没选装」/「加钱的那套高阶智驾我没要」/「带激光那个版本得加钱」
    购置税 ：「减半的购置税交了八千八」/「税减半，购置税八千八」/「购置税减半后交了八千八」/「税按减半算交了八千八」
    提车句 ：「到济宁润凯定了这台…，六月底提车」/「7月底把车开回来的」/「5月底入手…」/「6月初在佛山买的…」
"""
import re
import sys
import glob
import os
import itertools


def han_len(t):
    return len(re.findall(r'[\u4e00-\u9fff]', t))


def body_of(path):
    s = open(path, encoding="utf-8").read()
    # 正文 = 第二个 --- 之后，且去掉 markdown 标题行
    parts = s.split("---\n")
    body = parts[-1] if len(parts) > 1 else s
    return body.split("\n", 1)[1] if "\n" in body else body


def grams(text, n):
    t = re.sub(r'[^\u4e00-\u9fff]', '', text)
    return {t[i:i + n] for i in range(max(0, len(t) - n))}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    root = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    files = sorted(glob.glob(os.path.join(root, "*.md")))
    files = [f for f in files if os.path.basename(f).startswith(tuple("0123456789"))] or files
    if not files:
        print("未找到 .md 文件：", root)
        return 1

    docs, G = {}, {}
    print("=== 单篇体检 ===")
    for p in files:
        b = body_of(p)
        docs[p] = b
        G[p] = grams(b, n)
        npoints = len(re.findall(r'【[^】]+】', b))
        flag = "" if 380 <= han_len(b) <= 1100 else "  <-- 字数异常"
        print(f"  {os.path.basename(p)}: {han_len(b)} 纯汉字 | 小点 {npoints} 个{flag}")

    print(f"\n=== 两两 {n} 字级交叉重复 ===")
    bad = 0
    for a, b in itertools.combinations(files, 2):
        ov = G[a] & G[b]
        if ov:
            bad += 1
            print(f"  {os.path.basename(a)} × {os.path.basename(b)}: {len(ov)} 处")
            for x in sorted(ov)[:8]:
                print(f"      {x}")
    total = len(files) * (len(files) - 1) // 2
    print(f"\n结论：有重叠篇对 {bad}/{total} —— " + ("达标" if bad == 0 else "需按片段换措辞后复检"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
