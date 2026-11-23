"""Regression tests for previews, note portability and experimental sync."""
import sys
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import booklists


class BooklistsTests(unittest.TestCase):
    def test_markdown_without_heading_and_named_section(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            note = root / "topic.md"
            note.write_text("One specific question", encoding="utf-8")
            self.assertEqual(booklists.local_note(root, {"path": note.name}), {"path": note.name})
            with self.assertRaises(ValueError):
                booklists.local_note(root, {"path": note.name, "heading": "Missing"})
            note.write_text("## Section\nA question", encoding="utf-8")
            row = booklists.local_note(root, {"path": note.name, "heading": "Section"})
            self.assertEqual(row["heading"], "Section")

    def test_note_stays_in_vault(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            vault = root / "vault"
            vault.mkdir()
            (root / "outside.md").write_text("Outside", encoding="utf-8")
            with self.assertRaises(ValueError):
                booklists.local_note(vault, {"path": "../outside.md"})

    def test_inclusive_discussion_window(self):
        evidence = {"date": "2026-10-25", "url": "https://example.org/review", "voice": "reader"}
        self.assertEqual(booklists.checked_evidence([evidence], date(2026, 11, 23)), [evidence])
        for outside in ("2026-10-24", "2026-11-24"):
            with self.subTest(outside=outside), self.assertRaises(ValueError):
                booklists.checked_evidence([{**evidence, "date": outside}], date(2026, 11, 23))

    def test_preview_never_fetches_account_or_shelf(self):
        draft = booklists.load(ROOT / "examples" / "issue-001.json")
        catalog = {r["bookId"]: r for group in booklists.NAMES for r in draft[group]}

        def only_book_info(method, bookId):
            self.assertEqual(method, "/book/info")
            return {**catalog[bookId], "readerLink": "https://weread.qq.com/web/reader/" + bookId}

        with patch.object(booklists, "api", side_effect=only_book_info):
            result = booklists.resolve(draft, ROOT / "examples" / "notes")
        rendered = booklists.render_preview(result)
        self.assertNotIn("account", result)
        self.assertEqual(rendered.count("### 《"), 4)
        self.assertEqual(rendered.count("笔记依据：reading.md"), 2)

    def test_shelf_and_lists_are_independent(self):
        entry = {"bookId": "42", "title": "A", "link": "https://weread.qq.com/a"}
        plan = {"run": "sample", "personal": [entry], "open": [entry]}
        initial = booklists.reconcile(plan, set(), {})
        self.assertEqual(len(initial["shelf_missing"]), 1)
        complete = dict(scope="my_created_booklists", state="present", members=["42"], all_pages=True)
        personal, opened = booklists.NAMES.values()
        partial = dict(complete, members=[], all_pages=False)
        observed = booklists.reconcile(plan, {"42"}, {personal: complete, opened: partial})
        self.assertEqual(observed["lists"][opened]["action"], "inspect")
        self.assertFalse(observed["verified"])
        self.assertTrue(booklists.reconcile(plan, {"42"}, {personal: complete, opened: complete})["verified"])
