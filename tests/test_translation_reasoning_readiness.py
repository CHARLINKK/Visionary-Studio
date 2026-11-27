import unittest
from unittest.mock import MagicMock, patch
import json

from src.translation_engine.json_healer import (
    strip_reasoning_traces,
    parse_or_heal_translation_json,
)
from src.translation_engine.prompt_builder import (
    is_reasoning_model,
    detect_model_tier,
    build_system_prompt,
)
from src.translation_engine.translation_sanitizer import sanitize_translated_text
from src.translation_engine.context_optimizer import calculate_optimal_num_ctx
from src.translation_engine.ollama_client import call_ollama


class TestTranslationReasoningReadiness(unittest.TestCase):
    """
    Suíte de testes de prontidão arquitetural para modelos de reasoning (DeepSeek-R1, QwQ).
    Garante que todo o terreno de parsing, streaming, prompts e sanitização esteja 100% blindado.
    """

    def test_is_reasoning_model_detection(self):
        """Verifica a identificação precisa de modelos de reasoning sem falsos positivos em modelos densos."""
        reasoning_models = [
            "deepseek-r1:7b",
            "deepseek-r1:8b",
            "deepseek-r1:14b",
            "deepseek-r1:32b",
            "deepseek-r1",
            "DeepSeek-R1-Distill-Qwen-7B",
            "qwq:32b",
            "qwq-32b-preview",
            "marco-o1:7b",
            "my-custom-reasoner",
        ]
        for m in reasoning_models:
            self.assertTrue(is_reasoning_model(m), f"Deveria detectar como reasoning: {m}")

        dense_models = [
            "qwen2.5:32b",
            "qwen2.5:14b",
            "qwen2.5:7b",
            "qwen2.5-coder:32b",
            "llama3.1:8b",
            "llama3.3:70b",
            "mistral-nemo",
            "gemma2:27b",
            "",
            None,
        ]
        for m in dense_models:
            self.assertFalse(is_reasoning_model(m), f"Não deveria detectar como reasoning: {m}")

    def test_strip_reasoning_traces_clean_and_dirty(self):
        """Valida a remoção segura de tags de pensamento (<think>...</think>) sem afetar o JSON final."""
        # 1. Caso limpo simples
        raw = "<think>\nVamos analisar a cena.\nO balão 1 é agressivo.\n</think>\n{\"translations\": []}"
        self.assertEqual(strip_reasoning_traces(raw), "{\"translations\": []}")

        # 2. Caso com markdown code block após think
        raw_md = "<think>Ponderando...</think>\n```json\n{\"translations\": [{\"id\": 1, \"text\": \"olá\"}]}\n```"
        self.assertEqual(
            strip_reasoning_traces(raw_md),
            "```json\n{\"translations\": [{\"id\": 1, \"text\": \"olá\"}]}\n```"
        )

        # 3. Caso crítico: IA menciona rascunhos de JSON dentro de <think>
        raw_with_drafts = (
            "<think>\n"
            "Talvez devesse ser {\"id\": 1, \"text\": \"ruim\"}.\n"
            "Não, a melhor opção é {\"id\": 1, \"text\": \"boa\"}.\n"
            "</think>\n"
            "{\"translations\": [{\"id\": 1, \"text\": \"tradução final aprovada\"}]}"
        )
        cleaned = strip_reasoning_traces(raw_with_drafts)
        self.assertNotIn("ruim", cleaned)
        self.assertNotIn("boa", cleaned)
        self.assertIn("tradução final aprovada", cleaned)

        # 4. Caso com fechamento solto </think> (início de pensamento truncado)
        raw_cut = "pensamento residual...</think>\n{\"translations\": [{\"id\": 2, \"text\": \"ok\"}]}"
        self.assertEqual(strip_reasoning_traces(raw_cut), "{\"translations\": [{\"id\": 2, \"text\": \"ok\"}]}")

        # 5. Caso sem nenhuma tag de raciocínio
        standard = "{\"translations\": [{\"id\": 1, \"text\": \"normal\"}]}"
        self.assertEqual(strip_reasoning_traces(standard), standard)

    def test_parse_or_heal_translation_json_with_reasoning_output(self):
        """Garante que o parser final extrai EXCLUSIVAMENTE o payload correto de saídas com raciocínio."""
        # Saída simulando DeepSeek-R1 completa com markdown
        r1_output = (
            "<think>\n"
            "The dialogue is from a boxing manga.\n"
            "Bubble 1: 'YOU'VE GOTTA BE KIDDING! DID YOU SEE THAT COUNTER?!'\n"
            "In Portuguese dubbing, 'tá de sacanagem!' sounds best.\n"
            "Bubble 2: 'HE TOOK IT HEAD ON...'\n"
            "Let's output JSON:\n"
            "</think>\n\n"
            "```json\n"
            "{\n"
            "  \"translations\": [\n"
            "    {\"id\": 1, \"text\": \"tá de sacanagem! viu aquele contra-ataque?!\"},\n"
            "    {\"id\": 2, \"text\": \"ele aguentou de peito aberto...\"}\n"
            "  ]\n"
            "}\n"
            "```"
        )
        parsed = parse_or_heal_translation_json(r1_output)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["id"], 1)
        self.assertEqual(parsed[0]["text"], "tá de sacanagem! viu aquele contra-ataque?!")
        self.assertEqual(parsed[1]["id"], 2)
        self.assertEqual(parsed[1]["text"], "ele aguentou de peito aberto...")

    def test_parse_or_heal_ignores_json_objects_inside_thinking(self):
        """Verifica que regex de fallback nunca captura objetos rascunhados dentro do <think>."""
        tricky_r1_output = (
            "<think>\n"
            "Option A: {\"id\": 999, \"text\": \"rascunho falso\"}\n"
            "Option B: {\"id\": 888, \"text\": \"outro descarte\"}\n"
            "</think>\n"
            "{\"translations\": [{\"id\": 10, \"text\": \"apenas este deve sobreviver\"}]}"
        )
        parsed = parse_or_heal_translation_json(tricky_r1_output)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(str(parsed[0]["id"]), "10")
        self.assertEqual(parsed[0]["text"], "apenas este deve sobreviver")

    def test_sanitize_translated_text_strips_stray_think_tags(self):
        """Valida que a sanitização final elimina qualquer tag <think> residual vazada para o texto do balão."""
        dirty_text = "<think>pensamento acidental</think> fala real do personagem"
        sanitized = sanitize_translated_text(dirty_text)
        self.assertNotIn("<think>", sanitized)
        self.assertNotIn("pensamento acidental", sanitized)
        self.assertEqual(sanitized, "fala real do personagem")

    @patch("src.config.Config.get")
    @patch("urllib.request.urlopen")
    @patch("http.client.HTTPConnection")
    def test_call_ollama_omits_format_and_expands_predict_for_reasoning(
        self, mock_http_conn_cls, mock_urlopen, mock_config_get
    ):
        """
        Valida que para modelos de reasoning:
        1. A chave 'format' NÃO é enviada no payload (libera streaming de <think> sem erro no BNF grammar).
        2. 'num_predict' recebe headroom generoso (+1536 tokens) para evitar truncamento prematuro.
        3. 'temperature' é ajustada para 0.55.
        """
        mock_config_get.return_value = "http://127.0.0.1:11435/api"
        mock_urlopen.side_effect = Exception("offline")

        mock_conn = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.side_effect = [
            b'{"message": {"content": "<think>pensando</think>{\\"translations\\": []}"}}\n',
            b""
        ]
        mock_conn.getresponse.return_value = mock_resp
        mock_http_conn_cls.return_value = mock_conn

        captured_requests = []

        def capture_request(method, url, body=None, headers=None):
            if body:
                captured_requests.append(json.loads(body.decode("utf-8")))

        mock_conn.request.side_effect = capture_request

        with patch("src.model_manager.ModelManager.ensure_ollama_running"):
            # Chamada com modelo de reasoning (DeepSeek-R1)
            call_ollama(
                system_prompt="sys",
                user_prompt="usr",
                model="deepseek-r1:7b",
                num_ctx=2048,
                expected_chars=200,
                total_ids=2,
            )

        self.assertTrue(len(captured_requests) > 0)
        req_data = captured_requests[0]

        # 1. 'format' não deve estar presente no request para não quebrar o <think>
        self.assertNotIn("format", req_data)
        # 2. 'num_predict' deve ter o headroom de reasoning (> 1500)
        self.assertGreaterEqual(req_data["options"]["num_predict"], 1536)
        # 3. 'temperature' deve ser 0.55
        self.assertEqual(req_data["options"]["temperature"], 0.55)

    @patch("src.config.Config.get")
    @patch("urllib.request.urlopen")
    @patch("http.client.HTTPConnection")
    def test_call_ollama_retains_format_for_standard_models(
        self, mock_http_conn_cls, mock_urlopen, mock_config_get
    ):
        """Valida que para modelos padrão (Qwen 32B/14B), 'format' e predict compacto são preservados."""
        mock_config_get.return_value = "http://127.0.0.1:11435/api"
        mock_urlopen.side_effect = Exception("offline")

        mock_conn = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.side_effect = [
            b'{"message": {"content": "{\\"translations\\": []}"}}\n',
            b""
        ]
        mock_conn.getresponse.return_value = mock_resp
        mock_http_conn_cls.return_value = mock_conn

        captured_requests = []

        def capture_request(method, url, body=None, headers=None):
            if body:
                captured_requests.append(json.loads(body.decode("utf-8")))

        mock_conn.request.side_effect = capture_request

        with patch("src.model_manager.ModelManager.ensure_ollama_running"):
            call_ollama(
                system_prompt="sys",
                user_prompt="usr",
                model="qwen2.5:32b",
                num_ctx=2048,
                expected_chars=200,
                total_ids=2,
            )

        self.assertTrue(len(captured_requests) > 0)
        req_data = captured_requests[0]

        # Para modelo padrão, 'format' é mantido
        self.assertIn("format", req_data)
        # Previsão compacta mantida (< 300 tokens para 200 chars)
        self.assertLess(req_data["options"]["num_predict"], 500)
        self.assertEqual(req_data["options"]["temperature"], 0.35)

    def test_prompt_builder_includes_reasoning_protocol_when_model_is_reasoning(self):
        """Verifica que o prompt do sistema instrui a fechar </think> e emitir JSON exclusivo."""
        prompt_r1 = build_system_prompt(preset="neutral", model="deepseek-r1:7b")
        self.assertIn("Protocolo Operacional de Raciocínio (Modo Reasoning Ativo)", prompt_r1)
        self.assertIn("<think>", prompt_r1)
        self.assertIn("</think>", prompt_r1)

        prompt_standard = build_system_prompt(preset="neutral", model="qwen2.5:7b")
        self.assertNotIn("Protocolo Operacional de Raciocínio (Modo Reasoning Ativo)", prompt_standard)

    def test_context_optimizer_adds_reasoning_headroom(self):
        """Verifica que o Pre-Scan aloca headroom de contexto adicional para modelos de reasoning."""
        with patch("src.utils.file_resilience.resilient_read_json") as mock_json:
            mock_json.return_value = {"boxes": [{"text": "Hello world"}]}
            with patch("src.utils.vram_arbiter.vram_arbiter.cap_context_for_tier", side_effect=lambda ctx: ctx):
                ctx_standard = calculate_optimal_num_ctx(["page_001_map.json"], model="qwen2.5:7b")
                ctx_reasoning = calculate_optimal_num_ctx(["page_001_map.json"], model="deepseek-r1:7b")
                self.assertGreaterEqual(ctx_reasoning, ctx_standard)


if __name__ == "__main__":
    unittest.main()
