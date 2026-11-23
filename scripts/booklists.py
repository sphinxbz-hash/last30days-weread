"""Resolve, freeze and reconcile two WeRead lists. Official API calls are read-only."""
import argparse
import hashlib
import json
import os
import re
import tempfile
import unicodedata
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

NAMES = {"personal": "last30days个性化书单", "open": "last30days开放书单"}
SKILLS = Path(__file__).resolve().parents[2]
GATEWAY = "https://i.weread.qq.com/api/agent/gateway"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def normalized(value):
    return "".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def api(method, **params):
    key = os.environ.get("WEREAD_API_KEY")
    require(key, "未找到 WEREAD_API_KEY")
    spec = os.environ.get("WEREAD_SKILL_DIR")
    roots = [Path(spec)] if spec else [
        SKILLS / "weread-skills",
        Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills" / "weread-skills",
        Path.home() / ".agents" / "skills" / "weread-skills",
    ]
    manifest = next((root / "SKILL.md" for root in roots if (root / "SKILL.md").is_file()), None)
    require(manifest, "请安装 weread-skills，或用 WEREAD_SKILL_DIR 指定其目录")
    text = manifest.read_text(encoding="utf-8-sig")
    version = re.search(r"(?m)^version:\s*['\"]?([\d.]+)", text)
    require(version, "无法读取已安装微信读书技能的版本")
    body = json.dumps({"api_name": method, "skill_version": version[1], **params}).encode()
    req = Request(GATEWAY, data=body, headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + key})
    with urlopen(req, timeout=25) as response:
        result = json.load(response)
    require(isinstance(result, dict) and not result.get("errcode"), f"微信读书查询失败 {method}")
    return result


def official_link(book):
    for field in ("readerLink", "deepLink"):
        url = book.get(field, "")
        if not isinstance(url, str):
            continue
        parsed = urlsplit(url)
        if parsed.scheme == "https" and parsed.netloc == "weread.qq.com":
            return url
    return None


def search(title, context):
    require(context.strip(), "缺少触发查书的用户请求")
    result = api("/store/search", scope=10, keyword=title, context=context)
    rows = []
    for group in result.get("results", []):
        for row in group.get("books", []):
            book = row.get("bookInfo", {})
            if book.get("bookId") and str(book.get("soldout", 0)) != "1":
                rows.append({**{k: book.get(k) for k in ("bookId", "title", "author", "translator")},
                             "link": official_link(book)})
    return rows


def local_note(vault, ref):
    require(isinstance(ref, dict), "个性化书目缺少知识库出处")
    require(vault is not None and vault.is_dir(), "请用 --vault 指定可读取的 Markdown 笔记目录")
    relative = Path(ref["path"])
    require(not relative.is_absolute(), "笔记出处需要库内相对路径")
    full = (vault / relative).resolve()
    require(full.is_relative_to(vault.resolve()) and full.suffix.lower() == ".md" and full.is_file(),
            "知识库出处无法定位: " + str(relative))
    heading = ref.get("heading", "").strip()
    content = full.read_text(encoding="utf-8-sig")
    require(content.strip(), "笔记没有正文: " + str(relative))
    if not heading:
        return {"path": relative.as_posix()}
    headings = [m[1].strip().rstrip("#").strip() for m in
                re.finditer(r"(?m)^#{1,6}[ \t]+(.+)$", content)]
    require(heading in headings, "笔记标题未找到: " + str(relative) + " / " + heading)
    return {"path": relative.as_posix(), "heading": heading}


def checked_evidence(evidence, end):
    require(isinstance(evidence, list) and evidence, "每本书须有近期讨论出处")
    checked = []
    for item in evidence:
        day = date.fromisoformat(item["date"])
        require(end - timedelta(days=29) <= day <= end, "出处日期在本次窗口以外")
        parsed = urlsplit(item["url"])
        require(parsed.scheme in {"https", "http"} and parsed.hostname, "缺少有效的讨论链接")
        require(str(item.get("voice", "")).strip(), "须说明讨论来自哪个平台或读者")
        checked.append({k: item[k] for k in ("date", "voice", "url")})
    return checked


def account_and_name():
    profile = api("/user")
    vid = str(profile.get("userVid") or "").strip()
    require(vid, "无法确认微信读书账号")
    return hashlib.sha256(vid.encode()).hexdigest(), profile.get("name", "")


def resolve(draft, vault):
    end = date.fromisoformat(draft["as_of"])
    require(end <= date.today(), "截至日不能在未来")
    lists, catalog = {}, {}
    for group in NAMES:
        rows = draft[group]
        require(isinstance(rows, list), f"{NAMES[group]}书目格式无效")
        selected, seen = [], set()
        for row in rows:
            bid = str(row["bookId"]).strip()
            require(bid and bid not in seen, f"{NAMES[group]}含空 ID 或重复书目 {bid}")
            seen.add(bid)
            reason = row["reason"].strip()
            require(reason, "缺少推荐理由")
            sources = checked_evidence(row["evidence"], end)
            if bid not in catalog:
                catalog[bid] = api("/book/info", bookId=bid)
            book = catalog[bid]
            require(str(book.get("bookId")) == bid and str(book.get("soldout", 0)) != "1"
                    and official_link(book), f"无法确认官方电子书版本 {bid}")
            for field in ("title", "author"):
                require(book.get(field) and normalized(row[field]) == normalized(book[field]),
                        f"{bid} 的{field}与官方书目不一致，请核对搜索结果")
            result = {"bookId": bid, "title": book["title"], "author": book["author"],
                      "link": official_link(book), "reason": reason, "evidence": sources}
            for field in ("translator", "publisher", "isbn"):
                if book.get(field):
                    result[field] = book[field]
            if group == "personal":
                result["note"] = local_note(vault, row["note"])
            selected.append(result)
        lists[group] = selected
    require(any(lists.values()), "两份书单都没有可核实的书目，保留草案")
    return {"as_of": end.isoformat(), **lists}


def render_preview(selection):
    end = date.fromisoformat(selection["as_of"])
    lines = [f"# 微信读书双书单 · {end}", "", f"讨论时间：{end - timedelta(days=29)} 至 {end}。"]
    for key, name in NAMES.items():
        lines.extend(["", f"## {name}", ""])
        if not selection[key]:
            lines.append("本期没有找到符合条件的版本。")
        for book in selection[key]:
            lines.extend([f"### 《{book['title']}》 · {book['author']}", "", book["reason"], ""])
            if key == "personal":
                note = book["note"]
                where = note["path"] + (f" › {note['heading']}" if note.get("heading") else "")
                lines.extend([f"笔记依据：{where}", ""])
            links = [f"[{item['voice']} · {item['date']}]({item['url']})" for item in book["evidence"]]
            links.append(f"[微信读书]({book['link']})")
            lines.extend([" · ".join(links), ""])
    return "\n".join(lines).rstrip() + "\n"


def save_new_plan(path, plan):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".booklists-", suffix=".tmp", delete=False) as tmp:
        staged = Path(tmp.name)
        try:
            json.dump(plan, tmp, ensure_ascii=False, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
        except BaseException:
            tmp.close()
            staged.unlink(missing_ok=True)
            raise
    try:
        # Windows rename refuses to replace a destination. POSIX rename would replace it.
        if os.name == "nt":
            os.rename(staged, path)
        else:
            os.link(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def prepare(args):
    require(not args.state.exists(), "本批次已有固定计划。用 status 续办；新选书请另建批次")
    plan = resolve(load(args.draft), args.vault)
    account, _ = account_and_name()
    plan.update(schema=1, run=uuid.uuid4().hex, account=account)
    save_new_plan(args.state, plan)
    return {"run": plan["run"], "state": str(args.state), "lists": {
        NAMES[k]: len(plan[k]) for k in NAMES}}


def reconcile(plan, shelf_ids, views):
    targets = {b["bookId"]: b for key in NAMES for b in plan[key]}
    missing = [b for bid, b in targets.items() if bid not in shelf_ids]
    result = {"run": plan["run"], "shelf_missing": [
        {k: book[k] for k in ("bookId", "title", "link")} for book in missing], "lists": {}}
    for key, name in NAMES.items():
        ids = [b["bookId"] for b in plan[key]]
        view = views.get(name, {})
        state = view.get("state", "unknown")
        require(state in {"unknown", "ambiguous", "missing", "present"}, "书单观察状态无效")
        if state in {"present", "missing", "ambiguous"}:
            require(view.get("scope") == "my_created_booklists",
                    "请从当前账号自己创建的书单取得观察结果")
        members = view.get("members", [])
        require(isinstance(members, list) and all(isinstance(i, str) for i in members),
                "members 必须是实际识别的版本 ID 数组")
        present = set(members) if state == "present" else set()
        absent = [bid for bid in ids if bid not in present]
        complete_scan = view.get("all_pages") is True
        if state == "present" and not absent:
            action = "verified"
        elif state == "present" and complete_scan:
            action = "add_missing"
        elif state == "missing" and complete_scan:
            action = "create"
        elif state == "ambiguous":
            action = "identify_list"
        else:
            action = "inspect"
        result["lists"][name] = {"action": action, "target_count": len(ids),
                                "verified_ids": [i for i in ids if i in present],
                                "outstanding_ids": absent}
    result["verified"] = not missing and all(
        item["action"] == "verified" for item in result["lists"].values())
    return result


def status(args):
    plan = load(args.state)
    require(plan["schema"] == 1, "不支持的计划版本")
    account, name = account_and_name()
    require(account == plan["account"], "当前账号与本批次计划不同")
    shelf = api("/shelf/sync")
    require(isinstance(shelf.get("books"), list), "书架返回不完整，稍后重查")
    shelf_ids = {str(b["bookId"]) for b in shelf["books"] if b.get("bookId")}
    views = {}
    if args.ui:
        proof = load(args.ui)
        require(proof.get("run") == plan["run"] and proof.get("account_checked") is True,
                "请在本次运行的同一账号重新观察个人书单")
        when = datetime.fromisoformat(proof["observed_at"])
        require(when.tzinfo is not None and timedelta(seconds=-30) <=
                datetime.now(timezone.utc) - when <= timedelta(minutes=10),
                "书单观察已过期或缺少时区，请重新打开书单")
        views = proof["lists"]
        require(isinstance(views, dict) and set(views) <= set(NAMES.values()),
                "书单观察的名称不匹配")
    return {"account_name": name, **reconcile(plan, shelf_ids, views)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    lookup = commands.add_parser("search")
    lookup.add_argument("title")
    lookup.add_argument("--context", required=True, help="本次用户请求，仅保留找书所需信息")
    inputs = argparse.ArgumentParser(add_help=False)
    inputs.add_argument("draft", type=Path)
    inputs.add_argument("--vault", type=Path, default=os.environ.get("WEREAD_VAULT"))
    commands.add_parser("preview", parents=[inputs], help="核对电子书，输出 Markdown 推荐书单")
    start = commands.add_parser("prepare", parents=[inputs])
    start.add_argument("--state", type=Path, required=True)
    check = commands.add_parser("status")
    check.add_argument("state", type=Path)
    check.add_argument("--ui", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "search":
            result = search(args.title, args.context)
        elif args.action == "preview":
            print(render_preview(resolve(load(args.draft), args.vault)), end="")
            return
        elif args.action == "prepare":
            result = prepare(args)
        else:
            result = status(args)
    except (ValueError, KeyError, TypeError, OSError, HTTPError, URLError) as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
