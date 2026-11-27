"""
Operações de modelos Ollama: pull com streaming/ETA, cancelamento, deleção,
benchmark de tradução e cálculo de armazenamento de manifestos.
"""

import json
import threading
import time
import requests

from src.config import Config


MODEL_PULL_ALIASES = {
    "amadeus:7b": "hf.co/mradermacher/AV-BI-Qwen2.5-7B-PT-BR-Instruct-GGUF:Q4_K_M",
    "amadeus:14b": "hf.co/mradermacher/Amadeus-Verbo-FI-Qwen2.5-14B-PT-BR-Instruct-GGUF:Q4_K_M",
    "amadeus:32b": "hf.co/mradermacher/AV-BI-Qwen2.5-32B-PT-BR-Instruct-GGUF:Q4_K_M",
}

REVERSE_MODEL_ALIASES = {
    "hf.co/mradermacher/AV-BI-Qwen2.5-7B-PT-BR-Instruct-GGUF:Q4_K_M": "amadeus:7b",
    "hf.co/mradermacher/AV-BI-Qwen2.5-7B-PT-BR-Instruct-i1-GGUF:Q4_K_M": "amadeus:7b",
    "mradermacher/AV-BI-Qwen2.5-7B-PT-BR-Instruct-GGUF:Q4_K_M": "amadeus:7b",
    "mradermacher/AV-BI-Qwen2.5-7B-PT-BR-Instruct-i1-GGUF:Q4_K_M": "amadeus:7b",
    "hf.co/mradermacher/Amadeus-Verbo-FI-Qwen2.5-14B-PT-BR-Instruct-GGUF:Q4_K_M": "amadeus:14b",
    "mradermacher/Amadeus-Verbo-FI-Qwen2.5-14B-PT-BR-Instruct-GGUF:Q4_K_M": "amadeus:14b",
    "hf.co/mradermacher/AV-BI-Qwen2.5-32B-PT-BR-Instruct-GGUF:Q4_K_M": "amadeus:32b",
    "mradermacher/AV-BI-Qwen2.5-32B-PT-BR-Instruct-GGUF:Q4_K_M": "amadeus:32b",
}


def cancel_ollama_download(mgr, model_name: str) -> dict:
    with mgr._get_lock():
        cancelled = False
        if hasattr(mgr, "_cancel_events") and model_name in mgr._cancel_events:
            mgr._cancel_events[model_name].set()
            mgr._cancel_events.pop(model_name, None)
            cancelled = True

        if hasattr(mgr, "_active_sessions") and model_name in mgr._active_sessions:
            try:
                mgr._active_sessions[model_name].close()
            except Exception:
                pass
            mgr._active_sessions.pop(model_name, None)
            cancelled = True

        dls = mgr._get_downloads()
        if model_name in dls:
            del dls[model_name]
            cancelled = True

        if hasattr(mgr, "_completed_models"):
            mgr._completed_models.discard(model_name)
            if ":" not in model_name:
                mgr._completed_models.discard(f"{model_name}:latest")
            else:
                mgr._completed_models.discard(model_name.split(":")[0])

    if cancelled:
        if hasattr(mgr, "invalidate_tags_cache"):
            mgr.invalidate_tags_cache()
        try:
            from src.model_engines.ollama_manifest_scanner import invalidate_manifests_cache
            invalidate_manifests_cache()
        except Exception:
            pass
        mgr.notify_progress(throttle_interval=0.0)
        return {"success": True}
    return {"success": False, "message": "Download não encontrado"}


def delete_ollama_model(mgr, model_name: str, session_factory=None) -> dict:
    if not model_name or not str(model_name).strip():
        return {"success": False, "error": "Nome de modelo inválido."}
    make_session = session_factory or requests.Session
    try:
        # Descarrega o modelo da VRAM do Ollama antes da remoção dos blobs físicos
        try:
            from src.utils.gpu_utils import unload_ollama_models
            unload_ollama_models(model_name)
        except Exception:
            pass

        with mgr._get_lock():
            if hasattr(mgr, "_completed_models"):
                mgr._completed_models.discard(model_name)
                if ":" not in model_name:
                    mgr._completed_models.discard(f"{model_name}:latest")
                else:
                    mgr._completed_models.discard(model_name.split(":")[0])
            dls = mgr._get_downloads()
            dls.pop(model_name, None)
            if ":" not in model_name:
                dls.pop(f"{model_name}:latest", None)
            else:
                dls.pop(model_name.split(":")[0], None)
        mgr.notify_progress(throttle_interval=0.0)

        session = make_session()
        session.trust_env = False
        base_url = Config.get("ollama_url", "http://127.0.0.1:11435/api").replace("localhost", "127.0.0.1").rstrip("/")
        url = f"{base_url}/delete"
        resp = session.delete(url, json={"name": model_name}, timeout=10)
        alt_names = []
        if model_name in MODEL_PULL_ALIASES:
            alt_names.append(MODEL_PULL_ALIASES[model_name])
        if model_name in REVERSE_MODEL_ALIASES:
            alt_names.append(REVERSE_MODEL_ALIASES[model_name])
        for alt in alt_names:
            try:
                session.delete(url, json={"name": alt}, timeout=5)
            except Exception:
                pass

        if resp.status_code in [200, 204] or (resp.status_code == 404 and alt_names):
            if hasattr(mgr, "invalidate_tags_cache"):
                mgr.invalidate_tags_cache()
            try:
                from src.model_engines.ollama_manifest_scanner import invalidate_manifests_cache
                invalidate_manifests_cache()
            except Exception:
                pass
            if hasattr(mgr, "api") and mgr.api:
                if hasattr(mgr.api, "hf_orchestrator") and hasattr(mgr.api.hf_orchestrator, "invalidate_storage_cache"):
                    mgr.api.hf_orchestrator.invalidate_storage_cache()
                elif hasattr(mgr.api, "_model_service") and hasattr(mgr.api._model_service, "hf_orchestrator"):
                    mgr.api._model_service.hf_orchestrator.invalidate_storage_cache()
            try:
                from src.utils.event_bus import event_bus
                event_bus.publish("model_inventory_changed", {"action": "delete", "model": model_name, "success": True})
            except Exception:
                pass
            mgr.notify_progress(throttle_interval=0.0)
            return {"success": True}
        return {"success": False, "error": f"Código {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def test_ollama_translation(mgr, model_name: str, prompt: str = None, session_factory=None) -> dict:
    if not model_name or not str(model_name).strip():
        return {"success": False, "error": "Nome de modelo não especificado."}

    if not prompt or not str(prompt).strip():
        prompt = "Traduza para PT-BR com naturalidade e estilo autêntico de mangá: 'Hold on tight! The demon realm gate is collapsing!'"

    make_session = session_factory or requests.Session
    base_url = Config.get("ollama_url", "http://127.0.0.1:11435/api").replace("localhost", "127.0.0.1").rstrip("/")
    url = f"{base_url}/generate"
    t0 = time.time()
    try:
        session = make_session()
        session.trust_env = False
        resp = session.post(
            url,
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False,
            },
            timeout=45,
        )
        if resp.status_code == 404 and model_name in MODEL_PULL_ALIASES:
            resp = session.post(
                url,
                json={
                    "model": MODEL_PULL_ALIASES[model_name],
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=45,
            )

        if resp.status_code != 200:
            return {"success": False, "error": f"Erro Ollama HTTP {resp.status_code}: {resp.text}"}

        data = resp.json()
        eval_count = data.get("eval_count", 0)
        eval_duration_ns = data.get("eval_duration", 0)
        total_duration_sec = round(time.time() - t0, 2)

        tokens_per_sec = 0.0
        if eval_duration_ns > 0 and eval_count > 0:
            tokens_per_sec = round(eval_count / (eval_duration_ns / 1e9), 1)

        return {
            "success": True,
            "model": model_name,
            "translation": data.get("response", "").strip(),
            "eval_count": eval_count,
            "tokens_per_second": tokens_per_sec,
            "duration_seconds": total_duration_sec,
        }
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Servidor Ollama não está acessível. Verifique se o serviço está ativo."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_ollama_models_details(mgr) -> dict:
    """
    Retorna mapa de metadados detalhados (tamanho em bytes e formatado) de cada modelo Ollama,
    combinando o scanner de manifestos em disco com o cache do daemon HTTP.
    """
    details = {}
    try:
        from src.model_engines.ollama_manifest_scanner import scan_local_manifests
        manifests = scan_local_manifests(parse_sizes=True)
        for m in manifests:
            name = m.get("name")
            if name:
                sz_bytes = m.get("size", 0)
                sz_gb = sz_bytes / (1024 ** 3)
                details[name] = {
                    "size": sz_bytes,
                    "sizeFormatted": f"{sz_gb:.1f} GB" if sz_gb >= 1.0 else f"{sz_bytes / (1024**2):.0f} MB",
                }
    except Exception:
        pass

    data = getattr(mgr, "_tags_cache_data", None)
    if isinstance(data, dict) and "models" in data:
        for m in data.get("models", []):
            name = m.get("name")
            if name and name not in details:
                sz_bytes = m.get("size", 0)
                sz_gb = sz_bytes / (1024 ** 3)
                details[name] = {
                    "size": sz_bytes,
                    "sizeFormatted": f"{sz_gb:.1f} GB" if sz_gb >= 1.0 else f"{sz_bytes / (1024**2):.0f} MB",
                }
    for alias_friendly, alias_remote in MODEL_PULL_ALIASES.items():
        if alias_remote in details and alias_friendly not in details:
            details[alias_friendly] = details[alias_remote]
        elif alias_friendly in details and alias_remote not in details:
            details[alias_remote] = details[alias_friendly]

    return details


def pull_ollama_model(mgr, model_name: str, session_factory=None) -> dict:
    if not model_name or not str(model_name).strip():
        return {"success": False, "message": "Nome de modelo inválido."}

    raw_model_name = str(model_name).strip()
    target_remote_name = MODEL_PULL_ALIASES.get(raw_model_name, raw_model_name)
    model_name = raw_model_name

    make_session = session_factory or requests.Session

    with mgr._get_lock():
        if hasattr(mgr, "_completed_models"):
            mgr._completed_models.discard(model_name)
        dls = mgr._get_downloads()
        if model_name in dls:
            return {"success": False, "message": "Já está baixando"}
        dls[model_name] = {
            "progress": 0,
            "text": "Conectando ao Ollama...",
            "speed_mbps": 0.0,
            "eta_seconds": 0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
        }
        cancel_event = threading.Event()
        if not hasattr(mgr, "_cancel_events"):
            mgr._cancel_events = {}
        mgr._cancel_events[model_name] = cancel_event

    mgr.notify_progress(throttle_interval=0.0)

    def download_thread():
        session = make_session()
        session.trust_env = False
        with mgr._get_lock():
            if not hasattr(mgr, "_active_sessions"):
                mgr._active_sessions = {}
            mgr._active_sessions[model_name] = session

        base_url = Config.get("ollama_url", "http://127.0.0.1:11435/api").replace("localhost", "127.0.0.1").rstrip("/")
        url = f"{base_url}/pull"
        last_time = time.time()
        last_cum_bytes = 0
        speed_mb = 0.0
        peak_speed_mb = 0.0
        eta_s = 0
        last_pct = 0.0
        digest_completed = {}
        digest_totals = {}

        try:
            with session.post(url, json={"name": target_remote_name}, stream=True, timeout=3600) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if cancel_event.is_set():
                        try:
                            r.close()
                        except Exception:
                            pass
                        break

                    if line:
                        data = json.loads(line)
                        if "error" in data and data["error"]:
                            raise RuntimeError(str(data["error"]))
                        status = data.get("status", "")

                        if "total" in data and "completed" in data:
                            total = data["total"]
                            completed = data["completed"]
                            digest = data.get("digest") or "main"

                            digest_totals[digest] = max(digest_totals.get(digest, 0), total)
                            digest_completed[digest] = min(digest_totals[digest], completed)

                            cum_completed = sum(digest_completed.values())
                            cum_total = sum(digest_totals.values())

                            now = time.time()
                            dt = now - last_time
                            if dt >= 0.2:
                                delta = cum_completed - last_cum_bytes
                                if dt > 0 and delta > 0:
                                    instant_spd = (delta / (1024 * 1024)) / dt
                                    if speed_mb > 0.05:
                                        speed_mb = round(0.35 * instant_spd + 0.65 * speed_mb, 1)
                                    else:
                                        speed_mb = round(instant_spd, 1)
                                    if speed_mb > peak_speed_mb:
                                        peak_speed_mb = speed_mb

                                last_time = now
                                last_cum_bytes = cum_completed

                                if cum_total > cum_completed and speed_mb > 0.05:
                                    rem_bytes = max(0, cum_total - cum_completed)
                                    calc_spd = max(speed_mb, 0.35 * peak_speed_mb) if peak_speed_mb > 1.0 else speed_mb
                                    raw_eta = int(rem_bytes / (calc_spd * 1024 * 1024))
                                    if eta_s > 0:
                                        eta_s = int(0.35 * raw_eta + 0.65 * eta_s)
                                    else:
                                        eta_s = raw_eta
                                else:
                                    eta_s = 0

                            # Monotonicidade estrita: nunca regride o progresso e não pula para 100% em layers minúsculos
                            calc_pct = (cum_completed / cum_total * 100.0) if cum_total > 0 else 0.0
                            calc_pct = min(99.0, max(last_pct, round(calc_pct, 1)))
                            last_pct = calc_pct

                            speed_str = f" • {speed_mb:.1f} MB/s" if speed_mb > 0 else ""
                            eta_str = f" • {eta_s}s rest." if eta_s > 0 else ""

                            with mgr._get_lock():
                                dls = mgr._get_downloads()
                                if model_name in dls:
                                    dls[model_name]["progress"] = calc_pct
                                    dls[model_name]["speed_mbps"] = round(speed_mb, 1)
                                    dls[model_name]["eta_seconds"] = eta_s
                                    dls[model_name]["downloaded_bytes"] = cum_completed
                                    dls[model_name]["total_bytes"] = cum_total
                                    dls[model_name]["text"] = f"{status} ({calc_pct:.1f}%{speed_str}{eta_str})"
                            mgr.notify_progress(throttle_interval=0.1)
                        else:
                            with mgr._get_lock():
                                dls = mgr._get_downloads()
                                if model_name in dls:
                                    dls[model_name]["text"] = status
                                    if status == "success":
                                        dls[model_name]["progress"] = 100.0
                                        dls[model_name]["status"] = "success"
                                        dls[model_name]["speed_mbps"] = 0.0
                                        dls[model_name]["eta_seconds"] = 0
                                        if cum_total > 0:
                                            dls[model_name]["downloaded_bytes"] = cum_total
                                            dls[model_name]["total_bytes"] = cum_total
                                        if hasattr(mgr, "_completed_models"):
                                            mgr._completed_models.add(model_name)
                                        if target_remote_name != model_name:
                                            try:
                                                copy_url = f"{base_url}/copy"
                                                copy_resp = session.post(
                                                    copy_url,
                                                    json={"source": target_remote_name, "destination": model_name},
                                                    timeout=30,
                                                )
                                                if copy_resp.status_code in (200, 204):
                                                    try:
                                                        session.delete(f"{base_url}/delete", json={"name": target_remote_name}, timeout=10)
                                                    except Exception:
                                                        pass
                                            except Exception:
                                                pass
                                        if hasattr(mgr, "invalidate_tags_cache"):
                                            mgr.invalidate_tags_cache()
                                        try:
                                            from src.model_engines.ollama_manifest_scanner import invalidate_manifests_cache
                                            invalidate_manifests_cache()
                                        except Exception:
                                            pass
                                        if hasattr(mgr, "api") and mgr.api:
                                            if hasattr(mgr.api, "hf_orchestrator") and hasattr(mgr.api.hf_orchestrator, "invalidate_storage_cache"):
                                                mgr.api.hf_orchestrator.invalidate_storage_cache()
                                            elif hasattr(mgr.api, "_model_service") and hasattr(mgr.api._model_service, "hf_orchestrator"):
                                                mgr.api._model_service.hf_orchestrator.invalidate_storage_cache()
                                        try:
                                            from src.utils.event_bus import event_bus
                                            event_bus.publish("model_inventory_changed", {"action": "install", "model": model_name, "success": True})
                                        except Exception:
                                            pass
                            mgr.notify_progress(throttle_interval=0.1)

                if not cancel_event.is_set():
                    if hasattr(mgr, "invalidate_tags_cache"):
                        mgr.invalidate_tags_cache()
                    try:
                        from src.model_engines.ollama_manifest_scanner import invalidate_manifests_cache
                        invalidate_manifests_cache()
                    except Exception:
                        pass
                    mgr.notify_progress(throttle_interval=0.0)
                    time.sleep(2)
                    with mgr._get_lock():
                        dls = mgr._get_downloads()
                        if model_name in dls:
                            del dls[model_name]
                    mgr.notify_progress(throttle_interval=0.0)
        except Exception as e:
            if not cancel_event.is_set():
                with mgr._get_lock():
                    dls = mgr._get_downloads()
                    if model_name in dls:
                        dls[model_name] = {"progress": 0, "text": f"Erro: {str(e)}"}
                mgr.notify_progress(throttle_interval=0.0)
                time.sleep(3)
                with mgr._get_lock():
                    dls = mgr._get_downloads()
                    if model_name in dls:
                        del dls[model_name]
                mgr.notify_progress(throttle_interval=0.0)
        finally:
            try:
                session.close()
            except Exception:
                pass
            with mgr._get_lock():
                if hasattr(mgr, "_cancel_events"):
                    mgr._cancel_events.pop(model_name, None)
                if hasattr(mgr, "_active_sessions"):
                    mgr._active_sessions.pop(model_name, None)

    threading.Thread(target=download_thread, daemon=True).start()
    return {"success": True}
