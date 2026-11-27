<div align="center">
  <img src="assets/logo3d.png" alt="Visionary Studio" width="92" />
  <h1>Visionary Studio</h1>
  <p>Suite desktop para delimitação vetorial de balões, extração óptica (OCR) e tradução local de mangás e quadrinhos (EN → PT-BR).</p>

  <p>
    <img src="https://img.shields.io/badge/Platform-Windows%20x64-0078D6?style=flat-square&logo=windows&logoColor=white" alt="Windows x64" />
    <img src="https://img.shields.io/badge/Electron-41-47848F?style=flat-square&logo=electron&logoColor=white" alt="Electron 41" />
    <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React 19" />
    <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11" />
    <img src="https://img.shields.io/badge/PyTorch-2.11%20%C2%B7%20CUDA%2012.8-EE4C2C?style=flat-square&logo=pytorch&logoColor=white" alt="PyTorch 2.11" />
    <img src="https://img.shields.io/badge/License-ISC-blue?style=flat-square" alt="License ISC" />
  </p>

  <p>
    <a href="#m%C3%B3dulos-da-interface">Interface</a> ·
    <a href="#pipeline-de-processamento">Pipeline</a> ·
    <a href="#escopo-e-sa%C3%ADdas">Escopo</a> ·
    <a href="#arquitetura">Arquitetura</a> ·
    <a href="#desenvolvimento-local">Instalação</a>
  </p>
</div>

---

## Visão Geral

O **Visionary Studio** automatiza a etapa de extração e tradução de capítulos inteiros rodando 100% na máquina do usuário, sem dependência de APIs externas ou envio de arquivos para nuvem.

Em vez de misturar tradução com edição gráfica pesada, o software foca exclusivamente na precisão da leitura e entrega do roteiro estruturado para o fluxo editorial em softwares como **Adobe Photoshop**, **Clip Studio Paint** ou **InDesign**.

---

## Módulos da Interface

* **Estúdio (`Konva Canvas`):** Editor vetorial interativo para delimitação de balões por caixas retangulares ou polígonos orgânicos (edição direta de vértices), classificação `Fala ⇄ SFX`, união de balões cortados (`[CORTE]`), reordenação de leitura e inspeção dos modos Layout, OCR e Tradução.
* **Biblioteca & Letreiramento:** Visualizador de roteiro nos modos *Roteiro*, *Lado a Lado* (imagem sincronizada com auto-zoom no balão ativo) e *Texto Puro*. Permite cópia contínua balão a balão via teclado (`Espaço` / `Enter`), histórico de itens colados, busca no capítulo (`Ctrl+F`), edição inline e exportação em `.txt` ou `.rtf`.
* **Mesa de Luz (`Lightbox`):** Grade com miniaturas em cache para organização visual do capítulo, pré-visualização rápida em resolução original (*Quick Look*), reordenação *drag-and-drop*, junção/divisão de páginas duplas e exclusão em lote.
* **Central de Módulos & Hardware:** Telemetria em tempo real de GPU/VRAM (NVML/CUDA), instalação isolada do runtime PyTorch/Ollama sem poluir variáveis globais do sistema e gerenciamento de modelos Hugging Face e GGUF.

---

## Pipeline de Processamento

1. **Detecção e Segmentação (`YOLOv8`):** Mapeamento de balões e quadros da página com geração de contornos poligonais.
2. **Ordenação de Leitura:** Sequenciamento topológico configurável para fluxo oriental (**RTL**) ou ocidental (**LTR**), respeitando quadros e agrupamentos vinculados.
3. **Extração Textual (`Florence-2`):** Reconhecimento óptico em inglês (`base` / `large`, FP16 na GPU) com limpeza de hifenização e sincronização de pontuação dramática.
4. **Tradução Contextual (`Ollama`):** Tradução em lote EN → PT-BR com suporte a glossários por obra/capítulo e controle de VRAM entre estágios.

---

## Escopo e Saídas

* **Formatos gerados:** Roteiros estruturados por capítulo (`.txt`), roteiro formatado para letristas (`.txt` limpo / `.rtf`) e mapas de coordenadas/metadados por página (`_map.json`).
* **Fora de escopo:** Edição de pixels, remoção de texto por *inpainting*, diagramação automática de páginas e renderização de lettering final sobre a arte.

---

## Arquitetura

```text
Visionary Studio
├── electron/                 # Main process, janela, System Tray, sidecar FastAPI e auto-updater (GitHub Releases)
├── gui/                      # Frontend React 19 + Vite 8 + Konva + Zustand
├── src/
│   ├── server.py             # Servidor FastAPI, auth local por token de sessão e WebSocket (/ws/logs)
│   ├── routers/              # Rotas HTTP (healthcheck, imagens/thumbnails LRU, pipeline, RPC)
│   ├── batch_pipeline/       # Orquestração de Layout, OCR, ordenação RTL/LTR e tradução
│   ├── model_engines/        # Motores YOLO, Florence-2, gerenciamento de Ollama e instalador isolado
│   ├── api_services/         # Serviços de biblioteca, hardware (NVML/CUDA), explorer e downloads
│   ├── domain/               # Contratos de balões, PageStore e transações de reordenação
│   └── geometry/             # Polígonos, quadros e detecção de calhas (gutters)
├── scripts/                  # Build de release (pré-compilação PEP 552 + empacotamento NSIS)
├── build/                    # Scripts NSIS (instalação Per-User e uninstaller com opção de limpeza de modelos)
└── tests/                    # Suítes pytest, Vitest (gui) e Node test runner (electron)
```

---

## Stack Técnica

| Camada | Tecnologias |
| :--- | :--- |
| **Shell Desktop** | Electron 41, NSIS (`Per-User`, Delta Packages), Auto-Updater via GitHub Releases |
| **Interface** | React 19, Vite 8, Konva (`react-konva`), Zustand |
| **Backend** | Python 3.11, FastAPI, Uvicorn, WebSockets, Pillow |
| **Visão & OCR** | PyTorch 2.11 (`CUDA 12.8`), Ultralytics YOLOv8, Florence-2 (`FP16`) |
| **Tradução Local** | Ollama (LLMs locais com gerenciamento de VRAM e glossários) |

---

## Desenvolvimento Local

### Pré-requisitos
* **Windows 10/11 (x64)**
* **Node.js 20+** (20.19+ ou 22+)
* **Python 3.11** (ou runtime embarcado em `engine/`)
* **GPU NVIDIA** com suporte a CUDA 12.8 recomendado (fallback para CPU suportado)

### Instalação e Execução

```bash
# 1. Dependências Electron e Interface
npm install
npm --prefix gui install

# 2. Dependências Python (runtime + IA)
pip install -r requirements.txt
pip install -r requirements-ai.txt

# 3. Build do frontend e execução do aplicativo
npm run build:ui
npm start
```

### Testes

```bash
# Instalar dependências de teste Python (pytest)
pip install -r requirements-dev.txt

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

---

## Licença

Distribuído sob a licença **ISC**. Consulte o arquivo [LICENSE](LICENSE) para mais detalhes.
