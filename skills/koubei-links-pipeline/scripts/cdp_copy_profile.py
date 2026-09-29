import os, shutil, sys, time

SRC_UD = r'C:\Users\Administrator\AppData\Local\Google\Chrome\User Data'
DST_UD = r'D:\kbd_ud'
SRC_P3 = os.path.join(SRC_UD, 'Profile 3')
DST_P3 = os.path.join(DST_UD, 'Profile 3')

# 可再生的缓存类目录，不复制
SKIP_DIRS = {
    'cache', 'code cache', 'gpucache', 'service worker', 'crashpad',
    'dawncache', 'dawngraphitecache', 'graphitedawncache',
    'shareddictionarycache', 'component_crx_cache', 'optimizationhints',
    'extensions', 'extension state', 'extension rules', 'extension scripts',
    'sync extension settings', 'local extension settings',
    'managed extension settings', 'serverboundcertificates',
    'segmentation platform', 'persistentoriginconflicts',
}

def log(msg):
    print(msg, flush=True)
    with open(r'D:\项目\汽车之家\核对\下载_20260910\data\copy_p3.log', 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

def main():
    t0 = time.time()
    if os.path.exists(DST_UD):
        shutil.rmtree(DST_UD, ignore_errors=True)
    os.makedirs(DST_P3, exist_ok=True)

    # 1) 根级 Local State（ABE 主密钥所在，必须）
    ls = os.path.join(SRC_UD, 'Local State')
    shutil.copy2(ls, os.path.join(DST_UD, 'Local State'))
    log('[OK] Local State copied (%d bytes)' % os.path.getsize(ls))

    # 2) Profile 3 完整复制
    copied = 0
    failed = 0
    for root, dirs, files in os.walk(SRC_P3):
        # 跳过缓存目录
        rel = os.path.relpath(root, SRC_P3)
        parts = [] if rel == '.' else rel.split(os.sep)
        if any(p.lower() in SKIP_DIRS for p in parts):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS]
        target_root = os.path.join(DST_P3, rel) if rel != '.' else DST_P3
        os.makedirs(target_root, exist_ok=True)
        for name in files:
            s = os.path.join(root, name)
            d = os.path.join(target_root, name)
            try:
                shutil.copy2(s, d)
                copied += 1
            except Exception as e:
                failed += 1
                if failed <= 10:
                    log('[SKIP] %s :: %s' % (s, str(e)[:80]))

    log('[DONE] copied=%d failed=%d elapsed=%.1fs' % (copied, failed, time.time() - t0))
    log('[CHECK] Cookies: %s' % os.path.exists(os.path.join(DST_P3, 'Network', 'Cookies')))
    log('[CHECK] Local State: %s' % os.path.exists(os.path.join(DST_UD, 'Local State')))
    log('[CHECK] Preferences: %s' % os.path.exists(os.path.join(DST_P3, 'Preferences')))

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log('[FATAL] %r' % e)
        sys.exit(1)
