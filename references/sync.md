# 保存到我的微信读书

本页仅在用户选了保存后使用。单说“保存”时，在对话里提供两个选项：**仅加入书架（已实测）**、**创建或补充个人书单（实验）**。询问要哪张榜、哪些书，可按编号、书名或整榜选。用户已经说清的无需重问。说明所选版本、目标位置和所需登录，使用同一份推荐继续。

## 准备所选书目

- 选择建单时，优先确认当前可操作的客户端是否有“我创建的书单”的编辑入口。已确认不支持时直接保留推荐，不提示为网页扫码。此前实测的网页版与电脑微信小程序可查看书架，没有找到个人书单编辑入口。
- 保存才用 `weread-skills`。需要时安装 `npx skills add Tencent/WeChatReading --skill weread-skills -a codex -g`，从[官方页面](https://weread.qq.com/r/weread-skills)领取并在本地配置 `WEREAD_API_KEY`。先读上游 `search.md`、`book.md`，入架时加读 `shelf.md`。缺 `bookId` 的已选条目用书名和作者查官方电子书，出现译本歧义时核对后再继续。传给微信读书的检索上下文只保留找书所需的信息。
- 用 `prepare` 核对所选版本并固定选择。可以选整榜（如 `--pick open`）或按榜选单本（如 `--pick open:801458`）；多选就重复该参数。只对选中的条目核实官方版本。计划绑定当前账号，仅保存所选电子书和必要的运行信息。私人笔记、问题、推荐理由和来源无需传入账号操作。
- 以下是从技能目录运行的两个独立示例；一次操作只执行对应的一种。每个请求用独立的本地批次目录。对已经创建的计划用 `status` 续办。

```sh
python -X utf8 scripts/booklists.py prepare examples/issue-001.json --mode shelf --pick open:801458 --state outputs/shelf-example/plan.json
python -X utf8 scripts/booklists.py prepare examples/issue-001.json --mode booklist --pick open --state outputs/booklist-example/plan.json
```

## 仅加入书架

运行 `python -X utf8 scripts/booklists.py status <plan.json>`。在微信读书官方书架核对显示账号，只打开 `shelf_missing` 中所选版本的官方阅读链接，点击“加入书架”。状态已改变或响应超时时先重新读取书架。多榜重复入选同一版本仅入架一次。缺项变为零即可报告入架完成。遇付费页面仅办理用户所选的保存操作。

## 创建个人书单（实验）

确认当前账号与计划一致。在官方客户端进入自己的书单目录。按计划中的精确名称找自己有权编辑的书单；确认查完仍缺失才新建。重名时结合既有定位信息辨认。优先选择仅自己可见，已有书单保持原来的可见性。只能公开发布时先询问。不要将笔记或个性化推荐理由写入书单介绍。

在编辑界面用书城搜索或“添加到书单”添加所选版本。保留已有成员并跳过重复项。**没有编辑入口、只能创建书架分组、或必须先将缺书加入书架时，停止这一项并保留推荐**。如用户随后明确另选入架，建立独立的 `shelf` 计划。两种操作不会相互代办。

保存后离开编辑页，再从“我创建的”分别打开目标书单，逐一比对真实书籍版本。按实际观察在批次目录写 `observed.json`，再运行 `python -X utf8 scripts/booklists.py status <plan.json> --ui <observed.json>`。示例描述数据格式。

```json
{
  "run": "<本批次 run>",
  "account_checked": true,
  "observed_at": "<含时区的实际观察时间>",
  "lists": {
    "last30days开放书单": {
      "scope": "my_created_booklists", "state": "present",
      "all_pages": true, "members": ["<实际看到的版本 ID>"]
    }
  }
}
```

观察有效期十分钟。已找到书单填 `present`，查完自己的全部书单仍无匹配填 `missing`，同名未定位填 `ambiguous`，尚未观察填 `unknown`。部分可见时将 `all_pages` 设为 false。确认当前客户端无法编辑时，填 `unavailable`，返回 `keep_recommendations` 即终止保存，保留推荐。返回 `inspect` 时继续观察，`identify_list` 定位同名书单，`create` 或 `add_missing` 才办理对应请求。按重新打开后实际可识别的成员数量报告结果。旧版计划没有保存方式，按用户本次选择重新准备并使用新文件。
