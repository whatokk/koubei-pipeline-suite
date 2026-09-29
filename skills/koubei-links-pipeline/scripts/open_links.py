# -*- coding: utf-8 -*-
"""分批用 Chrome 打开链接，每窗口 N 个（默认 10）。
输入：data/rows.json 数组 [{seq, acct, car, url}]，或 links.txt（每行一个 URL）。
用法：python open_links.py [每批数量] [rows.json 路径]
"""
import sys, os, json, subprocess

CHROME = r"C:\Users\Administrator\AppData\Local\Google\Chrome\Application\chrome.exe"
BATCH = int(sys.argv[1]) if len(sys.argv) > 1 else 10
DATA = sys.argv[2] if len(sys.argv) > 2 else os.path.join("data", "rows.json")

# 探测 Chrome 路径
if not os.path.exists(CHROME):
    for cand in [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                 r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]:
        if os.path.exists(cand):
            CHROME = cand
            break

def load_urls():
    if os.path.exists(DATA):
        rows = json.load(open(DATA, encoding="utf-8"))
        return [r["url"] for r in rows]
    # 回退：links.txt
    if os.path.exists("links.txt"):
        return [ln.strip() for ln in open("links.txt", encoding="utf-8") if ln.strip()]
    print("找不到输入：", DATA, "或 links.txt")
    sys.exit(1)

def main():
    urls = load_urls()
    print(f"共 {len(urls)} 个链接，每窗口 {BATCH} 个")
    for i in range(0, len(urls), BATCH):
        batch = urls[i:i + BATCH]
        cmd = [CHROME, "--new-window"] + batch
        print(f"[批次 {i // BATCH + 1}] 打开 {len(batch)} 个标签")
        subprocess.Popen(cmd)
    print("完成")

if __name__ == "__main__":
    main()
