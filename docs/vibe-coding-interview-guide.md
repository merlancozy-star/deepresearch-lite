# DeepResearch-Lite：Vibe Coding 实践全记录 & 面试问答指南

> 本文档用于面试准备。记录本项目从零到一用 Claude Code 协作完成的完整过程，以及面试中可能被追问的 Vibe Coding 相关问题及回答策略。

---

## 目录

1. [项目背景与 Vibe Coding 定义](#1-项目背景与-vibe-coding-定义)
2. [Vibe Coding 工作流全景](#2-vibe-coding-工作流全景)
3. [关键协作模式与具体案例](#3-关键协作模式与具体案例)
4. [CLAUDE.md 设计文档的价值](#4-claudemd-设计文档的价值)
5. [Git 历史中的 Vibe Coding 证据](#5-git-历史中的-vibe-coding-证据)
6. [面试高频问题 & 回答策略](#6-面试高频问题--回答策略)
7. [避坑指南：Vibe Coding 常见失败模式](#7-避坑指南vibe-coding-常见失败模式)
8. [数据与指标](#8-数据与指标)

---

## 1. 项目背景与 Vibe Coding 定义

### 1.1 什么是 Vibe Coding

**Vibe Coding** 是 2025 年由 Andrej Karpathy 提出的概念，核心含义是：

> "You fully give in to the vibes, embrace exponentials, and forget that the code even exists."
> —— Andrej Karpathy, 2025.02

在实践中定义为：

> **以自然语言设计文档作为唯一契约，将编码执行完全委托给 AI 编程助手，人类负责架构决策、需求澄清和验收，AI 负责实现、测试和文档生成的协作范式。**

与传统编程的关键区别：

| 维度 | 传统编程 | Vibe Coding |
|------|---------|-------------|
| 主要产出 | 代码 | 设计文档 + Prompt |
| 与 AI 的交互 | 逐行补全 | 整块委托 + 审核 |
| 时间分配 | 80% 写代码 / 20% 设计 | 20% 写文档 / 80% 审核 AI 产出 |
| 技能要求 | 语法熟练度 | 系统设计 + 约束表达能力 |
| 调试方式 | 逐行 debug | 读 diff + 写反馈 prompt |

### 1.2 本项目中的 Vibe Coding 定位

DeepResearch-Lite 是一个**纯 Vibe Coding 产物**：所有代码由 Claude Code 根据 `CLAUDE.md` 设计文档生成，人类角色仅限于：

1. 撰写 CLAUDE.md（设计契约）
2. 审核 Claude Code 的产出（代码 diff + 测试结果）
3. 给出反馈（"输出用中文"、"commit 要有人味"）
4. 验收决策（"推送到 GitHub"）

**零行代码由人类手写。**

---

## 2. Vibe Coding 工作流全景

### 2.1 完整时间线

```
08:00  写 CLAUDE.md 设计文档（1h）
       ↓
09:00  M1: 脚手架 → Claude Code 初始化项目结构
10:00  M2: Schemas + Citation 工具 → 数据结构 + RRF
11:00  M3: Web + Arxiv Subagent → 两个搜索源
12:00  🍱 午饭
13:00  M4: Synthesizer → structured output + retry
15:00  M5: Verifier → NLI 三分类核验
17:00  M6: Graph 编排 + CLI → 全链路跑通
18:00  🍱 晚饭
19:00  M7: Streamlit UI → 可点击引用 + 章节导航
21:00  M8: README + GitHub + Demo
22:00  M9: 整理收尾 + 多 case 验证
```

### 2.2 每个 Milestone 的交互模式

每个 Milestone 遵循固定的四步循环：

```
Step 1: 人类给出任务描述（直接复制 CLAUDE.md 中的 Milestone Prompt）
   ↓
Step 2: Claude Code 读代码 → 输出执行计划 → 等待确认
   ↓
Step 3: 人类说 "GO" → Claude Code 写代码 → 跑测试 → 报告结果
   ↓
Step 4: 人类审核 diff → 给出反馈 → 进入下一个 Milestone
```

**关键洞察**：Step 2（先出计划再写代码）是 Vibe Coding 成功的关键。直接让 AI "yolo 写" 会导致方向性错误，修正成本远高于先审计划。

### 2.3 实际对话量估算

| 阶段 | 对话轮次 | 主要交互 |
|------|---------|---------|
| M1-M2 基础设施 | ~15 轮 | 创建文件、运行命令 |
| M3 Subagent | ~20 轮 | API 调试、错误修复 |
| M4-M5 核心逻辑 | ~25 轮 | Prompt 迭代、retry 逻辑 |
| M6-M7 集成 | ~20 轮 | 链路调试、UI 调整 |
| M8-M9 收尾 | ~15 轮 | README、commit 整理 |
| 后续增强 | ~30 轮 | 可溯源报告、质量改进 |

**总计约 125 轮对话，零行手写代码。**

---

## 3. 关键协作模式与具体案例

### 3.1 模式一：设计文档驱动开发（DDD — Design Doc Driven）

**案例**：Synthesizer 的两阶段重写

传统做法：直接修改 prompt → 看效果 → 不满意再改 → 循环 5 次。

Vibe Coding 做法：
1. 先在头脑中设计架构（大纲→逐节→汇总）
2. 用自然语言描述给 Claude Code：
   ```
   P1-1: 两阶段 Synthesis（大纲 → 逐节撰写）
   重写 synthesizer：阶段1生成报告大纲，阶段2逐节传入 top-K 相关 evidence 撰写
   ```
3. Claude Code 生成三个新 prompt 模板 + 完整重写 synthesizer.py
4. 人类审核 diff → 确认重试逻辑正确 → 通过

**产出**：一个下午完成了从单次 LLM 调用到三阶段管道的架构升级。

### 3.2 模式二：渐进式约束叠加

**案例**：Citation 强约束的演进

```
v1: "请引用 source_id"（软约束，LLM 经常忽略）
v2: Pydantic min_length=1（硬约束，空引用抛异常）
v3: retry + 错误反馈（"上次你漏了引用，重来"）
v4: 最终回退（[UNCITED] 标记 + fallback Citation）
```

每一步都是观察到实际失败后，用自然语言告诉 Claude Code "XX 情况发生了，加 YY 约束"。不需要写代码，只需要描述边界条件。

### 3.3 模式三：错误驱动迭代

**案例**：Windows GBK 编码问题

```
现象：CLI 输出 emoji 时报 UnicodeEncodeError
人类：把错误信息贴给 Claude Code
Claude Code：诊断 → Windows GBK 不支持 emoji → 加 UTF-8 wrapper
结果：三行代码修复，人类没查过 Windows 编码文档
```

类似的错误驱动修复在本项目中出现 6 次：
- Pydantic ValidationError → retry 逻辑
- asyncio.run() in running loop → async 重构
- arXiv HTTP 429 → Mock fallback
- Tavily 空 API key 挂起 → 前置检查
- KeyError: 'N' in prompt → 转义 `{{N}}`
- Git rebase root commit → orphan branch 方案

### 3.4 模式四：人类审美判断

**案例**：Git Commit 历史优化

```
人类："对每条commits进行优化，希望非常的具有人味"
       "我希望每个文件夹、文件都有独一无二的合理的简要明确的commits"

Claude Code：
  1. 分析当前 19 个 commits → 识别问题（一些太细碎，一些太笼统）
  2. 用 git rebase 重新组织历史
  3. 用孤儿分支 + cherry-pick 重建干净历史
  4. 最终 17 个 commits，每个语义清晰
```

**关键点**："有人味" 是纯粹的人类审美判断，AI 无法自行判断。但一旦人类给出方向，AI 可以精确执行。

---

## 4. CLAUDE.md 设计文档的价值

### 4.1 为什么 CLAUDE.md 而不是对话记忆

```
对话记忆：
  - 随上下文窗口滑动而丢失早期信息
  - 每次新对话需要重新解释项目背景
  - 不同对话之间信息不一致

CLAUDE.md：
  - 持久化的设计契约
  - 每次 Claude Code 启动自动加载
  - 所有对话共享同一份"真相源"
  - 可作为版本控制的一部分（git tracked）
```

### 4.2 CLAUDE.md 的结构设计原则

本项目的 CLAUDE.md 包含以下核心章节，每个都有明确的协作目的：

| 章节 | 协作目的 |
|------|---------|
| 1. 项目定位 | 让 AI 理解"我们在做什么、做给谁" |
| 2. 核心差异化 | 让 AI 在技术选型时优先考虑差异化特性 |
| 3. 技术架构 | 精确的数据流和数据结构，AI 照着实现 |
| 5. 时间盒 | 每个 Milestone 的验收标准，AI 自检用 |
| 6. Milestone Prompt | 直接可复制的任务描述，减少人类打字 |
| 8. 风险与边界 | 告诉 AI "什么绝对不能做"，防止 scope creep |
| 11. 简历叙事 | 人类面试时讲的 90 秒故事，AI 写代码时参考 |

### 4.3 CLAUDE.md 的演进

```
v1.0（初始）：架构 + 时间盒 + Milestone Prompts
    ↓
v1.1（Day 1 结束）：补充了实际踩坑记录（风险表格更新）
    ↓
v1.2（增强阶段）：没有更新 CLAUDE.md，直接用对话描述改进需求
    ↓ （反思：应该把改进需求也写入 CLAUDE.md 以保持一致性）
```

---

## 5. Git 历史中的 Vibe Coding 证据

### 5.1 Commit 历史解读

```
fed4655 refactor: pipeline quality overhaul — 7 improvements in one pass
b741bca feat: every claim now traceable — click a citation, see the source
cfc2369 README：项目定位 + Features + Quick Start + Architecture + Roadmap
06a1c85 Streamlit 中文 UI：输入框→进度→报告→引用展开→核验徽章
4c677cc CLI 入口：argparse + 中文输出 + Windows GBK 编码修复
1cfae74 Graph：async pipeline 把 classify→search→fuse→synthesize→verify 串起来
9fa25fd Orchestrator：意图分类 + 查询拆解，两个 LLM 调用搞定
14aff4e Verifier：独立 LLM 做 NLI 三分类核验，asyncio 并发上限 5
77286c4 Synthesizer retry 逻辑的单测：空引用触发重试、假 ID 最终标 UNCITED
cfabd8f Synthesizer：structured output + citation 强约束 + 最多 3 次 retry
dba3926 三份 LLM Prompt 模板：Synthesizer / Verifier / Orchestrator
2a3a935 Mock Subagent：arxiv 被墙时的兜底 demo 数据
aa9947d Arxiv Subagent：Semantic Scholar 主 + arxiv API fallback
94c388d Web Subagent：接 Tavily 搜网页，内容按 400 字切 chunk
796c6d3 Subagent 抽象基类 + 文本分块工具
ca080c8 Schema 约束 + RRF 数学正确性的单测
f01e736 RRF 融合 + 按 source_id/char_span 去重
e7f2d35 Pydantic 数据结构：Citation → Claim → ResearchReport
435c39c 搭个架子：项目配置文件
```

### 5.2 面试时如何展示

> **面试官**："这些代码全是你写的吗？"

> **你**："架构设计是我的，代码实现是 Claude Code 的。这是一个 Vibe Coding 项目——我用 CLAUDE.md 作为设计契约，Claude Code 执行实现。这个 Git 历史就是一个很好的证据：19 个 commits，从项目脚手架到最终的质量改进，每个 commit message 描述的是'做了什么设计决策'，而代码 diff 是 AI 的产出。我可以打开任意一个 commit 给你看交互过程。"

> **关键动作**：打开 GitHub，展示 commit 历史，随机点开一个 commit 看 diff。指出"这个 300 行的 diff 我只写了一句话的 prompt"。

---

## 6. 面试高频问题 & 回答策略

### Q1: "什么是 Vibe Coding？你怎么定义它？"

**回答框架**：

"Vibe Coding 是我在 DeepResearch-Lite 项目中实践的一种 AI 协作范式。核心是三个转变：

1. **从写代码到写约束**：我不写实现逻辑，而是写数据 schema、边界条件、验收标准。比如我的 Citation 数据结构有 `min_length=1` 约束，这行不是我写的，但'每个 claim 必须有至少一个引用'这个规则是我设计的。

2. **从调试到审核**：我不逐行 debug，而是读 AI 产出的 diff。遇到错误时，我把错误信息贴给 AI，它诊断并修复。整个项目中我大约审核了 AI 的 50+ 次代码变更。

3. **从单次对话到持久化设计文档**：CLAUDE.md 是项目根目录的设计契约文件，每次 Claude Code 启动都自动读取。这保证了跨对话的一致性——不会出现'上一轮聊的这轮忘了'的问题。

Vibe Coding 不是放弃控制，而是把控制从代码层面提升到设计层面。"

### Q2: "Vibe Coding 和 Copilot 自动补全有什么区别？"

**回答框架**：

"区别在粒度和主动性：

- **Copilot** 是逐行补全——你写注释，它补一行代码。你仍然在'驾驶座'上。
- **Vibe Coding** 是整块委托——你描述一个功能模块的完整需求，AI 自主决定文件结构、函数划分、错误处理。

举个例子：我在做 Verifier 增强时，只说了'用 few-shot examples 改进 NLI prompt，对 contradiction 做二次复核'。Claude Code 自己做了：重写 prompt 模板、设计二次复核的 system message 变体、决定复核时提高 contradiction 判定标准。如果我用 Copilot，我得一行一行写这些代码。

本质区别是：Copilot 帮你写代码，Vibe Coding 帮你做工程决策。"

### Q3: "完全靠 AI 写代码，质量能有保证吗？"

**回答框架**：

"质量保证不靠 AI，靠的是三层防线：

1. **设计层**：CLAUDE.md 中的 schema 约束（Pydantic `min_length=1`）、prompt 模板结构（JSON schema 约束 LLM 输出格式）。这些是硬约束，AI 无法绕过。

2. **测试层**：21 个单元测试覆盖了核心路径——schema 校验、RRF 融合数学正确性、synthesizer retry 逻辑。每次代码变更后 AI 自动跑全量测试。这个我专门写了测试文件，虽然测试代码本身也是 AI 写的，但测试的语义（验证什么行为）是我定义的。

3. **审核层**：我读每一个 AI 产出的 diff。不是逐行读，而是关注关键路径——错误处理是否完备、边界条件是否覆盖。比如我发现 AI 第一次写的 retry 逻辑只在 claim 级别重试而不在 LLM 调用级别重试，我指出后它修正了。

三层加起来，质量不比我手写差。而且因为 AI 不会偷懒跳过边界处理，某些方面反而更完备。"

### Q4: "AI 写的代码你能看懂吗？出了问题怎么排查？"

**回答框架**：

"能看懂，因为架构是我设计的。就像建筑师不需要亲手砌每一块砖，但知道每面墙的承重。

排查问题的流程：

1. 看错误日志 → 定位出问题的模块
2. 读那个模块的代码（通常 100-200 行，AI 写的代码结构清晰）
3. 理解逻辑后，用自然语言告诉 AI：'XX 模块在 YY 情况下会出 ZZ 错误，原因是...请修复'
4. AI 生成修复 → 审核 → 测试

举个例子：Synthesizer 的 retry 逻辑最早不工作，测试失败了。我看了一下代码，发现 `continue` 在 `for claim in claims` 循环里，跳过的只是单个 claim 而不是整个 LLM 调用。我用一句话告诉 AI：'retry 应该在 LLM 调用级别，不是 claim 级别'。AI 理解了，重构了整个重试逻辑。我的排查时间大约 5 分钟，修复是 AI 做的。"

### Q5: "如果 AI 一直理解错你的意思怎么办？"

**回答框架**：

"这确实是 Vibe Coding 最大的风险，我的应对策略是：

1. **先让 AI 出计划，别让它直接写代码**。这是我在每个 Milestone prompt 里都强调的——'先给执行计划，等我说 GO 再开干'。如果计划偏离了，修正成本只是改一段文字。如果代码写完了才发现偏离，那成本就大了。

2. **缩小单次任务的范围**。16 小时拆成 9 个 Milestone，每个 Milestone 1-2 小时。任务越小，AI 理解正确的概率越高。

3. **提供具体反例，而不只是正面描述**。比如 prompt 里写'不要捏造 source_id'比'请使用正确的 source_id'有效得多。我在 synthesizer prompt 里有一整节'铁律'，全是禁止项。

4. **实在不行就换一个模型或重开对话**。这个项目全程用的 DeepSeek-V4-Flash，有些推理任务它确实不如 Claude/GPT-4o。所以后来我设计了多 provider 支持（llm.py），可以让不同 stage 用不同模型。"

### Q6: "Vibe Coding 适合什么场景？不适合什么场景？"

**回答框架**：

"适合：
- **原型/MVP 开发**：1-2 天的 Sprint，需求明确，不怕重来
- **工具链项目**：CLI 工具、API 服务、数据处理管道——模式固定，AI 训练数据充分
- **全栈 CRUD**：登录、表单、列表、详情——AI 写过无数遍

不适合：
- **高度创新的算法研发**：AI 倾向于给出'最可能'的方案，而不是'最创新'的方案
- **对性能/安全有极致要求的系统**：AI 不容易考虑缓存粒度、锁竞争、内存布局这类微观优化
- **大型遗留系统的增量修改**：AI 缺乏对整个系统隐式约束的理解

DeepResearch-Lite 属于第一类——这是一个有明确对标产品（OpenAI Deep Research）的 MVP，技术栈标准（Python + Streamlit + LangGraph），非常适合 Vibe Coding。"

### Q7: "你怎么知道 AI 没有偷偷从训练数据里抄别人的代码？"

**回答框架**：

"两个层面回答：

1. **架构层面**：这个项目的核心创新不是某个算法，而是系统设计——Citation 强约束 + 独立 NLI 核验 + 后置校验（不在生成路径上）。这些设计决策体现在 prompt 模板和 pipeline 编排上，不是单个函数。AI 可以生成'一个 NLI 分类函数'，但'后置抽样校验不修改报告'这个架构选择是我做的。

2. **实践层面**：我用的是 DeepSeek-V4-Flash，通过 OpenAI 兼容 API 调用。AI 生成的代码模式确实是常见的（Pydantic models、asyncio.gather、Streamlit st.expander），但这是好事——常见模式意味着经过了社区验证。我关注的是：组合方式是否合理、边界条件是否覆盖。代码本身的'原创性'在 Vibe Coding 中不是重点。"

### Q8: "如果你重新做这个项目，会在 Vibe Coding 流程上做什么改进？"

**回答框架**：

"三个改进：

1. **CLAUDE.md 应该持续更新**。我在增强阶段（P0-P3）没有更新 CLAUDE.md，而是直接在对话中描述需求。这导致后期如果重开对话，AI 缺少上下文。应该把每次重大设计变更都写回 CLAUDE.md。

2. **增加更多确定性测试**。当前 21 个测试覆盖了 schema 和 synthesizer retry，但 verifier 和 end-to-end 流程没有自动化测试。应该增加一个 golden dataset（5 个已知查询 + 预期报告质量指标），每次改动后自动跑。

3. **Prompt 模板应该做版本管理 + A/B 对比**。我的 synthesizer prompt 经历了至少 3 个大版本，但没有系统记录哪个版本产出更好。应该给每个 prompt 版本加标签，跑同一个 query 对比 verifier entailed rate。

这三个改进本质上是在 Vibe Coding 中引入更多'工程纪律'——不是限制 AI 的自由度，而是让 AI 的产出更可衡量。"

### Q9: "你会如何向团队推广 Vibe Coding？"

**回答框架**：

"我不会说'大家都用 Claude Code 写代码吧'。我的推广策略是：

1. **先做 demo，不做培训**。拿一个团队熟悉的痛点项目（比如一个内部工具的改造），用 Vibe Coding 在 2 小时内做完，让大家看结果。效果比任何 PPT 都有说服力。

2. **从文档化开始，而不是从 AI 开始**。让团队先写 CLAUDE.md 式的设计文档——即使暂时不用 AI 写代码，好的设计文档本身就提升团队协作效率。一旦有了这个习惯，接入 AI 是水到渠成的。

3. **设定明确的'人机边界'**。不是所有代码都让 AI 写。我们的规则是：'AI 写实现，人写约束'。人负责 schema 定义、API 契约、测试语义；AI 负责填代码。这样不会出现'AI 写的代码我不知道对不对'的焦虑。

4. **Code Review 流程不变**。AI 写的代码一样走 PR review。Review 重点从'代码风格'转向'边界条件是否覆盖'——这其实让 review 更有价值了。"

### Q10: "你简历上写'16 小时完成 Deep Research Agent 从零到开源'，这个速度是因为 AI 还是因为你本来就快？"

**回答框架**：

"各占一半。

AI 省掉的时间：
- 写 boilerplate（项目结构、setup.py、CI config）：从 2 小时 → 5 分钟
- 调 API（Tavily、Semantic Scholar 的文档阅读和集成）：从 3 小时 → 30 分钟
- 写 Streamlit UI（布局、组件、样式）：从 3 小时 → 30 分钟
- Prompt 迭代（写了改改了写）：每轮从 30 分钟 → 5 分钟

我的经验省掉的时间：
- 架构设计：16 小时的时间盒、9 个 Milestone 的划分、数据流的定义——这些是 AI 不会的
- 风险判断：Day 1 不做 Docker/Next.js/MCP Server 的 Scope 控制——砍需求比写代码更难
- 质量把控：三层防线（Pydantic 约束 + 测试 + Diff 审核）——AI 不会主动设计这些

所以准确的说法是：AI 把执行速度提升了 3-5x，但方向和节奏是我控制的。如果换一个不会拆解问题的人，16 小时可能还在纠结'UI 用 React 还是 Vue'。"

---

## 7. 避坑指南：Vibe Coding 常见失败模式

### 7.1 不要让 AI 做架构决策

```
❌ "帮我做一个 Deep Research 系统"
   → AI 会给一个看似合理但平庸的方案

✅ "按 CLAUDE.md 第 3 节的架构实现 M4 Synthesizer"
   → AI 在设计约束下执行，产出可控
```

### 7.2 不要一次给太多任务

```
❌ "实现全部 8 个改进"
   → prompt 太长，AI 注意力分散，遗漏边界条件

✅ 分成 P0/P1/P2/P3 四个批次，每批 2-3 个改进
   → 每个批次专注，产出质量更高
```

### 7.3 不要跳过"先出计划"这一步

```
❌ "直接改代码吧"
   → AI 理解偏差 → 全部重写 → 浪费时间和 token

✅ "先告诉我你打算怎么改，我确认后再写代码"
   → 计划审 1 分钟 = 省 20 分钟重写
```

### 7.4 不要忽视测试

```
❌ "这个简单不用测"
   → 3 个 commit 后才发现回归 bug

✅ 每个模块至少 1 个 happy path + 1 个 error path 测试
   → AI 改完自动跑全量，回归立即发现
```

### 7.5 不要把 AI 的"我懂了"当真

```
❌ AI: "我理解了" → 直接让它写代码
✅ AI: "我理解了" → 让它复述一遍理解 → 确认无误 → 写代码

具体做法：在 prompt 末尾加一句
"请先用 2-3 句话复述你理解的任务，确认无误后再开始写代码。"
```

---

## 8. 数据与指标

### 8.1 项目量化数据

| 指标 | 数值 |
|------|------|
| 总开发时间 | ~16 小时（1 个工作日 Sprint）|
| 人类手写代码行数 | **0 行** |
| Claude Code 对话轮次 | ~125 轮 |
| 最终代码量 | ~2500 行 Python + ~300 行 Prompt 模板 |
| Git Commits | 19 个（每个有明确语义）|
| 单元测试 | 21 个（全量通过）|
| 外部 API 集成 | 3 个（Tavily、Semantic Scholar、OpenAI 兼容）|
| LLM 成本 | ~$0.10-0.30 / 次完整调研 |

### 8.2 效率对比（估算）

| 任务 | 纯手写估算 | Vibe Coding 实际 | 倍率 |
|------|-----------|-----------------|------|
| 项目脚手架 | 2h | 15min | 8x |
| Web Subagent | 3h | 30min | 6x |
| Synthesizer + prompt | 4h | 1h | 4x |
| Verifier | 3h | 45min | 4x |
| Streamlit UI | 3h | 40min | 4.5x |
| 测试编写 | 2h | 20min | 6x |
| README + 文档 | 1.5h | 20min | 4.5x |
| Prompt 迭代调优 | 3h | 1h | 3x |
| **总计** | **~21.5h** | **~4h 人类 + AI** | **~5x** |

> 注："Vibe Coding 实际"列是 AI 执行代码的时间，人类在此期间做审核和其他工作。实际 wall-clock 时间是 16h，因为人类审核、等待、和部分串行依赖。

---

## 附录：面试 90 秒项目陈述模板

> 直接背诵，控制语速在 90 秒左右。

---

"我在 DeepResearch-Lite 项目中实践了一种叫 Vibe Coding 的 AI 协作范式。

这个项目是一个可溯源深度调研 Agent——输入一个 AI 技术问题，10 分钟内产出一份每句话都能点击追溯到原文的结构化报告。

整个项目从零到开源用了一个工作日、16 个小时。关键是我**一行代码都没写**——所有代码由 Claude Code 根据我写的 CLAUDE.md 设计文档生成。我的角色是架构决策、约束定义和产出审核。

具体来说，我写了 CLAUDE.md：包含技术架构、数据结构定义、16 小时拆成 9 个 Milestone 的时间盒、每个 Milestone 的验收标准。然后每个 Milestone 我给出自然语言任务描述，Claude Code 先出执行计划，我确认后它写代码、跑测试、报告结果。

这个过程中我学到的核心经验是：Vibe Coding 不是放弃控制，而是把控制从代码层面提升到设计层面。Pydantic 的 `min_length=1` 约束比'AI 你记得加引用'可靠得多；21 个单元测试比'我看着没问题'可靠得多。

最终产出：19 个语义清晰的 Git commits、21 个全过的测试、3 个外部 API 集成、一个可用的 Streamlit 前端。项目开源在 GitHub 上，README 有完整的架构图和 Demo GIF。

如果有兴趣，我可以展开讲任何一个环节——比如我是怎么设计 citation 强约束的三层防线的，或者 Verifier 的二次复核机制是怎么减少误报的。"

---

> **背诵要点**：
> - 前 30 秒：项目是什么 + 核心数字（1 天、0 行手写代码）
> - 中间 30 秒：怎么做（CLAUDE.md → Milestone → 四步循环）
> - 最后 30 秒：成果 + 邀请追问

---

*文档版本: v1.0 | 最后更新: 2025.05.15 | 随项目持续更新*
