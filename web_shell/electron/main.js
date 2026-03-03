const { app, BrowserWindow, ipcMain, session } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

const BACKEND_URL = process.env.SMX_BACKEND_URL || 'http://127.0.0.1:5001';
const PYTHON = process.env.SMX_PYTHON || 'python';
let backendProc = null;
let mainWindow = null;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitBackend(url, attempts = 60) {
  for (let i = 0; i < attempts; i += 1) {
    try {
      const res = await fetch(`${url}/api/health`);
      if (res.ok) return true;
    } catch (_) {}
    await sleep(300);
  }
  return false;
}

async function ensureBackend() {
  if (await waitBackend(BACKEND_URL, 2)) return;

  const repoRoot = path.resolve(__dirname, '..', '..');
  backendProc = spawn(PYTHON, ['-m', 'smart_explorer.backend.server'], {
    cwd: repoRoot,
    env: process.env,
    stdio: 'inherit',
  });

  const up = await waitBackend(BACKEND_URL, 80);
  if (!up) {
    throw new Error('Backend did not start in time.');
  }
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: '#020617',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js'),
    },
  });
  try {
    win.webContents.session.clearCache().catch(() => {});
  } catch (_) {}
  const cacheBust = `v=${Date.now()}`;
  win.loadURL(`${BACKEND_URL}/web/index.html?${cacheBust}`);
  mainWindow = win;
}

function extractSharePointCookies(allCookies, host) {
  const tenantHost = String(host || '').toLowerCase();
  const out = {};
  for (const c of allCookies || []) {
    const name = String(c?.name || '').trim();
    const value = String(c?.value || '');
    const domain = String(c?.domain || '').replace(/^\./, '').toLowerCase();
    if (!name || !value) continue;
    const hostMatch = domain === tenantHost || tenantHost.endsWith(`.${domain}`);
    const commonMatch =
      domain.endsWith('sharepoint.com') ||
      domain.endsWith('microsoftonline.com') ||
      domain.endsWith('office.com') ||
      domain.endsWith('live.com');
    if (hostMatch || commonMatch) out[name] = value;
  }
  return out;
}

function hasAuthCookies(cookies) {
  const keys = Object.keys(cookies || {}).map((k) => k.toLowerCase());
  if (keys.includes('fedauth') && keys.includes('rtfa')) return true;
  return keys.includes('spoidcrl') || keys.includes('spoidcrlid');
}

async function postJson(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${txt || res.statusText}`);
  }
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) return res.json();
  return {};
}

async function persistSharePointAuth(baseUrl, cookies) {
  await postJson(`${BACKEND_URL}/api/settings`, { sp_base_url: baseUrl });
  await postJson(`${BACKEND_URL}/api/sp/cookies`, { base_url: baseUrl, cookies });
}

async function runEmbeddedSharePointAuth(baseUrl) {
  const parsed = new URL(baseUrl);
  if (!parsed.protocol || !parsed.host) throw new Error('Invalid SharePoint URL.');

  const authSession = session.fromPartition('persist:smx-sp-auth');
  const authWin = new BrowserWindow({
    width: 1200,
    height: 860,
    parent: mainWindow || undefined,
    modal: false,
    title: 'SharePoint Sign In',
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      session: authSession,
    },
  });

  authWin.webContents.setWindowOpenHandler(({ url }) => {
    authWin.loadURL(url);
    return { action: 'deny' };
  });

  let done = false;
  const finish = (ok, payload) => {
    if (done) return null;
    done = true;
    try {
      if (!authWin.isDestroyed()) authWin.close();
    } catch (_) {}
    return { ok, ...payload };
  };

  const tryCapture = async () => {
    if (done) return null;
    const all = await authSession.cookies.get({});
    const jar = extractSharePointCookies(all, parsed.host);
    if (!hasAuthCookies(jar)) return null;
    await persistSharePointAuth(baseUrl, jar);
    return finish(true, {
      message: `Captured ${Object.keys(jar).length} cookie(s) from embedded SharePoint sign-in.`,
      count: Object.keys(jar).length,
    });
  };

  return new Promise((resolve) => {
    const interval = setInterval(async () => {
      try {
        const result = await tryCapture();
        if (result) {
          clearInterval(interval);
          resolve(result);
        }
      } catch (err) {
        clearInterval(interval);
        resolve(finish(false, { message: String(err) }));
      }
    }, 1500);

    authWin.on('closed', async () => {
      clearInterval(interval);
      if (done) return;
      try {
        const result = await tryCapture();
        resolve(result || finish(false, { message: 'Sign-in window closed before auth cookies were detected.' }));
      } catch (err) {
        resolve(finish(false, { message: String(err) }));
      }
    });

    authWin.loadURL(baseUrl).catch((err) => {
      clearInterval(interval);
      resolve(finish(false, { message: `Failed to open URL: ${String(err)}` }));
    });
  });
}

ipcMain.handle('smx:sp-auth-flow', async (_evt, payload) => {
  const baseUrl = String(payload?.baseUrl || '').trim();
  if (!baseUrl) return { ok: false, message: 'SharePoint URL is required.' };
  try {
    return await runEmbeddedSharePointAuth(baseUrl);
  } catch (err) {
    return { ok: false, message: String(err) };
  }
});

app.whenReady().then(async () => {
  try {
    await ensureBackend();
    createWindow();
  } catch (err) {
    console.error(err);
    app.quit();
  }

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});

app.on('quit', () => {
  if (backendProc && !backendProc.killed) backendProc.kill();
});
