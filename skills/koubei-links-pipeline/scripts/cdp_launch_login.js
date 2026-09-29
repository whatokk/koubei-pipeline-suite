// 启动专用自动化 Chrome 窗口（独立 user-data-dir + CDP 端口），保持常驻供用户登录
const { spawn } = require('child_process');
const fs = require('fs');

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const UD = 'D:\\kbd_ud';
const PROFILE = 'Profile 3';
const PORT = '9333';
const LOG = 'D:\\项目\\汽车之家\\核对\\下载_20260910\\data\\login_launch.log';

function log(m) {
  const line = `[${new Date().toISOString().slice(11, 19)}] ${m}`;
  try { fs.appendFileSync(LOG, line + '\n', 'utf-8'); } catch (e) {}
  console.log(line);
}

log(`launch ud=${UD} profile=${PROFILE} port=${PORT}`);

const child = spawn(CHROME, [
  `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${UD}`,
  `--profile-directory=${PROFILE}`,
  '--no-first-run',
  '--no-default-browser-check',
  '--window-size=1200,900',
  '--new-window',
  'https://www.dongchedi.com/',
], { stdio: ['ignore', 'ignore', 'pipe'], windowsHide: false });

child.stderr.on('data', d => {
  const s = d.toString().trim();
  if (/DevTools listening/i.test(s)) log('READY: ' + s.slice(0, 120));
});
child.on('exit', c => log(`chrome exited code=${c}`));
log(`spawned pid=${child.pid}, keeping alive`);

// 保持 Node 常驻，防止 Chrome 被连带回收
setInterval(() => {}, 60000);
