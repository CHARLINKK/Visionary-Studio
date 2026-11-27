import unittest
import time
from unittest.mock import patch, MagicMock
from src.api_services.pipeline_service import PipelineService
import json

class TestPipelineService(unittest.TestCase):
    def setUp(self):
        self.api = MagicMock()
        self.api.getSettings.return_value = {}
        self.ps = PipelineService(self.api)

    @patch("src.run_batch.run_batch_pipeline")
    def test_queueJob_and_getStatus(self, mock_run):
        # Allow the background thread to finish quickly
        mock_run.return_value = True
        
        data = {"job_id": "job123", "folderPath": "/tmp/test", "steps": {"layout": True, "ocr": True, "translate": True}}
        res = self.ps.queueJob(data)
        
        self.assertTrue(res["success"])
        self.assertEqual(res["job_id"], "job123")
        
        # Wait for thread to finish (max 2 seconds)
        for _ in range(20):
            status = self.ps.getJobStatus("job123")
            if status["status"] in ["completed", "failed", "cancelled"]:
                break
            time.sleep(0.1)
            
        status = self.ps.getJobStatus("job123")
        self.assertTrue(status["success"])
        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["progress"], 100)
        
        all_status = self.ps.getPipelineStatus()
        self.assertTrue(all_status["success"])
        self.assertIn("job123", all_status["jobs"])

    @patch("src.run_batch.run_batch_pipeline")
    def test_queueJob_fail(self, mock_run):
        mock_run.side_effect = Exception("Forced error")
        
        res = self.ps.queueJob({"job_id": "jobfail", "folderPath": "/tmp/test"})
        self.assertTrue(res["success"])
        
        for _ in range(50):
            status = self.ps.getJobStatus("jobfail")
            if status["status"] in ["completed", "failed", "cancelled"]:
                break
            time.sleep(0.1)
            
        status = self.ps.getJobStatus("jobfail")
        self.assertEqual(status["status"], "failed")

    def test_getJobStatus_not_found(self):
        status = self.ps.getJobStatus("inexistente")
        self.assertFalse(status["success"])

    def test_clearCompletedJobs(self):
        self.ps._active_jobs["job1"] = {"status": "completed"}
        self.ps._active_jobs["job2"] = {"status": "failed"}
        self.ps._active_jobs["job3"] = {"status": "cancelled"}
        self.ps._active_jobs["job4"] = {"status": "running"}
        
        res = self.ps.clearCompletedJobs()
        self.assertTrue(res["success"])
        self.assertEqual(res["cleared_count"], 3)
        self.assertIn("job4", self.ps._active_jobs)
        self.assertNotIn("job1", self.ps._active_jobs)

    def test_clearJobLogs(self):
        self.ps._active_jobs["job1"] = {"status": "running", "logs": ["log1", "log2"]}
        res = self.ps.clearJobLogs("job1")
        self.assertTrue(res["success"])
        self.assertEqual(len(self.ps._active_jobs["job1"]["logs"]), 0)

    def test_clearJobLogs_not_found(self):
        res = self.ps.clearJobLogs("inexistente")
        self.assertFalse(res["success"])

    @patch("src.run_batch.request_cancel")
    def test_cancelJob(self, mock_cancel):
        res = self.ps.cancelJob("job123")
        self.assertTrue(res["success"])
        mock_cancel.assert_called_once()

    @patch("src.utils.txt_sync.sync_chapter_txt")
    def test_finalizePipeline(self, mock_sync):
        mock_sync.return_value = {"success": True}
        res = self.ps.finalizePipeline({"inputPath": "/tmp/test", "finalName": "cap1"})
        self.assertTrue(res["success"])
        mock_sync.assert_called_once()

    def test_finalizePipeline_no_path(self):
        res = self.ps.finalizePipeline({"inputPath": ""})
        self.assertFalse(res["success"])

    @patch("src.run_batch.request_cancel")
    def test_cancelJob_queued_does_not_cancel_running_job(self, mock_cancel):
        # Job A está rodando na GPU
        self.ps._active_jobs["jobA"] = {"status": "running"}
        self.ps._current_running_job_id = "jobA"

        # Job B está na fila de espera
        self.ps._active_jobs["jobB"] = {"status": "running"}

        # Cancelar Job B (da fila) NÃO pode chamar request_cancel() nem matar Job A!
        res = self.ps.cancelJob("jobB")
        self.assertTrue(res["success"])
        self.assertEqual(self.ps._active_jobs["jobB"]["status"], "cancelled")
        mock_cancel.assert_not_called()
        self.assertEqual(self.ps._current_running_job_id, "jobA")

        # Cancelar Job A (em execução) DEVE chamar request_cancel()
        res_a = self.ps.cancelJob("jobA")
        self.assertTrue(res_a["success"])
        self.assertEqual(self.ps._active_jobs["jobA"]["status"], "cancelled")
        mock_cancel.assert_called_once()

    @patch("src.run_batch.request_cancel")
    def test_cancelAllJobs(self, mock_cancel):
        self.ps._active_jobs["job1"] = {"status": "running"}
        self.ps._active_jobs["job2"] = {"status": "pending"}
        self.ps._active_jobs["job3"] = {"status": "completed"}

        res = self.ps.cancelAllJobs()
        self.assertTrue(res["success"])
        self.assertEqual(res["cancelled_count"], 2)
        self.assertEqual(self.ps._active_jobs["job1"]["status"], "cancelled")
        self.assertEqual(self.ps._active_jobs["job2"]["status"], "cancelled")
        self.assertEqual(self.ps._active_jobs["job3"]["status"], "completed")
        mock_cancel.assert_called_once()

    @patch("src.run_batch.run_batch_pipeline")
    def test_queued_job_exits_without_running_if_cancelled(self, mock_run):
        # Simula cancelamento prévio de um job na fila antes da thread adquirir o lock
        data = {"job_id": "job_cancelled_early", "folderPath": "/tmp/test"}
        
        # Enfileira
        res = self.ps.queueJob(data)
        self.assertTrue(res["success"])

        # Cancela imediatamente antes da execução
        self.ps.cancelJob("job_cancelled_early")
        self.assertEqual(self.ps._active_jobs["job_cancelled_early"]["status"], "cancelled")

        # Aguarda tempo suficiente para a thread ter chance de rodar
        time.sleep(0.3)

        # run_batch_pipeline NUNCA deve ser chamado para job cancelado na fila
        mock_run.assert_not_called()

    @patch("src.run_batch.request_cancel")
    def test_cancelJob_queue_timing_edge_case(self, mock_cancel):
        # Simula momento de inicialização: jobs enfileirados, mas _current_running_job_id ainda é None
        self.ps._current_running_job_id = None
        self.ps._job_queue = ["job_primeiro", "job_segundo"]
        self.ps._active_jobs["job_primeiro"] = {"status": "running"}
        self.ps._active_jobs["job_segundo"] = {"status": "running"}

        # Cancelar o segundo da fila não pode disparar cancelamento do pipeline!
        res_segundo = self.ps.cancelJob("job_segundo")
        self.assertTrue(res_segundo["success"])
        self.assertEqual(self.ps._active_jobs["job_segundo"]["status"], "cancelled")
        mock_cancel.assert_not_called()
        self.assertNotIn("job_segundo", self.ps._job_queue)

        # Cancelar o primeiro da fila deve disparar cancelamento do pipeline
        res_primeiro = self.ps.cancelJob("job_primeiro")
        self.assertTrue(res_primeiro["success"])
        self.assertEqual(self.ps._active_jobs["job_primeiro"]["status"], "cancelled")
        mock_cancel.assert_called_once()
        self.assertNotIn("job_primeiro", self.ps._job_queue)

    def test_queueJob_input_validations(self):
        # Non-dict payload
        res = self.ps.queueJob(None)
        self.assertFalse(res["success"])
        self.assertIn("Payload inválido", res["error"])

        # Missing folderPath
        res = self.ps.queueJob({"job_id": "test"})
        self.assertFalse(res["success"])
        self.assertIn("folderPath", res["error"])

        # Empty folderPath
        res = self.ps.queueJob({"folderPath": "   "})
        self.assertFalse(res["success"])
        self.assertIn("folderPath", res["error"])

    @patch("src.run_batch.request_cancel")
    def test_cancelAllJobs_cancels_queued_jobs(self, mock_cancel):
        self.ps._active_jobs["running_job"] = {"status": "running"}
        self.ps._active_jobs["queued_job"] = {"status": "queued"}
        self.ps._active_jobs["completed_job"] = {"status": "completed"}
        self.ps._job_queue = ["queued_job"]

        res = self.ps.cancelAllJobs()
        self.assertTrue(res["success"])
        self.assertEqual(res["cancelled_count"], 2)
        self.assertEqual(self.ps._active_jobs["running_job"]["status"], "cancelled")
        self.assertEqual(self.ps._active_jobs["queued_job"]["status"], "cancelled")
        self.assertEqual(self.ps._active_jobs["completed_job"]["status"], "completed")
        self.assertEqual(len(self.ps._job_queue), 0)

    @patch("src.utils.txt_sync.sync_chapter_txt")
    def test_finalizePipeline_string_path(self, mock_sync):
        mock_sync.return_value = {"success": True}
        res = self.ps.finalizePipeline("/tmp/test/cap1")
        self.assertTrue(res["success"])
        mock_sync.assert_called_with("/tmp/test/cap1", None)

    def test_bounded_terminal_jobs_retention(self):
        """Valida que jobs finalizados que excedam o limite máximo são descartados do mais antigo para o mais novo."""
        ps = PipelineService(self.api, max_retained_jobs=3)

        # Injeta 5 jobs finalizados com timestamps crescentes
        for i in range(1, 6):
            ps._active_jobs[f"job_{i}"] = {
                "status": "completed",
                "finished_at": 1000 + i,
                "logs": [f"Log {i}"]
            }
            ps._job_sessions[f"job_{i}"] = MagicMock()

        # Dispara a política de evicção
        with ps._jobs_lock:
            ps._evict_old_terminal_jobs()

        # Como o limite é 3, os 2 mais antigos (job_1 e job_2) devem ser removidos
        self.assertEqual(len(ps._active_jobs), 3)
        self.assertNotIn("job_1", ps._active_jobs)
        self.assertNotIn("job_2", ps._active_jobs)
        self.assertIn("job_3", ps._active_jobs)
        self.assertIn("job_4", ps._active_jobs)
        self.assertIn("job_5", ps._active_jobs)

        # As sessões correspondentes também devem ser limpas da memória
        self.assertNotIn("job_1", ps._job_sessions)
        self.assertNotIn("job_2", ps._job_sessions)
        self.assertIn("job_3", ps._job_sessions)

    def test_eviction_preserves_running_and_queued_jobs(self):
        """Garante que tarefas em execução ou na fila nunca sejam descartadas pela evicção de memória."""
        ps = PipelineService(self.api, max_retained_jobs=2)

        # 3 jobs concluídos (1 a mais que o limite)
        ps._active_jobs["old_done"] = {"status": "completed", "finished_at": 100}
        ps._active_jobs["new_done"] = {"status": "completed", "finished_at": 200}
        ps._active_jobs["failed_job"] = {"status": "failed", "finished_at": 300}

        # 2 jobs ativos
        ps._active_jobs["active_running"] = {"status": "running", "created_at": 50}
        ps._active_jobs["active_queued"] = {"status": "queued", "created_at": 60}

        with ps._jobs_lock:
            ps._evict_old_terminal_jobs()

        # O terminal mais antigo ('old_done') foi evictado, mas os ativos continuam intactos
        self.assertNotIn("old_done", ps._active_jobs)
        self.assertIn("new_done", ps._active_jobs)
        self.assertIn("failed_job", ps._active_jobs)
        self.assertIn("active_running", ps._active_jobs)
        self.assertIn("active_queued", ps._active_jobs)


