# DeepResearch-Lite — 项目简报（1 天 Sprint 版）

> **用法**：将本文档放置于项目根目录，重命名为 `CLAUDE.md`。每次 Claude Code 进入项目时会自动读取此文档作为上下文。每个时间盒（Time-box）开始前，先让 Claude Code 通读相关章节再写代码。
>
> **本版本对应简历"1 个工作日 ~16 小时 Sprint MVP"叙事**。Day 1 之后的扩展计划在第 10 节"Roadmap"中标注。

---

## 1. 项目定位

**项目名**：DeepResearch-Lite
**副标题**：面向 AI 工程师的可溯源深度调研 Agent MVP（Claude Code Vibe Coding Sprint）

**一句话定义**：输入一个开放式 AI 技术问题，10 分钟内产出一份**每条结论可点击溯源、且经独立 Verifier Agent 三分类校验**的结构化调研报告。

**Day 1 Scope（必须当天交付）**：
- 后端核心链路（CLI 可跑通）
- Citation 强约束 + Verifier 校验
- Web + arXiv 两类 Subagent
- Streamlit 极简前端（输入框 + 报告 + 引用展开）
- 2-3 个 demo case 调通
- GitHub 开源 + README + Demo GIF

**Day 1 不做（写进 README Roadmap）**：
- ❌ Next.js 完整前端
- ❌ MCP Server 封装（只在架构上预留接口）
- ❌ Docker compose
- ❌ GitHub / Blog Subagent
- ❌ 3 分钟 Demo 视频（只录 30 秒 GIF）
- ❌ Verifier 评测脚本（无人工标注集）

---

## 2. 核心差异化

对标 OpenAI Deep Research / GPT-Researcher / OpenDeepResearch，差异化两点（MCP 那条 Day 1 不交付，先不当差异化讲）：

1. **可溯源校验**：竞品给 citation 但不做声明-证据一致性校验。本项目用独立 Verifier 做 NLI 三分类，contradiction 项明确标红
2. **AI 工程师领域 prior**：数据源（arXiv + Tavily）、词表、prompt 模板都向 AI/ML 领域倾斜

---

## 3. 技术架构

### 3.1 数据流（Day 1 实际链路）

```
用户问题
  └─> Orchestrator (LangGraph state graph)
        ├─ Intent Classifier: [exploration | comparison | latest]  # 3 类即可
        ├─ Query Decomposer: 拆解为 3-5 个 sub-questions
        └─ Subagent Router
              │
              ├─> Web Subagent      (Tavily API)        ── asyncio.gather 并发
              └─> arXiv Subagent    (arxiv-py)
                    │
                    └─> 每个 Subagent 内部:
                        search → fetch → chunk → extract → (reflection 暂不做, Day 2+)
                    │
                    └─> 返回 List[Citation]
              │
        Citation Pool (RRF 融合 + 去重)
              │
  └─> Synthesizer
        ├─ Pydantic structured output 强约束: 每条 claim 必须挂 ≥1 个 source_id
        ├─ 无证据 claim → reject + retry (最多 3 次)
        └─ 输出 Markdown 报告 + Claim 列表
              │
  └─> Verifier (独立 LLM 实例)
        ├─ Day 1 简化: 所有 claim 全验 (不做抽样策略)
        ├─ NLI prompt: entailment | contradiction | neutral
        └─ 标记不一致项, 不修改原报告
              │
        └─> Streamlit Web UI (输入 + 报告渲染 + 引用展开)
        # MCP Server 不在 Day 1 交付, 但 graph 节点设计为可独立调用 (为 Day 2+ 暴露 MCP 留口子)
```

### 3.2 Citation 数据结构（核心，必须 Day 1 完成）

```python
# deepresearch/schemas.py
from typing import Literal, List, Tuple
from pydantic import BaseModel, Field

class Citation(BaseModel):
    source_id: str = Field(..., description="规范化来源 ID, e.g. arxiv:2310.06825")
    source_title: str
    source_url: str
    chunk_id: str
    text: str = Field(..., description="原文段落, 用于前端展开显示")
    char_span: Tuple[int, int] = Field(..., description="字符偏移 [start, end)")
    score: float = Field(..., ge=0, le=1)

class Claim(BaseModel):
    text: str
    citations: List[Citation] = Field(..., min_length=1)  # 强约束
    verifier_label: Literal["entailed", "contradicted", "neutral", "unchecked"] = "unchecked"
    verifier_score: float = Field(default=0.0, ge=0, le=1)
    verifier_reasoning: str = ""

class ResearchReport(BaseModel):
    query: str
    intent: Literal["exploration", "comparison", "latest"]
    claims: List[Claim]
    markdown: str
    verifier_summary: dict = Field(default_factory=dict)
    cost_usd: float = 0.0
    elapsed_seconds: float = 0.0
```

### 3.3 Verifier 校验机制（简历核心卖点，必须 Day 1 完成）

**两层校验**：

**Layer 1: 生成时强约束**（Synthesizer 阶段）
- Pydantic `min_length=1` 强制每个 claim 至少 1 个 evidence
- 无证据 claim → ValidationError → 自动 retry（最多 3 次）

**Layer 2: 后置 NLI 校验**（Verifier Agent）

```
你是一个严格的事实校验员。给定 Claim 和 Evidence, 判断 Evidence 是否蕴含 Claim:

Claim: {claim_text}
Evidence:
{evidence_text}

请用 JSON 输出:
{
  "label": "entailed" | "contradicted" | "neutral",
  "score": 0~1,
  "reasoning": "1-2 句话"
}

注意: 只看 Evidence 是否支持 Claim, 不引入外部知识。
```

**Day 1 简化**：所有 claim 全验，不做抽样。理由是 demo case 通常 10-20 条 claim，全验也就 $0.05-0.1 成本，不需要省。

**Verifier Summary**（写到报告底部，截图给 Demo GIF）：

```
校验摘要: 共 15 条 claims
├─ Entailed:     13 (87%)
├─ Neutral:       1 (7%, 已标黄)
└─ Contradicted:  1 (7%, 已标红, 第 8 条)
校验成本: $0.06 | 校验耗时: 23s
```

**与 AgenticRAG 的连接（面试关键叙事）**：

> "AgenticRAG 中 Verifier 在线反馈给 Planner 导致过度纠正，是该项目第 9 轮迭代发现的核心问题。本项目改为后置抽样校验：Verifier 不修改报告、不在生成路径上、不影响生成质量。这是从训练侧反思到推理侧设计的工程成长。"

---

## 4. 目录结构（Day 1 实际）

```
deepresearch-lite/
├── CLAUDE.md                    # 本文档
├── README.md
├── LICENSE                      # MIT
├── pyproject.toml
├── .env.example
├── .gitignore
│
├── deepresearch/
│   ├── __init__.py
│   ├── schemas.py               # Citation, Claim, Report
│   ├── citation.py              # RRF + 去重
│   ├── graph.py                 # LangGraph 编排
│   ├── orchestrator.py          # Intent classifier + decomposer
│   ├── subagents/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── web.py               # Tavily
│   │   └── arxiv.py
│   ├── synthesizer.py
│   ├── verifier.py
│   ├── prompts/
│   │   ├── orchestrator.txt
│   │   ├── synthesizer.txt
│   │   └── verifier.txt
│   └── cli.py                   # python -m deepresearch.cli "your query"
│
├── app.py                       # Streamlit 入口
├── tests/
│   ├── test_schemas.py
│   ├── test_citation_rrf.py
│   └── test_synthesizer_strict.py
└── docs/
    └── architecture.png
```

---

## 5. 16 小时时间盒（核心章节，Day 1 执行剧本）

> **基本节奏**：每 1-2 小时一个里程碑。每个里程碑开始前，给 Claude Code 喂相应的启动 prompt（见第 6 节）。**先让它给计划再写代码**，不要让它一上来就 yolo。

| 时间 | 时长 | 里程碑 | 验收 |
|------|------|--------|------|
| 08:00-09:00 | 1h | **M1 项目脚手架** | git init, .env 就绪, `uv run python -c "import deepresearch"` 不报错 |
| 09:00-10:00 | 1h | **M2 Schemas + Citation 工具** | `pytest tests/test_schemas.py tests/test_citation_rrf.py` 通过 |
| 10:00-12:00 | 2h | **M3 Subagent (Web + arXiv)** | 单独运行 `python -m deepresearch.subagents.web "Mamba"` 能返回 List[Citation] |
| 12:00-13:00 | 1h | 🍱 午饭 + buffer | — |
| 13:00-15:00 | 2h | **M4 Synthesizer** | 给定 mock Citation pool 能输出符合 schema 的 Report，无证据 claim 会触发 retry |
| 15:00-17:00 | 2h | **M5 Verifier** | NLI prompt 在 3 个已知 entailed/contradicted/neutral 样本上正确分类 |
| 17:00-18:00 | 1h | **M6 LangGraph 编排 + CLI** | `python -m deepresearch.cli "vLLM vs SGLang"` 完整跑通，输出 JSON 报告 |
| 18:00-19:00 | 1h | 🍱 晚饭 + buffer | — |
| 19:00-21:00 | 2h | **M7 Streamlit 前端** | `streamlit run app.py`，输入问题 → 看到报告 + 可展开引用 + Verifier 徽章 |
| 21:00-22:00 | 1h | **M8 README + GitHub + Demo GIF** | 公开仓库可访问，README 有架构图和 Quick Start，GIF 录好 |
| 22:00-23:00 | 1h | **M9 整理 + 收尾** | commit 历史合理化，多 demo case 测试 |
| 23:00-24:00 | 1h | 🛡️ Buffer | 处理意外，补测试 |

**纪律红线**（防止超时）：
- 每个里程碑超出 30 分钟就强制截止，把未完成项移到 Day 2
- 不要"再优化一点"，宁可烂尾也要 push GitHub
- Streamlit 前端不追求漂亮，能展示就行
- 4 个 Subagent 砍到 2 个，砍掉的写进 README Roadmap

---

## 6. 每个里程碑的 Claude Code 启动 Prompt

> 直接复制粘贴到 Claude Code 终端。**强约束模式：每个 prompt 都要求"先给计划再实施"**。

### M1 — 项目脚手架（08:00）

```
请通读项目根目录的 CLAUDE.md (本文档)。

任务: M1 项目脚手架

执行步骤:
1. 用 uv init 初始化项目, Python 3.11+
2. 按 CLAUDE.md 第 4 节的目录结构创建空文件 (不要写实现, 只创建 __init__.py 和占位)
3. 写 .env.example: ANTHROPIC_API_KEY, TAVILY_API_KEY
4. 写 .gitignore (标准 Python + .env + .venv)
5. 写最小化 pyproject.toml: pydantic, anthropic, tavily-python, langgraph, arxiv, streamlit, pytest
6. git init, 首次 commit 信息: "feat: scaffold project structure"

验收: uv run python -c "import deepresearch" 不报错

请先给我看你的执行计划, 等我说 GO 再开干。
```

### M2 — Schemas + Citation 工具（09:00）

```
任务: M2 Schemas + Citation 工具

按 CLAUDE.md 第 3.2 节实现:
1. deepresearch/schemas.py: Citation, Claim, ResearchReport (严格按文档)
2. deepresearch/citation.py: 实现
   - rrf_fusion(citations_list: List[List[Citation]], k=60) -> List[Citation]
   - deduplicate(citations: List[Citation]) -> List[Citation]  # 按 source_id + char_span 去重
3. tests/test_schemas.py: 验证 Citation min_length=1 约束, 无 citation 创建 Claim 会抛 ValidationError
4. tests/test_citation_rrf.py: 验证 RRF 融合的数学正确性 (用 mock data)
5. commit: "feat(schemas): add Citation/Claim/Report data structures + RRF"

验收: pytest tests/ 全过

先给执行计划。
```

### M3 — Subagent (Web + arXiv)（10:00）

```
任务: M3 Web + arXiv Subagent

按 CLAUDE.md 第 3.1 节实现:
1. deepresearch/subagents/base.py:
   - Subagent ABC, 定义 async def search(query: str) -> List[Citation]
   - 通用 chunk + char_span 提取工具 (300-500 字符滑动窗口, 重叠 50)
2. deepresearch/subagents/web.py:
   - 用 tavily-python, max_results=5
   - fetch 内容用 requests + beautifulsoup4 提取纯文本
   - 每个结果转成 List[Citation] (source_id 形如 web:<hash>)
3. deepresearch/subagents/arxiv.py:
   - 用 arxiv 库搜 abstract (Day 1 不抓 PDF)
   - source_id 形如 arxiv:<paper_id>
4. 各自加 __main__ 入口: python -m deepresearch.subagents.web "Mamba"
5. 所有外部调用: timeout 30s, 重试 3 次 (用 tenacity 或手写)
6. commit: "feat(subagents): add web (Tavily) and arxiv subagents"

验收: 两个 subagent 命令行各跑通一次, 返回非空 List[Citation]

先给执行计划。注意: tavily 和 arxiv 库的 API 你不熟就先 read docs, 不要瞎写。
```

### M4 — Synthesizer（13:00）

```
任务: M4 Synthesizer

按 CLAUDE.md 第 3.3 节 Layer 1 实现:
1. deepresearch/prompts/synthesizer.txt: 写 prompt, 强调
   - "对每条 claim 必须从 evidence pool 选择至少 1 条作为依据"
   - "用 source_id 和 chunk_id 引用, 不要编造"
   - "如果某个子问题 evidence 不足, 在 claim 中如实声明 '证据不足'"
2. deepresearch/synthesizer.py:
   - synthesize(query, intent, citation_pool: List[Citation]) -> ResearchReport
   - 用 anthropic SDK + tools API 强制 structured output (按 Claim schema)
   - 解析失败 -> retry 最多 3 次, 每次把错误反馈回 prompt
3. tests/test_synthesizer_strict.py:
   - 用 mock Citation pool 测试 happy path
   - mock LLM 返回无 citation 的 claim, 验证触发 retry
4. commit: "feat(synthesizer): structured output with citation enforcement"

验收: pytest tests/test_synthesizer_strict.py 全过

先给执行计划。重点关注 retry 逻辑的健壮性。
```

### M5 — Verifier（15:00）

```
任务: M5 Verifier

按 CLAUDE.md 第 3.3 节 Layer 2 实现:
1. deepresearch/prompts/verifier.txt: NLI prompt (照抄文档里那段)
2. deepresearch/verifier.py:
   - verify_claim(claim: Claim) -> Claim (附加 verifier_label/score/reasoning)
   - verify_report(report: ResearchReport) -> ResearchReport (Day 1 全验)
   - 用独立 LLM 实例 (不复用 synthesizer 的 client)
   - 并发: asyncio.gather, 一次最多 5 个 claim 并发
3. 生成 verifier_summary 写入 report (照抄文档第 3.3 节的格式)
4. 手动测试: 准备 3 个 hardcoded 样本 (entailed/contradicted/neutral) 验证 prompt 正确分类
5. commit: "feat(verifier): NLI-based claim verification"

验收: 3 个 hardcoded 样本分类全对

先给执行计划。
```

### M6 — LangGraph 编排 + CLI（17:00）

```
任务: M6 LangGraph 编排 + CLI

按 CLAUDE.md 第 3.1 节实现:
1. deepresearch/orchestrator.py:
   - intent_classify(query) -> Literal["exploration", "comparison", "latest"]
   - decompose(query, intent) -> List[str] (3-5 个子问题)
2. deepresearch/graph.py:
   - LangGraph StateGraph, 节点: orchestrator -> subagent_dispatch -> synthesizer -> verifier
   - subagent_dispatch 用 asyncio.gather 并发 Web + arXiv
   - State 用 TypedDict
3. deepresearch/cli.py:
   - argparse 解析 query
   - 调用 graph, 把 ResearchReport 输出到 stdout (JSON) 和 reports/<timestamp>.md (Markdown)
4. 跑通 1 个完整 demo case: "vLLM vs SGLang 的架构差异"
5. commit: "feat(graph): wire up LangGraph orchestration with CLI"

验收: python -m deepresearch.cli "vLLM vs SGLang" 完整跑通, 输出报告

先给执行计划。如果时间紧, intent_classify 可以先返回固定值, 后续优化。
```

### M7 — Streamlit 前端（19:00）

```
任务: M7 Streamlit 前端

实现 app.py:
1. 顶部输入框 (st.text_area), 提交按钮
2. 提交后:
   - st.status 显示进度 (Orchestrator → Subagents → Synthesizer → Verifier)
   - 用 st.write_stream 流式展示报告 markdown
3. 报告下方:
   - 引用列表: 每条 Citation 用 st.expander, 标题是 [^source_id] source_title, 展开后显示 text 原文段落和 url
   - Verifier 摘要: 用 st.metric 展示三色统计
4. Claim 内嵌引用: 用 st.markdown 渲染 [^x] 脚注 (Streamlit 原生支持脚注语法)
5. 测试 2 个 demo case:
   - "Mamba 状态空间模型最新进展"
   - "Agent 框架面试常考点"
6. commit: "feat(ui): minimal Streamlit interface with citation expander"

验收: streamlit run app.py, 2 个 case 可以跑出报告 + 可展开引用 + Verifier 徽章

先给执行计划。Streamlit 越简单越好, 不要追求漂亮。
```

### M8 — README + GitHub + Demo GIF（21:00）

```
任务: M8 README + GitHub + Demo GIF

1. 写 README.md (英文为主, 中文 README_zh.md 可选):
   - Hero: 一句话定位 + Demo GIF (占位先放 [demo.gif])
   - Features: 4 条 (Citation 强约束 / Verifier NLI / Multi-Agent 并发 / Streamlit UI)
   - Quick Start: 3 步 (clone, .env, streamlit run)
   - Architecture: 引用 docs/architecture.png
   - Roadmap: 列出 Day 2+ 计划 (Next.js / MCP / Docker / 评测脚本)
   - License: MIT
2. 用 ascii / mermaid 画架构图保存到 docs/architecture.png (mermaid live editor 截图)
3. 录 Demo GIF:
   - 用 LICEcap (Mac/Win 都有) 或 peek (Linux)
   - 录 25-30 秒: 输入问题 → 看到报告 → 点开 1 个引用 → 看 Verifier 摘要
   - 保存为 docs/demo.gif, < 5MB
4. push 到 GitHub 公开仓库
5. final commit: "docs: README + demo GIF + roadmap"

验收: GitHub 仓库可公开访问, README 渲染正常, GIF 自动播放

先给执行计划。这一步是面试官第一眼看到的, 不能糊弄。
```

### M9 — 整理 + 收尾（22:00）

```
任务: M9 整理 + 收尾

1. 整理 commit 历史: 看一下 git log, 把零碎的 fix 提交 squash 到主要 milestone
2. 跑 5 个 demo case 检查稳定性:
   - "Mamba 状态空间模型最新进展" (exploration)
   - "vLLM vs SGLang 架构对比" (comparison)
   - "Claude 4 最新发布信息" (latest)
   - "Agent 主流编排框架对比" (comparison)
   - "RAG 最新评测方法" (exploration)
3. 任何稳定性问题: prompt 调一下, 不重写架构
4. 在 README 添加一个 "Tested Demo Queries" 章节列出这 5 个

验收: 5 个 case 都能输出合理报告 (>= 80% Verifier entailed)

先给执行计划。如果时间不够, 优先保证 README 完整。
```

---

## 7. Vibe Coding 工作流要点（面试时讲）

这一节专门为简历 bullet 1 提供素材。面试官追问"Vibe Coding 到底是什么"时直接拿这些讲：

- **设计文档驱动**：本文档（CLAUDE.md）就是设计契约，先写文档再写代码。每个 milestone 的 prompt 都要求 Claude Code 先回讲计划，确认没误解再实施
- **阶段化任务拆解**：16 小时拆成 9 个 milestone，每个 milestone 1-2 小时，有明确验收标准。这避免了"我让 Claude Code 一晚上写个 Deep Research 给我"这种失败模式
- **记忆库管理**：CLAUDE.md 在项目根目录，每次 Claude Code 启动都读。比对话式 prompt 更稳定
- **组合开源组件**：LangGraph（你 AgenticRAG 经验）、Tavily（现成 API）、Streamlit（一行 import 一个前端）— 不自己造轮子
- **AI 可执行原子任务**：每个 milestone prompt 都强约束 → 测试验收 → commit 信息 → 不留尾巴

---

## 8. 风险与边界

| 风险 | 应对 |
|------|------|
| Tavily / Anthropic API 中途挂了 | tenacity 重试 + buffer 时间用来等恢复 |
| arXiv 抓取被限流 | 加 sleep，Day 1 demo case 都用预取的几篇论文 |
| Synthesizer 总是 retry 不收敛 | 把 retry 上限设 3 次，失败就在报告里标"该子问题证据不足"，不死循环 |
| Verifier 把对的标红误报多 | Day 1 容忍，在 README 写"Verifier 自身 P/R 待 Day 2+ 评测" |
| Streamlit 流式渲染卡顿 | 退化到非流式：等所有结果出来再一次性渲染 |
| 16 小时不够用 | M3/M5/M7 各有 30 分钟弹性，实在不够砍 M9 的多 case 测试 |

**Scope 红线（绝对不能在 Day 1 做）**：
- ❌ 用户系统 / 登录
- ❌ 数据库持久化（暂存到 reports/*.md 文件即可）
- ❌ Docker
- ❌ Next.js
- ❌ MCP Server 真实实现
- ❌ 评测脚本和数字

---

## 9. Day 1 验收清单

收工前自检：

- [ ] GitHub 公开仓库可访问，URL 已记录
- [ ] README 含 Hero、Demo GIF、Features、Quick Start、Architecture、Roadmap、License
- [ ] Demo GIF 在 README 中能自动播放，文件 < 5MB
- [ ] CLAUDE.md 在仓库根目录
- [ ] 至少 5 个有意义的 git commit，commit message 规范（feat/fix/docs）
- [ ] `streamlit run app.py` 一行启动
- [ ] 至少 3 个 demo case 跑通且报告合理
- [ ] Verifier 摘要在每个报告底部正确显示三色统计
- [ ] 引用可点击展开看原文段落
- [ ] 任何外部 API key 都通过 .env 配置，没 hardcode

---

## 10. Roadmap（写在 README 里给面试官看）

> 这一节也是面试卖点。"我清楚 Day 1 做了什么、没做什么、Day 2+ 怎么扩展"— 这显示工程判断力。

**Phase 2（1-2 周）**：
- [ ] GitHub + Blog Subagent
- [ ] Verifier 抽样策略（高置信 30%、低置信 100%）
- [ ] Intent Classifier 加 reproduction 类型
- [ ] Next.js 前端（Citation Popover 跳转高亮、流式可视化树）

**Phase 3（3-4 周）**：
- [ ] MCP Server 封装（5 个 tools 单独暴露）
- [ ] Docker compose 一键启动
- [ ] Verifier 评测脚本（30-50 条人工标注集 + P/R 数字）
- [ ] Prompt caching 优化（4 Subagent system prompt 共享）

**Phase 4（精品化）**：
- [ ] 3 分钟产品 Demo 视频
- [ ] 技术博客 + 投 awesome-mcp-servers / awesome-langchain
- [ ] 长期任务支持（>10 分钟的研究、checkpoint 续跑）

---

## 11. 简历叙事（面试时一字不差讲）

> "AgenticRAG 中我做了金融垂域的深度 RAG（重训练 + GRPO），过程中发现 Verifier 在线反馈给 Planner 会导致过度纠正。基于这个反思，**我在 DeepResearch-Lite 中用一个工作日 Sprint 验证了一个新设计：后置抽样校验 + 不修改报告**，把校验从在线路径解耦出来。这个 Sprint 整个过程用 Claude Code 协作完成，CLAUDE.md 设计文档先行、9 个 milestone 时间盒分阶段交付——这就是我对 Vibe Coding 范式的实际理解。"

这是 90 秒的项目陈述模板。要练到自然。

---

## 12. 当天结束后必做的 3 件事

收完工，不要立刻睡：

1. **在 README 顶部加一个 "Built in 1 day with Claude Code" 徽章** — 这是简历可信度的直接证明，面试官点开 GitHub 第一眼看到
2. **截 5-10 张关键提交的 commit 历史截图** — 面试时如果被追问 Vibe Coding 工作流，这是最强证据。`git log --oneline --graph` 截图保存
3. **把 Claude Code 的对话历史导出存档**（Claude Code 有 `/export` 命令）— 万一被深问"你用 Claude Code 都聊了些什么"，能展示真实过程
