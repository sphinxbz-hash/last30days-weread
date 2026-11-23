# 微信读书双书单

**看推荐无需登录。** 开放书单挑最近 30 天真正有人讨论的书。个性化书单可以从你眼下的一个问题出发，也可以参考你选定的笔记。每本都附推荐理由、讨论原文和「在 Z-Library 搜索」。核实微信读书版本后，一并附上阅读链接。

[翻开第一期双书单](examples/issue-001.md)。示例读者午休只有二十分钟，却常把时间花在挑书上。个性化榜推荐《四周》和《老人与海》，开放榜选出《第二十二条军规》和《弗兰肯斯坦》。[示例笔记](examples/notes/reading.md)

## 怎么用

在 Codex 中任选一种说法。

| 想看什么 | 可以这样说 |
| --- | --- |
| 开放书单 | 用 $last30days-weread，从最近一个月的跨平台讨论中挑 5 本书。 |
| 按问题选书 | 我常把午休花在挑书上。用 $last30days-weread 给我一份个性化书单。 |
| 参考笔记 | 用 $last30days-weread，参考我指定的「阅读笔记」目录，给我两份书单，各 3 本。 |

开放推荐只使用公开材料。按问题选书也无需提供笔记。选择笔记推荐时，只有你指定的目录供当前 AI 客户端读取。公开搜索使用概括后的主题。预览不会访问微信读书账号、读取书架或要求扫码。链接待核实时仍会展示书名、理由和讨论来源。

## 安装与试读

在支持技能的 Codex 中使用。推荐功能需要本技能和研究技能 `last30days`。如果使用 Node.js，可以用以下命令安装；也可以让 Codex 从对应 GitHub 仓库安装。

```sh
npx skills add mvanhorn/last30days-skill --skill last30days -a codex -g
npx skills add sphinxbz-hash/last30days-weread --skill last30days-weread -a codex -g
```

新开对话后开始选书。解析 Obsidian 双向链接时可加装 `obsidian-markdown`。只有选择保存到微信读书时才需要配置 `weread-skills` 和个人密钥。[研究技能](https://github.com/mvanhorn/last30days-skill) · [Obsidian 技能](https://github.com/obsidianmd/obsidian-skills) · [微信读书官方技能](https://github.com/Tencent/WeChatReading)

仓库里的首期数据已附核实过的公开链接。用 Python 3.9 或以上版本可以离线复现，无需安装依赖或配置密钥。第一行只看开放榜，第二行用仓库自带的示例笔记生成两榜。

```sh
python -X utf8 scripts/booklists.py preview examples/issue-001.json --list open
python -X utf8 scripts/booklists.py preview examples/issue-001.json --vault examples/notes
```

## 微信读书和 Z-Library

「在 Z-Library 搜索」使用书名和作者。例如《赎罪》会搜“赎罪 伊恩·麦克尤恩”，以便和凑佳苗的同名小说区分。链接在本地生成；点击后，浏览器才会把搜索词交给目标网站。能否打开结果页取决于该站点及读者的网络。可以用 `preview --help` 查看支持的站点，再通过 `--zlibrary-host` 选择自己的常用入口。

如果已经在本机连接 [heartleo/zlib](https://github.com/heartleo/zlib)，可以说“用我已连接的 Z-Library 核对开放书单的版本”。使用命令行时运行：

```sh
python -X utf8 scripts/booklists.py preview examples/issue-001.json --list open --match-zlibrary
```

该选项只运行书目搜索，优先按已核实的 ISBN 查询。ISBN 相符，或完整书名、作者和明确标出的译者相符且版本信息无冲突时，显示「Z-Library 同版书目」。目录缺字段、候选有歧义或客户端未连接时，保留普通搜索链接。个人笔记、推荐理由和微信读书账号信息不会作为查询参数。搜索入口和同版书目均指向网页。

## 看完再决定是否保存

回复 **“存到我的微信读书”** 后，选哪张书单、哪几本，以及怎么存。也可以直接说“只把开放榜里的《第二十二条军规》加入书架”。到这一步才处理微信读书登录和账号核对。

| 保存方式 | 会发生什么 |
| --- | --- |
| 仅加入书架 | 在已登录的官方界面添加所选版本，已在架的跳过。已用四本书实测，并连续两次回读确认无缺项。 |
| 创建个人书单（实验） | 在支持编辑个人书单的界面创建或补充所选书单。已测试的网页版和电脑小程序未找到建单入口，遇到这种情况会停下，保留推荐。只有另选“加入书架”才会改动书架。 |

个人书单的创建、回读及重复运行仍待完整实测。“开放”指推荐来源；公开发布书单是单独的选择。[保存步骤](references/sync.md)

## 许可

本仓库采用 [MIT 许可证](LICENSE)。上游技能分别安装，遵循各自仓库的许可。
