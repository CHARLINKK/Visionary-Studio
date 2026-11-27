"""
Testes de regressão da auditoria da pipeline (steps 1 e 3).

Convenções deste arquivo:
- GUARDAS: passam hoje e protegem comportamento correto contra "correções" exageradas.
- xfail(strict=True): descrevem o comportamento CORRETO de um bug conhecido (ID Bn do
  relatório de auditoria). Falham hoje de propósito. Quando o bug for corrigido o teste
  passa a dar XPASS, o que FALHA a suíte (strict) e obriga a remover o marcador.

Todos os testes são puros: só chamam funções de produção com dados sintéticos em memória.
Nenhum toca settings.json, library/, models/ ou %APPDATA% reais (o conftest.py já isola
VISIONARY_USER_DATA em diretório temporário).
"""
import json
import cv2
import numpy as np
import pytest

from src.step3_text_cleaner import clean_ocr_hallucinations, clean_bubbles_list
from src.step1_layout_detector import _validate_bubble_morphology, _merge_bubbles


# ═══════════════════════════════════════════════════════════════════════════════
#  STEP 3 — Text cleaner
# ═══════════════════════════════════════════════════════════════════════════════

class TestStep3Guards:
    """Comportamentos corretos que a Fase 1 NÃO pode quebrar."""

    @pytest.mark.parametrize("raw, expected", [
        ("DIDN ' T YOU SEE?", "DIDN'T YOU SEE?"),
        ("THEY ' RE GONE", "THEY'RE GONE"),
    ])
    def test_split_contraction_is_rejoined(self, raw, expected):
        assert clean_ocr_hallucinations(raw) == expected

    def test_trailing_ones_after_shout_become_exclamations(self):
        assert clean_ocr_hallucinations("STOP 11") == "STOP!!"

    @pytest.mark.parametrize("sfx", ["TCH", "TSK...", "ZZZ", "BRRR"])
    def test_real_onomatopoeia_is_still_deleted_in_bubbles(self, sfx):
        out = clean_bubbles_list([{"id": 1, "text": sfx, "label": "text_bubble"}])
        assert out[0]["text"] == "[DELETE]"
        assert out[0]["is_sfx"] is True

    def test_normal_dialogue_is_untouched(self):
        out = clean_bubbles_list([{"id": 1, "text": "NORMAL DIALOGUE", "label": "text_bubble"}])
        assert out[0]["text"] == "NORMAL DIALOGUE"
        assert not out[0].get("is_sfx", False)


class TestStep3FixedRegressions:
    """Testes de regressão permanentes para bugs B1 a B6 do step3."""

    @pytest.mark.parametrize("text", [
        "YOU LEARN SOMETHIN' NEW EEEVERY DAY...",
        "NICE 'ND FIRED UP!",
        "HE SAID 'GO' AND LEFT",
    ])
    def test_b1_dropped_g_and_single_quotes_are_preserved(self, text):
        assert clean_ocr_hallucinations(text) == text

    @pytest.mark.parametrize("text", ["ROUND 1", "ROUND 1!"])
    def test_b2_real_number_one_is_not_turned_into_exclamation(self, text):
        assert clean_ocr_hallucinations(text) == text

    @pytest.mark.parametrize("text", [
        "THE PURSE IS $1,000,000",
        "MEET AT 12:30",
    ])
    def test_b3_numbers_with_separators_are_preserved(self, text):
        assert clean_ocr_hallucinations(text) == text

    def test_b4_lone_pronoun_i_is_not_an_exclamation(self):
        assert clean_ocr_hallucinations("I") == "I"

    @pytest.mark.parametrize("word", ["TV", "PC", "DR.", "MRS"])
    def test_b5_abbreviations_are_not_deleted_as_sfx(self, word):
        out = clean_bubbles_list([{"id": 1, "text": word, "label": "text_bubble"}])
        assert out[0]["text"] != "[DELETE]"
        assert not out[0].get("is_sfx", False)

    def test_b6_accented_latin_characters_and_symbols_preserved(self):
        assert clean_ocr_hallucinations("CAFÉ ♪ OK") == "CAFÉ ♪ OK"


# ═══════════════════════════════════════════════════════════════════════════════
#  STEP 1 — Layout detector
# ═══════════════════════════════════════════════════════════════════════════════

def _crop_with_text(inverted: bool) -> np.ndarray:
    """Recorte sintético 120x240: texto preto em fundo branco (ou o inverso)."""
    img = np.full((120, 240), 255, dtype=np.uint8)
    cv2.putText(img, "WHAT THE HELL", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 0, 2)
    return 255 - img if inverted else img


class TestStep1Guards:

    def test_normal_polarity_bubble_with_text_is_accepted(self):
        assert _validate_bubble_morphology(_crop_with_text(inverted=False), "text_bubble") is True

    def test_empty_white_crop_is_rejected(self):
        empty = np.full((120, 240), 255, dtype=np.uint8)
        assert _validate_bubble_morphology(empty, "text_bubble") is False

    def test_isolated_boxes_are_not_merged(self):
        boxes = [
            {"x1": 0, "y1": 0, "x2": 50, "y2": 50, "confidence": 0.9, "label": "text_bubble"},
            {"x1": 500, "y1": 500, "x2": 550, "y2": 550, "confidence": 0.8, "label": "text_bubble"},
        ]
        assert len(_merge_bubbles(boxes)) == 2


class TestStep1FixedRegressions:

    @pytest.mark.parametrize("label", ["text_bubble", "text_free"])
    def test_b7_inverted_polarity_text_is_accepted(self, label):
        assert _validate_bubble_morphology(_crop_with_text(inverted=True), label) is True

    def test_b8_merge_recomputes_flags_from_final_label(self):
        text_free = {
            "x1": 0, "y1": 0, "x2": 100, "y2": 100, "confidence": 0.9, "label": "text_free",
            "is_bubble": False, "is_sfx": True, "bg_type": "sfx", "area": 10000,
        }
        text_bubble = {
            "x1": 50, "y1": 50, "x2": 150, "y2": 150, "confidence": 0.5, "label": "text_bubble",
            "is_bubble": True, "is_sfx": False, "bg_type": "white", "area": 10000,
        }
        merged = _merge_bubbles([text_free, text_bubble])
        assert len(merged) == 1
        assert merged[0]["label"] == "text_bubble"
        assert merged[0]["is_bubble"] is True
        assert merged[0]["is_sfx"] is False


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANSLATION ENGINE & STEP 4 (B12, B17)
# ═══════════════════════════════════════════════════════════════════════════════

from src.translation_engine.prompt_builder import build_system_prompt
from src.server import PRESETS

class TestTranslationPresetsB12:

    @pytest.mark.parametrize("preset", ["neutral", "neutro", "default", None, "", "unknown_preset"])
    def test_neutral_and_unknown_fallbacks_do_not_inject_boxing_slang(self, preset):
        prompt = build_system_prompt(preset)
        assert "TRADITIONAL BOXING" not in prompt
        assert "quebra pau" not in prompt
        assert "motivado pra caralho" not in prompt
        assert "Featherweight" not in prompt
        assert "Neutro e Equilibrado" in prompt

    def test_boxing_preset_contains_combat_guidelines(self):
        prompt = build_system_prompt("boxing")
        assert "Luta e Confronto" in prompt
        assert "Featherweight" in prompt

    def test_server_presets_dictionary_accuracy(self):
        assert "neutral" in PRESETS
        assert "boxing" in PRESETS
        assert "shonen" in PRESETS
        assert "seinen" in PRESETS
        assert "comedy" in PRESETS
        # Boxing não pode estar rotulado falsamente como 'Neutro'
        assert "neutro" not in PRESETS["boxing"]["name"].lower()
        assert "neutro" in PRESETS["neutral"]["name"].lower()


class TestStep4ResumeCheckB17:

    def test_page_with_sfx_and_delete_is_recognized_as_fully_translated(self, tmp_path):
        from src.step4_translator import OllamaTranslator
        translator = OllamaTranslator(model="test-model", preset="neutral")
        
        # Página com diálogo já traduzido + SFX sem tradução + [DELETE]
        existing_bubbles = [
            {"id": 1, "text": "HELLO", "translated_text": "olá", "is_sfx": False},
            {"id": 2, "text": "[DELETE]", "translated_text": "", "is_sfx": True},
            {"id": 3, "text": "BOOM", "translated_text": "", "is_sfx": True},
        ]
        
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        
        in_map = input_dir / "page_01_map.json"
        out_map = output_dir / "page_01_map.json"
        in_map.write_text(json.dumps(existing_bubbles), encoding="utf-8")
        out_map.write_text(json.dumps(existing_bubbles), encoding="utf-8")
        
        # Mock translate_bubbles para garantir que NUNCA seja chamado
        calls = []
        def _mock_translate(*args, **kwargs):
            calls.append(True)
            return existing_bubbles, []
            
        import src.step4_translator as st
        orig = st.translate_bubbles
        st.translate_bubbles = _mock_translate
        try:
            translator.process_directory(str(input_dir), str(output_dir), overwrite=False)
            assert len(calls) == 0, "Página com SFX/[DELETE] não deveria re-acionar a tradução!"
        finally:
            st.translate_bubbles = orig


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 2 — PROMPT & HEURISTICS OPTIMIZATIONS (M1, M2, M5)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase2Optimizations:

    def test_m1_prompt_contains_ocr_and_allcaps_awareness(self):
        prompt = build_system_prompt("neutral")
        assert "MAIÚSCULAS" in prompt
        assert "OCR óptico" in prompt

    @pytest.mark.parametrize("input_text,expected", [
        ("Tradução: e aí, beleza?", "e aí, beleza?"),
        ("PT-BR: tudo certo!", "tudo certo!"),
        ("Português: vamos lá!", "vamos lá!"),
        ("Resposta: entendi.", "entendi."),
        ('"isso é um teste"', "isso é um teste"),
        ("'outro teste'", "outro teste"),
        ("droga droga droga droga droga droga", "droga droga"),
        ("não não", "não não"),
        ("VAI VAI VAI", "VAI VAI VAI"),
        ("```json tudo bem ```", "tudo bem"),
    ])
    def test_m5_sanitize_translated_text(self, input_text, expected):
        from src.translation_engine.ollama_client import sanitize_translated_text
        assert sanitize_translated_text(input_text) == expected

    def test_m2_few_shot_retrieval_finds_relevant_manga_pairs(self):
        from src.translation_engine.few_shot_retriever import retrieve_relevant_few_shots
        # Consulta com termo característico presente no dataset
        results = retrieve_relevant_few_shots(["Y'think you can own my debt?!"], max_examples=2)
        assert len(results) > 0
        assert any("debt" in r.get("en", "").lower() or "dívida" in r.get("pt", "").lower() for r in results)

    def test_m2_few_shot_retrieval_handles_empty_or_non_matching(self):
        from src.translation_engine.few_shot_retriever import retrieve_relevant_few_shots
        assert retrieve_relevant_few_shots([]) == []
        assert retrieve_relevant_few_shots(["xyzqqq_completely_unrelated_nonsense_123"]) == []


class TestFlorence2LargeConfig:

    def test_florence_reader_defaults_to_large(self):
        from src.step2_ocr_extractor import FlorenceReader, MODEL_ID
        assert MODEL_ID == "microsoft/Florence-2-large"
        reader = FlorenceReader()
        assert reader.model_id == "microsoft/Florence-2-large"

    def test_florence2_large_in_models_registry(self):
        from src.model_manager import MODELS_REGISTRY
        assert "florence2_large" in MODELS_REGISTRY
        entry = MODELS_REGISTRY["florence2_large"]
        assert entry["repo_id"] == "microsoft/Florence-2-large"
        assert entry["cache_folder"] == "florence-2-large"

