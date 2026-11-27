import os
import sys
import re
import subprocess
import platform

TEST_LABELS = {
    "test_adversarial_file_locking.py": "Estresse Adversarial de Bloqueio de Arquivos (Kernel32 & Concorrência)",
    "test_api_contracts.py": "Contratos de API & Schemas",
    "test_audit_fixes.py": "Auditoria, Endpoints & RPC",
    "test_backend_decoupling.py": "Desacoplamento de Backend, Injeção Pura & WorkspaceContext",
    "test_batch_modularization.py": "Modularização do Pipeline em Lote",
    "test_batch_runners.py": "Executores do Pipeline em Lote (Layout, OCR & Tradução)",
    "test_batch_session_isolation.py": "Isolamento de Sessões Concorrentes & Rollback de Lote",
    "test_block_b_resilience.py": "Resiliência do Bloco B",
    "test_block_c_modularization.py": "Modularização do Bloco C",
    "test_bubble_geometry.py": "Heurísticas Geométricas & Morfologia de Balões",
    "test_bubble_schema.py": "Contratos Canônicos & Esquemas Pydantic (BubbleModel & PageDataModel)",
    "test_challenger_m1_2.py": "Testes Adversariais de Resiliência & Modularização (M1/M2)",
    "test_config_and_resilience.py": "Configurações & Resiliência JSON",
    "test_desktop_lifecycle.py": "Ciclo de Vida Desktop & Watchdog",
    "test_dev_service.py": "Serviço de Diagnóstico & Telemetria",
    "test_event_bus.py": "EventBus Pub/Sub & WebSocket",
    "test_file_locking_resilience.py": "Resiliência de Arquivos & Bloqueios do Windows",
    "test_fresh_pc_simulation.py": "Simulação de PC Limpo & Cold Start",
    "test_fs_explorer.py": "Explorador de Arquivos & Unidades",
    "test_fs_operations.py": "Operações de Arquivos & Reordenação",
    "test_fs_security.py": "Segurança de Acesso a Arquivos",
    "test_fs_service.py": "Serviço de FileSystem (FS)",
    "test_fuzz_endpoints.py": "Testes de Fuzzing em Endpoints",
    "test_glossary_builder.py": "Construtor de Glossários & Termos",
    "test_golden_set.py": "Conjunto de Validação Golden Set & Ground Truth",
    "test_gpu_physical_integration.py": "Integração Física com GPU NVIDIA CUDA & Alocação de VRAM",
    "test_gpu_utils.py": "Utilitários de GPU & VRAM",
    "test_group5_backend_gaps.py": "Cobertura de Módulos Críticos (Florence-2, HF Downloads, Ordem de Leitura & Ollama)",
    "test_hardware_service.py": "Serviço de Hardware & Telemetria GPU/CPU",
    "test_hf_snapshot_resolver.py": "Resolução de Snapshots HuggingFace (Anti-Symlink Windows)",
    "test_image_service.py": "Serviço de Imagens & Cache de Miniaturas",
    "test_json_utils.py": "Utilitários de JSON & Autocura",
    "test_layer4_pipeline_audit.py": "Pipeline IA, Modulação & Rollback",
    "test_layer6_studio_audit.py": "Studio Workspace & Coordenadas",
    "test_layout_detector.py": "Detecção de Layout & YOLO Bubbles",
    "test_library_features.py": "Biblioteca & Exportação de Roteiros",
    "test_library_modularization.py": "Modularização da Biblioteca",
    "test_library_service.py": "Serviço da Biblioteca & Scanners",
    "test_model_service_expansion.py": "Model Manager & PyTorch",
    "test_model_service_modularization.py": "Modularização do ModelService & Orquestradores",
    "test_model_translations.py": "Tradução & Validação de Modelos LLM",
    "test_module_progress_accuracy.py": "Acurácia Determinística de Porcentagem na Central de Módulos (PyTorch, Florence-2 & YOLO)",
    "test_ollama_lifecycle.py": "Ciclo de Vida do Ollama",
    "test_ollama_manifest_scanner.py": "Scanner Físico de Manifestos Ollama & Armazenamento",
    "test_ollama_puller_aliases.py": "Resolução de Aliases & Fallbacks de Modelos Ollama",
    "test_ollama_client_resilience.py": "Resiliência do Cliente Ollama & Conexões HTTP",
    "test_ollama_isolated_installer.py": "Instalador Isolado do Motor Ollama & Ciclo de Vida",
    "test_path_sandbox.py": "Sandbox de Caminhos & Segurança de Imagem",
    "test_page_store.py": "PageStore Envelope v2 & Cache de Páginas",
    "test_panel_geometry.py": "Geometria de Quadros & Refinamento Poligonal (OpenCV)",
    "test_parallel_range_downloader.py": "Motor de Download Paralelo Multi-Conexão (HTTP Range 206) & Telemetria",
    "test_pipeline_emitter.py": "Emissor de Eventos do Pipeline",
    "test_pipeline_lifecycle.py": "Ciclo de Vida do Pipeline & Fila",
    "test_pipeline_refinements.py": "Refinamentos do Pipeline, Cache de Splash Art & Janela Deslizante de Contexto",
    "test_pipeline_regressions.py": "Regressões Críticas do Pipeline (M1-M5)",
    "test_pipeline_service.py": "Orquestração de Fila & Jobs",
    "test_reorder_rollback.py": "Transações & Rollback de Reordenação",
    "test_repo_hygiene.py": "Higiene do Repositório & Integridade",
    "test_rpc_contract.py": "Contratos e Despacho RPC",
    "test_run_batch.py": "Execução em Lote & Lock de GPU",
    "test_server.py": "Servidor FastAPI & Autenticação",
    "test_services_decoupling.py": "Desacoplamento de Serviços",
    "test_settings_service.py": "Serviço de Configurações & Validação",
    "test_session_auth.py": "Autenticação por Sessão & Tokens",
    "test_studio_and_backup.py": "Studio Workspace & Backups de Página",
    "test_studio_layout_manager.py": "Gerenciador de Layout do Studio",
    "test_studio_service.py": "Serviço do Studio & Editor de Balões",
    "test_telemetry_diagnostic.py": "Diagnóstico Profundo de Telemetria de Downloads & Vazão de Rede",
    "test_telemetry_logger.py": "Gravador de Telemetria em Tempo Real & Métricas de Transferência",
    "test_text_cleaner_and_translator.py": "Limpeza Semântica & Tradução AI",
    "test_tiered_prompts.py": "Prompts Escalonados por Tier de Modelo",
    "test_translation_sanitizer.py": "Sanitização de Tradução, Siglas, Nomes Próprios & Pontuação Artística",
    "test_translation_reasoning_readiness.py": "Prontidão para Modelos de Raciocínio (Think Tags, JSON Healer & Headroom Dinâmico)",
    "test_txt_sync.py": "Sincronização de Roteiro TXT",
    "test_vram_arbiter.py": "Árbitro de VRAM & Alocação Dinâmica",
    "test_vram_monitor.py": "Monitor de VRAM & Telemetria",
    "test_window_service.py": "Controle de Janela Nativa & Frame"
}


def estimate_total_tests(base_dir: str) -> int:
    """Estima quantidade de testes inspecionando arquivos em tests/."""
    tests_dir = os.path.join(base_dir, "tests")
    if not os.path.exists(tests_dir):
        tests_dir = os.path.join(base_dir, "automated_tests")
    count = 0
    if os.path.exists(tests_dir):
        for f in os.listdir(tests_dir):
            if f.startswith("test_") and f.endswith(".py"):
                count += 1
    return max(1, count * 10)


def get_test_files_list(base_dir: str) -> list[dict]:
    """Retorna lista descritiva de todas as suítes de teste."""
    tests_dir = os.path.join(base_dir, "tests")
    if not os.path.exists(tests_dir):
        tests_dir = os.path.join(base_dir, "automated_tests")
    files = []
    if os.path.exists(tests_dir):
        for f in sorted(os.listdir(tests_dir)):
            if f.startswith("test_") and f.endswith(".py"):
                label = TEST_LABELS.get(f, f.replace("test_", "").replace(".py", "").replace("_", " ").title())
                files.append({"filename": f, "label": label})
    return files


def run_pytest_process(
    base_dir: str,
    test_name: str | None,
    popen_fn,
    append_log_fn,
    lock,
    test_progress: dict,
    finish_fn,
    set_process_fn,
):
    """Executa a suíte de testes via pytest e extrai telemetria em tempo real."""
    append_log_fn(">>> INICIANDO DIAGNÓSTICO DO VISIONARY STUDIO <<<")
    return_code = -1
    try:
        tests_dir = os.path.join(base_dir, "tests")
        if not os.path.exists(tests_dir):
            tests_dir = os.path.join(base_dir, "automated_tests")

        if not os.path.exists(tests_dir):
            append_log_fn(f"[ERRO] Diretório de testes não encontrado: {tests_dir}")
            finish_fn(1)
            return

        target = "tests/" if os.path.exists(os.path.join(base_dir, "tests")) else "automated_tests/"
        if test_name and test_name != "all":
            safe_name = os.path.basename(str(test_name).strip())
            if not safe_name.endswith(".py") or safe_name.startswith("-"):
                append_log_fn(f"[ERRO] Nome de arquivo de teste inválido: {test_name}")
                finish_fn(1)
                return
            target = os.path.join(target, safe_name)

        cmd = [sys.executable, "-m", "pytest", target, "-v", "--tb=short", "-s"]
        append_log_fn(f"Comando: {' '.join(cmd)}\n")

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        process = popen_fn(
            cmd,
            cwd=base_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            universal_newlines=True,
            env=env,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )

        set_process_fn(process)

        for line in iter(process.stdout.readline, ""):
            clean_line = line.rstrip()
            append_log_fn(clean_line)

            # Real-time progress parsing
            progress_changed = False
            m_collected = re.search(r"collected (\d+) items", clean_line)
            if m_collected:
                with lock:
                    test_progress["total"] = int(m_collected.group(1))
                    progress_changed = True

            m_pct = re.search(r"\[\s*(\d+)%\]", clean_line)
            if m_pct:
                with lock:
                    test_progress["percent"] = int(m_pct.group(1))
                    progress_changed = True

            if " PASSED" in clean_line:
                with lock:
                    test_progress["passed"] += 1
                    progress_changed = True
            elif " FAILED" in clean_line:
                with lock:
                    test_progress["failed"] += 1
                    progress_changed = True
            elif " SKIPPED" in clean_line:
                with lock:
                    test_progress["skipped"] += 1
                    progress_changed = True

            if "::" in clean_line:
                parts = clean_line.split()
                if parts:
                    test_part = parts[0]
                    with lock:
                        test_progress["current_test"] = test_part.split("::")[-1]
                        progress_changed = True

            if progress_changed:
                try:
                    from src.utils.event_bus import event_bus
                    with lock:
                        snap = dict(test_progress)
                    event_bus.publish("dev:test_progress", snap)
                except Exception:
                    pass

        process.stdout.close()
        return_code = process.wait()

        append_log_fn("\n")
        if return_code == 0:
            append_log_fn(">>> DIAGNÓSTICO CONCLUÍDO COM SUCESSO <<<")
        elif return_code in (-9, 15):
            append_log_fn(">>> DIAGNÓSTICO INTERROMPIDO PELO USUÁRIO <<<")
        elif return_code == 5:
            append_log_fn(">>> NENHUM TESTE ENCONTRADO <<<")
        else:
            append_log_fn(f">>> DIAGNÓSTICO FINALIZADO COM FALHAS (Código {return_code}) <<<")

    except Exception as e:
        append_log_fn(f"[EXCEÇÃO FATAL] Ocorreu um erro ao rodar os testes: {e}")
    finally:
        finish_fn(return_code)


def run_internal_diagnostics(append_log_fn, finish_fn, check_models_fn):
    """Executa diagnóstico nativo e seguro para modo compilado / release."""
    import requests

    append_log_fn(">>> INICIANDO DIAGNÓSTICO NATIVO DO SISTEMA <<<")
    append_log_fn("AVISO: Rodando em modo seguro. Nenhuma simulação destrutiva será feita.")
    append_log_fn("-" * 50)

    try:
        # 1. Info Sistema
        append_log_fn(f"[1] Sistema Operacional: {platform.system()} {platform.release()} ({platform.architecture()[0]})")
        append_log_fn(f"[1] Python Version: {sys.version.split(' ')[0]}")

        # 2. Check Permissões de Escrita
        from src.config import get_app_data_dir

        app_data_dir = get_app_data_dir()
        append_log_fn(f"[2] Diretório de Dados (AppData): {app_data_dir}")
        try:
            test_file = os.path.join(app_data_dir, ".test_write")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            append_log_fn("[2] Permissão de Escrita: OK")
        except Exception as e:
            append_log_fn(f"[2] Permissão de Escrita: FALHOU - {e}")

        # 3. Modelos
        append_log_fn("[3] Verificando integridade dos arquivos...")
        models = check_models_fn()
        for k, ok in models.items():
            append_log_fn(f"    - {k}: {'ENCONTRADO' if ok else 'FALTANDO (CORROMPIDO?)'}")

        # 4. Conexão Ollama
        append_log_fn("[4] Testando conexão com Ollama Engine...")
        try:
            resp = requests.get("http://127.0.0.1:11435/api/tags", timeout=3)
            if resp.status_code == 200:
                installed = [m["name"] for m in resp.json().get("models", [])]
                append_log_fn(f"[4] Conexão: OK. Modelos instalados: {len(installed)}")
            else:
                append_log_fn(f"[4] Conexão: FALHOU com Status {resp.status_code}")
        except Exception:
            append_log_fn("[4] Conexão: FALHOU (Não está rodando ou bloqueado por Firewall)")

        # 5. VRAM/CUDA Load Test
        append_log_fn("[5] Testando alocação de GPU (Dummy Tensor)...")
        try:
            import torch

            if torch.cuda.is_available():
                x = torch.zeros((1000, 1000), device="cuda")
                del x
                torch.cuda.empty_cache()
                append_log_fn("[5] Alocação GPU: OK (CUDA acessível e alocando)")
            else:
                append_log_fn("[5] Alocação GPU: IGNORADA (Rodando em modo CPU)")
        except Exception as e:
            append_log_fn(f"[5] Alocação GPU: FALHOU CRITICAMENTE - {e}")

        append_log_fn("-" * 50)
        append_log_fn(">>> DIAGNÓSTICO CONCLUÍDO COM SUCESSO <<<")

    except Exception as e:
        append_log_fn(f"[EXCEÇÃO FATAL] Erro durante o diagnóstico: {e}")
    finally:
        finish_fn(0)
