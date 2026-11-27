@echo off
setlocal enabledelayedexpansion
title Visionary Studio - Compilador de Executaveis
color 0b

:: Garante execucao no diretorio raiz do projeto mesmo se invocado por duplo clique em scripts\
cd /d "%~dp0\.."

echo.
echo ===================================================
echo     GERADOR DE INSTALADOR DO VISIONARY STUDIO
echo ===================================================
echo.

where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] O utilitario 'npm' nao foi encontrado no PATH do sistema.
    echo Instale o Node.js v18+ para continuar.
    pause
    exit /b 1
)

echo Compilando Interface Visual (React/Vite) e empacotando Instalador (NSIS)...
call npm run dist:installer
if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Falha durante a compilacao ou empacotamento do instalador (dist:installer).
    echo O processo foi abortado para evitar a geracao de instalador quebrado.
    pause
    exit /b %errorlevel%
)

:: Finaliza copiando o pacote de runtime Python e gerando engine-runtime.manifest.json
where python >nul 2>&1
if %errorlevel% equ 0 (
    python scripts\build_release.py --finalize-only
    if %errorlevel% neq 0 (
        echo [AVISO] Falha ao gerar manifesto do runtime via build_release.py.
    )
) else if exist "assets\python\engine-runtime.tar.zst" (
    echo.
    echo Copiando engine-runtime.tar.zst para a pasta dist_installer...
    copy /y "assets\python\engine-runtime.tar.zst" "dist_installer\engine-runtime.tar.zst" >nul
) else (
    echo.
    echo [AVISO] assets\python\engine-runtime.tar.zst nao encontrado.
)

echo.
echo ===================================================
echo COMPILACAO CONCLUIDA COM SUCESSO!
echo Os executaveis foram gerados na pasta "dist_installer"
echo ===================================================
pause
