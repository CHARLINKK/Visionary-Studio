<div align="center">
  <img src="assets/logo3d.png" alt="Visionary Studio" width="96" />
  <h1>Visionary Studio</h1>
  <p>Suite desktop para segmentação de balões, extração óptica (OCR) e tradução assistida de mangás e quadrinhos (EN → PT-BR) com inferência 100% local.</p>

  <p>
    <img src="https://img.shields.io/badge/Electron-41-47848F?style=flat-square&logo=electron&logoColor=white" alt="Electron 41" />
    <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React 19" />
    <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11" />
    <img src="https://img.shields.io/badge/PyTorch-2.11%20%C2%B7%20CUDA%2012.8-EE4C2C?style=flat-square&logo=pytorch&logoColor=white" alt="PyTorch 2.11" />
    <img src="https://img.shields.io/badge/License-ISC-blue?style=flat-square" alt="License ISC" />
  </p>
</div>

O foco do projeto é acelerar a etapa de preparação e tradução até a entrega do roteiro estruturado (`.txt` e `_map.json`) para diagramação em softwares dedicados como Photoshop, Clip Studio Paint ou InDesign.

---

## Arquitetura

```text
Visionary Studio
├── electron/                 # Processo principal, gerenciamento de janela, tray, sidecar Python e auto-updater
├── gui/                      # Interface React 19 + Vite + Konva + Zustand
├── src/
│   ├── server.py             # API FastAPI + WebSocket de telemetria
│   ├── routers/              # Endpoints HTTP (sistema, imagens/thumbnails, pipeline, RPC)
│   ├── batch_pipeline/       # Orquestração de Layout, OCR, ordenação RTL/LTR e tradução
│   ├── model_engines/        # Motores YOLO, Florence-2, gerenciamento de Ollama e instalador isolado
│   ├── api_services/         # Serviços de biblioteca, hardware (NVML/CUDA), explorer e downloads
│   ├── domain/               # Contratos de balões, transações de reordenação e PageStore
│   └── geometry/             # Geometria de polígonos, quadros e calhas (gutters)
├── scripts/                  # Build de release (pré-compilação PEP 552 + empacotamento NSIS)
├── build/                    # Scripts NSIS (uninstaller com limpeza opcional de modelos)
└── tests/                    # Suítes pytest, Vitest (gui) e Node test runner (electron)
```

---

## Stack Técnica

| Camada | Tecnologias |
| :--- | :--- |
| **Shell Desktop** | Electron 41, NSIS (Per-User, Delta Updates), GitHub Releases Updater |
| **Interface** | React 19, Vite 8, Konva (`react-konva`), Zustand |
| **Backend** | Python 3.11, FastAPI, Uvicorn, WebSockets |
| **Visão & OCR** | PyTorch 2.11 (CUDA 12.8), Ultralytics YOLOv8, Florence-2 (`base` / `large`, FP16) |
| **Tradução Local** | Ollama (LLMs locais com suporte a glossários por capítulo) |

---

## Pipeline de Processamento

1. **Detecção e Segmentação (`YOLOv8`):** Mapeamento poligonal de balões (fala / SFX) e quadros, com editor vetorial interativo no Estúdio.
2. **Ordenação de Leitura:** Sequenciamento espacial configurável para leitura oriental (**RTL**) ou ocidental (**LTR**), com agrupamento de balões vinculados (`[CORTE]`).
3. **Extração Textual (`Florence-2`):** Leitura óptica em inglês com preservação de pontuação e limpeza de artefatos.
4. **Tradução Contextual (`Ollama`):** Tradução em lote mantendo contexto do capítulo e exportação sincronizada para `.txt` e `_map.json`.

---

## Desenvolvimento Local

### Pré-requisitos
* **Node.js** 18+
* **Python** 3.11 (ou runtime isolado em `engine/`)
* **GPU NVIDIA** com suporte a CUDA 12.8 (recomendado para inferência local; fallback para CPU disponível)

### Instalação e Execução

```bash
# Dependências Electron e GUI
npm install
npm --prefix gui install

# Dependências Python
pip install -r requirements.txt
pip install -r requirements-ai.txt

# Build da interface e inicialização do app
npm run build:ui
npm start
```

### Testes

```bash
# Backend Python
pytest tests/ -v

# Interface React (Vitest)
npm run test:ui

# Lifecycle e Bootstrap Electron
npm run test:electron
```

### Build de Distribuição (Windows)

```bash
# Pré-compila bytecode PEP 552 (CHECKED_HASH), compila GUI e gera instalador NSIS em dist_installer/
python scripts/build_release.py
```
