import os
import unittest
import tempfile
from src.utils.hf_snapshot_resolver import (
    resolve_hf_snapshot_path,
    _resolve_hf_snapshot_path,
    is_valid_florence_dir,
)


class TestHfSnapshotResolver(unittest.TestCase):
    def test_nonexistent_directory(self):
        res = resolve_hf_snapshot_path("C:/nonexistent/path/here", "repo/model")
        self.assertIsNone(res)

    def test_snapshot_resolution_order(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_folder = os.path.join(tmp_dir, "models--test--model")
            snapshots_dir = os.path.join(repo_folder, "snapshots")
            os.makedirs(snapshots_dir, exist_ok=True)

            # Create older snapshot
            snap1 = os.path.join(snapshots_dir, "snap1")
            os.makedirs(snap1, exist_ok=True)
            with open(os.path.join(snap1, "model.bin"), "wb") as f:
                f.write(b"older_data")

            # Create newer snapshot
            snap2 = os.path.join(snapshots_dir, "snap2")
            os.makedirs(snap2, exist_ok=True)
            with open(os.path.join(snap2, "model.bin"), "wb") as f:
                f.write(b"newer_data")

            # Update mtime of snap2 to be newer
            os.utime(snap1, (1000, 1000))
            os.utime(snap2, (2000, 2000))

            resolved = resolve_hf_snapshot_path(tmp_dir, "test/model")
            self.assertEqual(resolved, snap2)

    def test_ignores_empty_or_lock_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_folder = os.path.join(tmp_dir, "models--test--model")
            snapshots_dir = os.path.join(repo_folder, "snapshots")
            os.makedirs(snapshots_dir, exist_ok=True)

            # Create snapshot with only lock file
            snap = os.path.join(snapshots_dir, "snap_lock")
            os.makedirs(snap, exist_ok=True)
            with open(os.path.join(snap, "download.lock"), "wb") as f:
                f.write(b"lock")

            resolved = resolve_hf_snapshot_path(tmp_dir, "test/model")
            self.assertIsNone(resolved)

    def test_is_valid_florence_dir_edge_cases(self):
        self.assertFalse(is_valid_florence_dir(None))
        self.assertFalse(is_valid_florence_dir("C:/nonexistent/path"))

        with tempfile.TemporaryDirectory() as tmp_dir:
            self.assertFalse(is_valid_florence_dir(tmp_dir))

            # Apenas config.json
            with open(os.path.join(tmp_dir, "config.json"), "w") as f:
                f.write("{}")
            self.assertFalse(is_valid_florence_dir(tmp_dir))

            # config.json + processing_florence2.py (sem pesos)
            with open(os.path.join(tmp_dir, "processing_florence2.py"), "w") as f:
                f.write("# code")
            self.assertFalse(is_valid_florence_dir(tmp_dir))

            # config.json + processing_florence2.py + model.safetensors -> Válido
            safetensors_path = os.path.join(tmp_dir, "model.safetensors")
            with open(safetensors_path, "wb") as f:
                f.write(b"weights")
            self.assertTrue(is_valid_florence_dir(tmp_dir))

            # Teste alternativo com modeling_florence2.py e pytorch_model.bin
            os.remove(os.path.join(tmp_dir, "processing_florence2.py"))
            os.remove(safetensors_path)
            self.assertFalse(is_valid_florence_dir(tmp_dir))

            with open(os.path.join(tmp_dir, "modeling_florence2.py"), "w") as f:
                f.write("# model code")
            with open(os.path.join(tmp_dir, "pytorch_model.bin"), "wb") as f:
                f.write(b"weights")
            self.assertTrue(is_valid_florence_dir(tmp_dir))


if __name__ == "__main__":
    unittest.main()
