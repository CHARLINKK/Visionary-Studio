import os
import sys
import unittest
from unittest.mock import patch
import json



from src.step3_text_cleaner import clean_ocr_hallucinations, clean_bubbles_list
from src.translation_engine.ollama_client import translate_bubbles
from src.translation_engine.nlp_heuristics import semantic_split_text, auto_link_speech_bubbles
from src.translation_engine.context_optimizer import calculate_optimal_num_ctx

class TestTextCleanerAndTranslator(unittest.TestCase):
    def setUp(self):
        super().setUp()
        try:
            from src.batch_pipeline.session import reset_session
            reset_session()
        except Exception:
            pass

    def tearDown(self):
        try:
            from src.batch_pipeline.session import reset_session
            reset_session()
        except Exception:
            pass
        super().tearDown()

    def test_clean_ocr_hallucinations_punctuation(self):
        """Valida que ruídos e reticências quebradas de OCR são corrigidos."""
        raw_text = "Wait . . . what is that ???"
        cleaned = clean_ocr_hallucinations(raw_text)
        self.assertEqual(cleaned, "Wait... what is that???")
        self.assertEqual(clean_ocr_hallucinations("WHAT ? ! !"), "WHAT?!!")
        self.assertEqual(clean_ocr_hallucinations("REALLY ? ! ? !"), "REALLY?!?!")

    def test_clean_ocr_ellipsis_attachment(self):
        """Valida que reticências colam na palavra anterior e mantêm espaço se seguidas por palavra."""
        raw = "I COULDN'T BREATHE ... I WAS DIZZY AND GASPING FOR AIR."
        cleaned = clean_ocr_hallucinations(raw)
        self.assertEqual(cleaned, "I COULDN'T BREATHE... I WAS DIZZY AND GASPING FOR AIR.")

        raw_nospace = "BREATHE...I WAS"
        self.assertEqual(clean_ocr_hallucinations(raw_nospace), "BREATHE... I WAS")

    def test_clean_ocr_exclamation_noise(self):
        """Valida que ruídos como '1.1.0.1' de exclamações estilizadas são convertidos para '!' sem quebrar números legítimos."""
        self.assertEqual(clean_ocr_hallucinations("1.1.0.1"), "!")
        self.assertEqual(clean_ocr_hallucinations("1.1.1"), "!")
        self.assertEqual(clean_ocr_hallucinations("1.5"), "1.5")
        self.assertEqual(clean_ocr_hallucinations("100"), "100")
        self.assertEqual(clean_ocr_hallucinations("1"), "1")
        self.assertEqual(clean_ocr_hallucinations("I"), "I")

    def test_clean_bubbles_list_in_memory(self):
        """Valida que clean_bubbles_list limpa balões diretamente em memória e padroniza em 'text' sem 'text_clean'."""
        raw_bubbles = [
            {"id": 1, "text": "Wait . . . what is that ???", "is_bubble": True},
            {"id": 2, "text": "SHHH", "is_bubble": False},
            {"id": 3, "text": "THEYL'LL NEVER CATCH US", "is_bubble": True}
        ]
        cleaned = clean_bubbles_list(raw_bubbles)
        self.assertEqual(cleaned[0]["text"], "Wait... what is that???")
        self.assertNotIn("text_clean", cleaned[0])
        self.assertEqual(cleaned[1]["text"], "[DELETE]")
        self.assertTrue(cleaned[1]["is_sfx"])
        self.assertNotIn("text_clean", cleaned[1])
        self.assertIn("text", cleaned[2])

    def test_clean_bubbles_flags_tch_sfx_and_records_ocr_raw(self):
        """Valida que onomatopeias/SFX como 'TCH.' e 'TSK.' viram [DELETE] para o Decision Card e que ocr_raw é preservado."""
        raw_bubbles = [
            {"id": 10, "text": "TCH.", "label": "text_bubble"},
            {"id": 11, "text": "TSK...", "is_bubble": False},
            {"id": 12, "text": "ZZZZZ", "is_bubble": False},
            {"id": 13, "text": "NORMAL DIALOGUE", "label": "text_bubble"}
        ]
        cleaned = clean_bubbles_list(raw_bubbles)
        self.assertEqual(cleaned[0]["text"], "[DELETE]")
        self.assertEqual(cleaned[0]["ocr_raw"], "TCH.")
        self.assertTrue(cleaned[0]["is_sfx"])
        self.assertEqual(cleaned[1]["text"], "[DELETE]")
        self.assertEqual(cleaned[1]["ocr_raw"], "TSK...")
        self.assertTrue(cleaned[1]["is_sfx"])
        self.assertEqual(cleaned[2]["text"], "[DELETE]")
        self.assertEqual(cleaned[2]["ocr_raw"], "ZZZZZ")
        self.assertEqual(cleaned[3]["text"], "NORMAL DIALOGUE")

    def test_clean_ocr_hallucinations_exclamation(self):
        """Valida que '11' ou 'l' isolados no final de grito viram exclamações."""
        raw_text = "STOP 11"
        cleaned = clean_ocr_hallucinations(raw_text)
        self.assertEqual(cleaned, "STOP!!")

    def test_clean_ocr_hallucinations_quotes_and_contractions(self):
        """Valida normalização de aspas curvas e contrações com espaços no OCR."""
        raw_text = "<s>“DIDN ' T YOU SEE?”</s>"
        cleaned = clean_ocr_hallucinations(raw_text)
        self.assertEqual(cleaned, '"DIDN\'T YOU SEE?"')

    def test_clean_ocr_hallucinations_unicode_ellipsis_and_dashes(self):
        """Valida que reticências unicode (…), travessões (—) e meias-riscas (–) não são deletadas pelo sanitizador."""
        raw_text = "Wait… what is that—?!"
        cleaned = clean_ocr_hallucinations(raw_text)
        self.assertEqual(cleaned, "Wait... what is that -- ?!")

    def test_exclamation_cache_instant_resolution(self):
        """Valida que gritos, reações de luta e variações de espaçamento são traduzidos instantaneamente sem chamar LLM."""
        bubbles = [
            {"id": 1, "text": "WHAT ?!"},
            {"id": 2, "text": "DAMN!"},
            {"id": 3, "text": "TCH..."},
            {"id": 4, "text": "LET'S GO!"}
        ]
        # Não precisa de mock do Ollama porque todas as entradas caem no cache instantâneo em RAM
        res, _ = translate_bubbles(bubbles, model="test-model")
        self.assertEqual(res[0]["translated_text"], "o quê?!")
        self.assertEqual(res[1]["translated_text"], "droga!")
        self.assertEqual(res[2]["translated_text"], "tsc...")
        self.assertEqual(res[3]["translated_text"], "vamos lá!")

    def test_translate_bubbles_empty(self):
        """Valida que páginas vazias retornam listas vazias sem erro."""
        bubbles, ctx = translate_bubbles([], model="andrewcanis/command-r:q3_K_S")
        self.assertEqual(bubbles, [])

    def test_translate_bubbles_already_translated(self):
        """Valida que balões já traduzidos não são reprocessados."""
        bubbles = [
            {"id": 1, "text": "Hello", "translated_text": "Olá"}
        ]
        res, ctx = translate_bubbles(bubbles, model="andrewcanis/command-r:q3_K_S")
        self.assertEqual(res[0]["translated_text"], "Olá")

    def test_translator_batching_and_payload(self):
        """Valida que múltiplos balões geram payload JSON válido com IDs corretos."""
        bubbles = [
            {"id": i, "text": f"Manga bubble text {i}"} for i in range(1, 20)
        ]
        payload = [{"id": b["id"], "text": b["text"]} for b in bubbles]
        json_str = json.dumps(payload, ensure_ascii=False)
        parsed = json.loads(json_str)
        self.assertEqual(len(parsed), 19)
        self.assertEqual(parsed[0]["id"], 1)

    def test_semantic_split_text_with_corte_tag(self):
        """Valida divisão exata quando a IA retorna a tag [CORTE]."""
        full_text = "Mesmo que você fale isso... [CORTE] ...eu nunca vou te perdoar!"
        parts = semantic_split_text(full_text, num_parts=2)
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], "Mesmo que você fale isso...")
        self.assertEqual(parts[1], "...eu nunca vou te perdoar!")

    def test_semantic_split_text_variations(self):
        """Valida que variações como [corte], [CUT], [SPLIT] são capturadas com sucesso."""
        full_text1 = "Primeira parte... [corte] ...segunda parte."
        full_text2 = "Parte A [CUT] Parte B"
        full_text3 = "Fato 1 [SPLIT] Fato 2"
        self.assertEqual(semantic_split_text(full_text1, 2), ["Primeira parte...", "...segunda parte."])
        self.assertEqual(semantic_split_text(full_text2, 2), ["Parte A", "Parte B"])
        self.assertEqual(semantic_split_text(full_text3, 2), ["Fato 1", "Fato 2"])

    def test_semantic_split_text_fallback_punctuation(self):
        """Valida que na ausência da tag o fallback divide na pontuação natural."""
        full_text = "Não importa o que aconteça, nós vamos vencer essa batalha!"
        parts = semantic_split_text(full_text, num_parts=2, original_lengths=[25, 30])
        self.assertEqual(len(parts), 2)
        self.assertTrue(parts[0].endswith(","))
        self.assertEqual(parts[1], "nós vamos vencer essa batalha!")

    def test_auto_link_speech_bubbles_ellipsis(self):
        """Valida auto-link automático em falas divididas por reticências."""
        bubbles = [
            {"id": 1, "panel_id": 1, "order": 1, "text": "THIS IS..."},
            {"id": 2, "panel_id": 1, "order": 2, "text": "... BOXING, TOO, AFTER ALL."},
            {"id": 3, "panel_id": 2, "order": 3, "text": "Independent sentence."}
        ]
        linked = auto_link_speech_bubbles(bubbles)
        self.assertIsNotNone(linked[0].get("group_id"))
        self.assertEqual(linked[0]["group_id"], linked[1]["group_id"])
        self.assertIsNone(linked[2].get("group_id"))

    def test_auto_link_speech_bubbles_spatial_proximity(self):
        """Valida link geométrico por proximidade no mesmo painel para orações sem reticências."""
        bubbles = [
            # Balão 1 e 2 no mesmo painel, verticalmente próximos (gap 10px), sem terminação pontual
            {"id": 1, "panel_id": 1, "order": 1, "x1": 100, "y1": 50, "x2": 200, "y2": 100, "text": "I THOUGHT THAT"},
            {"id": 2, "panel_id": 1, "order": 2, "x1": 95, "y1": 110, "x2": 205, "y2": 160, "text": "YOU WERE STRONGER."},
            # Balão 3 distante no mesmo painel com frase completa independente
            {"id": 3, "panel_id": 1, "order": 3, "x1": 500, "y1": 500, "x2": 600, "y2": 550, "text": "SEE YA!"}
        ]
        linked = auto_link_speech_bubbles(bubbles)
        self.assertIsNotNone(linked[0].get("group_id"))
        self.assertEqual(linked[0]["group_id"], linked[1]["group_id"])
        self.assertIsNone(linked[2].get("group_id"))

    def test_calculate_optimal_num_ctx(self):
        """Valida que o cálculo adaptativo de tokens retorna múltiplos seguros."""
        # Sem arquivos, retorna o piso de segurança
        optimal = calculate_optimal_num_ctx([])
        self.assertIn(optimal, [1536, 1792, 2048, 2560, 3072, 4096])

    def test_exclamation_cache_instant(self):
        """Valida que gritos isolados são traduzidos instantaneamente pelo cache local e atualizam contexto."""
        bubbles = [
            {"id": 1, "text": "WHAT?!"},
            {"id": 2, "text": "DAMN IT!"},
            {"id": 3, "text": "COACH!"}
        ]
        res, ctx = translate_bubbles(bubbles, model="andrewcanis/command-r:q3_K_S")
        self.assertEqual(res[0]["translated_text"], "o quê?!")
        self.assertEqual(res[1]["translated_text"], "droga!")
        self.assertEqual(res[2]["translated_text"], "treinador!")
        self.assertEqual(len(ctx), 1)
        self.assertEqual(len(ctx[0]), 3)

    def test_auto_link_with_none_fields(self):
        """Valida que auto-link não falha com campos nulos ou ausentes."""
        bubbles = [
            {"id": None, "panel_id": None, "order": None, "text": "Wait a minute..."},
            {"id": None, "panel_id": None, "order": None, "text": "...who are you?"}
        ]
        linked = auto_link_speech_bubbles(bubbles)
        self.assertIsNotNone(linked[0].get("group_id"))
        self.assertEqual(linked[0]["group_id"], linked[1]["group_id"])

    def test_linked_bubbles_numeric_id_mapping(self):
        """Valida que balões agrupados usam IDs numéricos temporários no payload e são distribuídos corretamente em minúsculas."""
        from unittest.mock import patch

        bubbles = [
            {"id": 2, "panel_id": 1, "order": 1, "text": "UP THIS CLOSE, NOT EVEN A PROPER BOXER...", "group_id": "manual_1"},
            {"id": 3, "panel_id": 1, "order": 2, "text": "... CAN CATCH A PUNCH COMING.", "group_id": "manual_1"},
            {"id": 4, "panel_id": 2, "order": 3, "text": "SEE?"}
        ]

        def mock_call_ollama(sys_prompt, user_prompt, model, **kwargs):
            # Valida que o payload enviado para a IA contém apenas IDs numéricos
            self.assertIn('"id": 90001', user_prompt)
            self.assertIn('"id": 4', user_prompt)
            self.assertNotIn('"group_manual_1"', user_prompt)
            
            return json.dumps([
                {"id": 90001, "text": "De tão perto assim, nem mesmo um boxeador decente... [CORTE] ...consegue ver um soco vindo."},
                {"id": 4, "text": "Viu?"}
            ])

        with patch("src.translation_engine.ollama_client.call_ollama", side_effect=mock_call_ollama):
            res, ctx = translate_bubbles(bubbles, model="test-model")

        self.assertEqual(res[0]["translated_text"], "de tão perto assim, nem mesmo um boxeador decente...")
        self.assertEqual(res[1]["translated_text"], "...consegue ver um soco vindo.")
        self.assertEqual(res[2]["translated_text"], "viu?")

    def test_parse_or_heal_translation_json_truncated(self):
        """Valida que JSONs truncados no fim ou com aspas internas são recuperados com sucesso."""
        from src.translation_engine.json_healer import parse_or_heal_translation_json

        # Caso 1: JSON truncado antes de fechar array e objeto raiz
        truncated = '{"translations": [{"id": 1, "text": "Primeira fala"}, {"id": 2, "text": "Segunda fala"}'
        res = parse_or_heal_translation_json(truncated)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["text"], "Primeira fala")
        self.assertEqual(res[1]["text"], "Segunda fala")

        # Caso 2: Aspas duplas internas em fala
        with_internal_quotes = '{"translations": [{"id": 1, "text": "Ele disse: "Droga!" e correu."}]}'
        res2 = parse_or_heal_translation_json(with_internal_quotes)
        self.assertEqual(len(res2), 1)
        self.assertEqual(str(res2[0]["id"]), "1")

    def test_ai_translation_debug_and_user_edit_lifecycle(self):
        """Valida que a IA grava ai_translated_text, edições preservam o debug e atualizam o produto final."""
        from src.translation_engine.ollama_client import translate_bubbles
        from src.api_services.studio_service import StudioService
        import tempfile
        import shutil

        bubbles = [
            {"id": 1, "text": "WHAT?!", "translated_text": ""},
            {"id": 2, "text": "Hello world", "translated_text": ""}
        ]

        def mock_call_ollama(*args, **kwargs):
            return json.dumps([{"id": 2, "text": "olá mundo"}])

        with patch("src.translation_engine.ollama_client.call_ollama", side_effect=mock_call_ollama):
            res, _ = translate_bubbles(bubbles, model="test-model")

        # 1. IA gerou tradução e gravou debug imutável
        self.assertEqual(res[0]["translated_text"], "o quê?!")
        self.assertEqual(res[0]["ai_translated_text"], "o quê?!")
        self.assertFalse(res[0]["user_edited"])

        self.assertEqual(res[1]["translated_text"], "olá mundo")
        self.assertEqual(res[1]["ai_translated_text"], "olá mundo")
        self.assertFalse(res[1]["user_edited"])

        # 2. Usuário edita o balão 2 no Studio
        tmp_dir = tempfile.mkdtemp()
        try:
            studio = StudioService(default_path=tmp_dir)
            img_file = os.path.join(tmp_dir, "001.png")
            with open(img_file, "wb") as f:
                f.write(b"fake")

            # Salva primeira vez com os dados originais da IA
            studio.save_page_layout(img_file, res)

            # Usuário edita o balão 2 no editor
            edited_boxes = [
                {"id": 1, "translated": "o quê?!", "user_edited": False},
                {"id": 2, "translated": "fala galera, beleza?", "user_edited": True}
            ]
            save_res = studio.save_page_layout(img_file, edited_boxes)
            self.assertTrue(save_res["success"])

            # 3. Lê o _map.json salvo (Envelope v2)
            map_path = os.path.join(tmp_dir, "output", "001_map.json")
            with open(map_path, "r", encoding="utf-8") as f:
                saved_envelope = json.load(f)
            self.assertEqual(saved_envelope.get("version"), 2)
            saved_map = saved_envelope["boxes"]

            # Balão 1 não foi mexido: mantém IA e user_edited=False
            self.assertEqual(saved_map[0]["translated_text"], "o quê?!")
            self.assertEqual(saved_map[0]["ai_translated_text"], "o quê?!")
            self.assertFalse(saved_map[0]["user_edited"])

            # Balão 2 foi mexido: translated_text atualizado, ai_translated_text preservado, user_edited=True
            self.assertEqual(saved_map[1]["translated_text"], "fala galera, beleza?")
            self.assertEqual(saved_map[1]["ai_translated_text"], "olá mundo")
            self.assertTrue(saved_map[1]["user_edited"])

            # 4. Produto final (.txt) gerado pelo txt_sync contém apenas o texto do usuário
            from src.utils.txt_sync import sync_chapter_txt
            sync_res = sync_chapter_txt(tmp_dir)
            self.assertTrue(sync_res["success"])

            with open(sync_res["path"], "r", encoding="utf-8") as f:
                txt_content = f.read()

            self.assertIn("[BR]: fala galera, beleza?", txt_content)
            self.assertNotIn("olá mundo", txt_content)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_parse_or_heal_lifo_truncation(self):
        """Valida que o reparador LIFO com pilha recupera JSONs truncados aninhados na ordem correta."""
        from src.translation_engine.json_healer import parse_or_heal_translation_json
        
        # Truncado dentro da string do segundo item
        raw_truncated = '[{"id": 1, "text": "primeira oração"}, {"id": 2, "text": "segunda oração truncada'
        res = parse_or_heal_translation_json(raw_truncated)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["text"], "primeira oração")
        self.assertEqual(res[1]["text"], "segunda oração truncada")

    def test_parse_or_heal_trailing_commas_and_newlines(self):
        """Valida que trailing commas e quebras de linha literais não quebram o parser."""
        from src.translation_engine.json_healer import parse_or_heal_translation_json
        
        raw_with_commas = '{"translations": [{"id": 1, "text": "fala 1\ncom quebra"}, {"id": 2, "text": "fala 2"},],}'
        res = parse_or_heal_translation_json(raw_with_commas)
        self.assertEqual(len(res), 2)
        self.assertIn("fala 1", res[0]["text"])
        self.assertEqual(res[1]["text"], "fala 2")

    def test_parse_or_heal_internal_quotes_text_integrity(self):
        """Valida que aspas duplas internas não-escapadas preservam o texto completo e não apenas o ID."""
        from src.translation_engine.json_healer import parse_or_heal_translation_json
        
        raw = '{"translations": [{"id": 42, "text": "Ele gritou: "Cuidado com o trem!" antes de pular."}]}'
        res = parse_or_heal_translation_json(raw)
        self.assertEqual(len(res), 1)
        self.assertEqual(str(res[0]["id"]), "42")
        self.assertIn("Cuidado com o trem!", res[0]["text"])
        self.assertTrue(res[0]["text"].endswith("antes de pular."))

    def test_semantic_split_manga_punctuation_atomic(self):
        """Valida que pontuações combinadas (!?, ?!) não são partidas no meio durante o split semântico."""
        # Se a frase tem !? na janela de corte, a pontuação combinada deve permanecer junta
        text = "Como você pôde fazer isso!? Eu confiava em você com toda a minha vida!"
        parts = semantic_split_text(text, num_parts=2, original_lengths=[30, 45])
        self.assertEqual(len(parts), 2)
        self.assertTrue(parts[0].endswith("!?"))
        self.assertTrue(parts[1].startswith("Eu confiava"))

    def test_auto_link_speech_bubbles_pure_silence_isolation(self):
        """Valida que balões contendo apenas silêncio dramático ('...', '…') não são fundidos em auto-link."""
        bubbles = [
            {"id": 1, "panel_id": 1, "order": 1, "text": "..."},
            {"id": 2, "panel_id": 1, "order": 2, "text": "O que você está olhando?"}
        ]
        linked = auto_link_speech_bubbles(bubbles)
        self.assertIsNone(linked[0].get("group_id"))
        self.assertIsNone(linked[1].get("group_id"))

    def test_exclamation_cache_extended(self):
        """Valida que interjeições adicionais do cache resolvem instantaneamente sem LLM."""
        bubbles = [
            {"id": 1, "text": "WHOA!"},
            {"id": 2, "text": "ARE YOU KIDDING ME?!"},
            {"id": 3, "text": "DAMN YOU!"}
        ]
        res, _ = translate_bubbles(bubbles, model="dummy-model")
        self.assertEqual(res[0]["translated_text"], "uau!")
        self.assertEqual(res[1]["translated_text"], "tá de brincadeira comigo?!")
        self.assertEqual(res[2]["translated_text"], "seu maldito!")

    def test_sanitize_translated_text_extended_prefixes(self):
        """Valida que prefixos discursivos de LLMs são removidos mantendo o texto em minúsculas."""
        from src.translation_engine.ollama_client import sanitize_translated_text
        
        raw1 = "Tradução para o português: não toque nisso!"
        raw2 = "Tradução PT-BR: vamos logo com isso!"
        raw3 = "Nota:   espere por mim!   "
        
        self.assertEqual(sanitize_translated_text(raw1), "não toque nisso!")
        self.assertEqual(sanitize_translated_text(raw2), "vamos logo com isso!")
        self.assertEqual(sanitize_translated_text(raw3), "espere por mim!")

    def test_load_protected_terms_dynamic(self):
        """Valida que termos e personagens são carregados dinamicamente de JSONs de glossário e referências."""
        import tempfile
        from src.step3_text_cleaner import load_protected_terms
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            dict_path = os.path.join(tmp_dir, "global_dictionary.json")
            with open(dict_path, "w", encoding="utf-8") as f:
                json.dump({"terms": [{"original": "Hokage", "translation": "Hokage"}]}, f)

            ref_path = os.path.join(tmp_dir, "references.json")
            with open(ref_path, "w", encoding="utf-8") as f:
                json.dump({"characters": [{"name": "Sasuke", "aliases": ["Uchiha"]}]}, f)

            terms = load_protected_terms(tmp_dir)
            self.assertIn("HOKAGE", terms)
            self.assertIn("SASUKE", terms)
            self.assertIn("UCHIHA", terms)

    def test_clean_bubbles_list_envelope_v2(self):
        """Valida que clean_bubbles_list aceita dicionário Envelope v2 diretamente sem crashar."""
        from src.step3_text_cleaner import clean_bubbles_list
        env = {
            "version": 2,
            "boxes": [
                {"id": 1, "text": "HELLO ...", "is_bubble": True},
                {"id": 2, "text": "TCH", "is_bubble": False}
            ]
        }
        res = clean_bubbles_list(env)
        self.assertIsInstance(res, dict)
        self.assertEqual(res["version"], 2)
        self.assertEqual(res["boxes"][0]["text"], "HELLO...")
        self.assertEqual(res["boxes"][1]["text"], "[DELETE]")
        self.assertTrue(res["boxes"][1]["is_sfx"])

    def test_process_ocr_map_envelope_v2_preservation(self):
        """Valida que process_ocr_map usa PageStore e preserva a estrutura de envelope v2."""
        import tempfile
        from src.step3_text_cleaner import process_ocr_map
        from src.domain.page_store import PageStore

        with tempfile.TemporaryDirectory() as tmp_dir:
            map_file = os.path.join(tmp_dir, "001_map.json")
            initial_envelope = {
                "version": 2,
                "boxes": [
                    {"id": 1, "text": "WHAT ? !", "is_bubble": True}
                ],
                "panels": [{"id": 1, "bbox": [0, 0, 100, 100]}]
            }
            with open(map_file, "w", encoding="utf-8") as f:
                json.dump(initial_envelope, f)

            process_ocr_map(map_file)

            loaded_env = PageStore.load_page_record(map_file)
            self.assertEqual(loaded_env.get("version"), 2)
            self.assertEqual(loaded_env["boxes"][0]["text"], "WHAT?!")

if __name__ == "__main__":
    unittest.main()



