import pytest
from src.translation_engine.prompt_builder import (
    build_system_prompt,
    detect_model_tier,
    normalize_preset,
    is_amadeus_model
)

class TestTieredPrompts:

    @pytest.mark.parametrize("model,expected_tier", [
        ("qwen2.5:7b", "7b"),
        ("qwen2.5-7b-instruct", "7b"),
        ("qwen2.5:3b", "7b"),
        ("qwen2.5:8b", "7b"),
        ("llama-3.1-8b", "7b"),
        ("qwen2.5:14b", "14b"),
        ("amadeus:14b", "14b"),
        ("amadeus:7b", "7b"),
        ("amadeus:32b", "32b"),
        ("qwen2.5-14b-instruct", "14b"),
        ("mistral-nemo", "14b"),
        ("qwen2.5:32b", "32b"),
        ("qwen2.5:72b", "32b"),
        ("qwen3-30b-a3b", "32b"),
        ("custom-large", "32b"),
        (None, "32b"),
        ("", "32b"),
    ])
    def test_detect_model_tier(self, model, expected_tier):
        assert detect_model_tier(model) == expected_tier

    def test_7b_prompt_contains_contrastive_few_shots(self):
        prompt = build_system_prompt(preset="neutral", model="qwen2.5:7b")
        assert "TABELA DE CALIBRAGEM CONTRASTIVA" in prompt
        assert "C'MON, NOW." in prompt
        assert "qual foi." in prompt
        assert "se esmurrando." in prompt
        assert "ei velhote..." in prompt
        assert "HEURÍSTICA DE COMPRESSÃO ESPACIAL" in prompt

    def test_14b_prompt_contains_deanglicization_and_corte_mastery(self):
        prompt = build_system_prompt(preset="neutral", model="qwen2.5:14b")
        assert "DESANGLICIZAÇÃO E FALA VISCERAL" in prompt
        assert "PARÁFRASE ATIVA E CONTROLE ESPACIAL" in prompt
        assert "Conexão e Cadência em Balões Quebrados" in prompt
        assert "[CORTE]" in prompt
        assert "na real" in prompt

    def test_32b_prompt_contains_editorial_mastery_and_subtext(self):
        prompt = build_system_prompt(preset="neutral", model="qwen2.5:32b")
        assert "ANÁLISE CÊNICA GLOBAL E DINÂMICA INTER-BALÕES" in prompt
        assert "TRADUÇÃO PRAGMÁTICA E SUBTEXTO" in prompt
        assert "ELASTICIDADE ESPACIAL E FONÉTICA DE QUADRINHO" in prompt
        assert "MATRIZ DE CALIBRAGEM EDITORIAL AVANÇADA" in prompt

    @pytest.mark.parametrize("tier_model", ["qwen2.5:7b", "qwen2.5:14b", "qwen2.5:32b"])
    @pytest.mark.parametrize("preset,expected_text", [
        ("shonen", "Shonen (Ação, Intensidade e Espírito Jovem)"),
        ("seinen", "Seinen (Maduro, Dramático e Profundo)"),
        ("comedy", "Comédia e Humor Brasileiro"),
        ("boxing", "Luta e Confronto"),
        ("neutral", "Neutro e Equilibrado"),
    ])
    def test_presets_render_across_all_tiers(self, tier_model, preset, expected_text):
        prompt = build_system_prompt(preset=preset, model=tier_model)
        assert expected_text in prompt

    @pytest.mark.parametrize("tier_model", ["qwen2.5:7b", "qwen2.5:14b", "qwen2.5:32b"])
    def test_custom_instructions_injected_in_all_tiers(self, tier_model):
        custom = "Gohan -> Guerreiro Z"
        prompt = build_system_prompt(preset="shonen", custom_instructions=custom, model=tier_model)
        assert "Work-Specific Glossary" in prompt
        assert "Gohan -> Guerreiro Z" in prompt

    def test_is_amadeus_model_detection(self):
        assert is_amadeus_model("amadeus:14b") is True
        assert is_amadeus_model("amadeus:7b") is True
        assert is_amadeus_model("amadeus:32b") is True
        assert is_amadeus_model("hf.co/mradermacher/AV-BI-Qwen2.5-32B-PT-BR-Instruct-GGUF") is True
        assert is_amadeus_model("qwen2.5:14b") is False
        assert is_amadeus_model("deepseek-r1:7b") is False
        assert is_amadeus_model(None) is False
