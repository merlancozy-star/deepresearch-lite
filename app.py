"""Streamlit UI for DeepResearch-Lite — 中文界面.

单页应用：输入问题 → 查看报告 + 可展开引用 + 核验徽章
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import streamlit as st

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(
    page_title="DeepResearch-Lite 深度调研",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 DeepResearch-Lite")
st.caption("可溯源深度调研 Agent —— 每一条论断都有据可查，经独立核验")

# --- 输入区 ---
query = st.text_area(
    "研究问题",
    placeholder="例如：vLLM 与 SGLang 架构对比、Mamba 状态空间模型最新进展、Agent 框架面试考点...",
    height=80,
)

col1, col2, col3 = st.columns([1, 1, 3])
with col1:
    submit = st.button("🔬 开始调研", type="primary", use_container_width=True)
with col2:
    skip_verify = st.checkbox("跳过核验", value=False)

# --- 输出区 ---
if submit and query.strip():
    from deepresearch.graph import run_pipeline

    try:
        with st.status("正在执行深度调研流程...", expanded=True) as status:
            st.write("🔍 正在分类意图 & 拆解查询...")
            st.write("🌐 正在并发搜索 Web + arXiv...")
            st.write("📝 正在撰写报告（含引用约束）...")
            if not skip_verify:
                st.write("✅ 正在核验论断（NLI 三分类）...")

            report = asyncio.run(run_pipeline(query.strip()))

            status.update(label="调研完成！", state="complete", expanded=False)

        st.divider()

        # 核验摘要
        vs = report.verifier_summary
        if vs:
            st.subheader("📊 核验摘要")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("论断总数", vs.get("total", 0))
            m2.metric("✅ 蕴含", f"{vs.get('entailed', 0)} ({vs.get('entailed_pct', 0)}%)")
            m3.metric("🟡 中立", f"{vs.get('neutral', 0)} ({vs.get('neutral_pct', 0)}%)")
            contra = vs.get('contradicted', 0)
            m4.metric("🔴 矛盾", f"{contra} ({vs.get('contradicted_pct', 0)}%)",
                      delta="⚠" if contra > 0 else None)
            st.caption(f"核验成本：${vs.get('cost_usd', 0):.4f} | "
                       f"流程耗时：{report.elapsed_seconds:.1f}s")

        st.divider()

        # 主报告
        st.subheader("📄 调研报告")
        st.markdown(report.markdown)

        # 论断与引用
        st.divider()
        st.subheader(f"📎 论断与引用（共 {len(report.claims)} 条）")

        for i, claim in enumerate(report.claims):
            label = claim.verifier_label
            label_cn = {
                "entailed": "蕴含",
                "contradicted": "矛盾",
                "neutral": "中立",
                "unchecked": "未核验",
            }.get(label, label)

            badge = {
                "entailed": "✅",
                "contradicted": "🔴",
                "neutral": "🟡",
                "unchecked": "⬜",
            }.get(label, "⬜")

            with st.expander(
                f"论断 #{i+1} — {badge} `{label_cn}` {claim.verifier_reasoning[:80]}..."
                if label != "entailed"
                else f"论断 #{i+1} — ✅ `{label_cn}`"
            ):
                st.markdown(f"**论断：** {claim.text}")

                if claim.verifier_reasoning:
                    st.caption(f"核验意见：{claim.verifier_reasoning}")

                st.markdown("**来源：**")
                for j, cit in enumerate(claim.citations):
                    st.markdown(
                        f"> **[^{cit.source_id}]** [{cit.source_title}]({cit.source_url})  \n"
                        f"> {cit.text[:300]}{'...' if len(cit.text) > 300 else ''}"
                    )

        # 报告元信息
        st.divider()
        st.caption(
            f"意图：`{report.intent}` | "
            f"流程耗时：{report.elapsed_seconds:.1f}s | "
            f"成本：${report.cost_usd:.4f}"
        )

    except Exception as e:
        st.error(f"调研流程失败：{e}")
        st.exception(e)

elif submit and not query.strip():
    st.warning("请输入研究问题。")
