"""Regression tests for previews, note portability and experimental sync."""
import json
import sys
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
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

    def setUp(self):
        self.draft = booklists.load(ROOT / "examples" / "issue-001.json")

    def test_open_preview_is_offline_and_ignores_all_notes(self):
        with patch.object(booklists, "api", side_effect=AssertionError), \
             patch.object(booklists, "local_note", side_effect=AssertionError):
            selection = booklists.preview_selection(self.draft)
            explicit = booklists.preview_selection(self.draft, ROOT / "examples/notes", "open")
        self.assertEqual(selection, explicit)
        self.assertNotIn("personal", selection)
        rendered = booklists.render_preview(selection)
        self.assertEqual(rendered.count("### 《"), 2)
        self.assertEqual(rendered.count("存到我的微信读书"), 1)
        self.assertNotIn("reading.md", rendered)

    def test_personal_preview_from_notes_needs_no_account(self):
        with patch.object(booklists, "api", side_effect=AssertionError):
            selection = booklists.preview_selection(self.draft, ROOT / "examples/notes")
        rendered = booklists.render_preview(selection)
        self.assertEqual(rendered.count("### 《"), 4)
        self.assertEqual(rendered.count("笔记依据：reading.md"), 2)

    def test_question_only_and_unavailable_version(self):
        row = self.draft["personal"][0].copy()
        row.pop("bookId")
        row["readerLink"] = "https://weread.qq.com.evil.example/web/reader/123"
        draft = {"as_of": self.draft["as_of"], "question": "怎样面对待办？", "personal": [row]}
        with patch.object(booklists, "local_note", side_effect=AssertionError), \
             patch.object(booklists, "api", side_effect=AssertionError):
            output = booklists.render_preview(booklists.preview_selection(draft, group="personal"))
        self.assertIn("微信读书版本待核实", output)
        self.assertNotIn("evil.example", output)
        self.assertNotIn("reading.md", output)
        self.assertNotIn("开放书单", output)

    def test_save_scopes_reads_and_does_not_store_notes(self):
        draft = booklists.load(ROOT / "examples" / "issue-001.json")
        catalog = {r["bookId"]: r for group in booklists.NAMES for r in draft[group]}

        def only_book_info(method, bookId):
            self.assertEqual(method, "/book/info")
            return catalog[bookId]

        with patch.object(booklists, "api", side_effect=only_book_info) as api:
            result = booklists.save_editions(draft, ["personal:3300202632", "personal:3300202632"])
        api.assert_called_once_with("/book/info", bookId="3300202632")
        self.assertEqual(list(result), ["personal"])
        self.assertEqual([book["bookId"] for book in result["personal"]], ["3300202632"])
        self.assertNotIn("reading.md", json.dumps(result))
        self.assertNotIn("reason", result["personal"][0])
        with patch.object(booklists, "api", side_effect=AssertionError):
            with self.assertRaises(ValueError):
                booklists.save_editions(draft, ["open", "open:missing"])

    def test_save_rejects_different_edition_with_same_title_and_author(self):
        row = self.draft["open"][0]
        wrong = dict(row, readerLink="https://weread.qq.com/web/reader/another")
        with patch.object(booklists, "api", return_value=wrong), self.assertRaises(ValueError):
            booklists.save_editions(self.draft, ["open:" + row["bookId"]])

    def test_shelf_and_lists_are_independent(self):
        entry = {"bookId": "42", "title": "A", "link": "https://weread.qq.com/a"}
        plan = {"run": "sample", "mode": "shelf", "personal": [entry], "open": [entry]}
        initial = booklists.reconcile(plan, set(), {})
        self.assertEqual(len(initial["shelf_missing"]), 1)
        self.assertEqual(initial["lists"], {})
        self.assertTrue(booklists.reconcile(plan, {"42"}, {})["verified"])
        plan["mode"] = "booklist"
        initial = booklists.reconcile(plan, set(), {})
        self.assertEqual(initial["shelf_missing"], [])
        self.assertFalse(initial["verified"])
        complete = dict(scope="my_created_booklists", state="present", members=["42"], all_pages=True)
        personal, opened = booklists.NAMES.values()
        partial = dict(complete, members=[], all_pages=False)
        observed = booklists.reconcile(plan, {"42"}, {personal: complete, opened: partial})
        self.assertEqual(observed["lists"][opened]["action"], "inspect")
        self.assertFalse(observed["verified"])
        self.assertTrue(booklists.reconcile(plan, set(), {personal: complete, opened: complete})["verified"])

    def test_booklist_only_without_editor_never_touches_shelf(self):
        plan = {"schema": 2, "run": "sample", "mode": "booklist", "account": "test",
                "open": [{"bookId": "42", "title": "A", "link": "https://weread.qq.com/a"}]}
        with patch.object(booklists, "load", return_value=plan), \
             patch.object(booklists, "account_and_name", return_value=("test", "demo")), \
             patch.object(booklists, "api", side_effect=AssertionError):
            result = booklists.status(SimpleNamespace(state="unused", ui=None))
        self.assertEqual(result["shelf_missing"], [])
        self.assertEqual(list(result["lists"]), [booklists.NAMES["open"]])
        self.assertEqual(result["lists"][booklists.NAMES["open"]]["action"], "inspect")
        self.assertFalse(result["verified"])
        unavailable = {booklists.NAMES["open"]: {"state": "unavailable"}}
        stopped = booklists.reconcile(plan, set(), unavailable)
        self.assertEqual(stopped["lists"][booklists.NAMES["open"]]["action"], "keep_recommendations")
        self.assertFalse(stopped["shelf_missing"])
        self.assertFalse(stopped["verified"])

    def test_old_plan_does_not_authorize_either_save_mode(self):
        with patch.object(booklists, "load", return_value={"schema": 1, "run": "old"}), \
             patch.object(booklists, "api", side_effect=AssertionError):
            result = booklists.status(SimpleNamespace(state="unused", ui=None))
        self.assertEqual(result["action"], "choose_save_mode")
        self.assertFalse(result["verified"])
