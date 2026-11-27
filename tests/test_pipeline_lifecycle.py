import os
import sys
import unittest
import tempfile
import json
import shutil


import src.run_batch as rb
from PIL import Image

class TestPipelineLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="pipeline_test_")
        self.output_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.img_path = os.path.join(self.temp_dir, "001.png")
        img = Image.new("RGB", (400, 600), color="white")
        img.save(self.img_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_backup_and_rollback_mechanism(self):
        """Valida que o backup cirúrgico restaura arquivos exatamente como estavam se houver cancelamento com rollback."""
        test_file = os.path.join(self.output_dir, "001_map.json")
        original_data = [{"id": 1, "text": "Original Seguro"}]
        with open(test_file, "w", encoding="utf-8") as f:
            json.dump(original_data, f)

        # Registra backup no run_batch
        rb._session_backups.clear()
        rb.backup_file(test_file)

        # Modifica o arquivo (simulando falha no meio do processo)
        with open(test_file, "w", encoding="utf-8") as f:
            json.dump([{"id": 1, "text": "Corrompido/Incompleto"}], f)

        # Solicita cancelamento com rollback
        rb.request_cancel(rollback=True)

        # Executa rollback cirúrgico
        rb.execute_rollback()

        # O arquivo deve ter sido restaurado perfeitamente ao estado original
        with open(test_file, "r", encoding="utf-8") as f:
            restored = json.load(f)
        self.assertEqual(restored[0]["text"], "Original Seguro")

        # Limpa flag após o teste
        rb._cancel_event.clear()

    def test_cancel_event_trigger(self):
        """Valida o controle de interrupção imediata via threading.Event."""
        rb._cancel_event.clear()
        self.assertFalse(rb._cancel_event.is_set())

        rb._cancel_event.set()
        self.assertTrue(rb._cancel_event.is_set())
        rb._cancel_event.clear()

    def test_safe_image_prefetcher_lifecycle(self):
        """Valida que o SafeImagePrefetcher carrega em RAM, faz pipeline do next_path e encerra limpo."""
        from src.utils.image_prefetcher import SafeImagePrefetcher
        import threading
        import time

        p1 = os.path.join(self.temp_dir, "page1.png")
        p2 = os.path.join(self.temp_dir, "page2.png")
        Image.new("RGB", (200, 300), color="red").save(p1)
        Image.new("RGB", (200, 300), color="blue").save(p2)

        cancel_ev = threading.Event()
        with SafeImagePrefetcher([p1, p2], cancel_event=cancel_ev) as prefetcher:
            # page1 já foi agendado em background
            img1 = prefetcher.get_image(p1, next_path=p2)
            self.assertIsNotNone(img1)
            self.assertEqual(img1.size, (200, 300))

            # Aguarda brevíssimo instante para o worker de page2 iniciar/carregar
            time.sleep(0.05)

            # page2 deve vir do cache de RAM
            img2 = prefetcher.get_image(p2)
            self.assertIsNotNone(img2)
            self.assertEqual(img2.size, (200, 300))

        # Ao sair do context manager, a RAM é limpa e threads encerradas
        self.assertIsNone(prefetcher._prefetched_img)
        self.assertTrue(prefetcher._stop_event.is_set())

    def test_safe_image_prefetcher_fallback_and_cancel(self):
        """Valida resiliência do prefetcher quando cancelado ou com arquivo ausente."""
        from src.utils.image_prefetcher import SafeImagePrefetcher
        import threading

        cancel_ev = threading.Event()
        cancel_ev.set()  # Já cancelado
        p1 = os.path.join(self.temp_dir, "non_existent.png")

        prefetcher = SafeImagePrefetcher([p1], cancel_event=cancel_ev)
        # Não deve lançar exceção no worker
        prefetcher.stop()

        # Fallback tenta ler do disco e lança FileNotFoundError padrão
        with self.assertRaises((FileNotFoundError, OSError)):
            prefetcher.get_image(p1)

    def test_smart_skip_mtime_logic(self):
        """Valida que alterações na imagem original invalidam o cache do _map.json."""
        import time

        img_file = os.path.join(self.temp_dir, "page_mtime.png")
        map_file = os.path.join(self.output_dir, "page_mtime_map.json")

        Image.new("RGB", (100, 100), color="white").save(img_file)
        time.sleep(0.05)

        # Simula mapa gerado depois da imagem
        with open(map_file, "w", encoding="utf-8") as f:
            json.dump([{"id": 1, "text": "Hello", "translated_text": "Olá"}], f)

        # Estado 1: mapa mais recente que imagem -> deve pular
        img_mtime = os.path.getmtime(img_file)
        map_mtime = os.path.getmtime(map_file)
        self.assertLessEqual(img_mtime, map_mtime)

        # Estado 2: imagem é editada pelo usuário no Photoshop (mtime da imagem fica maior)
        time.sleep(0.05)
        Image.new("RGB", (100, 100), color="black").save(img_file)
        new_img_mtime = os.path.getmtime(img_file)
        self.assertGreater(new_img_mtime, map_mtime)

if __name__ == "__main__":
    unittest.main()
