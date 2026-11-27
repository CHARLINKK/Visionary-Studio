import pytest
from unittest.mock import patch

from src.domain.bubble_contract import (
    normalize_bubble_for_gui,
    normalize_bubble_for_storage,
    reconcile_and_normalize_bubbles
)
from src.translation_engine.ollama_client import translate_bubbles


class TestModelTranslationsFeature:

    def test_normalize_bubble_for_gui_exposes_model_translations(self):
        box = {
            "id": 1,
            "text": "Hello",
            "translated_text": "Olá",
            "user_edited": False,
            "model_translations": {
                "qwen2.5:7b": "Olá",
                "qwen2.5:32b": "E aí"
            }
        }
        gui = normalize_bubble_for_gui(box, index=0)
        assert "model_translations" in gui
        assert gui["model_translations"]["qwen2.5:7b"] == "Olá"
        assert gui["model_translations"]["qwen2.5:32b"] == "E aí"

    def test_normalize_bubble_for_storage_merges_and_preserves_model_translations(self):
        existing_box = {
            "id": 1,
            "text": "Hello",
            "translated_text": "Olá",
            "model_translations": {
                "qwen2.5:7b": "Olá"
            }
        }
        frontend_box = {
            "id": 1,
            "text": "Hello",
            "translated_text": "Olá!",
            "user_edited": True,
            "model_translations": {
                "qwen2.5:32b": "E aí cara"
            }
        }
        storage = normalize_bubble_for_storage(frontend_box, index=0, existing_box=existing_box)
        assert "model_translations" in storage
        assert storage["model_translations"]["qwen2.5:7b"] == "Olá"
        assert storage["model_translations"]["qwen2.5:32b"] == "E aí cara"
        assert storage["translated_text"] == "Olá!"
        assert storage["user_edited"] is True

    def test_reconcile_and_normalize_bubbles_preserves_model_translations(self):
        detected_boxes = [
            {"id": 1, "x1": 10, "y1": 10, "x2": 50, "y2": 50, "text": "Fight!"}
        ]
        existing_boxes = [
            {
                "id": 1, "x1": 10, "y1": 10, "x2": 50, "y2": 50,
                "text": "Fight!",
                "translated_text": "Lute!",
                "user_edited": True,
                "model_translations": {
                    "qwen2.5:7b": "Lute!",
                    "qwen2.5:14b": "Cai pra dentro!"
                }
            }
        ]
        reconciled = reconcile_and_normalize_bubbles(detected_boxes, existing_boxes)
        assert len(reconciled) == 1
        assert "model_translations" in reconciled[0]
        assert reconciled[0]["model_translations"]["qwen2.5:14b"] == "Cai pra dentro!"
        assert reconciled[0]["translated_text"] == "Lute!"
        assert reconciled[0]["user_edited"] is True

    @patch("src.translation_engine.ollama_client.call_ollama")
    def test_translate_bubbles_accumulates_model_translations_and_protects_user_edited(self, mock_call):
        # 1. Primeira chamada com modelo 7B
        mock_call.return_value = '{"translations": [{"id": 1, "text": "primeira traducao 7b"}]}'
        boxes = [{"id": 1, "text": "First speech."}]

        res_7b, _ = translate_bubbles(boxes, model="qwen2.5:7b")
        assert res_7b[0]["translated_text"] == "primeira traducao 7b"
        assert res_7b[0]["model_translations"]["qwen2.5:7b"] == "primeira traducao 7b"
        assert res_7b[0]["user_edited"] is False

        # 2. Usuário edita manualmente a tradução
        res_7b[0]["translated_text"] = "edicao manual do usuario"
        res_7b[0]["user_edited"] = True

        # 3. Segunda chamada com modelo 32B (não deve sobrescrever a edição humana!)
        mock_call.return_value = '{"translations": [{"id": 1, "text": "segunda traducao 32b"}]}'
        res_32b, _ = translate_bubbles(res_7b, model="qwen2.5:32b")

        # O texto ativo continua sendo a edição manual
        assert res_32b[0]["translated_text"] == "edicao manual do usuario"
        assert res_32b[0]["user_edited"] is True

        # Mas o modelo 32B foi registrado cumulativamente no histórico
        assert res_32b[0]["model_translations"]["qwen2.5:7b"] == "primeira traducao 7b"
        assert res_32b[0]["model_translations"]["qwen2.5:32b"] == "segunda traducao 32b"

    def test_bubble_needs_translation_heuristics(self):
        from src.translation_engine.ollama_client import bubble_needs_translation

        # Balão novo sem tradução
        b_fresh = {"id": 1, "text": "Hello", "translated_text": ""}
        assert bubble_needs_translation(b_fresh, "qwen2.5:7b") is True

        # SFX ou DELETE não precisa de tradução
        assert bubble_needs_translation({"id": 2, "text": "BOOM", "is_sfx": True}, "qwen2.5:7b") is False
        assert bubble_needs_translation({"id": 3, "text": "[DELETE]"}, "qwen2.5:7b") is False
        assert bubble_needs_translation({"id": 4, "text": "   "}, "qwen2.5:7b") is False

        # Balão já traduzido por 7B
        b_translated = {
            "id": 5, "text": "Hello", "translated_text": "Olá",
            "model_translations": {"qwen2.5:7b": "Olá"}
        }
        # Mesma LLM -> Não precisa de tradução (pula!)
        assert bubble_needs_translation(b_translated, "qwen2.5:7b") is False

        # Outra LLM selecionada -> Precisa de tradução!
        assert bubble_needs_translation(b_translated, "qwen2.5:14b") is True
        assert bubble_needs_translation(b_translated, "qwen2.5:32b") is True

        # Balão legado (tem tradução mas sem dicionário model_translations) -> preserva
        b_legacy = {"id": 6, "text": "Hello", "translated_text": "Olá legado"}
        assert bubble_needs_translation(b_legacy, "qwen2.5:7b") is False

    @patch("src.translation_engine.ollama_client.call_ollama")
    def test_step4_translator_skips_only_same_llm(self, mock_call, tmp_path):
        import json
        from src.step4_translator import OllamaTranslator

        out_dir = tmp_path / "output"
        out_dir.mkdir()

        page_file = out_dir / "001_map.json"
        initial_data = [
            {
                "id": 1,
                "text": "Hello world",
                "translated_text": "Olá mundo 7B",
                "user_edited": False,
                "model_translations": {
                    "qwen2.5:7b": "Olá mundo 7B"
                }
            }
        ]
        page_file.write_text(json.dumps(initial_data), encoding="utf-8")

        # 1. Executa com qwen2.5:7b sem overwrite -> DEVE PULAR (mock_call não chamado)
        trans_7b = OllamaTranslator(model="qwen2.5:7b")
        trans_7b.process_directory(str(out_dir), str(out_dir), overwrite=False)
        assert mock_call.call_count == 0

        # 2. Executa com qwen2.5:14b sem overwrite -> NÃO PULA, traduz e salva
        mock_call.return_value = '{"translations": [{"id": 1, "text": "Olá mundo 14B"}]}'
        trans_14b = OllamaTranslator(model="qwen2.5:14b")
        trans_14b.process_directory(str(out_dir), str(out_dir), overwrite=False)
        assert mock_call.call_count == 1

        # Verifica que o arquivo foi atualizado com ambos os modelos
        with open(page_file, "r", encoding="utf-8") as f:
            updated = json.load(f)
        boxes = updated["boxes"] if isinstance(updated, dict) else updated
        assert boxes[0]["model_translations"]["qwen2.5:7b"] == "Olá mundo 7B"
        assert boxes[0]["model_translations"]["qwen2.5:14b"] == "olá mundo 14b"
        assert boxes[0]["translated_text"] == "olá mundo 14b"

        # 3. Executa com qwen2.5:14b novamente sem overwrite -> DEVE PULAR
        mock_call.reset_mock()
        trans_14b.process_directory(str(out_dir), str(out_dir), overwrite=False)
        assert mock_call.call_count == 0

        # 4. Executa com qwen2.5:7b novamente sem overwrite -> DEVE PULAR
        mock_call.reset_mock()
        trans_7b.process_directory(str(out_dir), str(out_dir), overwrite=False)
        assert mock_call.call_count == 0

        # 5. Executa com qwen2.5:7b COM overwrite=True -> NÃO PULA (forçado)
        mock_call.return_value = '{"translations": [{"id": 1, "text": "Re-traduzido 7B"}]}'
        trans_7b.process_directory(str(out_dir), str(out_dir), overwrite=True)
        assert mock_call.call_count == 1

    @patch("src.translation_engine.ollama_client.call_ollama")
    def test_translate_bubbles_fast_paths_bypass_ollama(self, mock_call):
        from src.translation_engine.ollama_client import translate_bubbles

        boxes = [
            {"id": 1, "text": "WHAT?!", "translated_text": ""},
            {"id": 2, "text": "...", "translated_text": ""},
            {"id": 3, "text": "42", "translated_text": ""},
        ]

        res, _ = translate_bubbles(boxes, model="amadeus:14b")

        assert mock_call.call_count == 0
        assert res[0]["translated_text"] == "o quê?!"
        assert res[0]["model_translations"]["amadeus:14b"] == "o quê?!"
        assert res[1]["translated_text"] == "..."
        assert res[1]["model_translations"]["amadeus:14b"] == "..."
        assert res[2]["translated_text"] == "42"
        assert res[2]["model_translations"]["amadeus:14b"] == "42"

    @patch("src.translation_engine.ollama_client.call_ollama")
    def test_translate_bubbles_fullwidth_japanese_and_dynamic_exclamations(self, mock_call):
        from src.translation_engine.ollama_client import translate_bubbles, _clean_ocr_noise
        from src.translation_engine.prompt_builder import resolve_fast_path_exclamation
        from src.translation_engine.translation_sanitizer import sync_trailing_punctuation, sanitize_translated_text

        # 1. Fast-Path com pontuação full-width japonesa e combinações dinâmicas
        boxes = [
            {"id": 1, "text": "！？", "translated_text": ""},
            {"id": 2, "text": "HELP!", "translated_text": ""},
            {"id": 3, "text": "WAIT...!!", "translated_text": ""},
            {"id": 4, "text": "NO WAY", "translated_text": ""},
        ]
        res, _ = translate_bubbles(boxes, model="amadeus:14b")
        assert mock_call.call_count == 0
        assert res[0]["translated_text"] == "！？"
        assert res[1]["translated_text"] == "socorro!"
        assert res[2]["translated_text"] == "espere...!!"
        assert res[3]["translated_text"] == "sem chance"

        # 2. Teste direto do resolve_fast_path_exclamation
        assert resolve_fast_path_exclamation("SOMEONE HELP?!") == "alguém ajude?!"
        assert resolve_fast_path_exclamation("WHAT THE...?!") == "o que é isso...?!"
        assert resolve_fast_path_exclamation("ARE YOU KIDDING ME?!") == "tá de brincadeira comigo?!"

        # 3. Teste do _clean_ocr_noise (des-hifenização vs gagueira)
        assert _clean_ocr_noise("DETERMI-\nNATION") == "DETERMINATION"
        assert _clean_ocr_noise("UN- \n BELIEVABLE") == "UNBELIEVABLE"
        assert _clean_ocr_noise("N-NO! W-WHAT?!") == "N-NO! W-WHAT?!"

        # 4. Teste do sync_trailing_punctuation (restauração de pontuação dramática)
        assert sync_trailing_punctuation("ARE YOU CRAZY?!", "você tá maluco.") == "você tá maluco?!"
        assert sync_trailing_punctuation("DON'T TOUCH ME!!", "não encosta em mim.") == "não encosta em mim!!"
        assert sync_trailing_punctuation("WAIT...", "espera") == "espera..."
        assert sync_trailing_punctuation("CALM DOWN.", "calma.") == "calma."

        # 5. Teste de verbos conversacionais no sanitizador (letra minúscula) vs nomes próprios (maiúscula)
        assert sanitize_translated_text("Parece que ele venceu.") == "parece que ele venceu."
        assert sanitize_translated_text("Duvido que consiga.") == "duvido que consiga."
        assert sanitize_translated_text("Sasuke apareceu de repente.") == "Sasuke apareceu de repente."

