# -*- coding: utf-8 -*-
"""扫描本机 Chrome/Edge 所有 profile，检查懂车帝登录态在哪个 profile 里。

用途：跑 save_pages.py 前先自检，避免"以为登录了"结果整批抓到登录壳页。

坑位记录（重要）：
  1. Chrome 新版 Cookies 在 <User Data>/<Profile>/Network/Cookies，
     不是旧路径 <User Data>/<Profile>/Cookies —— 用旧路径扫会得到假阴性。
  2. Chrome 浏览器同步账号（右上角头像/Google 账号）≠ 懂车帝已登录。
     懂车帝是独立账号体系，必须单独在 m.dongchedi.com 用手机号登录。
  3. "打开过登录页"会留下 passport_csrf_token / ttwid / tt_webid，
     这几个不是登录态；真正的会话凭据是 sessionid / uid_tt / sid_guard /
     odin_tt / passport_auth_status / d_ticket 等。
  4. 无痕窗口登录不落盘，必须用普通窗口。

用法：python check_login.py
输出：每个 profile 的懂车帝 cookie 明细 + 结论（哪个 profile 可用）
"""
import os
import sys
import glob
import shutil
import sqlite3
import tempfile

# 真正的登录态凭据关键字（命中任一即视为已登录）
SESSION_KEYS = {
    "sessionid", "sessionid_ss", "sid_guard", "sid_tt", "uid_tt",
    "odin_tt", "passport_auth_status", "d_ticket", "login_shared",
    "n_mh", "passport_user", "sid_uc", "ssid_ucp_v1", "ttwid_user",
}
# 只是"访问过"的痕迹，不算登录
VISIT_ONLY = {"passport_csrf_token", "passport_csrf_token_default", "ttwid", "tt_webid"}
DOMAIN_LIKE = ("dongchedi", "toutiao", "bytedance", "snssdk", "dcar")


def chrome_bases():
    home = os.path.expanduser("~")
    cands = []
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        cands.append(os.path.join(local, "Google", "Chrome", "User Data"))
    cands.append(os.path.join(home, "AppData", "Local", "Google", "Chrome", "User Data"))
    cands.append(os.path.join(home, "AppData", "Local", "Microsoft", "Edge", "User Data"))
    return [c for c in cands if os.path.isdir(c)]


def cookie_dbs(base):
    """新路径优先（<Profile>/Network/Cookies），兼容旧路径（<Profile>/Cookies）"""
    out = []
    for p in glob.glob(os.path.join(base, "*", "Network", "Cookies")):
        out.append((os.path.basename(os.path.dirname(os.path.dirname(p))), p))
    for p in glob.glob(os.path.join(base, "*", "Cookies")):
        out.append((os.path.basename(os.path.dirname(p)), p))
    return out


def read_cookies(db_path):
    """Cookies 可能被 Chrome 锁住，先复制到临时文件再读"""
    tmp = os.path.join(tempfile.gettempdir(), "ck_probe_%d.db" % os.getpid())
    try:
        shutil.copyfile(db_path, tmp)
    except Exception:
        return None  # 被占用 => Chrome 正在运行该 profile
    try:
        con = sqlite3.connect(tmp)
        cur = con.cursor()
        where = " OR ".join(["host_key LIKE ?"] * len(DOMAIN_LIKE))
        cur.execute(
            "SELECT host_key, name FROM cookies WHERE " + where,
            ["%%%s%%" % d for d in DOMAIN_LIKE],
        )
        rows = cur.fetchall()
        con.close()
        return rows
    except Exception as e:
        return ("ERR", str(e))
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


def profile_display_names(base):
    """读 Local State 拿 profile 显示名，方便用户对照"""
    import json
    try:
        d = json.load(open(os.path.join(base, "Local State"), encoding="utf-8"))
        return {k: (v.get("name"), v.get("user_name"))
                for k, v in d.get("profile", {}).get("info_cache", {}).items()}
    except Exception:
        return {}


def main():
    bases = chrome_bases()
    if not bases:
        print("未找到 Chrome/Edge 用户数据目录")
        return
    for base in bases:
        print("=" * 62)
        print("User Data:", base)
        names = profile_display_names(base)
        hits = []
        for prof, db in sorted(cookie_dbs(base)):
            rows = read_cookies(db)
            disp = names.get(prof, ("", ""))[0] or ""
            if rows is None:
                print(f"  [{prof}] {disp:<12} 被占用（Chrome 正在运行，无法读取）")
                continue
            if isinstance(rows, tuple):
                print(f"  [{prof}] {disp:<12} 读取失败: {rows[1][:50]}")
                continue
            if not rows:
                continue
            sess = sorted({n for _, n in rows if n.lower() in SESSION_KEYS})
            visit = sorted({n for _, n in rows if n.lower() in VISIT_ONLY})
            other = sorted({n for _, n in rows
                            if n.lower() not in SESSION_KEYS and n.lower() not in VISIT_ONLY})
            flag = "已登录 ✅" if sess else ("仅访问过登录页 ❌" if visit or other else "无")
            print(f"  [{prof}] {disp:<12} {flag}")
            if sess:
                print(f"        会话凭据: {sess}")
            if visit:
                print(f"        访问痕迹: {visit}")
            if other:
                print(f"        其他: {other[:8]}")
            if sess:
                hits.append(prof)
        print("-" * 62)
        if hits:
            print(f"  >> 可用 profile: {hits}")
            print(f"  >> 下载命令: set KB_CHROME_PROFILE_NAME={hits[0]} 后运行 save_pages.py")
        else:
            print("  >> 未发现任何懂车帝登录态")
            print("  >> 请先在 Chrome 普通窗口打开 https://m.dongchedi.com 用手机号登录，")
            print("     确认能打开一条 /koubei/ 链接看到正文后，再完全退出 Chrome 重跑本脚本")


if __name__ == "__main__":
    main()
