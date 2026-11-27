const { describe, it, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const zlib = require('node:zlib');
const { Readable } = require('node:stream');

const {
  readTextFileUnicodeSafe,
  getExpectedEngineVersion,
  readEngineSourcePointer,
  saveEngineSourcePointer,
  resolveBundledEngineArchive,
} = require('../../electron/paths');

const {
  detectArchiveFormat,
  readSidecarManifest,
  computeArchiveFingerprint,
  estimateRequiredBytes,
  checkDiskSpace,
  readZipEntryCount,
  sanitizeExtractPath,
  extractTarStreamPureNode,
  extractTarZst,
  extractZipArchive,
  extractEngineArchive,
} = require('../../electron/engineArchive');

const {
  getCachedPython,
  setCachedPython,
  detectPython,
  autoSetupPython,
  readEngineManifest,
  writeEngineManifest,
  isEngineManifestCompatible,
  patchEmbeddablePthFiles,
  validateAndInjectVcRuntimeDlls,
  verifyPythonHealthDetailed,
} = require('../../electron/pythonBootstrap');

function createMockApp(userDataDir, { isPackaged = true } = {}) {
  return {
    isPackaged,
    getPath(name) {
      if (name === 'userData') return userDataDir;
      if (name === 'downloads') return path.join(userDataDir, 'downloads');
      if (name === 'desktop') return path.join(userDataDir, 'desktop');
      return userDataDir;
    },
  };
}

function buildTarHeader(name, size, typeFlag = '0') {
  const header = Buffer.alloc(512, 0);
  const nameBuf = Buffer.from(name, 'utf8');
  nameBuf.copy(header, 0, 0, Math.min(nameBuf.length, 100));
  Buffer.from('0000755\0', 'ascii').copy(header, 100);
  Buffer.from('0000000\0', 'ascii').copy(header, 108);
  Buffer.from('0000000\0', 'ascii').copy(header, 116);
  const sizeOct = size.toString(8).padStart(11, '0') + '\0';
  Buffer.from(sizeOct, 'ascii').copy(header, 124);
  const mtimeOct = Math.floor(Date.now() / 1000).toString(8).padStart(11, '0') + '\0';
  Buffer.from(mtimeOct, 'ascii').copy(header, 136);
  header.fill(0x20, 148, 156);
  header[156] = typeFlag.charCodeAt(0);
  Buffer.from('ustar\0', 'ascii').copy(header, 257);
  Buffer.from('00', 'ascii').copy(header, 263);

  let sum = 0;
  for (let i = 0; i < 512; i++) sum += header[i];
  const chk = sum.toString(8).padStart(6, '0') + '\0 ';
  Buffer.from(chk, 'ascii').copy(header, 148);
  return header;
}

function formatPaxRecord(key, value) {
  const body = `${key}=${value}\n`;
  let len = Buffer.byteLength(`0 ${body}`, 'utf8');
  while (true) {
    const rec = `${len} ${body}`;
    const byteLen = Buffer.byteLength(rec, 'utf8');
    if (byteLen === len) return Buffer.from(rec, 'utf8');
    len = byteLen;
  }
}

function buildTarBuffer(entries) {
  const blocks = [];
  for (const entry of entries) {
    const content = entry.type === '5' ? Buffer.alloc(0) : Buffer.from(entry.content || '');
    const needsPax = Buffer.byteLength(entry.name, 'utf8') > 95 || /[^\x20-\x7e]/.test(entry.name);
    if (needsPax) {
      const paxPayload = formatPaxRecord('path', entry.name);
      blocks.push(buildTarHeader('PaxHeader/entry', paxPayload.length, 'x'));
      blocks.push(paxPayload);
      const paxPad = (512 - (paxPayload.length % 512)) % 512;
      if (paxPad > 0) blocks.push(Buffer.alloc(paxPad, 0));
    }

    const shortName = needsPax ? 'pax_entry_placeholder' : entry.name;
    blocks.push(buildTarHeader(shortName, content.length, entry.type || '0'));
    if (content.length > 0) {
      blocks.push(content);
      const pad = (512 - (content.length % 512)) % 512;
      if (pad > 0) blocks.push(Buffer.alloc(pad, 0));
    }
  }
  blocks.push(Buffer.alloc(1024, 0));
  return Buffer.concat(blocks);
}

function buildZipBuffer(entries) {
  const localParts = [];
  const centralParts = [];
  let offset = 0;

  for (const entry of entries) {
    const nameBuf = Buffer.from(entry.name, 'utf8');
    const dataBuf = Buffer.from(entry.content || '');
    const crc = zlib.crc32(dataBuf) >>> 0;

    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(0x0800, 6); // UTF-8 flag
    local.writeUInt16LE(0, 8); // stored
    local.writeUInt16LE(0, 10);
    local.writeUInt16LE(0, 12);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(dataBuf.length, 18);
    local.writeUInt32LE(dataBuf.length, 22);
    local.writeUInt16LE(nameBuf.length, 26);
    local.writeUInt16LE(0, 28);

    localParts.push(local, nameBuf, dataBuf);

    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(0x0800, 8);
    central.writeUInt16LE(0, 10);
    central.writeUInt16LE(0, 12);
    central.writeUInt16LE(0, 14);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(dataBuf.length, 20);
    central.writeUInt32LE(dataBuf.length, 24);
    central.writeUInt16LE(nameBuf.length, 28);
    central.writeUInt16LE(0, 30);
    central.writeUInt16LE(0, 32);
    central.writeUInt16LE(0, 34);
    central.writeUInt16LE(0, 36);
    central.writeUInt32LE(0, 38);
    central.writeUInt32LE(offset, 42);

    centralParts.push(central, nameBuf);
    offset += local.length + nameBuf.length + dataBuf.length;
  }

  const centralSize = centralParts.reduce((acc, b) => acc + b.length, 0);
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(0, 4);
  eocd.writeUInt16LE(0, 6);
  eocd.writeUInt16LE(entries.length, 8);
  eocd.writeUInt16LE(entries.length, 10);
  eocd.writeUInt32LE(centralSize, 12);
  eocd.writeUInt32LE(offset, 16);
  eocd.writeUInt16LE(0, 20);

  return Buffer.concat([...localParts, ...centralParts, eocd]);
}

describe('Visionary Engine Bootstrap & Archive Suite', () => {
  let tmpRoot;
  let origResourcesPath;

  beforeEach(() => {
    tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'visionary-boot-test-'));
    origResourcesPath = process.resourcesPath;
    process.resourcesPath = path.join(tmpRoot, 'missing_resources');
  });

  afterEach(() => {
    process.resourcesPath = origResourcesPath;
    fs.rmSync(tmpRoot, { recursive: true, force: true });
  });

  it('lê ponteiro engine-source.path em UTF-16LE (com/sem BOM), UTF-8 e caminhos com acentos/vírgulas', () => {
    const specialDir = path.join(tmpRoot, 'Área, Instalação (João)');
    const userDataDir = path.join(tmpRoot, 'AppData, Usuário');
    fs.mkdirSync(specialDir, { recursive: true });
    fs.mkdirSync(userDataDir, { recursive: true });

    const archiveFile = path.join(specialDir, 'engine-runtime.tar.zst');
    fs.writeFileSync(archiveFile, Buffer.concat([Buffer.from([0x28, 0xb5, 0x2f, 0xfd]), Buffer.from('test')]));

    const app = createMockApp(userDataDir, { isPackaged: true });
    const pointerPath = path.join(userDataDir, 'engine-source.path');

    // 1. UTF-16LE com BOM (padrão NSIS FileWriteWord 0xFEFF + FileWriteUTF16LE)
    const utf16Bom = Buffer.concat([Buffer.from([0xff, 0xfe]), Buffer.from(`${archiveFile}\r\n`, 'utf16le')]);
    fs.writeFileSync(pointerPath, utf16Bom);
    assert.equal(readTextFileUnicodeSafe(pointerPath), archiveFile);
    assert.equal(readEngineSourcePointer(app), path.normalize(archiveFile));
    assert.equal(resolveBundledEngineArchive(app), path.normalize(archiveFile));

    // 2. UTF-16LE sem BOM
    fs.writeFileSync(pointerPath, Buffer.from(archiveFile, 'utf16le'));
    assert.equal(readTextFileUnicodeSafe(pointerPath), archiveFile);
    assert.equal(readEngineSourcePointer(app), path.normalize(archiveFile));

    // 3. UTF-8 com BOM e saveEngineSourcePointer
    fs.writeFileSync(pointerPath, Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), Buffer.from(`"${archiveFile}"`, 'utf8')]));
    assert.equal(readEngineSourcePointer(app), path.normalize(archiveFile));

    saveEngineSourcePointer(app, archiveFile);
    assert.equal(readEngineSourcePointer(app), path.normalize(archiveFile));
  });

  it('valida pre-flight de espaço livre em disco (ok e insuficiente)', () => {
    const okCheck = checkDiskSpace(tmpRoot, 1024);
    assert.equal(okCheck.ok, true);
    assert.ok(okCheck.freeBytes === null || okCheck.freeBytes >= 1024);

    const tooLarge = 100 * 1024 * 1024 * 1024 * 1024 * 1024; // 100 PB
    const failCheck = checkDiskSpace(tmpRoot, tooLarge);
    if (!failCheck.skipped) {
      assert.equal(failCheck.ok, false);
    }
  });

  it('identifica formatos por magic bytes e rejeita arquivos inválidos', () => {
    const zstPath = path.join(tmpRoot, 'ok.tar.zst');
    const zipPath = path.join(tmpRoot, 'ok.zip');
    const badPath = path.join(tmpRoot, 'html404.tar.zst');

    fs.writeFileSync(zstPath, zlib.zstdCompressSync(buildTarBuffer([{ name: 'a.txt', content: 'ok' }])));
    fs.writeFileSync(zipPath, buildZipBuffer([{ name: 'a.txt', content: 'ok' }]));
    fs.writeFileSync(badPath, '<html>404 Not Found</html>', 'utf8');

    assert.equal(detectArchiveFormat(zstPath), 'tar.zst');
    assert.equal(detectArchiveFormat(zipPath), 'zip');
    assert.equal(detectArchiveFormat(badPath), null);
  });

  it('extrai .tar.zst real (bsdtar e fallback pure-Node) com caminhos Unicode/longos e telemetria de progresso', async () => {
    const longPath = `Lib/site-packages/${'subpasta_muito_longa_'.repeat(6)}arquivo_final.py`;
    const entries = [
      { name: 'python.exe', content: 'MZ-fake-python' },
      { name: 'python311._pth', content: 'python311.zip\n.\n#import site\n' },
      { name: 'pasta, com acento (João)/dados.txt', content: 'conteúdo unicode OK' },
      { name: longPath, content: 'print("ok")' },
    ];
    const zstData = zlib.zstdCompressSync(buildTarBuffer(entries));
    const archivePath = path.join(tmpRoot, 'Caminho, Especial (Á)', 'engine-runtime.tar.zst');
    fs.mkdirSync(path.dirname(archivePath), { recursive: true });
    fs.writeFileSync(archivePath, zstData);

    // 1. Extrator primário
    const destTar = path.join(tmpRoot, 'out_tar');
    const tarEvents = [];
    await extractTarZst(archivePath, destTar, {
      onProgress: (ev) => tarEvents.push(ev),
    });
    assert.ok(tarEvents.length >= 2);
    assert.equal(tarEvents[tarEvents.length - 1].ratio, 1);
    assert.equal(fs.readFileSync(path.join(destTar, 'pasta, com acento (João)', 'dados.txt'), 'utf8'), 'conteúdo unicode OK');
    assert.equal(fs.readFileSync(path.join(destTar, ...longPath.split('/')), 'utf8'), 'print("ok")');

    // 2. Fallback TAR streaming puro em Node.js
    const destNode = path.join(tmpRoot, 'out_node');
    const nodeEvents = [];
    const res = await extractTarZst(archivePath, destNode, {
      forcePureNode: true,
      onProgress: (ev) => nodeEvents.push(ev),
    });
    assert.equal(res.engine, 'zstd-node');
    assert.ok(nodeEvents.length >= 2);
    assert.equal(nodeEvents[nodeEvents.length - 1].ratio, 1);
    assert.equal(fs.readFileSync(path.join(destNode, 'pasta, com acento (João)', 'dados.txt'), 'utf8'), 'conteúdo unicode OK');
    assert.equal(fs.readFileSync(path.join(destNode, ...longPath.split('/')), 'utf8'), 'print("ok")');
  });

  it('bloqueia path traversal no extrator TAR puro e em sanitizeExtractPath', async () => {
    assert.throws(() => sanitizeExtractPath(tmpRoot, '../fora.txt'), /path traversal/i);
    assert.throws(() => sanitizeExtractPath(tmpRoot, 'C:\\Windows\\system32\\cmd.exe'), /caminho absoluto/i);
    assert.throws(() => sanitizeExtractPath(tmpRoot, '/etc/passwd'), /caminho absoluto/i);

    const evilTar = buildTarBuffer([{ name: '../../escape.txt', content: 'pwn' }]);
    const dest = path.join(tmpRoot, 'safe_dest');
    await assert.rejects(
      () => extractTarStreamPureNode(Readable.from([evilTar]), dest),
      /path traversal/i
    );
    assert.equal(fs.existsSync(path.join(tmpRoot, 'escape.txt')), false);
  });

  it('extrai .zip real com leitura de EOCD e eventos de progresso', async () => {
    const zipBuf = buildZipBuffer([
      { name: 'python.exe', content: 'zip-python' },
      { name: 'sub/teste.txt', content: 'hello-zip' },
    ]);
    const zipPath = path.join(tmpRoot, 'Pasta, Espaço', 'prebuilt-engine.zip');
    fs.mkdirSync(path.dirname(zipPath), { recursive: true });
    fs.writeFileSync(zipPath, zipBuf);

    assert.equal(readZipEntryCount(zipPath), 2);
    const destZip = path.join(tmpRoot, 'out_zip');
    const events = [];
    await extractZipArchive(zipPath, destZip, {
      onProgress: (ev) => events.push(ev),
    });
    assert.ok(events.length >= 1);
    assert.equal(events[events.length - 1].ratio, 1);
    assert.equal(fs.readFileSync(path.join(destZip, 'sub', 'teste.txt'), 'utf8'), 'hello-zip');
  });

  it('valida patch de ._pth, manifesto de integridade e compatibilidade de versão', () => {
    const engineDir = path.join(tmpRoot, 'engine_manifest');
    fs.mkdirSync(engineDir, { recursive: true });
    const pthFile = path.join(engineDir, 'python311._pth');
    fs.writeFileSync(pthFile, 'python311.zip\n.\n#import site\n', 'utf8');

    const patched = patchEmbeddablePthFiles(engineDir);
    assert.equal(patched, 1);
    const pthAfter = fs.readFileSync(pthFile, 'utf8');
    assert.match(pthAfter, /^import site$/m);
    assert.doesNotMatch(pthAfter, /#import site/);

    writeEngineManifest(engineDir, {
      engineVersion: '1.0.0',
      archiveName: 'engine-runtime.tar.zst',
      archiveSize: 1234,
    });
    assert.equal(fs.existsSync(path.join(engineDir, '.engine-complete')), true);

    const manifest = readEngineManifest(engineDir);
    assert.equal(manifest.engineVersion, '1.0.0');
    assert.equal(isEngineManifestCompatible(manifest, { expectedEngineVersion: '1.0.0' }).compatible, true);

    const mismatch = isEngineManifestCompatible(manifest, { expectedEngineVersion: '2.0.0' });
    assert.equal(mismatch.compatible, false);
    assert.equal(mismatch.reason, 'version_mismatch');
  });

  it('autoSetupPython executa extração atômica, injeta VC++ DLLs, grava manifesto e recupera staging quebrado', async () => {
    const userDataDir = path.join(tmpRoot, 'User, Data (É)');
    fs.mkdirSync(userDataDir, { recursive: true });

    // Simula extração anterior interrompida
    const staleStaging = path.join(userDataDir, 'engine.staging');
    const staleEngine = path.join(userDataDir, 'engine');
    fs.mkdirSync(staleStaging, { recursive: true });
    fs.mkdirSync(staleEngine, { recursive: true });
    fs.writeFileSync(path.join(staleStaging, 'partial.tmp'), 'broken');
    fs.writeFileSync(path.join(staleEngine, 'orphan.tmp'), 'broken');

    const archiveDir = path.join(tmpRoot, 'Installer, Dir');
    fs.mkdirSync(archiveDir, { recursive: true });
    const archivePath = path.join(archiveDir, 'engine-runtime.tar.zst');
    const tarBuf = buildTarBuffer([
      { name: 'engine/python.exe', content: 'fake-py-exe' },
      { name: 'engine/python311._pth', content: 'python311.zip\n.\n#import site\n' },
      { name: 'engine/Lib/site-packages/torch/lib/marker.txt', content: 'torch-lib' },
    ]);
    fs.writeFileSync(archivePath, zlib.zstdCompressSync(tarBuf));

    // Sidecar manifest ao lado do archive
    const sidecarManifestPath = path.join(archiveDir, 'engine-runtime.manifest.json');
    fs.writeFileSync(
      sidecarManifestPath,
      JSON.stringify({
        schemaVersion: 1,
        engineVersion: getExpectedEngineVersion(createMockApp(userDataDir)),
        archiveName: 'engine-runtime.tar.zst',
        size: fs.statSync(archivePath).size,
      }),
      'utf8'
    );
    assert.ok(readSidecarManifest(archivePath));
    assert.ok(computeArchiveFingerprint(archivePath).length === 64);

    const app = createMockApp(userDataDir, { isPackaged: true });
    saveEngineSourcePointer(app, archivePath);

    const progressUpdates = [];
    const pythonExe = await autoSetupPython(
      app,
      (p) => progressUpdates.push(p),
      {
        verifyHealth: async () => ({ healthy: true, exitCode: 0, stderr: '' }),
      }
    );

    const expectedExe = path.join(userDataDir, 'engine', 'python.exe');
    assert.equal(pythonExe, expectedExe);
    assert.equal(fs.existsSync(expectedExe), true);
    assert.equal(fs.existsSync(path.join(userDataDir, 'engine', '.engine-complete')), true);
    assert.equal(fs.existsSync(path.join(userDataDir, 'engine', '.engine-manifest.json')), true);
    assert.equal(fs.existsSync(staleStaging), false);
    assert.equal(fs.existsSync(path.join(userDataDir, 'engine', 'orphan.tmp')), false);
    assert.equal(fs.existsSync(path.join(userDataDir, 'engine', 'msvcp140.dll')), true);

    // Progresso monotonicamente crescente e determinístico até 100%
    assert.ok(progressUpdates.length >= 4);
    assert.equal(progressUpdates[progressUpdates.length - 1].percent, 100);
    assert.equal(progressUpdates[progressUpdates.length - 1].deterministic, true);
    for (let i = 1; i < progressUpdates.length; i++) {
      assert.ok(progressUpdates[i].percent >= progressUpdates[i - 1].percent);
    }

    // Cache respeita versão compatível e invalida quando engineVersion diverge
    const cached = getCachedPython(app);
    assert.ok(cached && cached.found);
    setCachedPython(app, cached);
    const cacheFile = path.join(userDataDir, '.python_cache.json');
    const parsedCache = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
    parsedCache.engineVersion = '99.9.9';
    fs.writeFileSync(cacheFile, JSON.stringify(parsedCache), 'utf8');
    assert.equal(getCachedPython(app), null);
  });

  it('autoSetupPython não grava selo e preserva engine anterior quando health check falha', async () => {
    const userDataDir = path.join(tmpRoot, 'RollbackUser');
    const prevEngineDir = path.join(userDataDir, 'engine');
    fs.mkdirSync(prevEngineDir, { recursive: true });
    fs.writeFileSync(path.join(prevEngineDir, 'python.exe'), 'old-working-engine');
    writeEngineManifest(prevEngineDir, { engineVersion: '0.9.0' });

    const archivePath = path.join(tmpRoot, 'engine-runtime.tar.zst');
    fs.writeFileSync(
      archivePath,
      zlib.zstdCompressSync(buildTarBuffer([{ name: 'python.exe', content: 'new-broken-engine' }]))
    );

    const app = createMockApp(userDataDir, { isPackaged: true });

    await assert.rejects(
      () =>
        autoSetupPython(app, null, {
          archivePath,
          disablePipFallback: true,
          verifyHealth: async () => ({
            healthy: false,
            exitCode: 1,
            stderr: 'ImportError: DLL load failed while importing _imaging',
            isDllError: true,
          }),
        }),
      (err) => err.code === 'VC_RUNTIME_MISSING'
    );

    // Engine antiga foi preservada intacta e staging foi limpo
    assert.equal(fs.readFileSync(path.join(prevEngineDir, 'python.exe'), 'utf8'), 'old-working-engine');
    assert.equal(fs.existsSync(path.join(userDataDir, 'engine.staging')), false);
  });

  it('autoSetupPython aborta no pre-flight com INSUFFICIENT_DISK_SPACE sem tocar em engine/', async () => {
    const userDataDir = path.join(tmpRoot, 'DiskSpaceUser');
    fs.mkdirSync(userDataDir, { recursive: true });
    const archivePath = path.join(tmpRoot, 'engine-runtime.tar.zst');
    fs.writeFileSync(
      archivePath,
      zlib.zstdCompressSync(buildTarBuffer([{ name: 'python.exe', content: 'py' }]))
    );
    const app = createMockApp(userDataDir, { isPackaged: true });

    const probe = checkDiskSpace(userDataDir, 100 * 1024 * 1024 * 1024 * 1024 * 1024);
    if (!probe.skipped) {
      await assert.rejects(
        () =>
          autoSetupPython(app, null, {
            archivePath,
            requiredBytes: 100 * 1024 * 1024 * 1024 * 1024 * 1024,
          }),
        (err) => err.code === 'INSUFFICIENT_DISK_SPACE'
      );
      assert.equal(fs.existsSync(path.join(userDataDir, 'engine')), false);
    }
  });

  it('detectPython limpa engine/ incompleta quando archive existe e verifica saúde detalhada', async () => {
    const userDataDir = path.join(tmpRoot, 'AutoHealDetect');
    const engineDir = path.join(userDataDir, 'engine');
    fs.mkdirSync(engineDir, { recursive: true });
    fs.writeFileSync(path.join(engineDir, 'python.exe'), 'incomplete-without-seal');

    const archivePath = path.join(tmpRoot, 'engine-runtime.tar.zst');
    fs.writeFileSync(
      archivePath,
      zlib.zstdCompressSync(buildTarBuffer([{ name: 'python.exe', content: 'py' }]))
    );

    const app = createMockApp(userDataDir, { isPackaged: true });
    saveEngineSourcePointer(app, archivePath);

    const res = await detectPython(app);
    assert.equal(res.found, false);
    assert.equal(fs.existsSync(engineDir), false);

    // Health check detalhado reporta falha real de executável não-Python
    const detail = await verifyPythonHealthDetailed(process.execPath, [], { timeoutMs: 3000 });
    assert.equal(detail.healthy, false);
  });

  it('validateAndInjectVcRuntimeDlls copia DLLs App-Local e valida estimateRequiredBytes', async () => {
    const engineDir = path.join(tmpRoot, 'vc_target');
    fs.mkdirSync(path.join(engineDir, 'ollama'), { recursive: true });
    const app = createMockApp(tmpRoot, { isPackaged: false });

    const vcRes = validateAndInjectVcRuntimeDlls(app, engineDir);
    assert.equal(vcRes.ok, true);
    assert.ok(vcRes.injectedCount > 0);
    assert.equal(fs.existsSync(path.join(engineDir, 'msvcp140.dll')), true);
    assert.equal(fs.existsSync(path.join(engineDir, 'ollama', 'vcruntime140.dll')), true);

    const archivePath = path.join(tmpRoot, 'sample.tar.zst');
    fs.writeFileSync(archivePath, zlib.zstdCompressSync(buildTarBuffer([{ name: 'x.txt', content: 'abc' }])));
    const reqBytes = estimateRequiredBytes(archivePath);
    assert.ok(reqBytes >= 512 * 1024 * 1024);

    // extractEngineArchive rejeita arquivo inválido com código INVALID_ARCHIVE
    const badPath = path.join(tmpRoot, 'bad.bin');
    fs.writeFileSync(badPath, 'not-an-archive');
    await assert.rejects(() => extractEngineArchive(badPath, path.join(tmpRoot, 'unused')), (err) => err.code === 'INVALID_ARCHIVE');
  });

  it('sidecarManager garante cleanup idempotente, auto-recuperação via watchdog e trava anti-crash-loop (3 quedas em 60s)', async () => {
    const sidecar = require('../../electron/sidecarManager');
    const userDataDir = path.join(tmpRoot, 'WatchdogUser');
    const engineDir = path.join(userDataDir, 'engine');
    fs.mkdirSync(engineDir, { recursive: true });
    fs.writeFileSync(path.join(engineDir, 'python.exe'), 'py');
    const app = createMockApp(userDataDir, { isPackaged: false });
    writeEngineManifest(engineDir, { engineVersion: getExpectedEngineVersion(app) });

    sidecar.resetWatchdogStateForTests();
    sidecar.setCachedPython(app, {
      found: true,
      executable: path.join(engineDir, 'python.exe'),
      source: 'userData',
    });

    const statusEvents = [];
    sidecar.startRuntimeWatchdog(app, {
      onStatusChange: (ev) => statusEvents.push(ev),
      intervalMs: 60000,
    });
    sidecar.stopRuntimeWatchdog();

    // 1. Recuperação bem-sucedida na 1ª tentativa
    let startCalls = 0;
    const recOk = await sidecar.recoverPythonSidecar(app, 'simulated_crash', {
      startBackendFn: () => { startCalls += 1; },
      waitForServerFn: async () => ({ success: true }),
    });
    assert.equal(recOk.success, true);
    assert.equal(startCalls, 1);
    assert.ok(statusEvents.some((e) => e.state === 'reconnecting' && e.attempt === 1));
    assert.ok(statusEvents.some((e) => e.state === 'online' && e.attempt === 1));

    // 2. Simula mais 2 quedas dentro de 60s (total = 3 tentativas) e verifica bloqueio anti-crash-loop na 4ª
    await sidecar.recoverPythonSidecar(app, 'crash_2', {
      startBackendFn: () => { startCalls += 1; },
      waitForServerFn: async () => ({ success: false, reason: 'exited' }),
    });
    await sidecar.recoverPythonSidecar(app, 'crash_3', {
      startBackendFn: () => { startCalls += 1; },
      waitForServerFn: async () => ({ success: false, reason: 'exited' }),
    });

    const blockedRes = await sidecar.recoverPythonSidecar(app, 'crash_4_blocked', {
      startBackendFn: () => { startCalls += 1; },
      waitForServerFn: async () => ({ success: true }),
    });
    assert.equal(blockedRes.success, false);
    assert.equal(blockedRes.reason, 'crash_loop');
    assert.equal(startCalls, 3); // Não disparou o 4º spawn!
    assert.ok(statusEvents.some((e) => e.state === 'failed' && e.reason === 'crash_loop'));

    // 3. Restart manual pelo usuário reseta a janela de crash-loop e recupera
    const manualRes = await sidecar.recoverPythonSidecar(app, 'manual_user_restart', {
      manual: true,
      startBackendFn: () => { startCalls += 1; },
      waitForServerFn: async () => ({ success: true }),
    });
    assert.equal(manualRes.success, true);
    assert.equal(startCalls, 4);

    // 4. Cleanup idempotente: múltiplas chamadas simultâneas retornam a mesma Promise e bloqueiam o watchdog
    const p1 = sidecar.cleanup(app);
    const p2 = sidecar.cleanup(app);
    assert.strictEqual(p1, p2);
    await p1;
    assert.equal(sidecar.isSidecarShuttingDown(), true);

    const afterShutdown = await sidecar.recoverPythonSidecar(app, 'after_quit');
    assert.equal(afterShutdown.success, false);
    assert.equal(afterShutdown.reason, 'shutting_down');
    sidecar.resetWatchdogStateForTests();
  });

  it('updaterManager compara semver, seleciona instalador Windows, extrai SHA-256 e checa releases do GitHub', async () => {
    const updater = require('../../electron/updaterManager');

    assert.equal(updater.compareSemver('1.0.1', '1.0.0'), 1);
    assert.equal(updater.compareSemver('v1.2.0', '1.1.9'), 1);
    assert.equal(updater.compareSemver('1.0.0', '1.0.0'), 0);
    assert.equal(updater.compareSemver('0.9.9', '1.0.0'), -1);

    const sampleSha = 'a'.repeat(64);
    const fakeRelease = {
      tag_name: 'v9.9.9',
      html_url: 'https://github.com/CHARLINKK/Visionary-Studio/releases/tag/v9.9.9',
      body: `Release notes\n${sampleSha}  Visionary-Studio-Setup-9.9.9.exe`,
      assets: [
        { name: 'Visionary Studio Portable 9.9.9.exe', browser_download_url: 'https://example.com/portable.exe' },
        { name: 'Visionary-Studio-Setup-9.9.9.exe', browser_download_url: 'https://example.com/setup.exe' },
      ],
    };

    const chosen = updater.selectWindowsInstallerAsset(fakeRelease.assets);
    assert.equal(chosen.name, 'Visionary-Studio-Setup-9.9.9.exe');
    assert.equal(updater.extractSha256FromRelease(fakeRelease, chosen.name), sampleSha);

    const status = await updater.checkForUpdates({
      fetchFn: async () => fakeRelease,
    });
    assert.equal(status.state, 'available');
    assert.equal(status.latestVersion, '9.9.9');
    assert.equal(status.downloadUrl, 'https://example.com/setup.exe');
    assert.equal(status.expectedSha256, sampleSha);
  });
});
