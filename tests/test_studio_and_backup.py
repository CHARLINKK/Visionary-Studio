import os
import sys
import unittest
import tempfile
import json
import shutil


from src.api_services.studio_service import StudioService
from src.api_services.fs_service import FileSystemService
from PIL import Image

class TestStudioAndBackup(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="studio_test_")
        self.output_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Cria imagem fake
        self.img_path = os.path.join(self.temp_dir, "001.png")
        img = Image.new("RGB", (800, 1200), color="white")
        img.save(self.img_path)
        
        # Cria StudioService autônomo
        self.studio = StudioService(api_bridge=None, default_path=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_load_page_layout(self):
        """Valida salvar e carregar dados de página via SSOT (_map.json)."""
        boxes = [
            {"id": 1, "x1": 50, "y1": 50, "x2": 150, "y2": 150, "text": "Hello", "translated": "Olá", "label": "text_bubble", "is_bubble": True},
            {"id": 2, "x1": 200, "y1": 200, "x2": 300, "y2": 300, "text": "World", "translated": "Mundo", "label": "text_bubble", "is_bubble": True}
        ]
        save_res = self.studio.save_page_layout(self.img_path, boxes)
        self.assertTrue(save_res["success"])

        # Carrega e valida integridade
        load_res = self.studio.get_page_data(self.img_path)
        self.assertTrue(load_res["success"])
        self.assertEqual(len(load_res["cards"]), 2)
        self.assertEqual(load_res["cards"][0]["original"], "Hello")
        self.assertEqual(load_res["cards"][0]["translated"], "Olá")

    def test_create_and_restore_backup(self):
        """Valida criação de ponto de restauração (_backup_map.json) e recuperação."""
        boxes = [
            {"id": 1, "x1": 50, "y1": 50, "x2": 150, "y2": 150, "text": "Texto Original"}
        ]
        self.studio.save_page_layout(self.img_path, boxes)
        
        # Cria backup
        b_res = self.studio.create_page_backup(self.img_path)
        self.assertTrue(b_res["success"])
        self.assertTrue(self.studio.check_page_backup(self.img_path)["exists"])

        # Altera dados
        modified_boxes = [{"id": 1, "x1": 0, "y1": 0, "x2": 10, "y2": 10, "text": "Modificado"}]
        self.studio.save_page_layout(self.img_path, modified_boxes)
        load_mod = self.studio.get_page_data(self.img_path)
        self.assertEqual(load_mod["cards"][0]["original"], "Modificado")

        # Restaura backup
        rest_res = self.studio.restore_page_backup(self.img_path)
        self.assertTrue(rest_res["success"])
        load_rest = self.studio.get_page_data(self.img_path)
        self.assertEqual(load_rest["cards"][0]["original"], "Texto Original")

        # Exclui backup e valida que sumiu
        del_res = self.studio.delete_page_backup(self.img_path)
        self.assertTrue(del_res["success"])
        self.assertFalse(self.studio.check_page_backup(self.img_path)["exists"])

    def test_backup_in_portable_folder_without_output_subfolder(self):
        """Valida que backup funciona mesmo se a pasta de saída for a raiz do capítulo."""
        from src.domain.page_store import PageStore
        portable_img = os.path.join(self.temp_dir, "portable.png")
        with open(portable_img, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
        
        # Cria mapa diretamente na raiz do capítulo
        portable_map = os.path.join(self.temp_dir, "portable_map.json")
        with open(portable_map, "w", encoding="utf-8") as f:
            json.dump([{"id": 1, "text": "Base Portátil"}], f)

        # Checa e cria backup na raiz
        b_res = self.studio.create_page_backup(portable_img)
        self.assertTrue(b_res["success"])
        self.assertTrue(self.studio.check_page_backup(portable_img)["exists"])

        # Modifica boxes e restaura
        PageStore.save_boxes(portable_map, [{"id": 1, "text": "Alterado"}], target_map_path=portable_map)
        
        rest_res = self.studio.restore_page_backup(portable_img)
        self.assertTrue(rest_res["success"])
        with open(portable_map, "r", encoding="utf-8") as f:
            restored_data = json.load(f)
        self.assertEqual(restored_data["version"], 2)
        self.assertEqual(restored_data["boxes"][0]["text"], "Base Portátil")

    def test_empty_page_non_blocking(self):
        """Valida que páginas com 0 balões são marcadas como has_ocr=True e blockCount=0 para não travar a fila."""
        empty_map = os.path.join(self.output_dir, "001_map.json")
        with open(empty_map, "w", encoding="utf-8") as f:
            json.dump([], f)

        fs = FileSystemService()
        res = fs.list_directory(self.temp_dir)
        self.assertTrue(res["success"])
        item = [it for it in res["items"] if it.get("name") == "001.png"][0]
        self.assertEqual(item["blockCount"], 0)
        self.assertTrue(item["pageData"]["ocr"])
        self.assertTrue(item["pageData"]["translation"])

    def test_save_layout_compact_polygons(self):
        """Valida que o layout salvo formata o array de polígonos em linha única e compacta."""
        boxes = [
            {
                "id": 1,
                "x1": 10, "y1": 20, "x2": 100, "y2": 100,
                "polygon": [[10, 20], [100, 20], [100, 100], [10, 100]],
                "text": "Polygon bubble"
            }
        ]
        self.studio.save_page_layout(self.img_path, boxes)
        map_path = os.path.join(self.output_dir, "001_map.json")
        self.assertTrue(os.path.exists(map_path))

        with open(map_path, "r", encoding="utf-8") as f:
            content = f.read()

        # O polygon deve estar em uma linha única contendo [[10, 20], [100, 20]...
        self.assertIn('"polygon": [[10, 20], [100, 20], [100, 100], [10, 100]]', content)
        # E o carregamento padrão no envelope v2 deve ser idêntico
        loaded = json.loads(content)
        self.assertEqual(loaded["version"], 2)
        self.assertEqual(loaded["boxes"][0]["polygon"], [[10, 20], [100, 20], [100, 100], [10, 100]])

    def test_ai_translated_text_preservation_and_fallback(self):
        """Valida que ai_translated_text é gerado por fallback se unedited, preservado em edições e carregado pelo get_page_data."""
        # 1. Salvar página onde o balão só tem translated (sem ai_translated_text explícito) e user_edited=False
        boxes = [
            {
                "id": 1, "x1": 50, "y1": 50, "x2": 150, "y2": 150,
                "text": "Hello", "translated": "Olá Mundo IA", "user_edited": False
            }
        ]
        self.studio.save_page_layout(self.img_path, boxes)

        map_path = os.path.join(self.output_dir, "001_map.json")
        with open(map_path, "r", encoding="utf-8") as f:
            saved = json.load(f)["boxes"]

        # Deve ter preenchido ai_translated_text automaticamente
        self.assertEqual(saved[0].get("ai_translated_text"), "Olá Mundo IA")
        self.assertFalse(saved[0].get("user_edited"))

        # 2. Usuário edita o texto traduzido
        boxes_edited = [
            {
                "id": 1, "x1": 50, "y1": 50, "x2": 150, "y2": 150,
                "text": "Hello", "translated": "Olá Mundo Humano", "user_edited": True
            }
        ]
        self.studio.save_page_layout(self.img_path, boxes_edited)

        with open(map_path, "r", encoding="utf-8") as f:
            saved2 = json.load(f)["boxes"]

        # ai_translated_text deve permanecer "Olá Mundo IA", translated_text ser o novo, e user_edited=True
        self.assertEqual(saved2[0].get("ai_translated_text"), "Olá Mundo IA")
        self.assertEqual(saved2[0].get("translated_text"), "Olá Mundo Humano")
        self.assertTrue(saved2[0].get("user_edited"))

        # 3. get_page_data deve retornar tanto ai_translated quanto ai_translated_text
        page_data = self.studio.get_page_data(self.img_path)
        card = page_data["cards"][0]
        self.assertEqual(card["ai_translated"], "Olá Mundo IA")
        self.assertEqual(card["ai_translated_text"], "Olá Mundo IA")
        self.assertEqual(card["translated"], "Olá Mundo Humano")
        self.assertTrue(card["user_edited"])

    def test_detect_page_bubbles_preserves_translation_and_ai_text(self):
        """Valida que a detecção de balões mescla e preserva text, translated_text e ai_translated_text existentes."""
        # Cria um map prévio simulando balão já traduzido
        boxes = [
            {
                "id": 1, "x1": 50, "y1": 50, "x2": 150, "y2": 150,
                "text": "Hello", "translated_text": "Olá IA", "ai_translated_text": "Olá IA",
                "user_edited": False
            }
        ]
        self.studio.save_page_layout(self.img_path, boxes)

        # Chama detect_page_bubbles
        res = self.studio.detect_page_bubbles(self.img_path)
        self.assertTrue(res["success"])
        
        map_path = os.path.join(self.output_dir, "001_map.json")
        with open(map_path, "r", encoding="utf-8") as f:
            saved = json.load(f)["boxes"]

        # Se houver balão detectado próximo, ele deve manter os dados de tradução
        for b in saved:
            if abs(b["x1"] - 50) < 30 and abs(b["y1"] - 50) < 30:
                self.assertEqual(b.get("translated_text"), "Olá IA")
                self.assertEqual(b.get("ai_translated_text"), "Olá IA")
                self.assertFalse(b.get("user_edited"))


    def test_clear_page_data_ocr_and_translate(self):
        """Valida que clearPageData com stage 'ocr' remove ocr_raw, text, traduções e arquivos intermediários mantendo layout."""
        boxes = [
            {
                "id": 1, "x1": 50, "y1": 50, "x2": 150, "y2": 150,
                "text": "Hello", "ocr_raw": "Hello Raw", "translated_text": "Olá",
                "is_sfx": False, "user_edited": False
            }
        ]
        self.studio.save_page_layout(self.img_path, boxes)
        
        # Cria arquivos intermediários simulados
        clean_p = os.path.join(self.output_dir, "001_map_clean.json")
        ocr_p = os.path.join(self.output_dir, "001_map_ocr.json")
        with open(clean_p, "w", encoding="utf-8") as f: f.write("[]")
        with open(ocr_p, "w", encoding="utf-8") as f: f.write("[]")
        
        # Limpa etapa OCR
        res = self.studio.clearPageData([self.img_path], ["ocr", "translate"])
        self.assertTrue(res["success"])
        
        # Intermediários devem ter sido removidos
        self.assertFalse(os.path.exists(clean_p))
        self.assertFalse(os.path.exists(ocr_p))
        
        # _map.json deve existir com layout intacto mas sem OCR ou ocr_raw
        map_p = os.path.join(self.output_dir, "001_map.json")
        self.assertTrue(os.path.exists(map_p))
        with open(map_p, "r", encoding="utf-8") as f:
            envelope = json.load(f)
        self.assertEqual(envelope["version"], 2)
        data = envelope["boxes"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["x1"], 50)
        self.assertNotIn("text", data[0])
        self.assertNotIn("ocr_raw", data[0])
        self.assertNotIn("translated_text", data[0])


if __name__ == "__main__":
    unittest.main()


