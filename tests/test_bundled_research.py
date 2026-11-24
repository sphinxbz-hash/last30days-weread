import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research"


class BundledResearchTests(unittest.TestCase):
    def test_single_skill_entry_and_internal_guides(self):
        self.assertTrue((ROOT / "SKILL.md").is_file())
        self.assertEqual(list(RESEARCH.rglob("SKILL.md")), [])
        self.assertTrue((RESEARCH / "GUIDE.md").is_file())
        self.assertTrue((RESEARCH / "LICENSE").is_file())
        for mode in ("research-runbook", "discovery", "comparison", "library-queue"):
            self.assertTrue((RESEARCH / "references" / (mode + ".md")).is_file())

    @unittest.skipIf(sys.version_info < (3, 12), "Live research requires Python 3.12+")
    def test_standalone_engine_from_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            env = {key: value for key, value in os.environ.items()
                   if key.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT"}}
            env.update(HOME=folder, USERPROFILE=folder, APPDATA=folder, LOCALAPPDATA=folder,
                       PATH=str(Path(sys.executable).parent), FROM_BROWSER="off",
                       AGENTCOOKIE="off", LAST30DAYS_LIBRARY_CONTEXT="off")
            cmd = [sys.executable, "-B", "-X", "utf8", str(RESEARCH / "scripts/last30days.py"),
                   "book discussions", "--mock", "--search", "hackernews", "--no-browser-cookies",
                   "--as-of", "2026-11-24", "--days", "29", "--save-dir=",
                   "--emit=json", "--json-profile=raw"]
            result = subprocess.run(cmd, cwd=folder, env=env, capture_output=True,
                                    encoding="utf-8", timeout=45)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual((report["range_from"], report["range_to"]), ("2026-10-26", "2026-11-24"))
            self.assertIn("items_by_source", report)
