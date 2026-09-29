# -*- coding: utf-8 -*-
"""用 Chrome 无头模式复用登录态，批量保存口碑页为 HTML 快照。
前置：先完全关闭 Chrome（Stop-Process -Name chrome -Force），否则 profile 锁死。
输入：data/rows.json [{seq, acct, car, url}]
输出：<OUT_DIR>/<seq:02d>_<acct>_<car>.html
用法：python save_pages.py [OUT_DIR] [rows.json 路径]
"""
import sys, os, re, json, time, subprocess

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
# 按当前用户探测 profile 目录，不硬编码用户名
# 坑：profile 路径含中文(非 ASCII)时 Chrome 返回 21 且输出 0 字节 ——
#     需先把 User Data 复制到纯 ASCII 路径，再用环境变量 KB_CHROME_PROFILE 指定
USER_DATA_DIR = os.environ.get("KB_CHROME_PROFILE") or os.path.join(
    os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\User Data")
# 默认 Default；若登录态在其他 profile（如 "Profile 2"），用环境变量指定
PROFILE = os.environ.get("KB_CHROME_PROFILE_NAME", "Default")
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "html_snapshots"
DATA = sys.argv[2] if len(sys.argv) > 2 else os.path.join("data", "rows.json")

# 探测 Chrome 路径
if not os.path.exists(CHROME):
    for cand in [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                 r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]:
        if os.path.exists(cand):
            CHROME = cand
            break

def sanitize(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()

def main():
    rows = json.load(open(DATA, encoding="utf-8"))
    os.makedirs(OUT_DIR, exist_ok=True)
    total = len(rows)
    ok = 0
    fail = []
    for r in rows:
        seq = int(r["seq"])
        acct = r.get("acct", "")
        car = r.get("car", "")
        url = r["url"]
        fname = f"{seq:02d}_{sanitize(acct)}_{sanitize(car)}.html"
        fpath = os.path.join(OUT_DIR, fname)
        cmd = [
            CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions",
            "--user-agent=" + UA,
            "--virtual-time-budget=20000",
            "--user-data-dir=" + USER_DATA_DIR,
            "--profile-directory=" + PROFILE,
            "--dump-dom", url,
        ]
        print(f"[{seq}/{total}] {fname} ...", flush=True)
        try:
            # 必须用 subprocess 捕获字节流，Git Bash 重定向会得 0 字节
            result = subprocess.run(cmd, capture_output=True, timeout=90)
            out = result.stdout or b""
            # 坑：懂车帝登录壳页约 4.8KB，单纯用 >2000 判定会把壳页当成功。
            #     必须同时校验体积与登录墙特征，否则整批"成功"却全是空壳。
            head = out[:4000].decode("utf-8", "ignore")
            is_login_wall = ("统一登录" in head) or ("__NEXT_DATA__" not in out.decode("utf-8", "ignore"))
            if len(out) > 20000 and not is_login_wall:
                with open(fpath, "wb") as f:
                    f.write(out)
                ok += 1
                print(f"      OK ({len(out)} bytes)", flush=True)
            elif is_login_wall:
                fail.append((seq, fname, f"登录墙/无数据 ({len(out)} bytes)"))
                print(f"      FAIL 登录墙，未复用登录态", flush=True)
            else:
                fail.append((seq, fname, f"输出过短 ({len(out)} bytes)"))
                print(f"      FAIL 输出过短", flush=True)
        except subprocess.TimeoutExpired:
            fail.append((seq, fname, "超时"))
            print("      FAIL 超时", flush=True)
        except Exception as e:
            fail.append((seq, fname, str(e)))
            print(f"      FAIL {e}", flush=True)
        time.sleep(1)
    print(f"\n完成: 成功 {ok}/{total}")
    for seq, fname, why in fail:
        print(f"  {seq} {fname} -> {why}")

if __name__ == "__main__":
    main()
