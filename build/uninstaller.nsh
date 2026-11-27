!macro KillVisionaryProcesses
  # Encerra a instância principal (inclusive minimizada no System Tray) e aguarda liberação dos handles
  nsExec::Exec 'taskkill.exe /IM "Visionary Studio.exe" /F /T'
  Sleep 600

  # Encerra cirurgicamente apenas processos python.exe/ollama.exe executando dentro das pastas do Visionary
  nsExec::Exec `powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -Command "$$targets = @((Join-Path $$env:APPDATA 'Visionary Studio\engine'), (Join-Path $$env:LOCALAPPDATA 'Programs\Visionary Studio')); Get-CimInstance Win32_Process | Where-Object { $$p = $$_.ExecutablePath; $$p -and ($$targets | Where-Object { $$p.StartsWith($$_.TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase) }) } | ForEach-Object { Stop-Process -Id $$_.ProcessId -Force -ErrorAction SilentlyContinue }"`
  Sleep 400
!macroend

!macro customInit
  SetShellVarContext current
  !insertmacro KillVisionaryProcesses
!macroend

!macro customInstall
  SetShellVarContext current

  # Registra em UTF-16LE com BOM (suporte pleno a acentos, espaços e vírgulas) a localização do pacote sidecar
  IfFileExists "$EXEDIR\engine-runtime.tar.zst" 0 CheckFallbackZip
    CreateDirectory "$APPDATA\Visionary Studio"
    FileOpen $0 "$APPDATA\Visionary Studio\engine-source.path" w
    FileWriteWord $0 0xFEFF
    FileWriteUTF16LE $0 "$EXEDIR\engine-runtime.tar.zst"
    FileClose $0
    Goto EnginePointerDone

  CheckFallbackZip:
  IfFileExists "$EXEDIR\prebuilt-engine.zip" 0 EnginePointerDone
    CreateDirectory "$APPDATA\Visionary Studio"
    FileOpen $0 "$APPDATA\Visionary Studio\engine-source.path" w
    FileWriteWord $0 0xFEFF
    FileWriteUTF16LE $0 "$EXEDIR\prebuilt-engine.zip"
    FileClose $0

  EnginePointerDone:
!macroend

!macro customUnInstall
  SetShellVarContext current
  !insertmacro KillVisionaryProcesses

  # Quando o app for atualizado via instalador, ele preserva silenciosamente os dados e pula o prompt.
  ${if} ${isUpdated}
    Goto done
  ${endIf}

  # Caixa de diálogo perguntando ao usuário (em português do Brasil)
  MessageBox MB_YESNO "Você deseja apagar todos os modelos de Inteligência Artificial (~23GB), caches e configurações salvas do Visionary Studio?$\r$\n$\r$\n• Escolha 'Sim' para uma desinstalação completa (Total Wipe), liberando todo o espaço no disco.$\r$\n• Escolha 'Não' se pretende reinstalar futuramente e deseja preservar os arquivos pesados de IA já baixados." /SD IDNO IDNO Skipped IDYES Accepted

  Accepted:
    SetShellVarContext current

    # 1. Remove apenas os modelos do Visionary (sem apagar modelos pessoais de terceiros em .ollama)
    nsExec::Exec `powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -Command "$$ollama = Join-Path $$env:APPDATA 'Visionary Studio\engine\ollama\ollama.exe'; if (-not (Test-Path -LiteralPath $$ollama)) { $$cmd = Get-Command ollama -ErrorAction SilentlyContinue; if ($$cmd) { $$ollama = $$cmd.Source } else { $$ollama = $$null } }; if ($$ollama) { foreach ($$port in @(11434, 11435)) { $$tcp = New-Object System.Net.Sockets.TcpClient; try { $$ar = $$tcp.BeginConnect('127.0.0.1', $$port, $$null, $$null); if ($$ar.AsyncWaitHandle.WaitOne(150)) { $$tcp.EndConnect($$ar); $$env:OLLAMA_HOST = '127.0.0.1:' + $$port; foreach ($$m in @('amadeus:32b','amadeus:14b','amadeus:7b','hf.co/mradermacher/AV-BI-Qwen2.5-32B-PT-BR-Instruct-GGUF:Q4_K_M','hf.co/mradermacher/Amadeus-Verbo-FI-Qwen2.5-14B-PT-BR-Instruct-GGUF:Q4_K_M','hf.co/mradermacher/AV-BI-Qwen2.5-7B-PT-BR-Instruct-GGUF:Q4_K_M','qwen2.5:32b')) { & $$ollama rm $$m 2>$$null | Out-Null } } } catch {} finally { $$tcp.Dispose() } } }"`

    # 2. Garante ausência de locks antes da exclusão recursiva
    !insertmacro KillVisionaryProcesses

    # 3. Remove pasta completa de dados, modelos HF/YOLO, caches e engine isolada do usuário
    !ifdef APP_PRODUCT_FILENAME
      RMDir /r "$APPDATA\${APP_PRODUCT_FILENAME}"
      RMDir /r "$LOCALAPPDATA\${APP_PRODUCT_FILENAME}"
      RMDir /r "$LOCALAPPDATA\${APP_PRODUCT_FILENAME}-updater"
    !endif
    RMDir /r "$APPDATA\Visionary Studio"
    RMDir /r "$LOCALAPPDATA\Visionary Studio"
    RMDir /r "$LOCALAPPDATA\Visionary Studio-updater"
    Goto done

  Skipped:
    Goto done

  done:
!macroend
