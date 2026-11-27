const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const crypto = require('crypto');
const { Transform, compose } = require('stream');
const { pipeline } = require('stream/promises');
const { spawn, spawnSync } = require('child_process');

const ZSTD_MAGIC = Buffer.from([0x28, 0xb5, 0x2f, 0xfd]);
const ZIP_MAGIC = Buffer.from([0x50, 0x4b, 0x03, 0x04]);
const ZIP_EMPTY_MAGIC = Buffer.from([0x50, 0x4b, 0x05, 0x06]);
const ZIP_SPANNED_MAGIC = Buffer.from([0x50, 0x4b, 0x07, 0x08]);

function isAbortError(err) {
  return Boolean(err && (err.name === 'AbortError' || err.code === 'ABORT_ERR'));
}

function makeAbortError() {
  const err = new Error('Operação de extração cancelada.');
  err.name = 'AbortError';
  err.code = 'ABORT_ERR';
  return err;
}

/**
 * Identifica o formato real do pacote pelo magic header (Zstandard ou ZIP).
 */
function detectArchiveFormat(archivePath) {
  try {
    if (!archivePath || typeof archivePath !== 'string' || !fs.existsSync(archivePath)) {
      return null;
    }
    const stat = fs.statSync(archivePath);
    if (!stat.isFile()) return null;

    if (stat.size >= 4) {
      const buf = Buffer.alloc(4);
      const fd = fs.openSync(archivePath, 'r');
      let bytesRead = 0;
      try {
        bytesRead = fs.readSync(fd, buf, 0, 4, 0);
      } finally {
        fs.closeSync(fd);
      }

      if (bytesRead === 4) {
        if (
          buf.equals(ZSTD_MAGIC) ||
          ((buf[0] & 0xf0) === 0x50 && buf[1] === 0x2a && buf[2] === 0x4d && buf[3] === 0x18)
        ) {
          return 'tar.zst';
        }
        if (buf.equals(ZIP_MAGIC) || buf.equals(ZIP_EMPTY_MAGIC) || buf.equals(ZIP_SPANNED_MAGIC)) {
          return 'zip';
        }
        return null;
      }
    }

    const lower = archivePath.toLowerCase();
    if (lower.endsWith('.tar.zst')) return 'tar.zst';
    if (lower.endsWith('.zip')) return 'zip';
  } catch (_) {}
  return null;
}

/**
 * Lê o manifesto sidecar emitido junto ao pacote de release, validando nome e tamanho.
 */
function readSidecarManifest(archivePath) {
  try {
    if (!archivePath || !fs.existsSync(archivePath)) return null;
    const stat = fs.statSync(archivePath);
    const archiveName = path.basename(archivePath);
    const candidates = [
      path.join(path.dirname(archivePath), 'engine-runtime.manifest.json'),
      `${archivePath}.manifest.json`,
    ];

    for (const candidate of candidates) {
      if (!fs.existsSync(candidate)) continue;
      const raw = fs.readFileSync(candidate, 'utf-8');
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object') continue;
      if (parsed.archiveName && parsed.archiveName !== archiveName) continue;
      if (typeof parsed.size === 'number' && parsed.size !== stat.size) continue;
      return parsed;
    }
  } catch (_) {}
  return null;
}

/**
 * Calcula impressão digital rápida (tamanho + amostras de início/meio/fim) sem ler vários GB inteiros.
 */
function computeArchiveFingerprint(archivePath) {
  const stat = fs.statSync(archivePath);
  const size = stat.size;
  const hash = crypto.createHash('sha256');
  hash.update(String(size));

  const sampleSize = 64 * 1024;
  const offsets = [0];
  if (size > sampleSize * 2) {
    offsets.push(Math.floor((size - sampleSize) / 2));
  }
  if (size > sampleSize) {
    offsets.push(Math.max(0, size - sampleSize));
  }

  const fd = fs.openSync(archivePath, 'r');
  try {
    const buf = Buffer.allocUnsafe(sampleSize);
    for (const offset of offsets) {
      const bytesToRead = Math.min(sampleSize, Math.max(0, size - offset));
      if (bytesToRead <= 0) continue;
      const read = fs.readSync(fd, buf, 0, bytesToRead, offset);
      if (read > 0) {
        hash.update(buf.subarray(0, read));
      }
    }
  } finally {
    fs.closeSync(fd);
  }
  return hash.digest('hex');
}

/**
 * Estima o espaço em disco necessário para descompactar a engine com folga operacional.
 */
function estimateRequiredBytes(archivePath, manifestMeta = null, options = {}) {
  if (manifestMeta && typeof manifestMeta.uncompressedBytes === 'number' && manifestMeta.uncompressedBytes > 0) {
    const margin = options.marginBytes ?? 512 * 1024 * 1024;
    return manifestMeta.uncompressedBytes + margin;
  }

  const stat = fs.statSync(archivePath);
  const format = detectArchiveFormat(archivePath);
  if (format === 'zip') {
    const zipMargin = options.zipMarginBytes ?? 128 * 1024 * 1024;
    return Math.ceil(stat.size * 3.0) + zipMargin;
  }
  const zstMargin = options.zstMarginBytes ?? 512 * 1024 * 1024;
  return Math.ceil(stat.size * 3.5) + zstMargin;
}

/**
 * Verifica espaço livre no volume de destino usando fs.statfsSync nativo do Node.
 */
function checkDiskSpace(targetDir, requiredBytes) {
  let probePath = path.resolve(targetDir || process.cwd());
  while (probePath && !fs.existsSync(probePath)) {
    const parent = path.dirname(probePath);
    if (parent === probePath) break;
    probePath = parent;
  }

  if (typeof fs.statfsSync !== 'function') {
    return { ok: true, skipped: true, freeBytes: null, requiredBytes, checkedPath: probePath };
  }

  try {
    const stats = fs.statfsSync(probePath);
    const availBlocks = stats.bavail ?? stats.bfree;
    const freeBytes = Number(availBlocks) * Number(stats.bsize);
    if (!Number.isFinite(freeBytes)) {
      return { ok: true, skipped: true, freeBytes: null, requiredBytes, checkedPath: probePath };
    }
    return {
      ok: freeBytes >= requiredBytes,
      freeBytes,
      requiredBytes,
      checkedPath: probePath,
    };
  } catch (err) {
    return {
      ok: true,
      skipped: true,
      freeBytes: null,
      requiredBytes,
      checkedPath: probePath,
      warning: err.message,
    };
  }
}

function formatBytes(bytes) {
  if (typeof bytes !== 'number' || !Number.isFinite(bytes) || bytes < 0) return '0 B';
  if (bytes < 1024) return `${Math.round(bytes)} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let val = bytes / 1024;
  let idx = 0;
  while (val >= 1024 && idx < units.length - 1) {
    val /= 1024;
    idx++;
  }
  const decimals = val >= 100 ? 0 : (val >= 10 ? 1 : 2);
  return `${val.toFixed(decimals)} ${units[idx]}`;
}

/**
 * Lê a contagem total de entradas do diretório central (EOCD) de um arquivo ZIP em O(1).
 */
function readZipEntryCount(zipPath) {
  try {
    const stat = fs.statSync(zipPath);
    const tailSize = Math.min(stat.size, 65557);
    if (tailSize < 22) return null;

    const buf = Buffer.allocUnsafe(tailSize);
    const fd = fs.openSync(zipPath, 'r');
    try {
      fs.readSync(fd, buf, 0, tailSize, stat.size - tailSize);
    } finally {
      fs.closeSync(fd);
    }

    for (let i = tailSize - 22; i >= 0; i--) {
      if (
        buf[i] === 0x50 &&
        buf[i + 1] === 0x4b &&
        buf[i + 2] === 0x05 &&
        buf[i + 3] === 0x06
      ) {
        const count = buf.readUInt16LE(i + 10);
        return count === 0xffff ? null : count;
      }
    }
  } catch (_) {}
  return null;
}

/**
 * Bloqueia path traversal, caminhos absolutos, drives Windows e bytes nulos em entradas de arquivos compactados.
 */
function sanitizeExtractPath(destDir, entryName) {
  if (typeof entryName !== 'string' || !entryName) {
    throw new Error('Entrada vazia detectada no pacote.');
  }
  if (entryName.includes('\0')) {
    throw new Error('Caminho inseguro detectado no pacote (byte nulo).');
  }

  const normalizedSlashes = entryName.replace(/\\/g, '/').trim();
  if (!normalizedSlashes) {
    throw new Error('Entrada vazia detectada no pacote.');
  }
  if (
    normalizedSlashes.startsWith('/') ||
    /^[a-zA-Z]:/.test(normalizedSlashes) ||
    path.isAbsolute(entryName)
  ) {
    throw new Error(`Caminho inseguro detectado no pacote (caminho absoluto): ${entryName}`);
  }

  const segments = normalizedSlashes.split('/').filter((seg) => seg.length > 0 && seg !== '.');
  for (const seg of segments) {
    if (seg === '..') {
      throw new Error(`Caminho inseguro detectado no pacote (path traversal): ${entryName}`);
    }
  }

  const resolvedDest = path.resolve(destDir);
  if (segments.length === 0) {
    return resolvedDest;
  }

  const resolvedTarget = path.resolve(resolvedDest, ...segments);
  if (resolvedTarget !== resolvedDest && !resolvedTarget.startsWith(resolvedDest + path.sep)) {
    throw new Error(`Caminho inseguro detectado no pacote (escape de diretório): ${entryName}`);
  }
  return resolvedTarget;
}

function parsePaxHeaders(buffer) {
  const result = {};
  let offset = 0;
  while (offset < buffer.length) {
    const spaceIdx = buffer.indexOf(0x20, offset);
    if (spaceIdx === -1) break;
    const lenStr = buffer.subarray(offset, spaceIdx).toString('ascii');
    const recordLen = parseInt(lenStr, 10);
    if (!Number.isFinite(recordLen) || recordLen <= 0) break;

    const recordEnd = Math.min(buffer.length, offset + recordLen);
    const body = buffer.subarray(spaceIdx + 1, recordEnd).toString('utf8').replace(/\n$/, '');
    const eqIdx = body.indexOf('=');
    if (eqIdx !== -1) {
      const key = body.slice(0, eqIdx);
      const val = body.slice(eqIdx + 1);
      result[key] = val;
    }
    offset = recordEnd;
  }
  return result;
}

function parseTarNumber(buf, offset, length) {
  if ((buf[offset] & 0x80) !== 0) {
    let val = BigInt(buf[offset] & 0x7f);
    for (let i = 1; i < length; i++) {
      val = (val << 8n) | BigInt(buf[offset + i]);
    }
    return Number(val);
  }
  const raw = buf.subarray(offset, offset + length).toString('ascii').replace(/\0.*$/, '').trim();
  if (!raw) return 0;
  const parsed = parseInt(raw, 8);
  return Number.isFinite(parsed) ? parsed : 0;
}

function readTarAsciiField(buf, offset, length) {
  const slice = buf.subarray(offset, offset + length);
  const zeroIdx = slice.indexOf(0);
  const trimmed = zeroIdx === -1 ? slice : slice.subarray(0, zeroIdx);
  return trimmed.toString('utf8');
}

function isAllZeroBlock(block) {
  for (let i = 0; i < block.length; i++) {
    if (block[i] !== 0) return false;
  }
  return true;
}

/**
 * Extrator TAR streaming puro em Node.js (suporta USTAR, GNU LongName/LongLink, PAX e arquivos grandes com O(1) RAM).
 */
async function extractTarStreamPureNode(tarStream, destDir, { onEntry, signal } = {}) {
  const resolvedDest = path.resolve(destDir);
  fs.mkdirSync(resolvedDest, { recursive: true });

  const iterator = tarStream[Symbol.asyncIterator]();
  const chunks = [];
  let headOffset = 0;
  let buffered = 0;
  let streamEnded = false;

  const ensureBytes = async (needed) => {
    while (buffered < needed && !streamEnded) {
      if (signal?.aborted) {
        try { await iterator.return?.(); } catch (_) {}
        throw makeAbortError();
      }
      const { value, done } = await iterator.next();
      if (done) {
        streamEnded = true;
        break;
      }
      if (value && value.length > 0) {
        chunks.push(value);
        buffered += value.length;
      }
    }
    return buffered >= needed;
  };

  const takeUpTo = (maxBytes) => {
    const head = chunks[0];
    const available = head.length - headOffset;
    const count = Math.min(maxBytes, available);
    const slice = head.subarray(headOffset, headOffset + count);
    headOffset += count;
    buffered -= count;
    if (headOffset >= head.length) {
      chunks.shift();
      headOffset = 0;
    }
    return slice;
  };

  const readExact = async (n) => {
    if (n === 0) return Buffer.alloc(0);
    const ok = await ensureBytes(n);
    if (!ok) {
      throw new Error('Arquivo TAR truncado inesperadamente.');
    }
    if (chunks[0].length - headOffset >= n) {
      return takeUpTo(n);
    }
    const out = Buffer.allocUnsafe(n);
    let written = 0;
    while (written < n) {
      const piece = takeUpTo(n - written);
      piece.copy(out, written);
      written += piece.length;
    }
    return out;
  };

  const skipExact = async (n) => {
    let remaining = n;
    while (remaining > 0) {
      if (buffered === 0) {
        const ok = await ensureBytes(1);
        if (!ok) return;
      }
      const piece = takeUpTo(remaining);
      remaining -= piece.length;
    }
  };

  const writeExactToFile = async (n, targetFile) => {
    fs.mkdirSync(path.dirname(targetFile), { recursive: true });
    const fd = fs.openSync(targetFile, 'w');
    let remaining = n;
    try {
      while (remaining > 0) {
        if (signal?.aborted) {
          throw makeAbortError();
        }
        if (buffered === 0) {
          const ok = await ensureBytes(1);
          if (!ok) {
            throw new Error('Arquivo TAR truncado durante escrita de arquivo.');
          }
        }
        const piece = takeUpTo(remaining);
        fs.writeSync(fd, piece);
        remaining -= piece.length;
      }
    } finally {
      fs.closeSync(fd);
    }
  };

  let entryCount = 0;
  let zeroBlocks = 0;
  const globalPax = {};
  let nextPax = {};
  let gnuLongName = null;
  let gnuLongLink = null;

  try {
    while (true) {
      if (signal?.aborted) {
        throw makeAbortError();
      }
      const hasHeader = await ensureBytes(512);
      if (!hasHeader) {
        if (buffered > 0) {
          throw new Error('Bloco final do TAR incompleto.');
        }
        break;
      }

      const header = await readExact(512);
      if (isAllZeroBlock(header)) {
        zeroBlocks++;
        if (zeroBlocks >= 2) {
          // Drena eventuais blocos nulos finais sem cortar o stream prematuramente
          while (await ensureBytes(1)) {
            takeUpTo(buffered);
          }
          break;
        }
        continue;
      }
      zeroBlocks = 0;

      const rawName = readTarAsciiField(header, 0, 100);
      const rawPrefix = readTarAsciiField(header, 345, 155);
      const ustarName = rawPrefix ? `${rawPrefix}/${rawName}` : rawName;
      const rawLink = readTarAsciiField(header, 157, 100);
      const rawSize = parseTarNumber(header, 124, 12);
      const typeFlag = header[156] === 0 ? '0' : String.fromCharCode(header[156]);

      if (typeFlag === 'L') {
        const nameBuf = await readExact(rawSize);
        gnuLongName = nameBuf.toString('utf8').replace(/\0+$/, '');
        await skipExact((512 - (rawSize % 512)) % 512);
        continue;
      }
      if (typeFlag === 'K') {
        const linkBuf = await readExact(rawSize);
        gnuLongLink = linkBuf.toString('utf8').replace(/\0+$/, '');
        await skipExact((512 - (rawSize % 512)) % 512);
        continue;
      }
      if (typeFlag === 'x') {
        const paxBuf = await readExact(rawSize);
        Object.assign(nextPax, parsePaxHeaders(paxBuf));
        await skipExact((512 - (rawSize % 512)) % 512);
        continue;
      }
      if (typeFlag === 'g') {
        const paxBuf = await readExact(rawSize);
        Object.assign(globalPax, parsePaxHeaders(paxBuf));
        await skipExact((512 - (rawSize % 512)) % 512);
        continue;
      }

      const entryPath = nextPax.path ?? gnuLongName ?? globalPax.path ?? ustarName;
      const entryLink = nextPax.linkpath ?? gnuLongLink ?? globalPax.linkpath ?? rawLink;
      const entrySize = nextPax.size !== undefined ? Number(nextPax.size) : rawSize;

      nextPax = {};
      gnuLongName = null;
      gnuLongLink = null;

      const padding = (512 - (entrySize % 512)) % 512;

      if (!entryPath) {
        await skipExact(entrySize + padding);
        continue;
      }

      const targetPath = sanitizeExtractPath(resolvedDest, entryPath);

      if (typeFlag === '5') {
        fs.mkdirSync(targetPath, { recursive: true });
        await skipExact(entrySize + padding);
      } else if (typeFlag === '0') {
        if (targetPath === resolvedDest) {
          throw new Error(`Caminho inseguro detectado no pacote: ${entryPath}`);
        }
        await writeExactToFile(entrySize, targetPath);
        await skipExact(padding);
      } else if (typeFlag === '1' || typeFlag === '2') {
        if (entryLink) {
          if (typeFlag === '1') {
            const linkTarget = sanitizeExtractPath(resolvedDest, entryLink);
            fs.mkdirSync(path.dirname(targetPath), { recursive: true });
            try {
              if (fs.existsSync(linkTarget)) {
                fs.linkSync(linkTarget, targetPath);
              }
            } catch (_) {}
          } else {
            // Valida que o symlink relativo não escapa de destDir
            const resolvedLink = path.isAbsolute(entryLink)
              ? sanitizeExtractPath(resolvedDest, entryLink)
              : path.resolve(path.dirname(targetPath), entryLink);
            if (resolvedLink !== resolvedDest && !resolvedLink.startsWith(resolvedDest + path.sep)) {
              throw new Error(`Symlink inseguro detectado no pacote: ${entryPath} -> ${entryLink}`);
            }
            fs.mkdirSync(path.dirname(targetPath), { recursive: true });
            try {
              fs.symlinkSync(entryLink, targetPath);
            } catch (_) {}
          }
        }
        await skipExact(entrySize + padding);
      } else {
        await skipExact(entrySize + padding);
      }

      entryCount++;
      onEntry?.({ path: entryPath, size: entrySize, count: entryCount });
    }
  } finally {
    try { await iterator.return?.(); } catch (_) {}
  }

  return entryCount;
}

function resolveSystemTar() {
  if (process.platform === 'win32') {
    const sysTar = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'tar.exe');
    if (fs.existsSync(sysTar)) return sysTar;
  }
  const check = spawnSync('tar', ['--version'], { windowsHide: true, stdio: 'ignore' });
  return check.status === 0 ? 'tar' : null;
}

function createByteMeterTransform(totalBytes, onProgress, engineName) {
  let bytesRead = 0;
  let lastEmitAt = 0;
  let prevSampleAt = Date.now();
  let prevSampleBytes = 0;
  let emaSpeed = 0;

  const emitProgress = (force = false) => {
    if (!onProgress) return;
    const now = Date.now();
    if (!force && now - lastEmitAt < 150) return;

    const dt = (now - prevSampleAt) / 1000;
    if (dt >= 0.15) {
      const instSpeed = (bytesRead - prevSampleBytes) / dt;
      emaSpeed = emaSpeed > 0 ? (emaSpeed * 0.65 + instSpeed * 0.35) : instSpeed;
      prevSampleAt = now;
      prevSampleBytes = bytesRead;
    }

    const ratio = totalBytes > 0 ? Math.min(1, bytesRead / totalBytes) : 0;
    const remainingBytes = Math.max(0, totalBytes - bytesRead);
    const etaSec = emaSpeed > 1024 ? remainingBytes / emaSpeed : null;
    lastEmitAt = now;

    onProgress({
      bytesRead,
      totalBytes,
      ratio,
      speedBytesPerSec: emaSpeed,
      etaSec,
      engine: engineName,
    });
  };

  const transform = new Transform({
    transform(chunk, _encoding, callback) {
      bytesRead += chunk.length;
      emitProgress(false);
      callback(null, chunk);
    },
    flush(callback) {
      emitProgress(true);
      callback();
    },
  });

  emitProgress(true);
  return transform;
}

function killChildTree(cp) {
  if (!cp || !cp.pid) return;
  try {
    if (process.platform === 'win32') {
      spawnSync('taskkill', ['/pid', String(cp.pid), '/f', '/t'], { windowsHide: true });
    } else {
      cp.kill('SIGKILL');
    }
  } catch (_) {}
}

async function runNativeZstdViaTar(archivePath, destDir, tarBin, totalBytes, { onProgress, signal, onSpawnChild }) {
  fs.mkdirSync(destDir, { recursive: true });

  const tarProc = spawn(tarBin, ['-m', '-xf', '-', '-C', destDir], {
    shell: false,
    windowsHide: true,
    stdio: ['pipe', 'ignore', 'pipe'],
  });
  onSpawnChild?.(tarProc);

  let stderrOut = '';
  if (tarProc.stderr) {
    tarProc.stderr.on('data', (d) => { stderrOut += d.toString(); });
  }
  if (tarProc.stdin) {
    tarProc.stdin.on('error', () => {});
  }

  const onAbort = () => killChildTree(tarProc);
  if (signal) {
    if (signal.aborted) {
      killChildTree(tarProc);
      throw makeAbortError();
    }
    signal.addEventListener('abort', onAbort, { once: true });
  }

  let tarExitedZero = false;
  let bytesReadSnapshot = 0;

  const tarExitPromise = new Promise((resolve, reject) => {
    tarProc.on('close', (code) => {
      onSpawnChild?.(null);
      if (code === 0) {
        tarExitedZero = true;
        resolve();
      } else {
        reject(new Error(`tar.exe falhou (código ${code}): ${stderrOut.trim()}`));
      }
    });
    tarProc.on('error', (err) => {
      onSpawnChild?.(null);
      reject(err);
    });
  });

  const readStream = fs.createReadStream(archivePath, { highWaterMark: 256 * 1024 });
  const meter = createByteMeterTransform(
    totalBytes,
    (prog) => {
      bytesReadSnapshot = prog.bytesRead;
      onProgress?.(prog);
    },
    'zstd-tar'
  );
  const zstd = zlib.createZstdDecompress();

  try {
    const pipelinePromise = pipeline(readStream, meter, zstd, tarProc.stdin, { signal }).catch((err) => {
      // bsdtar pode fechar stdin assim que lê os 2 blocos nulos de EOF do TAR;
      // se tar saiu com código 0 após ler >=99% do arquivo, o fluxo foi concluído com sucesso.
      if (
        tarExitedZero &&
        !signal?.aborted &&
        bytesReadSnapshot >= totalBytes * 0.99 &&
        (err.code === 'EPIPE' || err.code === 'ERR_STREAM_PREMATURE_CLOSE')
      ) {
        return;
      }
      throw err;
    });
    await Promise.all([pipelinePromise, tarExitPromise]);
  } finally {
    if (signal) signal.removeEventListener('abort', onAbort);
  }
}

async function runNativeZstdPureNode(archivePath, destDir, totalBytes, { onProgress, signal }) {
  fs.mkdirSync(destDir, { recursive: true });
  const readStream = fs.createReadStream(archivePath, { highWaterMark: 256 * 1024 });
  const meter = createByteMeterTransform(totalBytes, onProgress, 'zstd-node');
  const zstd = zlib.createZstdDecompress();
  const tarStream = compose(readStream, meter, zstd);
  await extractTarStreamPureNode(tarStream, destDir, { signal });
}

/**
 * Extrai arquivo .tar.zst usando zlib.createZstdDecompress nativo com progresso contínuo e fallback TAR puro em Node.
 */
async function extractTarZst(archivePath, destDir, options = {}) {
  const { onProgress, signal, forcePureNode = false, onSpawnChild } = options;
  if (signal?.aborted) throw makeAbortError();

  const totalBytes = fs.statSync(archivePath).size;
  const tarBin = forcePureNode ? null : resolveSystemTar();
  const hasNativeZstd = typeof zlib.createZstdDecompress === 'function';

  if (hasNativeZstd) {
    if (!forcePureNode && tarBin) {
      try {
        await runNativeZstdViaTar(archivePath, destDir, tarBin, totalBytes, { onProgress, signal, onSpawnChild });
        return { engine: 'zstd-tar', totalBytes };
      } catch (err) {
        if (isAbortError(err) || signal?.aborted) throw err;
        // Limpa extração parcial antes de tentar o extrator TAR streaming em Node.js
        try { fs.rmSync(destDir, { recursive: true, force: true }); } catch (_) {}
        await runNativeZstdPureNode(archivePath, destDir, totalBytes, { onProgress, signal });
        return { engine: 'zstd-node-fallback', totalBytes };
      }
    }

    await runNativeZstdPureNode(archivePath, destDir, totalBytes, { onProgress, signal });
    return { engine: 'zstd-node', totalBytes };
  }

  // Fallback extremo caso um runtime Node antigo não tenha zlib.createZstdDecompress
  if (tarBin) {
    fs.mkdirSync(destDir, { recursive: true });
    await new Promise((resolve, reject) => {
      const cp = spawn(tarBin, ['-m', '-xf', archivePath, '-C', destDir], {
        shell: false,
        windowsHide: true,
        stdio: ['ignore', 'ignore', 'pipe'],
      });
      onSpawnChild?.(cp);
      let stderrOut = '';
      if (cp.stderr) cp.stderr.on('data', (d) => { stderrOut += d.toString(); });
      cp.on('close', (code) => {
        onSpawnChild?.(null);
        if (code === 0) resolve();
        else reject(new Error(`tar falhou (${code}): ${stderrOut.trim()}`));
      });
      cp.on('error', (err) => {
        onSpawnChild?.(null);
        reject(err);
      });
    });
    onProgress?.({ bytesRead: totalBytes, totalBytes, ratio: 1, speedBytesPerSec: 0, etaSec: 0, engine: 'system-tar' });
    return { engine: 'system-tar', totalBytes };
  }

  throw new Error('Runtime atual não possui suporte nativo a Zstandard (zlib.createZstdDecompress) nem utilitário tar.');
}

async function runZipViaTar(archivePath, destDir, tarBin, totalEntries, { onProgress, signal, onSpawnChild }) {
  fs.mkdirSync(destDir, { recursive: true });
  return new Promise((resolve, reject) => {
    const cp = spawn(tarBin, ['-m', '-xvf', archivePath, '-C', destDir], {
      shell: false,
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    onSpawnChild?.(cp);

    let extractedEntries = 0;
    let lastEmitAt = 0;
    let lineRemainder = '';
    const errLines = [];

    const emitZipProgress = (force = false) => {
      if (!onProgress) return;
      const now = Date.now();
      if (!force && now - lastEmitAt < 150) return;
      lastEmitAt = now;
      const ratio = totalEntries && totalEntries > 0
        ? Math.min(1, extractedEntries / totalEntries)
        : (extractedEntries > 0 ? Math.min(0.95, 1 - Math.exp(-extractedEntries / 400)) : 0);
      onProgress({
        extractedEntries,
        totalEntries,
        ratio,
        engine: 'bsdtar-zip',
      });
    };

    const handleOutput = (chunk) => {
      const text = lineRemainder + chunk.toString('utf8');
      const lines = text.split(/\r?\n/);
      lineRemainder = lines.pop() || '';
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        if (trimmed.startsWith('x ')) {
          extractedEntries++;
          emitZipProgress(false);
        } else {
          errLines.push(trimmed);
          if (errLines.length > 20) errLines.shift();
        }
      }
    };

    if (cp.stdout) cp.stdout.on('data', handleOutput);
    if (cp.stderr) cp.stderr.on('data', handleOutput);

    const onAbort = () => killChildTree(cp);
    if (signal) {
      if (signal.aborted) {
        killChildTree(cp);
        reject(makeAbortError());
        return;
      }
      signal.addEventListener('abort', onAbort, { once: true });
    }

    emitZipProgress(true);

    cp.on('close', (code) => {
      if (signal) signal.removeEventListener('abort', onAbort);
      onSpawnChild?.(null);
      if (code === 0) {
        if (totalEntries && extractedEntries < totalEntries) {
          extractedEntries = totalEntries;
        }
        emitZipProgress(true);
        resolve();
      } else {
        reject(new Error(`tar ZIP falhou (${code}): ${errLines.join(' ')}`));
      }
    });

    cp.on('error', (err) => {
      if (signal) signal.removeEventListener('abort', onAbort);
      onSpawnChild?.(null);
      reject(err);
    });
  });
}

async function runZipViaPowerShell(archivePath, destDir, totalEntries, { onProgress, signal, onSpawnChild }) {
  fs.mkdirSync(destDir, { recursive: true });
  onProgress?.({ extractedEntries: 0, totalEntries, ratio: 0.1, engine: 'powershell-zip' });

  await new Promise((resolve, reject) => {
    const cp = spawn(
      'powershell.exe',
      [
        '-NoProfile',
        '-NonInteractive',
        '-Command',
        'Expand-Archive -LiteralPath $env:VISIONARY_ZIP_SRC -DestinationPath $env:VISIONARY_ZIP_DST -Force',
      ],
      {
        shell: false,
        windowsHide: true,
        env: {
          ...process.env,
          VISIONARY_ZIP_SRC: path.resolve(archivePath),
          VISIONARY_ZIP_DST: path.resolve(destDir),
        },
        stdio: ['ignore', 'ignore', 'pipe'],
      }
    );
    onSpawnChild?.(cp);

    let errOut = '';
    if (cp.stderr) cp.stderr.on('data', (d) => { errOut += d.toString(); });

    const onAbort = () => killChildTree(cp);
    if (signal) {
      if (signal.aborted) {
        killChildTree(cp);
        reject(makeAbortError());
        return;
      }
      signal.addEventListener('abort', onAbort, { once: true });
    }

    cp.on('close', (code) => {
      if (signal) signal.removeEventListener('abort', onAbort);
      onSpawnChild?.(null);
      if (code === 0) resolve();
      else reject(new Error(`Expand-Archive falhou (${code}): ${errOut.trim()}`));
    });
    cp.on('error', (err) => {
      if (signal) signal.removeEventListener('abort', onAbort);
      onSpawnChild?.(null);
      reject(err);
    });
  });

  onProgress?.({
    extractedEntries: totalEntries || 1,
    totalEntries: totalEntries || 1,
    ratio: 1,
    engine: 'powershell-zip',
  });
}

/**
 * Extrai arquivo .zip com contagem real de entradas (EOCD) e fallback PowerShell com -LiteralPath.
 */
async function extractZipArchive(archivePath, destDir, options = {}) {
  const { onProgress, signal, onSpawnChild, forcePowerShell = false } = options;
  if (signal?.aborted) throw makeAbortError();

  const totalEntries = readZipEntryCount(archivePath);
  const tarBin = forcePowerShell ? null : resolveSystemTar();

  if (tarBin) {
    try {
      await runZipViaTar(archivePath, destDir, tarBin, totalEntries, { onProgress, signal, onSpawnChild });
      return { engine: 'bsdtar-zip', totalEntries };
    } catch (err) {
      if (isAbortError(err) || signal?.aborted) throw err;
      if (process.platform !== 'win32') throw err;
      try { fs.rmSync(destDir, { recursive: true, force: true }); } catch (_) {}
    }
  }

  if (process.platform === 'win32') {
    await runZipViaPowerShell(archivePath, destDir, totalEntries, { onProgress, signal, onSpawnChild });
    return { engine: 'powershell-zip', totalEntries };
  }

  throw new Error('Não foi possível extrair o pacote ZIP neste sistema operacional.');
}

/**
 * Extrai um pacote do motor validando previamente seu formato real.
 */
async function extractEngineArchive(archivePath, destDir, options = {}) {
  const format = detectArchiveFormat(archivePath);
  if (!format) {
    const err = new Error(`Arquivo selecionado ou empacotado não é um pacote .tar.zst ou .zip válido: ${archivePath}`);
    err.code = 'INVALID_ARCHIVE';
    throw err;
  }

  if (format === 'tar.zst') {
    return extractTarZst(archivePath, destDir, options);
  }
  return extractZipArchive(archivePath, destDir, options);
}

module.exports = {
  detectArchiveFormat,
  readSidecarManifest,
  computeArchiveFingerprint,
  estimateRequiredBytes,
  checkDiskSpace,
  formatBytes,
  readZipEntryCount,
  sanitizeExtractPath,
  parsePaxHeaders,
  extractTarStreamPureNode,
  extractTarZst,
  extractZipArchive,
  extractEngineArchive,
  resolveSystemTar,
};
