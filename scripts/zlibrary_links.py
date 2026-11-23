"""Build public catalogue links locally; look up editions only on explicit request."""
import json
import re
import shutil
import subprocess
import unicodedata
from urllib.parse import quote, unquote, urlsplit


DEFAULT_HOST = "z-library.sk"
# Book catalogue hosts from heartleo/zlib's domain policy. Never use a draft-supplied host.
HOSTS = ("z-library.sk", "z-lib.sk", "z-lib.gd", "z-lib.gl", "z-lib.by", "z-lib.fm",
         "z-library.ec", "z-library.im", "z-library.qa", "z-library.website", "1lib.sk", "zlib.bz")


def book_title(title):
    # WeRead commonly appends edition names or promotional copy in full-width parentheses.
    stripped = re.sub(r"（[^（）]*(?:版|经典|原著|鲁迅文学奖|创意写作书系)[^（）]*）$", "", title)
    return stripped.strip() or title.strip()


def book_author(author):
    return " ".join(re.sub(r"\[(?:美|英|法|德|日|俄|加|意|澳|中)\]", "", author).split())


def catalogue_query(book):
    return book_title(book["title"]) + " " + book_author(book["author"])


def search_link(book, host=DEFAULT_HOST):
    if host not in HOSTS:
        raise ValueError("未知 Z-Library 书目站点")
    return "https://" + host + "/s/" + quote(catalogue_query(book), safe="")


def isbn13(value):
    """Validate either ISBN format and compare both using their ISBN-13."""
    if not isinstance(value, str):
        return ""
    digits = re.sub(r"[\s-]", "", value).upper()
    if re.fullmatch(r"[0-9]{9}[0-9X]", digits):
        check = 10 if digits[-1] == "X" else int(digits[-1])
        if (sum((10 - i) * int(n) for i, n in enumerate(digits[:9])) + check) % 11:
            return ""
        digits = "978" + digits[:9]
    elif not re.fullmatch(r"97[89][0-9]{10}", digits):
        return ""
    check = str(-sum(int(n) * (1 if i % 2 == 0 else 3) for i, n in enumerate(digits[:12])) % 10)
    return digits[:12] + check if len(digits) == 12 or digits[-1] == check else ""


def detail_url(value):
    if not isinstance(value, str):
        return ""
    try:
        url = urlsplit(value)
    except ValueError:
        return ""
    host = re.sub(r"^(?:en|zh)\.", "", url.netloc.lower())
    if url.scheme != "https" or host not in HOSTS or url.query or url.fragment:
        return ""
    parts = url.path.strip("/").split("/")
    if not (2 <= len(parts) <= 4 and parts[0] == "book" and re.fullmatch("[A-Za-z0-9]+", parts[1])):
        return ""
    decoded = [unquote(part) for part in parts]
    if any(not part or part in (".", "..") or re.search(r"[/\\%\x00-\x1f\x7f]", part) for part in decoded):
        return ""
    return "https://" + url.netloc.lower() + "/" + "/".join(quote(part, safe="-._~") for part in decoded)


def comparable(text):
    return "".join(unicodedata.normalize("NFKC", text).casefold().split())


def matching_edition(book, candidates):
    expected_isbn = isbn13(book.get("isbn"))
    exact, translated = set(), set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        link = detail_url(candidate.get("url"))
        if not link:
            continue
        codes = {isbn13(candidate.get(key)) for key in ("isbn_13", "isbn_10", "isbn")} - {""}
        if len(codes) > 1:
            continue
        if expected_isbn and codes:
            if codes == {expected_isbn}:
                exact.add(link)
            continue
        # Require an explicit translator credit. A coauthor is not evidence of translation.
        authors = candidate.get("authors")
        title = candidate.get("name")
        if not book.get("translator") or not isinstance(title, str) or not isinstance(authors, list):
            continue
        if not all(isinstance(name, str) for name in authors):
            continue
        credits = re.split(r"[;；，]", ";".join(authors))
        writers, translators = [], []
        for credit in credits:
            role = re.fullmatch(r"\s*(?:译者\s*[:：]\s*(.+)|(.+?)[（(]?译[）)]?)\s*", credit)
            if role:
                translators.append((role[1] or role[2]).strip())
            else:
                writers.append(book_author(re.sub(r"[（(]著[）)]$|\s+著$", "", credit.strip())))
        if (comparable(book["title"]) == comparable(title)
                and comparable(book_author(book["author"])) == comparable(" ".join(writers))
                and comparable(book["translator"]) == comparable(" ".join(translators))):
            publisher = candidate.get("publisher")
            if not publisher or not book.get("publisher") or comparable(str(publisher)) == comparable(book["publisher"]):
                translated.add(link)
    if exact:
        return sorted(exact)[0]
    return next(iter(translated)) if len(translated) == 1 else ""


def lookup_editions(books):
    """Use only the upstream non-interactive search command. Never surface its raw output."""
    executable = shutil.which("zlib")
    if not executable:
        return "未找到可选的 zlib 客户端，保留书目搜索入口。"
    cache = {}

    def search(query):
        if query not in cache:
            completed = subprocess.run([executable, "search", "--json", "--count", "10", "--", query],
                                       stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8",
                                       timeout=20, check=True)
            data = json.loads(completed.stdout)
            if not isinstance(data, dict) or not isinstance(data.get("books"), list):
                raise ValueError("invalid catalogue response")
            cache[query] = data["books"]
        return cache[query]

    try:
        for book in books:
            code = isbn13(book.get("isbn"))
            link = matching_edition(book, search(code)) if code else ""
            if not link and book.get("translator"):
                link = matching_edition(book, search(catalogue_query(book)))
            if link:
                book["zlibrary_edition"] = link
    except (OSError, ValueError, subprocess.SubprocessError):
        return "Z-Library 书目查询未完成，其余书目保留搜索入口。"
    return ""
