import pytest
from src.translation_engine.translation_sanitizer import (
    sanitize_translated_text,
    _extract_proper_nouns_from_instructions,
)
from src.config import Config


class TestTranslationSanitizerIntelligentCasing:
    """Valida a preservação de siglas, nomes próprios, pontuação artística e numerais no motor de tradução."""

    def test_all_caps_shouting_is_preserved(self):
        assert sanitize_translated_text("VAI VAI VAI") == "VAI VAI VAI"
        assert sanitize_translated_text("MORRA, SEU MALDITO!") == "MORRA, SEU MALDITO!"
        assert sanitize_translated_text("KABOOOM!!") == "KABOOOM!!"

    def test_acronyms_preserved_in_mixed_case(self):
        text = "O agente do FBI foi à sede da ONU com o esquadrão da CIA."
        expected = "o agente do FBI foi à sede da ONU com o esquadrão da CIA."
        assert sanitize_translated_text(text) == expected

    def test_dotted_acronyms_preserved(self):
        text = "Os representantes dos E.U.A. e U.S.A. assinaram o tratado K.O."
        expected = "os representantes dos E.U.A. e U.S.A. assinaram o tratado K.O."
        assert sanitize_translated_text(text) == expected

    def test_manga_and_gaming_acronyms(self):
        text = "Ele se transformou em SSJ e recuperou 500 de HP e 200 de MP contra o NPC!"
        expected = "ele se transformou em SSJ e recuperou 500 de HP e 200 de MP contra o NPC!"
        assert sanitize_translated_text(text) == expected

    def test_proper_nouns_mid_sentence_preserved(self):
        text = "Eu vi o Sasuke conversando com o Kakashi sobre Tóquio e o Brasil."
        expected = "eu vi o Sasuke conversando com o Kakashi sobre Tóquio e o Brasil."
        assert sanitize_translated_text(text) == expected

    def test_proper_nouns_at_sentence_start_preserved(self):
        text = "Sasuke, você viu onde o Naruto foi parar?"
        expected = "Sasuke, você viu onde o Naruto foi parar?"
        assert sanitize_translated_text(text) == expected

        text2 = "Goku partiu para o confronto contra o inimigo."
        expected2 = "Goku partiu para o confronto contra o inimigo."
        assert sanitize_translated_text(text2) == expected2

    def test_common_sentence_starters_normalized(self):
        assert sanitize_translated_text("De tão perto assim...") == "de tão perto assim..."
        assert sanitize_translated_text("Viu?") == "viu?"
        assert sanitize_translated_text("Não toque nisso!") == "não toque nisso!"
        assert sanitize_translated_text("O que foi isso?") == "o que foi isso?"

    def test_roman_numerals_preserved(self):
        text = "Capítulo IV: A Batalha Decisiva do Século XXI."
        expected = "Capítulo IV: a Batalha Decisiva do Século XXI."
        assert sanitize_translated_text(text) == expected

        text2 = "No Volume I e na Fase II teremos novos combates."
        expected2 = "no Volume I e na Fase II teremos novos combates."
        assert sanitize_translated_text(text2) == expected2

    def test_artistic_manga_punctuation_preserved(self):
        text = "O que você disse?! Não pode ser!? Ele sumiu... — e levou tudo! ♪ ★"
        expected = "o que você disse?! não pode ser!? ele sumiu... — e levou tudo! ♪ ★"
        assert sanitize_translated_text(text) == expected

    def test_mixed_case_onomatopoeias_and_camelcase_preserved(self):
        text = "Doki-Doki... Ele comeu no McDonald's e usou seu iPhone!"
        expected = "Doki-Doki... ele comeu no McDonald's e usou seu iPhone!"
        assert sanitize_translated_text(text) == expected

    def test_preserve_terms_explicit_override(self):
        text = "ele usou o kage bunshin no jutsu e depois o rasengan!"
        result = sanitize_translated_text(
            text,
            preserve_terms=["Kage Bunshin no Jutsu", "Rasengan"]
        )
        assert result == "ele usou o Kage Bunshin no Jutsu e depois o Rasengan!"

    def test_preserve_case_parameter_and_config(self, monkeypatch):
        text = "Olá, Sasuke! Você Conhece Este Lugar?"
        # 1. Parâmetro explícito preserve_case=True
        assert sanitize_translated_text(text, preserve_case=True) == text

        # 2. Configuração preserve_translation_case=True
        monkeypatch.setattr(Config, "get", lambda k, default=False: True if k == "preserve_translation_case" else default)
        assert sanitize_translated_text(text) == text

    def test_meta_prefixes_and_markdown_stripped(self):
        assert sanitize_translated_text("Tradução PT-BR: vamos logo com isso!") == "vamos logo com isso!"
        assert sanitize_translated_text("Resposta: entendi perfeitamente.") == "entendi perfeitamente."
        assert sanitize_translated_text("```json tudo bem com você? ```") == "tudo bem com você?"

    def test_outer_quote_varieties_stripped(self):
        assert sanitize_translated_text('"isso é um teste"') == "isso é um teste"
        assert sanitize_translated_text("'outro teste'") == "outro teste"
        assert sanitize_translated_text('“fala com aspas curvas”') == "fala com aspas curvas"
        assert sanitize_translated_text('«aspas francesas»') == "aspas francesas"
        assert sanitize_translated_text('「aspas japonesas」') == "aspas japonesas"

    def test_repetition_loops_collapsed(self):
        assert sanitize_translated_text("droga droga droga droga droga") == "droga droga"
        assert sanitize_translated_text("não toque nisso nisso nisso nisso") == "não toque nisso nisso"

    def test_idempotence(self):
        text = "Sasuke viu o agente do FBI em Tóquio. Ele disse: 'Pare!'?!"
        first_pass = sanitize_translated_text(text)
        second_pass = sanitize_translated_text(first_pass)
        assert first_pass == second_pass


class TestExtractProperNounsFromInstructions:
    """Valida a extração de termos e nomes próprios das instruções personalizadas."""

    def test_extract_arrow_mappings(self):
        instructions = "Hokage -> Líder da Vila, Rasengan => Esfera Espiral"
        terms = _extract_proper_nouns_from_instructions(instructions)
        assert "Líder da Vila" in terms
        assert "Esfera Espiral" in terms

    def test_extract_acronyms_and_capitalized_names(self):
        instructions = "Preservar siglas: ONU, FBI, EUA. Personagens: Sasuke Uchiha, Son Goku, Al, Ed."
        terms = _extract_proper_nouns_from_instructions(instructions)
        assert "ONU" in terms
        assert "FBI" in terms
        assert "EUA" in terms
        assert "Sasuke Uchiha" in terms
        assert "Son Goku" in terms
        assert "Al" in terms
        assert "Ed" in terms

    def test_filter_reserved_instruction_headers(self):
        instructions = "Work-Specific Glossary (Highest Priority — override everything above if conflict)\nHokage -> Hokage"
        terms = _extract_proper_nouns_from_instructions(instructions)
        assert "Work-Specific" not in terms
        assert "Highest Priority" not in terms
        assert "Hokage" in terms
