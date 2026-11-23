import json
import sys
import unittest
from pathlib import Path
from subprocess import TimeoutExpired
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import booklists
import zlibrary_links as links


class ZLibraryLinksTests(unittest.TestCase):
    book = {"title": "赎罪（英国同名电影原著）", "author": "[英]伊恩·麦克尤恩",
            "isbn": "9787532777754", "translator": "郭国良", "publisher": "上海译文出版社"}
    url = "https://z-library.sk/book/123/abcdef/atonement.html"
    result = {"name": "赎罪", "authors": ["伊恩·麦克尤恩"], "isbn_13": "978-7-5327-7775-4",
              "url": url, "download_url": "https://z-library.sk/dl/private", "hash": "test"}

    def test_offline_link_uses_only_public_title_author(self):
        row = dict(self.book, title="A/B? #&（修订版）", note="PRIVATE")
        url = urlsplit(links.search_link(row))
        self.assertEqual(unquote(url.path.split("/")[-1]), "A/B? #& 伊恩·麦克尤恩")
        self.assertEqual((url.query, url.fragment), ("", ""))
        self.assertEqual(links.catalogue_query(self.book), "赎罪 伊恩·麦克尤恩")
        with self.assertRaises(ValueError):
            links.search_link(row, "unrelated.example")

    def test_isbn10_and_isbn13(self):
        self.assertEqual(links.isbn13("0-306-40615-2"), "9780306406157")
        self.assertEqual(links.isbn13("0-8044-2957-X"), "9780804429573")
        for invalid in ("9787532777755", "", None, "9780306406157 extra"):
            self.assertEqual(links.isbn13(invalid), "")
        self.assertEqual(links.matching_edition(self.book, [self.result]), self.url)
        self.assertEqual(links.matching_edition(self.book, [dict(self.result, isbn_13="9780306406157")]), "")

    def test_translator_match_requires_consistent_unambiguous_edition(self):
        book = dict(self.book, title="赎罪")
        candidate = dict(self.result, isbn_13="", authors=["伊恩·麦克尤恩；郭国良（译）"])
        self.assertEqual(links.matching_edition(book, [candidate]), self.url)
        for changed in ({"authors": ["凑佳苗；郭国良（译）"]}, {"authors": ["伊恩·麦克尤恩；另一位译者（译）"]},
                        {"authors": ["伊恩·麦克尤恩；郭国良"]}, {"name": "赎罪（改写版）"},
                        {"publisher": "不同的出版社"}, {"isbn_13": "9780306406157"}):
            self.assertEqual(links.matching_edition(book, [dict(candidate, **changed)]), "")
        other = dict(candidate, url="https://z-library.sk/book/999/title.html")
        self.assertEqual(links.matching_edition(book, [candidate, other]), "")
        conflicting = dict(candidate, isbn_13=self.book["isbn"], isbn_10="0-306-40615-2")
        self.assertEqual(links.matching_edition(dict(book, isbn=""), [conflicting]), "")

    def test_only_catalogue_pages_are_rendered(self):
        for url in ("https://z-library.sk/dl/private", "https://z-library.sk/book/1/a?token=abc",
                    "https://z-library.sk.evil.example/book/1/a", "https://user@z-library.sk/book/1/a",
                    "https://z-library.sk/book/1/%2E%2E", "https://z-library.sk/book/1/%2Fdl",
                    "https://z-library.sk/book/1/foo%0abar", "https://[bad", None):
            self.assertEqual(links.matching_edition(self.book, [dict(self.result, url=url)]), "")

    def test_opt_in_queries_only_selected_public_metadata_once(self):
        draft = booklists.load(ROOT / "examples" / "issue-001.json")
        draft["open"] = [{**draft["open"][0], **self.book, "zlibrary_edition": "https://untrusted.example"}]
        selection = booklists.preview_selection(draft, group="open")
        book = selection["open"][0]
        with patch.object(links.subprocess, "run", side_effect=AssertionError):
            ordinary = booklists.render_preview(selection)
        self.assertIn("在 Z-Library 搜索", ordinary)
        self.assertNotIn("untrusted", ordinary)
        output = SimpleNamespace(stdout=json.dumps({"books": [self.result]}))
        with patch.object(links.shutil, "which", return_value="zlib"), \
             patch.object(links.subprocess, "run", return_value=output) as run:
            self.assertEqual(links.lookup_editions([book, book.copy()]), "")
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0], ["zlib", "search", "--json", "--count", "10", "--", self.book["isbn"]])
        self.assertIn("[Z-Library 同版书目](" + self.url + ")", booklists.render_preview(selection))
        self.assertNotIn("/dl/", booklists.render_preview(selection))

    def test_unavailable_lookup_preserves_preview(self):
        books = [self.book.copy(), self.book.copy()]
        with patch.object(links.shutil, "which", return_value=None), \
             patch.object(links.subprocess, "run", side_effect=AssertionError):
            self.assertTrue(links.lookup_editions(books))
        with patch.object(links.shutil, "which", return_value="zlib"), \
             patch.object(links.subprocess, "run", side_effect=TimeoutExpired("zlib", 20)) as run:
            self.assertTrue(links.lookup_editions(books))
            run.assert_called_once()
        self.assertFalse(any("zlibrary_edition" in book for book in books))

    def test_fallback_queries_title_and_author_after_empty_isbn_search(self):
        book = dict(self.book, title="赎罪")
        authors = ["伊恩·麦克尤恩（著），郭国良（译）"]
        candidate = dict(self.result, authors=authors, isbn_13="")
        responses = [SimpleNamespace(stdout=json.dumps({"books": rows})) for rows in ([], [candidate])]
        with patch.object(links.shutil, "which", return_value="zlib"), \
             patch.object(links.subprocess, "run", side_effect=responses) as run:
            self.assertEqual(links.lookup_editions([book]), "")
        self.assertEqual([call.args[0][-1] for call in run.call_args_list], [self.book["isbn"], "赎罪 伊恩·麦克尤恩"])
        self.assertEqual(book["zlibrary_edition"], self.url)
