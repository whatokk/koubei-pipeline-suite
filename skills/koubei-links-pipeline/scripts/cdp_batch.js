// 批抓：复用或启动有头 Chrome(CDP) -> 逐条抓 koubei __NEXT_DATA__ -> 落盘 JSON
// 用法: node cdp_batch.js <port> <udDir> <profileDir> <limit|all> [startIndex]
const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = parseInt(process.argv[2] || '9333', 10);
const UD = process.argv[3] || 'D:\\kbd_ud';
const PROFILE = process.argv[4] || 'Profile 3';
const LIMIT = process.argv[5] || 'all';
const START = parseInt(process.argv[6] || '0', 10);

// 工作目录可覆盖：env KB_WORK=<项目工作目录>（应含 data/rows.json 与 html_snapshots/）
// 未设置时回退到当前工作目录（cwd），避免硬编码其他项目路径
const WORK = process.env.KB_WORK || process.cwd();
const OUTDIR = path.join(WORK, 'html_snapshots');
const LOG = path.join(WORK, 'data', 'cdp_batch.log');

const UA_MOBILE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1';

function log(m) {
  const line = `[${new Date().toISOString().slice(11, 19)}] ${m}`;
  console.log(line);
  try { fs.appendFileSync(LOG, line + '\n', 'utf-8'); } catch (e) {}
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

function httpJson(p, method) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: '127.0.0.1', port: PORT, path: p, method: method || 'GET' }, res => {
      let d = ''; res.on('data', c => d += c);
      res.on('end', () => { try { resolve(JSON.parse(d)); } catch (e) { reject(new Error('badjson')); } });
    });
    req.on('error', reject);
    req.setTimeout(8000, () => req.destroy(new Error('http timeout')));
    req.end();
  });
}
function makeSender(ws) {
  let id = 0; const pending = new Map();
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const { resolve, reject } = pending.get(m.id); pending.delete(m.id);
      if (m.error) reject(new Error(JSON.stringify(m.error).slice(0, 150))); else resolve(m.result);
    }
  };
  return (method, params) => new Promise((resolve, reject) => {
    const myId = ++id; pending.set(myId, { resolve, reject });
    ws.send(JSON.stringify({ id: myId, method, params: params || {} }));
    setTimeout(() => { if (pending.has(myId)) { pending.delete(myId); reject(new Error('timeout ' + method)); } }, 60000);
  });
}

(async () => {
  fs.mkdirSync(OUTDIR, { recursive: true });
  const rows = JSON.parse(fs.readFileSync(path.join(WORK, 'data', 'rows.json'), 'utf-8'));
  let list = rows;
  if (LIMIT !== 'all') list = rows.slice(START, START + parseInt(LIMIT, 10));
  log(`rows.total=${rows.length} processing=${list.length} start=${START}`);

  // 1) 复用现有实例，否则新起一个
  let child = null, reused = false;
  try { await httpJson('/json/version'); reused = true; log('reuse existing chrome on port ' + PORT); } catch (e) {}
  if (!reused) {
    child = spawn(CHROME, [
      `--remote-debugging-port=${PORT}`, `--user-data-dir=${UD}`, `--profile-directory=${PROFILE}`,
      '--no-first-run', '--no-default-browser-check', '--window-size=1280,900', 'about:blank',
    ], { stdio: ['ignore', 'ignore', 'pipe'], windowsHide: false });
    child.stderr.on('data', d => { const s = d.toString(); if (/DevTools listening/i.test(s)) log('CHROME ready'); });
    for (let i = 0; i < 30; i++) { try { await httpJson('/json/version'); break; } catch (e) { await sleep(1000); } }
    log('spawned new chrome');
  }

  // 2) 连接页面 target
  const targets = await httpJson('/json/list');
  const page = targets.find(t => t.type === 'page');
  if (!page) { log('FATAL no page target'); if (child) child.kill(); process.exit(1); }
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('ws fail')); });
  const send = makeSender(ws);
  await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
  await send('Network.setUserAgentOverride', { userAgent: UA_MOBILE });
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 3, mobile: true });
  log('ws connected, mobile UA set');

  // 3) 先探测登录态
  await send('Page.navigate', { url: 'https://m.dongchedi.com/' }).catch(() => {});
  await sleep(3500);
  try {
    const ck = await send('Network.getCookies', { urls: ['https://m.dongchedi.com/', 'https://www.dongchedi.com/'] });
    const names = (ck.cookies || []).map(c => c.name);
    const hasSession = names.some(n => /sessionid|sid_tt|uid_tt|passport/i.test(n));
    const r = await send('Runtime.evaluate', { expression: `(()=>{const e=document.getElementById('__NEXT_DATA__');if(!e)return'';const d=JSON.parse(e.textContent);return String(d.props&&d.props.pageProps&&d.props.pageProps.isLoggedIn)})()`, returnByValue: true }).catch(() => null);
    log(`AUTH cookies=${names.length} hasSessionCookie=${hasSession} isLoggedIn=${r && r.result && r.result.value}`);
  } catch (e) { log('AUTH probe err ' + e.message); }

  let ok = 0, login = 0, fail = 0;
  for (let i = 0; i < list.length; i++) {
    const r = list[i];
    const outFile = path.join(OUTDIR, `kb_${r.seq}.json`);
    process.stdout.write(`[${i + 1}/${list.length}] ${r.seq} ${r.car} ... `);
    try {
      await send('Page.navigate', { url: r.url }).catch(() => {});
      let nd = null;
      for (let t = 0; t < 25; t++) {
        await sleep(1000);
        const res = await send('Runtime.evaluate', { expression: `(()=>{const e=document.getElementById('__NEXT_DATA__');return e?e.textContent:''})()`, returnByValue: true }).catch(() => null);
        const v = res && res.result && res.result.value;
        if (v && v.length > 1000) {
          try { const d = JSON.parse(v); if (d.page && /koubei|detail/i.test(d.page)) { nd = v; break; } } catch (e) {}
          if (!nd) nd = v; // 兜底：结构不符也先留
          if (nd && t > 12) break;
        }
      }
      if (nd) {
        const d = JSON.parse(nd);
        fs.writeFileSync(outFile, nd, 'utf-8');
        const pp = (d.props && d.props.pageProps) || {};
        ok++;
        log(`OK   seq=${r.seq} page=${d.page} bytes=${nd.length} isLoggedIn=${pp.isLoggedIn}`);
        console.log(`OK page=${d.page} ${nd.length}B`);
      } else {
        const res = await send('Runtime.evaluate', { expression: 'document.documentElement.outerHTML', returnByValue: true }).catch(() => null);
        const html = (res && res.result && res.result.value) || '';
        const isLogin = /统一登录|passport_csrf|请登录|立即登录|扫码登录/.test(html.slice(0, 12000));
        fs.writeFileSync(path.join(OUTDIR, `kb_${r.seq}.FAIL.html`), html, 'utf-8');
        if (isLogin) { login++; log(`LOGIN seq=${r.seq} html=${html.length}`); console.log('LOGIN'); }
        else { fail++; log(`MISS  seq=${r.seq} html=${html.length}`); console.log('MISS'); }
      }
    } catch (e) { fail++; log(`ERR   seq=${r.seq} ${e.message}`); console.log('ERR'); }
  }
  log(`SUMMARY ok=${ok} login=${login} fail=${fail}`);
  console.log(`SUMMARY ok=${ok} login=${login} fail=${fail}`);

  try { ws.close(); } catch (e) {}
  if (child) { try { child.kill(); } catch (e) {} }
  await sleep(1200);
  process.exit(0);
})().catch(e => { log('FATAL ' + e.message); process.exit(1); });
