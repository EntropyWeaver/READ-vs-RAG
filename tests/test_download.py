import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from read_vs_rag.download import fetch_upstream


class DownloadTests(unittest.TestCase):
    def prepare(self, root, data=b'{"sample":true}\n'):
        meta = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        manifest = {"commit": "a" * 40, "files": {name: meta for name in ["results.jsonl", "results_sweep.jsonl"]}}
        Path(root, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return data

    def test_fetch_verifies_bytes_and_reuses_cache(self):
        with tempfile.TemporaryDirectory() as root:
            data = self.prepare(root)
            with patch("urllib.request.urlopen", side_effect=lambda *a, **k: io.BytesIO(data)) as urlopen:
                result = fetch_upstream(root)
                self.assertEqual(len(result), 2)
                self.assertIn("/" + "a" * 40 + "/results/", urlopen.call_args.args[0])
            with patch("urllib.request.urlopen") as urlopen:
                self.assertTrue(all(r["status"] == "already_verified" for r in fetch_upstream(root)))
                urlopen.assert_not_called()

    def test_bad_download_not_written(self):
        with tempfile.TemporaryDirectory() as root:
            data = self.prepare(root)
            with patch("urllib.request.urlopen", return_value=io.BytesIO(b"x" * len(data))):
                with self.assertRaises(ValueError):
                    fetch_upstream(root)
            self.assertFalse(Path(root, "results.jsonl").exists())

    def test_existing_bad_file_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            self.prepare(root)
            path = Path(root, "results.jsonl")
            path.write_bytes(b"investigate this")
            with patch("urllib.request.urlopen") as urlopen, self.assertRaises(ValueError):
                fetch_upstream(root)
            urlopen.assert_not_called()
            self.assertEqual(path.read_bytes(), b"investigate this")
