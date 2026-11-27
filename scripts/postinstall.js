const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

// rcedit is a Windows PE binary tool; skip safely on non-Windows platforms
if (process.platform !== 'win32') {
  process.exit(0);
}

const rootDir = path.resolve(__dirname, '..');
const rceditPath = path.join(rootDir, 'node_modules', 'electron-winstaller', 'vendor', 'rcedit.exe');
const electronExe = path.join(rootDir, 'node_modules', 'electron', 'dist', 'electron.exe');
const iconPath = path.join(rootDir, 'assets', 'icon.ico');

// Skip gracefully if electron or rcedit or icon does not exist
if (!fs.existsSync(rceditPath) || !fs.existsSync(electronExe) || !fs.existsSync(iconPath)) {
  process.exit(0);
}

try {
  const result = spawnSync(rceditPath, [electronExe, '--set-icon', iconPath], {
    stdio: 'ignore',
    windowsHide: true,
  });
  if (result.error) {
    console.warn('[postinstall] Warning: Could not set electron dev icon:', result.error.message);
  }
} catch (err) {
  console.warn('[postinstall] Warning: Error during icon customization:', err && err.message);
}
