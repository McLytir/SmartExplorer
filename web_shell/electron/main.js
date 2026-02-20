const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

const BACKEND_URL = process.env.SMX_BACKEND_URL || 'http://127.0.0.1:5001';
const PYTHON = process.env.SMX_PYTHON || 'python';
let backendProc = null;

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
    },
  });
  win.loadURL(`${BACKEND_URL}/web/index.html`);
}

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
  if (backendProc && !backendProc.killed) {
    backendProc.kill();
  }
});
