from __future__ import annotations

import json
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts/novi_sad/reference/reports/novi_sad_validation_report.json"
RESULTS = ROOT / "artifacts/novi_sad/reference/models/novi_sad_powerflow_results.json"
REFERENCE_MANIFEST = ROOT / "artifacts/novi_sad/reference/reference_manifest.json"


class RepositoryTests(unittest.TestCase):
    def test_reference_model_baseline(self):
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        results = json.loads(RESULTS.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "INTERNAL_CONSISTENCY_PASS")
        self.assertTrue(all(report["validation_checks"].values()))
        self.assertEqual(results["counts"]["loads"], 2648)
        self.assertEqual(results["counts"]["external_grids"], 9)
        self.assertLess(results["max_transformer_loading_pct"], 90.0)

    def test_reference_bundle_checksums(self):
        manifest = json.loads(REFERENCE_MANIFEST.read_text(encoding="utf-8"))
        roots = (
            ROOT / "data/novi_sad/reference/inputs",
            ROOT / "data/novi_sad/reference/generated",
            ROOT / "artifacts/novi_sad/reference/models",
            ROOT / "artifacts/novi_sad/reference/maps",
            ROOT / "artifacts/novi_sad/reference/reports",
        )
        expected_paths = {
            path.relative_to(ROOT).as_posix()
            for root in roots
            for path in root.rglob("*")
            if path.is_file()
        }
        manifest_paths = {entry["path"] for entry in manifest["files"]}
        self.assertEqual(manifest_paths, expected_paths)
        for entry in manifest["files"]:
            path = ROOT / entry["path"]
            self.assertTrue(path.is_file(), entry["path"])
            content = path.read_bytes().replace(b"\r\n", b"\n")
            self.assertEqual(len(content), entry["canonical_size_bytes"], entry["path"])
            self.assertEqual(
                hashlib.sha256(content).hexdigest(),
                entry["sha256_lf_normalized"],
                entry["path"],
            )

    def test_root_has_no_runtime_or_python_dump_files(self):
        forbidden_suffixes = {".py", ".pkl", ".log", ".err"}
        offenders = [
            path.name
            for path in ROOT.iterdir()
            if path.is_file() and path.suffix.lower() in forbidden_suffixes
        ]
        self.assertEqual(offenders, [])

    def test_checkout_launcher_is_working_directory_independent(self):
        launcher = ROOT / "scripts/run_novi_sad.py"
        completed = subprocess.run(
            [sys.executable, str(launcher), "--help"],
            cwd=ROOT.parent,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--refresh-osm", completed.stdout)

    def test_missing_cache_requires_explicit_refresh(self):
        launcher = ROOT / "scripts/run_novi_sad.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_root = Path(temp_dir)
            config_dir = fake_root / "configs"
            config_dir.mkdir()
            (config_dir / "novi_sad.json").write_text("{}", encoding="utf-8")
            environment = os.environ.copy()
            environment["MVGRID_ROOT"] = str(fake_root)
            completed = subprocess.run(
                [sys.executable, str(launcher)],
                cwd=fake_root,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("use --refresh-osm", completed.stderr)

    def test_local_markdown_links_resolve(self):
        pattern = re.compile(r"\[[^]]*\]\(([^)]+)\)")
        missing = []
        for document in ROOT.rglob("*.md"):
            if any(part in {".git", ".venv", "data", "node_modules"} for part in document.parts[len(ROOT.parts):]):
                continue
            for target in pattern.findall(document.read_text(encoding="utf-8")):
                if "://" in target or target.startswith("#"):
                    continue
                clean_target = target.split("#", 1)[0]
                if clean_target and not (document.parent / clean_target).resolve().exists():
                    missing.append(f"{document.relative_to(ROOT)} -> {target}")
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
