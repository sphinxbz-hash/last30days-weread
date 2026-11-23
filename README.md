# 微信读书双书单

根据最近 30 天的读书讨论，挑出微信读书能打开的版本。一份从你笔记里的问题出发，另一份留给平常想不到要搜的书。

**先翻[第一期双书单](examples/issue-001.md)**。示例读者午休只有二十分钟，却总把时间花在挑书上。个性化榜给了他《四周》里一段谈阅读清单的作者访谈，和一部几个午休能读完的《老人与海》。同一期的开放榜里，一位书评作者从“谁该对造物负责”重读《弗兰肯斯坦》。四本书都有讨论原文和微信读书链接。[示例读者的两段笔记](examples/notes/reading.md)

## 让它给你选书

在能联网的 Codex 中调用。把引号里的目录换成你自己的笔记目录。普通 Markdown 或 Obsidian 都行，只有正文的笔记也能用。

> 用 $last30days-weread，参考「我的阅读笔记」目录，给我最近 30 天的两份微信读书书单，每份 3 本。告诉我每本书为什么值得读，附上原始讨论和微信读书链接。

也可以给它一个更具体的问题，比如“会议常常打断整块时间，有哪些书真正讲清楚了这个问题？”开放榜仍然独立挑书。默认每份五本，有据可查的版本少时就少选。

## 安装

需要支持技能的 Codex 和 Python 3.9 或更高版本。以下命令使用 Node.js 提供的 `npx`，把四个技能安装给当前用户。已经安装的依赖可以跳过。

```sh
npx skills add mvanhorn/last30days-skill --skill last30days -a codex -g
npx skills add Tencent/WeChatReading --skill weread-skills -a codex -g
npx skills add obsidianmd/obsidian-skills --skill obsidian-markdown -a codex -g
npx skills add sphinxbz-hash/last30days-weread --skill last30days-weread -a codex -g
```

也可以让 Codex 从这四个 GitHub 仓库安装对应技能。安装后新开一个对话。按研究技能的首次设置选择可用来源。[last30days](https://github.com/mvanhorn/last30days-skill) · [微信读书官方技能](https://github.com/Tencent/WeChatReading) · [Obsidian 官方技能](https://github.com/obsidianmd/obsidian-skills)

在微信读书的官方页面领取个人密钥，保存为运行 Codex 的环境变量 `WEREAD_API_KEY`。它用于核对电子书版本。笔记路径可以每次在请求中指定，也可以设置 `WEREAD_VAULT`。个人笔记保留在本机，查找讨论时只提交概括后的主题。请只选择愿意让当前 AI 客户端读取的笔记目录。[领取微信读书密钥](https://weread.qq.com/r/weread-skills)

## 复跑首期样例

[首期样单](examples/issue-001.md) 可以直接阅读。装好微信读书依赖并配置密钥后，在本仓库目录运行下列命令。它会用原始候选数据重新查询四个版本、检查笔记引用，输出 Markdown。固定窗口是 2026-10-25 至 2026-11-23。

```sh
python -X utf8 scripts/booklists.py preview examples/issue-001.json --vault examples/notes
```

日常使用只需告诉 Codex 你的问题。样例 JSON 用于复现一期结果。

## 同步到微信读书（实验功能）

默认只返回推荐。明确说“把这两份书单加入我的微信读书”后，Codex 才会尝试使用已登录、有个人书单编辑入口的官方界面。当前已验证书目查询、笔记引用和书架读取。创建个人书单及之后的重复运行仍待在真实账号完整验证。登录、可用界面和地区书目可能因账号而异。[同步步骤与核验方式](references/sync.md)

## 许可

本仓库的代码和文档使用 [MIT 许可证](LICENSE)。三个上游技能分别安装，遵循各自仓库的许可。
