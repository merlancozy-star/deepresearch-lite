"""Streamlit UI for DeepResearch-Lite — 可溯源深度调研报告.

核心特性：
- 章节导航侧边栏（从 Markdown 标题自动生成）
- 正文引用可点击 → 跳转到参考文献卡片
- 参考文献卡片：标题可点击跳转原文、源文摘录
- 调研方法展示 + 流程耗时分解
- 论断按章节分组 + 核验徽章
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(
    page_title="DeepResearch-Lite 深度调研",
    page_icon="🔍",
    layout="wide",
)

# ── Helpers ──────────────────────────────────────────────────────────────

def _parse_toc(markdown: str) -> list[tuple[str, str]]:
    """Extract ## headings from markdown for sidebar TOC."""
    headings = []
    for line in markdown.split("\n"):
        m = re.match(r"^##\s+(.+)$", line)
        if m:
            title = m.group(1).strip()
            # Remove emoji prefixes like "## 📋 摘要" → "摘要"
            title_clean = re.sub(r"^[\U0001F300-\U0001FFFF]\s*", "", title)
            if not title_clean:
                title_clean = title
            anchor = title_clean.replace(" ", "-").lower()
            headings.append((title_clean, anchor))
    return headings


def _make_citations_clickable(markdown: str, citation_map: dict[str, dict]) -> str:
    """Replace [^source_id] with clickable HTML superscript badges."""
    def _replacer(m: re.Match) -> str:
        sid = m.group(1)
        info = citation_map.get(sid, {})
        title = info.get("title", sid)
        url = info.get("url", "")
        tooltip = f"{title}"[:80]
        if url:
            return f'<sup><a href="{url}" target="_blank" title="{tooltip}" style="text-decoration:none;color:#1f77b4;font-weight:bold;font-size:0.8em;">[↗{sid}]</a></sup>'
        return f'<sup style="color:#888;font-size:0.8em;" title="{tooltip}">[{sid}]</sup>'

    return re.sub(r"\[\^([^\]]+)\]", _replacer, markdown)


def _build_citation_info_map(report) -> dict[str, dict]:
    """Build source_id → {title, url, excerpt} for all claims' citations."""
    info = {}
    for claim in report.claims:
        for cit in claim.citations:
            if cit.source_id not in info:
                info[cit.source_id] = {
                    "title": cit.source_title,
                    "url": cit.source_url,
                    "excerpt": cit.text[:200],
                }
    # Also add from references list
    for ref in report.references:
        rid = ref.get("ref_id", "")
        if rid and rid not in info:
            info[rid] = {
                "title": ref.get("title", ""),
                "url": ref.get("url", ""),
                "excerpt": ref.get("excerpt", ""),
            }
    return info


def _section_verifier_stats(report) -> dict[str, dict]:
    """Compute per-section verifier stats."""
    sections: dict[str, dict] = {}
    for claim in report.claims:
        sec = claim.section or "其他"
        if sec not in sections:
            sections[sec] = {"total": 0, "entailed": 0, "neutral": 0, "contradicted": 0}
        sections[sec]["total"] += 1
        label = claim.verifier_label
        if label in sections[sec]:
            sections[sec][label] += 1
    return sections


# ── UI ────────────────────────────────────────────────────────────────────

st.title("🔍 DeepResearch-Lite")
st.caption("可溯源深度调研 Agent —— 每一条结论都有据可查，引用可点击，经独立核验")

# Input
query = st.text_area(
    "研究问题",
    placeholder="例如：vLLM 与 SGLang 架构对比、Mamba 状态空间模型最新进展、RAG 评测方法现状...",
    height=80,
)

col1, col2, _ = st.columns([1, 1, 3])
with col1:
    submit = st.button("🔬 开始调研", type="primary", use_container_width=True)
with col2:
    skip_verify = st.checkbox("跳过核验", value=False)

# ── Run Pipeline ──────────────────────────────────────────────────────────

if submit and query.strip():
    from deepresearch.graph import run_pipeline

    try:
        with st.status("正在执行深度调研...", expanded=True) as status:
            st.write("🔍 分类意图 & 拆解查询...")
            st.write("🌐 并发搜索 Web + 学术...")
            st.write("📝 撰写结构化报告（每条引用可溯源）...")
            if not skip_verify:
                st.write("✅ NLI 核验每条论断...")
            report = asyncio.run(run_pipeline(query.strip()))
            status.update(label="调研完成！", state="complete", expanded=False)

        # ── Sidebar ───────────────────────────────────────────────────
        with st.sidebar:
            st.subheader("📑 目录")
            toc = _parse_toc(report.markdown)
            if toc:
                for title, _ in toc:
                    st.markdown(f"- {title}")
            else:
                st.caption("（无章节标题）")

            st.divider()
            st.subheader("⏱ 流程耗时")
            ps = report.pipeline_stats
            if ps:
                for stage, label in [
                    ("classify", "意图分类"),
                    ("search", "搜索阶段"),
                    ("fuse", "RRF 融合"),
                    ("reflect", "反思补充搜索"),
                    ("synthesize", "报告撰写"),
                    ("verify", "NLI 核验"),
                ]:
                    val = ps.get(stage, 0)
                    if val:
                        st.caption(f"{label}: {val:.1f}s")
                st.caption(f"**总计: {ps.get('total', report.elapsed_seconds):.1f}s**")
                if ps.get("sources_found"):
                    st.caption(f"原始片段: {ps['sources_found']} → 融合后: {ps.get('citations_after_fusion', 0)}")

        # ── Verifier Summary ──────────────────────────────────────────
        vs = report.verifier_summary
        if vs and vs.get("total", 0) > 0:
            st.subheader("📊 核验摘要")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("论断总数", vs.get("total", 0))
            m2.metric("✅ 蕴含", f"{vs.get('entailed', 0)} ({vs.get('entailed_pct', 0)}%)")
            m3.metric("🟡 中立", f"{vs.get('neutral', 0)} ({vs.get('neutral_pct', 0)}%)")
            contra = vs.get("contradicted", 0)
            m4.metric("🔴 矛盾", f"{contra} ({vs.get('contradicted_pct', 0)}%)",
                      delta="⚠ 需复核" if contra > 0 else None)
            m5.metric("💰 成本", f"${report.cost_usd + vs.get('cost_usd', 0):.4f}")

            # Per-section verifier
            section_stats = _section_verifier_stats(report)
            if len(section_stats) > 1:
                with st.expander("📊 按章节核验详情"):
                    cols = st.columns(len(section_stats))
                    for i, (sec, ss) in enumerate(section_stats.items()):
                        with cols[i]:
                            st.markdown(f"**{sec[:20]}**")
                            ent_pct = round(ss["entailed"] / ss["total"] * 100) if ss["total"] else 0
                            st.caption(f"✅ {ss['entailed']}/{ss['total']} ({ent_pct}%)")

        st.divider()

        # ── Methodology ───────────────────────────────────────────────
        if report.methodology:
            with st.expander("🔬 调研方法", expanded=False):
                st.markdown(report.methodology)
                if report.sub_questions:
                    st.markdown("**检索子问题：**")
                    for sq in report.sub_questions:
                        st.markdown(f"- {sq}")

        # ── Main Report ───────────────────────────────────────────────
        st.subheader("📄 调研报告")

        cit_info = _build_citation_info_map(report)
        processed_md = _make_citations_clickable(report.markdown, cit_info)
        st.markdown(processed_md, unsafe_allow_html=True)

        # ── References ────────────────────────────────────────────────
        st.divider()
        st.subheader(f"📚 参考文献（共 {len(cit_info)} 条来源）")

        if report.references:
            for ref in report.references:
                rid = ref.get("ref_id", "")
                title = ref.get("title", "未知来源")
                url = ref.get("url", "")
                excerpt = ref.get("excerpt", "")
                with st.expander(f"📎 [{rid}] {title[:100]}", expanded=False):
                    if url:
                        st.markdown(f"**链接：** [{url}]({url})")
                    if excerpt:
                        st.markdown(f"> {excerpt}")
        else:
            # Fallback: build reference cards from citation_map
            for sid, info in cit_info.items():
                title = info.get("title", sid)
                url = info.get("url", "")
                excerpt = info.get("excerpt", "")
                with st.expander(f"📎 [{sid}] {title[:100]}", expanded=False):
                    if url:
                        st.markdown(f"**链接：** [{url}]({url})")
                    if excerpt:
                        st.markdown(f"> {excerpt}")

        # ── Claims Detail ─────────────────────────────────────────────
        st.divider()
        st.subheader(f"📎 论断详情（共 {len(report.claims)} 条，按章节分组）")

        # Group claims by section
        claims_by_section: dict[str, list] = {}
        for c in report.claims:
            sec = c.section or "其他"
            if sec not in claims_by_section:
                claims_by_section[sec] = []
            claims_by_section[sec].append(c)

        for sec, claims in claims_by_section.items():
            st.markdown(f"### {sec}（{len(claims)} 条）")
            for i, claim in enumerate(claims):
                label = claim.verifier_label
                label_cn = {"entailed": "蕴含", "contradicted": "矛盾", "neutral": "中立", "unchecked": "未核验"}.get(label, label)
                badge = {"entailed": "✅", "contradicted": "🔴", "neutral": "🟡", "unchecked": "⬜"}.get(label, "⬜")

                title = f"#{i+1} {badge} `{label_cn}` — {claim.text[:100]}..."
                if label != "entailed":
                    title += f" ({claim.verifier_reasoning[:60]}...)"

                with st.expander(title, expanded=(label == "contradicted")):
                    st.markdown(f"**论断全文：** {claim.text}")
                    if claim.verifier_reasoning:
                        st.caption(f"核验意见：{claim.verifier_reasoning}")
                    st.markdown("**引用来源：**")
                    for cit in claim.citations:
                        st.markdown(
                            f"> 🔗 **[{cit.source_title}]({cit.source_url})**  \n"
                            f"> *{cit.text[:250]}{'...' if len(cit.text) > 250 else ''}*"
                        )

        # ── Footer ────────────────────────────────────────────────────
        st.divider()
        st.caption(
            f"意图：`{report.intent}` | "
            f"总耗时：{report.elapsed_seconds:.1f}s | "
            f"LLM 成本：${report.cost_usd:.4f}"
        )

    except Exception as e:
        st.error(f"调研流程失败：{e}")
        st.exception(e)

elif submit and not query.strip():
    st.warning("请输入研究问题。")
