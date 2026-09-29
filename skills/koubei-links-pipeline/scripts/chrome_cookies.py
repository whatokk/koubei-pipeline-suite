# -*- coding: utf-8 -*-
"""从 Chrome 登录态直接提取懂车帝 Cookie（DPAPI + AES-GCM 解密），供 requests 复用。

为什么需要它：
  save_pages.py 依赖「无头 Chrome 复用 profile」，但在部分机器上会失效——
  profile 路径含中文、Cookie store 被判定损坏重建、Local State 映射错乱等，
  表现都是「30/30 全部成功、实际全是登录壳页」。
  本脚本绕开 Chrome 进程，直接解密 Cookies 数据库拿明文 Cookie，
  再用 requests 抓页面，成功率与可控性都更高。

解密原理（Chrome ≥ v80）：
  Local State.os_crypt.encrypted_key  → base64 → 去掉 "DPAPI" 前 5 字节
  → CryptUnprotectData 解密 → 得到 AES-256-GCM 主密钥
  Cookies.encrypted_value → b'v10'/'v20' + nonce(12) + 密文 + tag(16) → AESGCM 解密

用法：
    python chrome_cookies.py                 # 自动找已登录 profile，输出 cookie 数
    python chrome_cookies.py --json out.json # 导出为 JSON
    from chrome_cookies import get_dongchedi_cookies
    cookies = get_dongchedi_cookies()        # dict，可直接 requests.get(..., cookies=)

依赖：cryptography（pip install cryptography）；仅 Windows。
"""
import os
import sys
import json
import glob
import base64
import shutil
import sqlite3
import tempfile
import argparse
import subprocess

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    AESGCM = None

DOMAINS = ("dongchedi", "toutiao", "bytedance", "snssdk", "dcar")
SESSION_KEYS = {"sessionid", "sessionid_ss", "sid_guard", "sid_tt", "uid_tt",
                "odin_tt", "passport_auth_status", "ssid_ucp_v1", "d_ticket"}


# ---------- DPAPI ----------
def _dpapi_decrypt(blob: bytes) -> bytes:
    import ctypes
    import ctypes.wintypes as wt

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    in_buf = ctypes.create_string_buffer(blob, len(blob))
    indata = DATA_BLOB(len(blob), in_buf)
    outdata = DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(indata), None, None, None, None, 0, ctypes.byref(outdata))
    if not ok:
        raise RuntimeError("CryptUnprotectData 失败（需在本机当前 Windows 用户下运行）")
    try:
        return ctypes.string_at(outdata.pbData, outdata.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(outdata.pbData)


def _aes_key(user_data_dir: str) -> bytes:
    ls = os.path.join(user_data_dir, "Local State")
    with open(ls, encoding="utf-8") as f:
        b64 = json.load(f)["os_crypt"]["encrypted_key"]
    raw = base64.b64decode(b64)
    if raw[:5] != b"DPAPI":
        raise RuntimeError("未知的 encrypted_key 格式")
    return _dpapi_decrypt(raw[5:])


def _decrypt_value(enc: bytes, key: bytes):
    """按 Chrome 版本前缀选解密方式，任一路径失败都返回空而不抛异常。

    v20: b'v20' + nonce(12) + AES-256-GCM 密文(含 16 字节 tag)  ← Chrome ≥ 80
    v10: b'v10' + DPAPI(密文)                                    ← Chrome 老版本
    无前缀: 直接 DPAPI(整块)
    """
    if not enc:
        return ""
    prefix = enc[:3]
    if prefix == b"v20":
        if AESGCM is None:
            return ""
        try:
            return AESGCM(key).decrypt(enc[3:15], enc[15:], None).decode("utf-8", "ignore")
        except Exception:
            # 主密钥可能取自另一份 Local State，退回 DPAPI 再试
            try:
                return _dpapi_decrypt(enc[3:]).decode("utf-8", "ignore")
            except Exception:
                return ""
    if prefix == b"v10":
        try:
            return _dpapi_decrypt(enc[3:]).decode("utf-8", "ignore")
        except Exception:
            return ""
    try:  # 无前缀老格式
        return _dpapi_decrypt(enc).decode("utf-8", "ignore")
    except Exception:
        return ""


# ---------- profile 定位 ----------
def _user_data_dirs():
    local = os.environ.get("LOCALAPPDATA", "")
    cands = []
    if local:
        cands.append(os.path.join(local, "Google", "Chrome", "User Data"))
    cands.append(os.path.join(os.path.expanduser("~"), "AppData", "Local",
                              "Google", "Chrome", "User Data"))
    return [c for c in cands if os.path.isdir(c)]


def _read_db(db_path):
    tmp = os.path.join(tempfile.gettempdir(), "ck_%d.db" % os.getpid())
    try:
        shutil.copyfile(db_path, tmp)
    except Exception:
        return None  # 被 Chrome 锁住
    try:
        con = sqlite3.connect(tmp)
        cur = con.cursor()
        where = " OR ".join(["host_key LIKE ?"] * len(DOMAINS))
        cur.execute(
            "SELECT host_key, name, value, encrypted_value, path FROM cookies WHERE " + where,
            ["%" + d + "%" for d in DOMAINS])
        rows = cur.fetchall()
        con.close()
        return rows
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


def get_dongchedi_cookies(profile=None, user_data_dir=None, verbose=True):
    """返回 {name: value} 的懂车帝 cookie；找不到登录态返回空 dict。"""
    bases = [user_data_dir] if user_data_dir else _user_data_dirs()
    best = {}
    for ud in bases:
        if not ud or not os.path.isdir(ud):
            continue
        try:
            key = _aes_key(ud)
        except Exception as e:
            if verbose:
                print(f"[!] 读取主密钥失败 {ud}: {str(e)[:60]}")
            continue
        # 优先扫描指定 profile，其次全部
        if profile:
            dbs = [(profile, os.path.join(ud, profile, "Network", "Cookies"))]
        else:
            dbs = []
            for p in glob.glob(os.path.join(ud, "*", "Network", "Cookies")):
                dbs.append((os.path.basename(os.path.dirname(os.path.dirname(p))), p))
        for prof, db in dbs:
            if not os.path.exists(db):
                continue
            rows = _read_db(db)
            if rows is None:
                if verbose:
                    print(f"[!] {prof} 被占用（Chrome 运行中），跳过")
                continue
            jar = {}
            for host, name, val, enc, _path in rows:
                v = val if val else _decrypt_value(enc, key)
                if v:
                    jar[name] = v
            has_sess = bool({k.lower() for k in jar} & SESSION_KEYS)
            if verbose:
                mark = "已登录 ✅" if has_sess else "仅访问痕迹"
                print(f"    [{prof}] {mark}  cookie {len(jar)} 个")
            if has_sess and len(jar) > len(best):
                best = jar
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", help="指定 profile 目录名，如 'Profile 2'")
    ap.add_argument("--user-data-dir", help="指定 Chrome User Data 目录")
    ap.add_argument("--json", help="导出 cookie 到 JSON 文件")
    args = ap.parse_args()

    print("扫描 Chrome 登录态 ...")
    jar = get_dongchedi_cookies(args.profile, args.user_data_dir)
    if not jar:
        print("\n未找到懂车帝登录态。请先在 Chrome 普通窗口登录 https://m.dongchedi.com")
        sys.exit(1)
    sess = sorted({k for k in jar if k.lower() in SESSION_KEYS})
    print(f"\n拿到 {len(jar)} 个 cookie，会话凭据: {sess}")
    if args.json:
        json.dump(jar, open(args.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print("已导出:", args.json)


if __name__ == "__main__":
    main()
