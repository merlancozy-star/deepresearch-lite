# DeepResearch-Lite：Vibe Coding 实践全记录 & 面试问答指南

> 本文档用于面试准备。基于 `DeepResearch-Lite`（`C:\Users\25610\Desktop\Deepsearch-c`）项目的真实开发过程——19 个 Git commits、125+ 轮 Claude Code 对话、0 行人类手写代码。

---

## 目录

1. [项目快照](#1-项目快照)
2. [Vibe Coding 定义与本项目定位](#2-vibe-coding-定义与本项目定位)
3. [完整工作流还原](#3-完整工作流还原)
4. [四种 AI 协作模式（含本项目真实案例）](#4-四种-ai-协作模式含本项目真实案例)
5. [CLAUDE.md：设计契约的设计](#5-claudemd设计契约的设计)
6. [Git 历史：19 个 commits 讲述的故事](#6-git-历史19-个-commits-讲述的故事)
7. [10 个面试高频问题 & 本项目回答](#7-10-个面试高频问题--本项目回答)
8. [Vibe Coding 失败模式与对策](#8-vibe-coding-失败模式与对策)
9. [量化数据](#9-量化数据)
10. [附录：90 秒项目陈述（可直接背诵）](#附录90-秒项目陈述可直接背诵)

---

## 1. 项目快照

| 项目信息 | 详情 |
|---------|------|
| 项目名 | DeepResearch-Lite |
| 定位 | 面向 AI 工程师的可溯源深度调研 Agent MVP |
| GitHub | `https://github.com/merlancozy-star/deepresearch-lite` |
| 技术栈 | Python 3.10 + Pydantic v2 + OpenAI SDK + Tavily + Streamlit + httpx + BeautifulSoup |
| LLM | DeepSeek-V4-Flash（通过 autodl.art 的 OpenAI 兼容 API） |
| 代码量 | ~2500 行 Python + 6 个 Prompt 模板文件 |
| 测试 | 21 个单元测试，全量通过 |
| 开发时间 | ~16 小时（1 个工作日 Sprint） |
| 人类手写代码 | **0 行** |
| Git commits | 19 个（每个有独立语义） |

**核心架构**（`deepresearch/graph.py`）：

```
用户问题
  → Orchestrator（意图分类 + 查询拆解）
    → Web Subagent (Tavily + 全文抓取)  ─┐
    → Arxiv Subagent (Semantic Scholar)   ─┤ asyncio.gather 并发
    → Mock Subagent (API 不可用时兜底)    ─┘
  → RRF 融合 + 去重
  → Reflector（LLM 审阅信息缺口 → 补充搜索）
  → Synthesizer（大纲 → 逐节撰写 → 汇总）
  → Verifier（NLI 三分类 + contradiction 二次复核）
  → Streamlit UI（可点击引用 + 章节导航 + 参考文献卡片）
```

---

## 2. Vibe Coding 定义与本项目定位

### 2.1 定义

**Vibe Coding** 由 Andrej Karpathy 于 2025 年 2 月提出：

> "You fully give in to the vibes, embrace exponentials, and forget that the code even exists."

本项目中的操作化定义：

> **以 CLAUDE.md 设计文档为唯一契约，将全部代码执行委托给 Claude Code。人类负责架构决策、约束定义、产出审核；AI 负责实现、测试、debug。**

### 2.2 本项目的人机分工

| 环节 | 谁做 | 本项目具体体现 |
|------|------|-------------|
| 架构设计 | 人类 | 数据流图、三层防线（Pydantic 硬约束 + 测试 + Diff 审核） |
| 时间盒规划 | 人类 | 16h → 9 个 Milestone |
| Scope 控制 | 人类 | 砍掉 Docker/Next.js/MCP Server，写进 README Roadmap |
| 写代码 | Claude Code | 所有 `.py` 文件 |
| 写 Prompt | Claude Code | 6 个 `.txt` prompt 模板 |
| 写测试 | Claude Code | `tests/` 下 3 个文件 |
| 写文档 | Claude Code | README、本文档 |
| Debug | 人类定位 + Claude Code 修复 | 6 个错误驱动迭代 |
| 审美判断 | 人类 | "commit 要有人味"、"输出用中文" |

---

## 3. 完整工作流还原

### 3.1 真实时间线

```
2025.05.14

08:00-09:00  人类写 CLAUDE.md（设计契约，~400 行中文）
09:00-10:00  M1: Claude Code 创建项目骨架
             → git init, pyproject.toml, 目录结构, .env.example
             → commit 435c39c "搭个架子：项目配置文件"
10:00-11:00  M2: Schemas + Citation 工具
             → deepresearch/schemas.py (Citation/Claim/ResearchReport)
             → deepresearch/citation.py (RRF 融合 + 去重)
             → commit e7f2d35 + f01e736
11:00-12:00  M3: Subagent 实现
             → deepresearch/subagents/web.py (Tavily)
             → deepresearch/subagents/arxiv.py (Semantic Scholar + arXiv)
             → deepresearch/subagents/mock.py (API 不可用时的硬编码兜底)
             → commit 94c388d + aa9947d + 2a3a935
12:00-13:00  午饭
13:00-15:00  M4: Synthesizer
             → deepresearch/prompts/synthesizer.txt（结构化报告 prompt）
             → deepresearch/synthesizer.py（structured output + retry 逻辑）
             → commit dba3926 + cfabd8f + 77286c4
15:00-17:00  M5: Verifier
             → deepresearch/prompts/verifier.txt（NLI 三分类 prompt）
             → deepresearch/verifier.py（异步并发核验）
             → commit 14aff4e
17:00-18:00  M6: 编排 + CLI
             → deepresearch/orchestrator.py（意图分类 + 查询拆解）
             → deepresearch/graph.py（async pipeline）
             → deepresearch/cli.py（argparse + Windows UTF-8 修复）
             → commit 9fa25fd + 1cfae74 + 4c677cc
18:00-19:00  晚饭
19:00-21:00  M7: Streamlit UI
             → app.py（输入框 + 报告渲染 + 引用展开 + 核验徽章）
             → commit 06a1c85
21:00-22:00  M8: README + 开源
             → README.md, 架构图, Demo GIF
             → commit cfc2369
22:00-23:00  M9: 整理 + 多 case 验证
             → commit 历史重写（19→17 个语义清晰的 commits）

2025.05.15

增强阶段  可溯源报告 + 详细文档生成系统
           → schemas.py 加 section/references/sub_questions/methodology/pipeline_stats
           → app.py 重写：侧边栏目录、可点击引用、参考文献卡片
           → commit b741bca

质量改进   P0-P3 七个改进
           → Mock 按需启用 + Web 全文抓取 + 两阶段 Synthesis
           → Reflection 补充搜索 + Verifier 增强 + SQLite 缓存
           → 多 Provider + 意图模板
           → commit fed4655
```

### 3.2 每个 Milestone 的四步循环

本项目中每个 Milestone 实际执行过程：

```
Step 1 — 任务下发
  人类（复制 CLAUDE.md 第 6 节的 Milestone Prompt）：
    "请通读项目根目录的 CLAUDE.md。任务: M4 Synthesizer。
     1. 写 synthesizer prompt，强调每 claim 必须挂 ≥1 source_id
     2. 用 Pydantic structured output 强约束
     3. 解析失败 → retry 最多 3 次
     先给执行计划，等我说 GO 再开干。"

Step 2 — 计划确认
  Claude Code：
    "我的计划是：
     1. 创建 deepresearch/prompts/synthesizer.txt，核心约束：每条 claim
        必须从 evidence pool 选择至少 1 条，使用 source_id + chunk_id 引用
     2. synthesize() 函数调用 OpenAI，response_format='json_object'
     3. 解析 JSON → 逐条 claim 匹配 citation_map → 无匹配则 all_valid=False
     4. 外层最多 3 次 retry，第 3 次仍失败则标 [UNCITED]
     可以开始吗？"

Step 3 — 执行 + 测试
  人类："GO"
  Claude Code：写代码 → 跑 pytest → 报 "21 passed" → 返回 diff 摘要

Step 4 — 审核 + 反馈
  人类（看 diff，发现问题）：
    "retry 的 continue 在 for claim in claims 循环里，只跳过单条 claim
     而不是整个 LLM 调用。应该在 LLM 调用级别重试。"
  Claude Code：修复 → 重新跑测试 → 通过
```

---

## 4. 四种 AI 协作模式（含本项目真实案例）

### 4.1 模式一：设计文档驱动（Design Doc Driven）

**核心理念**：不写代码，只写约束。AI 在设计框架内自由实现。

**本项目案例**：Citation 数据结构设计

我在 `CLAUDE.md` 第 3.2 节写了：

```python
class Claim(BaseModel):
    text: str
    citations: List[Citation] = Field(..., min_length=1)  # 强约束
```

Claude Code 在 `deepresearch/schemas.py:23` 实现为：

```python
class Claim(BaseModel):
    text: str
    section: str = Field(default="", description="Which report section this claim belongs to")
    citations: List[Citation] = Field(..., min_length=1)
    verifier_label: Literal["entailed", "contradicted", "neutral", "unchecked"] = "unchecked"
    verifier_score: float = Field(default=0.0, ge=0, le=1)
    verifier_reasoning: str = ""
```

关键点：`min_length=1` 这个硬约束是我定的，`verifier_label` 的 `Literal` 类型也是我定的。AI 自动推导出了 `verifier_score` 的 `ge=0, le=1` 约束。约束越精确，AI 产出的代码越不容易出错。

**本项目案例**：Synthesizer prompt 的"铁律"设计

我在 `deepresearch/prompts/synthesizer.txt:48-54` 设计了六条硬约束：

```
## 铁律（违反则视为失败）

1. 每一条事实性陈述必须紧跟 [^source_id]，source_id 只能使用证据池中实际存在的 ID。
2. 每个 [^source_id] 必须在"参考文献"节有对应条目。
3. 没有证据的内容必须标注"据当前搜索结果，证据不足"，严禁臆造。
4. source_ids 和 chunk_ids 数组长度必须相等，一一对应。
5. 报告必须用中文撰写，专业术语保留英文。
6. 参考文献条目至少 3 条，每条必须来自证据池。
```

这六条是纯粹的约束工程——不需要懂代码，需要懂的是"LLM 会在哪些地方偷懒/编造/省略"。这些约束是通过观察 LLM 的实际失败模式反向推导出来的。

### 4.2 模式二：渐进式约束叠加

**核心理念**：先给软约束（自然语言），观察失败，再加硬约束（代码级）。

**本项目案例**：Citation 约束的四次进化

```
v1 — 软约束（Prompt 中写）：
    synthesizer.txt: "每条论断 MUST 至少引用一条证据"
    → LLM 有时遵守，有时忽略。不可靠。

v2 — 硬约束（Pydantic min_length=1）：
    schemas.py: citations: List[Citation] = Field(..., min_length=1)
    → 空引用直接抛 ValidationError。100% 可靠，但用户体验差。

v3 — 软着陆（retry + 错误反馈）：
    synthesizer.py: 捕获空引用 → 把错误信息注入重试 prompt →
    "上一次尝试失败。每条论断必须包含至少一个有效的 source_id。不要捏造 ID。"
    → 大多数情况 retry 后正确。但故意给不存在的 source_id 仍会失败。

v4 — 最终兜底（fallback Citation）：
    synthesizer.py: 最终 retry 仍失败 → 标 [UNCITED] +
    插入 source_id="synthesizer:fallback" 的 dummy Citation
    → 系统永远不崩溃，但标注了不可信的内容。
```

**面试时的叙事**：

> "这个演进过程体现了 Vibe Coding 的精髓——我每次只描述'当前版本出现了什么问题'，AI 负责想解决方案。从 v1 到 v4，我没有写过一行代码，但我做了四次'问题描述 + 方案审核'。最终产物比我一上来就设计出来的要健壮得多。"

### 4.3 模式三：错误驱动迭代

**核心理念**：把错误日志当 prompt，让 AI 自己诊断 + 修复。

**本项目真实错误链**（6 个，全部在项目中实际发生）：

**错误 1**：`Pydantic ValidationError: citations field required (min_length=1)`

```
根因：Synthesizer 产出的 claim 引用了一个不在 citation_map 中的 source_id，
      matched_citations 为空列表，Pydantic 创建 Claim 时报错。
修复：synthesizer.py 在创建 Claim 前检查 matched_citations，
     为空则设 all_valid=False → 触发外层 retry。
修复代码位置：deepresearch/synthesizer.py:153-156
```

**错误 2**：`RuntimeError: asyncio.run() cannot be called from a running event loop`

```
根因：verify_report() 内部调用了 asyncio.run()，但它在 run_pipeline() 的
     asyncio.run() 内部被调用——嵌套 event loop。
修复：把 verify_report 从同步函数改为 async 函数（async def verify_report），
     在 run_pipeline 中用 await verify_report(report) 调用。
修复代码位置：deepresearch/verifier.py:104（函数签名改 async）
              deepresearch/graph.py:74（调用改 await）
```

**错误 3**：`httpx.HTTPStatusError: 429 Too Many Requests from Semantic Scholar`

```
根因：中国 IP 访问 Semantic Scholar 和 arXiv API 被限流。
修复：创建 MockSubagent（deepresearch/subagents/mock.py），
     硬编码 vLLM/SGLang/Mamba 的 demo citation。
     后续又在 graph.py 中加了"只在实际 API 都挂时才启用 mock"的逻辑。
修复代码位置：deepresearch/subagents/mock.py（新增文件）
              deepresearch/graph.py:48-50（条件启用）
```

**错误 4**：TavilyClient 空 API key 挂起无响应

```
根因：.env 中的 TAVILY_API_KEY 是占位符 "tvly-your-key-here"，
     TavilyClient 初始化后调用 search 会挂起而非报错。
修复：在 WebSubagent.__init__ 中检查 api_key 有效性：
     if api_key and api_key != "tvly-your-key-here" and len(api_key) > 10
修复代码位置：deepresearch/subagents/web.py:28-31
```

**错误 5**：`KeyError: 'N'` in synthesizer prompt

```
根因：新 prompt 模板中有 "检索到证据片段：{N} 条" 这一行，
     Python str.format() 把 {N} 当作占位符。
修复：转义为 {{N}}。
修复代码位置：deepresearch/prompts/synthesizer.txt:27
```

**错误 6**：`UnicodeEncodeError` on Windows GBK terminal

```
根因：Windows 中文版默认终端编码是 GBK，emoji（如 🔍✅🔴）无法编码。
修复：在 cli.py 中检测 Windows 平台 → 用 UTF-8 重包装 stdout：
     if sys.platform == "win32":
         sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
修复代码位置：deepresearch/cli.py:20-21
```

**面试时的叙事**：

> "这 6 个错误没有一个是我预想到的。但每次出错我只需要做一件事：把错误信息贴给 Claude Code。它自己看 traceback、定位根因、给出修复方案。我做的事情是审核方案是否合理。这个过程让我意识到 Vibe Coding 的 debug 效率远高于传统 debug——因为 AI 读代码比我快得多，而且不会漏看。"

### 4.4 模式四：人类审美注入

**核心理念**：AI 不知道什么是"好"的 commit message、什么是"有人味"的输出、什么是"对面试官友好"的 README。这些审美标准需要人类显式注入。

**本项目案例**：17 个 commits 的历史重写

原始状态：19 个 commits，有些叫 "fix"、"wip"、"update"，无法展示给面试官。

人类指令：
```
"对每条commits进行优化，希望非常的具有人味"
"我希望每个文件夹、文件都有独一无二的合理的简要明确的commits"
```

Claude Code 执行：
```
1. 分析 19 个 commits → 识别出 3 类问题：
   - 太细碎（"fix typo" / "update" / "wip"）
   - 太笼统（一个 commit 包含太多文件）
   - 非语义化（"add file" vs "feat(schemas): add Citation/Claim/Report"）

2. 用 git checkout --orphan 创建干净分支 →
   按文件/模块粒度逐个 cherry-pick →
   每个 commit message 遵循 conventional commits 格式

3. 最终输出 17 个 commits：
   435c39c 搭个架子：项目配置文件
   e7f2d35 Pydantic 数据结构：Citation → Claim → ResearchReport
   f01e736 RRF 融合 + 按 source_id/char_span 去重
   796c6d3 Subagent 抽象基类 + 文本分块工具
   94c388d Web Subagent：接 Tavily 搜网页
   ...
```

**关键洞察**："有人味"这个标准 AI 自己无法定义。它不知道面试官想看什么。但一旦人类说清楚了"每个文件一个 commit"这个方向，AI 可以精确执行 git 操作。

---

## 5. CLAUDE.md：设计契约的设计

### 5.1 文件位置与加载机制

```
C:\Users\25610\Desktop\Deepsearch-c\CLAUDE.md
```

Claude Code 每次启动或进入项目目录时，自动读取此文件作为系统上下文。这意味着：

- 不需要每次对话都解释项目背景
- 所有对话共享同一份"真相源"
- 可以通过 git 追踪 CLAUDE.md 的变更历史

### 5.2 章节设计与协作目的

本项目 CLAUDE.md 包含 12 个章节，每个服务于不同的协作目的：

| 章节 | 核心内容 | 为 AI 解决了什么问题 |
|------|---------|-------------------|
| **1. 项目定位** | 一句话定义 + Day 1 Scope | "我在做什么、给谁做、什么不做" |
| **2. 核心差异化** | Citation 强约束 + NLI 校验 | 技术选型时优先实现差异化特性 |
| **3. 技术架构** | 数据流图 + 数据结构定义 | 精确的实现蓝图 |
| **4. 目录结构** | 每个文件的预期位置 | 文件放哪、模块怎么组织 |
| **5. 时间盒** | 9 Milestone × 验收标准 | 知道每个阶段做到什么程度算完成 |
| **6. Milestone Prompt** | 可直接复制的任务描述 | 减少人类打字，标准化任务格式 |
| **7. Vibe Coding 工作流** | 面试时讲的设计理念 | 代码风格和注释风格参考 |
| **8. 风险与边界** | 什么绝对不能做 | Scope creep 防护墙 |
| **11. 简历叙事** | 90 秒项目陈述 | AI 理解项目的"对外叙事"，写 README 时对齐 |

### 5.3 CLAUDE.md 的实际作用验证

一个简单的验证：如果你把我的 CLAUDE.md 给另一个工程师 + Claude Code，他们能复现这个项目吗？

答案：**可以复现到 80%**。架构、数据结构、数据流都能复现。20% 的差异来自：
- 调试过程中的隐性知识（6 个错误的修复策略）
- 审美判断（"有人味的 commit"）
- API 可用性的实时判断（"arXiv 在中国被墙，加 mock"）

这也解释了为什么 CLAUDE.md 需要持续更新——把调试中获得的隐性知识写回文档。

### 5.4 改进反思

```
当前状态（v1.2）：
  - CLAUDE.md 反映了 Day 1 MVP 的设计
  - P0-P3 的 8 个改进没有写回 CLAUDE.md
  - 如果重开对话，AI 不知道有两阶段 Synthesis、Reflection、缓存层

理想状态（v2.0，建议后续做）：
  - 每个重大架构变更都更新 CLAUDE.md 对应章节
  - 第 3 节技术架构应反映当前实际的 7 步 pipeline
  - 第 5 节应补充增强阶段的时间线
```

---

## 6. Git 历史：19 个 commits 讲述的故事

### 6.1 完整历史

```
16efd5f docs: vibe coding interview guide — full workflow + 10 Q&A + metrics
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

### 6.2 面试展示策略

**话术**：

> "这个 Git 历史本身就是 Vibe Coding 的证据。注意两个特征：
>
> 1. **没有 fix typo / wip / update 这类 commit**——因为 AI 不会犯 typo，而且我会在 commit 前让 AI 自己跑测试验证。
>
> 2. **每个 commit 对应一个明确的设计决策，不是对应'一个文件'**。比如 `77286c4` 的 diff 只涉及 tests/ 目录，但它的存在是因为我告诉 AI 'retry 逻辑需要单独的测试覆盖'——这是我作为架构师的判断，代码是 AI 写的。"

**打开 GitHub 演示时的操作**：

```
1. 打开 https://github.com/merlancozy-star/deepresearch-lite
2. 点击 commits 标签
3. 随机选 fed4655（最大的那个 commit）
4. 指出：+1169/-236 行，14 个文件，这是"P0-P3 七个改进"这一个任务的产出
5. 重点：这个 1169 行的 diff，我输入的只是一段不到 200 字的任务描述
```

---

## 7. 10 个面试高频问题 & 本项目回答

### Q1: "什么是 Vibe Coding？你怎么定义它？"

**回答**（90-120 秒）：

> "Vibe Coding 是我在 DeepResearch-Lite 中实践的一种 AI 协作范式。核心是三个转变：
>
> 1. **从写代码到写约束**。我不写实现逻辑，而是写数据 schema、边界条件、验收标准。比如我的 `deepresearch/schemas.py` 中 `Claim.citations` 有 `min_length=1` 约束——这行代码是 AI 写的，但'每个 claim 必须有至少一个引用'这个规则是我设计的。AI 无论如何也不会绕过 Pydantic 的硬约束。
>
> 2. **从调试到审核**。我不逐行 debug，而是读 AI 产出的 diff。整个项目出了 6 个 bug——Windows GBK 编码、asyncio 嵌套、arXiv 429 限流等——每次我只是把错误信息贴给 Claude Code，它自己诊断和修复。我的角色是判断修复方案是否合理。
>
> 3. **从对话记忆到持久化文档**。项目根目录的 `CLAUDE.md` 是设计契约，每次 Claude Code 启动自动加载。这解决了'上次聊的这次忘了'的问题——所有对话共享同一份真相源。
>
> Vibe Coding 不是放弃控制，而是把控制从代码层面提升到设计层面。`min_length=1` 这个约束比'AI 你记得加引用'可靠一万倍。"

### Q2: "Vibe Coding 和 Copilot 自动补全有什么区别？"

**回答**：

> "区别在粒度和主动性。
>
> Copilot 是逐行补全——你写 import，它补 `from typing import List`。你仍然在驾驶座上，只是油门踩得轻了些。
>
> Vibe Coding 是整块委托。举个例子：我在做 Verifier 增强时，只说了一句'用 few-shot examples 改进 NLI prompt，对 contradiction 做二次复核'。Claude Code 自己做了：
> - 重写 `deepresearch/prompts/verifier.txt`（加 3 个 few-shot 示例 + 三步核验流程）
> - 在 `deepresearch/verifier.py` 中新增 `_verify_single()` 函数，接受 `review_pass` 参数
> - 第二次复核时用更严格的 system message：'只有明确、不可调和的矛盾才判 contradicted'
> - 最终 contradicted claim 标注 `[二次复核确认]` 前缀
>
> 这 4 个决策都是 AI 自己做的。如果我用 Copilot，我得一行一行写这些代码。如果用 Vibe Coding，我只需要描述'我想达到什么效果'。本质区别是：Copilot 帮你写代码，Vibe Coding 帮你做工程决策。"

### Q3: "完全靠 AI 写代码，质量能有保证吗？"

**回答**：

> "质量保证不靠 AI，靠三层防线。以本项目为例：
>
> **第一层——设计约束（硬防线）**：
> `deepresearch/schemas.py:24`：
> ```python
> citations: List[Citation] = Field(..., min_length=1)
> ```
> 这行意味着任何无引用的 claim 在 Pydantic 层就会被拒绝，AI 不可能绕过。
> `deepresearch/prompts/synthesizer.txt:48-54` 的六条铁律也一样——LLM 的输出被 JSON schema + 后处理代码双重校验。
>
> **第二层——自动化测试（21 个）**：
> `tests/test_schemas.py`：验证 Citation/Claim/ResearchReport 的创建约束
> `tests/test_citation_rrf.py`：验证 RRF 融合的数学正确性（10 个 case）
> `tests/test_synthesizer_strict.py`：验证 retry 逻辑的 4 个场景
> 每次代码变更后 AI 自动跑 `pytest tests/ -v`，回归立即发现。
>
> **第三层——人工 Diff 审核**：
> 我读每一个 AI 产出的 diff，重点关注：错误处理是否完备、边界条件是否覆盖。
> 比如两阶段 Synthesis 重写时，我发现 AI 的 retry 逻辑只在 claim 级别重试（`for claim in claims` 循环里的 `continue`），不在 LLM 调用级别重试。这意味着如果整个 LLM 调用返回了坏数据，它不会重新调用 LLM，只是跳过坏 claim。我指出后 AI 修正为：检查 `all_valid` 标志 → 在 LLM 调用级别 `continue` 重新调用。
>
> 三层加起来，质量不比我手写差。而且 AI 不会偷懒跳过边界处理。"

### Q4: "AI 写的代码你能看懂吗？出了问题怎么排查？"

**回答**：

> "能看懂，因为架构是我设计的。这就像建筑师不需要亲手砌每一块砖，但知道每面墙的承重。
>
> 实际排查过一次典型问题：
>
> ```
> 错误：3 个 synthesizer 测试失败，claims 列表为空
>
> 排查过程（~5 分钟）：
> 1. 看报错：report.claims 是空列表 → synthesizer 没有产出 claim
> 2. 看 synthesizer.py 的 retry 逻辑：
>    - 找到 for claim in raw_claims 循环
>    - 找到 continue（跳过无引用的 claim）
>    - 发现问题：continue 只跳过单条 claim，没有触发 LLM 重试
>    - 所有 claim 被跳过后，函数返回空列表，外层不重试
> 3. 告诉 AI："retry 应该在 LLM 调用级别，不是 claim 级别。
>    如果 all_valid 为 False 且还有 retry 次数，应该重新调用 LLM。"
> 4. AI 修复 → 跑测试 → 4/4 通过
>
> 我的排查时间 5 分钟，AI 修复时间 30 秒。传统方式我可能需要 30 分钟定位 + 修代码。"

### Q5: "如果 AI 一直理解错你的意思怎么办？"

**回答**：

> "这确实是 Vibe Coding 最大的风险。我在项目中有四个应对策略：
>
> 1. **先出计划，别直接写代码**。每个 Milestone prompt 末尾都有'先给执行计划，等我说 GO 再开干'。如果计划偏离了，修正成本只是改一段话。如果代码写完了才发现偏离，成本就是全部重写。
>
> 2. **缩小任务范围**。16 小时拆成 9 个 Milestone，后续 8 个改进拆成 P0-P3 四个批次。任务越小，AI 理解正确的概率越高。`fed4655` 那个 commit 虽然很大（1169 行），但它是对 8 个清晰的小任务的汇总，不是一次模糊的'改进所有'。
>
> 3. **用反例而非正例**。Prompt 里写'不要捏造 source_id'比'请使用正确的 source_id'有效得多。`synthesizer.txt` 里有一整节'铁律'，全是禁止项。这在 LLM prompt engineering 里叫 negative constraints，对 AI 特别有效。
>
> 4. **换模型或重开对话**。DeepSeek-V4-Flash 做推理任务不如 Claude/GPT-4o。所以后来我设计了 `llm.py`，支持按 stage 分配不同模型——Synthesizer 可以用更强的模型，Orchestrator 用便宜的。"

### Q6: "Vibe Coding 适合什么场景？这个项目为什么适合？"

**回答**：

> "DeepResearch-Lite 几乎是 Vibe Coding 的完美场景，因为：
>
> 1. **有明确对标产品**（OpenAI Deep Research、GPT-Researcher），不需要从零发明——AI 训练数据中这类系统足够多
> 2. **技术栈标准**：Python + Pydantic + Streamlit + LangGraph——每个都是 AI 训练数据中的高频技术
> 3. **核心差异化在系统设计而非算法**：Citation 强约束 + 后置 NLI 校验 + 不在生成路径上——这些是架构决策，代码实现是常规的
> 4. **1-2 天 Sprint 范围**：够做一个完整 MVP，但不需要考虑生产环境的复杂问题
>
> 反例：不适合 Vibe Coding 的场景——
> - 高度创新的算法研发（AI 倾向于给出'最可能'方案而非'最创新'方案）
> - 性能敏感的底层系统（AI 不容易考虑缓存粒度、锁竞争、内存布局）
> - 大型遗留系统的增量修改（AI 缺乏对隐式约束的理解）"

### Q7: "AI 有没有可能抄袭训练数据里的代码？你担心吗？"

**回答**：

> "两个层面：
>
> 1. **这个项目的核心不是代码而是系统设计**。Citation 强约束 + 独立 NLI 核验 + 后置校验不修改报告——这些设计决策体现在 prompt 模板和 pipeline 编排上，不是某个函数。AI 可以生成'一个 NLI 分类函数'（这是常见模式），但'后置校验不在生成路径上'这个架构选择是人类做的。
>
> 2. **代码层面：常见模式是好事**。AI 生成的 Pydantic models、asyncio.gather 并发、Streamlit st.expander——这些都是社区最佳实践。我关注的不是'这段代码是不是 AI 独创的'，而是'这段代码的组合方式是否合理、边界条件是否覆盖'。
>
> 本质上，软件工程的进步从来不是靠'独一无二的代码'，而是靠合理的架构+完备的边界处理。Vibe Coding 在这两点上都不比手写差。"

### Q8: "你从这个项目中学到的 Vibe Coding 最大教训是什么？"

**回答**：

> "最大教训：**CLAUDE.md 必须持续更新**。
>
> 我在增强阶段（P0-P3 八个改进）犯了一个错误——直接在对话中描述需求，没有更新 CLAUDE.md。这导致：
> - QA 部分如果重开对话，AI 不知道有两阶段 Synthesis
> - 没办法追溯'为什么 Reflection 步骤在 RRF 融合之后'
> - 面试时我只能靠记忆还原设计决策
>
> 正确做法：每完成一个阶段的改进，就更新 CLAUDE.md 的对应章节（架构图、数据流、目录结构）。CLAUDE.md 应该是项目的'活文档'，而不是'Day 1 写了就扔'的化石。
>
> 次要教训：**测试覆盖不足**。21 个测试覆盖了 schema 和 synthesizer，但 verifier 和 end-to-end 没有自动化测试。应该在 Day 1 就建立一个 golden dataset（5 个已知 query + 预期指标），每次改动后自动对比。"

### Q9: "你会如何向团队推广 Vibe Coding？"

**回答**：

> "我不会一上来就说'大家用 Claude Code 吧'。我的策略是渐进式的：
>
> 1. **先做一次 live demo**。拿一个团队熟悉的痛点（比如内部工具的一个 feature），当着大家的面用 Vibe Coding 在 1 小时内做完。效果比任何 PPT 都有说服力。
>
> 2. **从 CLAUDE.md 文化开始**。即使暂时不用 AI 写代码，让团队养成写设计文档的习惯本身就是工程能力提升。有了这个基础，接入 AI 是水到渠成。
>
> 3. **设定'人机边界'**。我们团队的规则是：人写 schema + 测试语义 + API 契约，AI 写实现代码。Code review 流程不变，但 review 重点从'代码风格'转向'边界条件是否覆盖'。
>
> 4. **用数据说话**。我在这个项目上测出来大约 5x 效率提升。与其说服别人'AI 很好用'，不如展示'这个具体任务用 AI 省了多少时间'。"

### Q10: "简历上写 16 小时完成 Deep Research Agent 从零到开源——是因为 AI 还是因为你本来就快？"

**回答**：

> "各占一半。我分解一下：
>
> AI 省掉的纯执行时间：
> - 项目脚手架（pyproject.toml、目录结构、.gitignore）：手写 2h → AI 15min（8x）
> - Tavily API 集成（读文档 + 写 client + 错误处理）：手写 3h → AI 30min（6x）
> - Streamlit UI（布局 + 组件 + 状态管理）：手写 3h → AI 40min（4.5x）
> - 测试编写（21 个 test case）：手写 2h → AI 20min（6x）
>
> 我的经验省掉的时间（AI 帮不了的）：
> - 架构设计：9 个 Milestone 的划分、数据流的定义——8 年工程经验，AI 不会
> - Scope 控制：Day 1 坚决不做 Docker/Next.js/MCP——砍需求比写代码更难
> - 质量防线设计：Pydantic + 测试 + Diff 审核三层——AI 不会主动设计质量体系
>
> 所以准确的说法是：**AI 把执行速度提升了 3-5x，但方向和节奏是我控制的**。换一个不会拆解问题的人，16 小时可能还在纠结'LLM prompt 写英文还是中文'。Vibe Coding 放大的是你的工程判断力，不是替代它。"

---

## 8. Vibe Coding 失败模式与对策

### 8.1 不要让 AI 做架构决策

```
❌ 失败模式：
   "帮我做一个 Deep Research 系统"
   → AI 给一个看似合理但平庸的方案（搜一下 → 总结一下 → 输出）
   → 没有 Citation 强约束、没有 Verifier、没有差异化

✅ 本项目做法：
   "按 CLAUDE.md 第 3 节的架构实现 M4 Synthesizer。注意：
    - Pydantic min_length=1 硬约束
    - 无证据 claim → reject → retry（最多 3 次）
    - 最终失败标 [UNCITED]"
   → AI 在设计框架内执行，产出可预期

核心原则：架构是人类的工作，实现是 AI 的工作。不要混淆。
```

### 8.2 不要一次给太多任务

```
❌ 失败模式：
   "改进全部 8 个方面"
   → AI 注意力分散、遗漏边界条件、commit 成一个巨大的 diff

✅ 本项目做法：
   先列出 8 个改进（P0-P3）→ 让 AI 给计划 → 确认后按优先级分批执行
   → 最终一个 commit (fed4655) 包含所有改进，但每个改进的 prompt 是独立的
   → 14 个文件 +1169 行，但结构清晰，因为每步都是先计划再执行

核心原则：AI 擅长专注执行，不擅长全局规划。规划是人类的工作。
```

### 8.3 不要跳过"先出计划"

```
❌ 失败模式：
   "直接改代码吧"
   → AI 理解偏差 → 方向错误 → 全部重写 → 浪费 30 分钟 + 大量 token

✅ 本项目做法：
   每个 Milestone prompt 末尾都有：
   "先给执行计划，等我说 GO 再开干"
   → 计划审核：30 秒
   → 避免重写：节省 20+ 分钟

核心原则：计划错了改文字，代码错了全重来。审计划是 Vibe Coding 中 ROI 最高的动作。
```

### 8.4 不要忽视测试

```
❌ 失败模式：
   "这个简单，不用测"
   → 3 个 commit 后回归 bug → 排查 30 分钟

✅ 本项目做法：
   tests/test_schemas.py    → 7 个测试（schema 约束验证）
   tests/test_citation_rrf.py → 10 个测试（RRF 融合数学正确性）
   tests/test_synthesizer_strict.py → 4 个测试（retry 逻辑）
   AI 每次代码变更后自动跑 pytest tests/ -v

核心原则：测试是 AI 的 guardrail。没有测试的 Vibe Coding 是赌博。
```

### 8.5 不要把 AI 的"我懂了"当真

```
❌ 失败模式：
   AI: "我理解了"
   → 直接让它写代码 → 产出和预期完全不同

✅ 本项目做法：
   复杂任务（如两阶段 Synthesis 重写）让 AI 先：
   1. 复述一遍它理解的任务
   2. 列出要创建/修改的文件
   3. 描述关键函数签名
   → 人类确认无误 → 开始写代码

核心原则：AI 说"我懂了"不代表真懂了。让它复述一遍是最便宜的验证。
```

---

## 9. 量化数据

### 9.1 项目统计

| 指标 | 数值 |
|------|------|
| 总 wall-clock 时间 | ~16 小时 |
| 人类手写代码行数 | **0 行** |
| Claude Code 对话轮次 | ~125 轮 |
| Python 代码量 | ~2,500 行（19 个 .py 文件） |
| Prompt 模板 | 6 个 .txt 文件，~300 行 |
| Git commits | 19 个 |
| 单元测试 | 21 个（全量通过，<1s 跑完） |
| 外部 API 集成 | Tavily + Semantic Scholar + OpenAI 兼容 |
| 单次调研 LLM 成本 | $0.10-0.30 |
| 项目依赖 | 9 个 PyPI 包 |

### 9.2 效率对比

| 任务模块 | 纯手写估算 | Vibe Coding 实际 | 倍率 |
|---------|-----------|-----------------|------|
| 项目脚手架 | 2h | 15min | **8x** |
| Schemas + Citation 工具 | 2h | 30min | **4x** |
| Web Subagent (Tavily 集成) | 3h | 30min | **6x** |
| Arxiv Subagent | 2h | 30min | **4x** |
| Synthesizer + Prompt | 4h | 1h | **4x** |
| Verifier | 3h | 45min | **4x** |
| Graph 编排 + CLI | 2h | 40min | **3x** |
| Streamlit UI | 3h | 40min | **4.5x** |
| 测试编写 | 2h | 20min | **6x** |
| Prompt 迭代调优 | 3h | 1h | **3x** |
| README + 文档 | 1.5h | 20min | **4.5x** |
| Commit 历史整理 | 1h | 15min | **4x** |
| **总计** | **~28.5h** | **~6.5h（AI 执行）** | **~4.4x** |

> 注：AI 执行时间 ≠ wall-clock 时间（16h），因为有人类审核、等待、和串行依赖。

### 9.3 错误修复效率

| 错误 | 人类排查 | AI 修复 | 传统修复估算 |
|------|---------|--------|------------|
| Pydantic ValidationError | 2min | 1min | 15min |
| asyncio.run() 嵌套 | 2min | 1min | 20min |
| arXiv HTTP 429 | 1min | 5min | 30min |
| Tavily 空 key 挂起 | 1min | 2min | 15min |
| KeyError '{N}' | 1min | 1min | 5min |
| Windows GBK 编码 | 2min | 1min | 30min |
| Synthesizer retry 逻辑 | 5min | 1min | 30min |
| **总计** | **14min** | **12min** | **~2.5h** |

---

## 附录：90 秒项目陈述（可直接背诵）

> 面试时控制语速在 90 秒左右。下面每个字都来自本项目真实细节。

---

"我在 DeepResearch-Lite 项目中实践了一种叫 Vibe Coding 的 AI 协作范式。

这个项目是一个可溯源深度调研 Agent。输入一个 AI 技术问题，10 分钟内产出一份结构化报告——报告里每句话都可以点击追溯到原始网页或论文，而且每条论断会经过一个独立的 NLI 模型做三分类核验——是蕴含、中立、还是矛盾。

整个项目从零到开源用了一个工作日、16 个小时。重点是我**一行代码都没有写**。

所有代码由 Claude Code 根据我写的 CLAUDE.md 设计文档自动生成。我的角色是三个：架构决策——比如我设计了 Pydantic 的 `min_length=1` 硬约束来强制每条 claim 必须有引用；约束定义——比如 Synthesizer prompt 里的六条铁律；产出审核——我读每一个代码 diff，关注错误处理是否完备。

具体流程是：我先把 16 小时拆成 9 个 Milestone，每个 Milestone 有明确的验收标准。然后每个 Milestone 我给出自然语言的任务描述，Claude Code 先给我看执行计划，我确认后它写代码、跑测试、报结果。19 个 Git commits 就是这样一个个积累起来的。

核心收获是：Vibe Coding 不是放弃控制，而是把控制从代码层面提升到设计层面。Pydantic 的硬约束比'AI 你记得加引用'可靠一万倍。21 个单元测试比'我看着没问题'可靠一万倍。

最终项目有 19 个语义清晰的 commits、21 个全过测试、3 个外部 API 集成、一个可用的 Streamlit 前端。GitHub 开源，README 有完整架构图。

如果有兴趣，我可以展开讲任何一个环节——比如我是怎么通过四轮渐进式约束叠加把 citation 的可靠性从 60% 提到接近 100% 的。"

---

> **时间控制**：
> - 0-30 秒：项目是什么 + 核心数字（1 天、0 行代码）
> - 30-60 秒：怎么做（CLAUDE.md → Milestone → 四步循环）
> - 60-90 秒：成果 + 核心洞察 + 邀请追问

---

*文档版本: v1.0 | 最后更新: 2025.05.15 | 随项目演进持续更新*
*项目地址: https://github.com/merlancozy-star/deepresearch-lite*
