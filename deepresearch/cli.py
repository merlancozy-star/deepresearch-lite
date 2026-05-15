"""CLI entry point for DeepResearch-Lite.

Usage:
    python -m deepresearch.cli "你的研究问题"
    python -m deepresearch.cli "vLLM 与 SGLang 架构对比"
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Fix Windows GBK encoding for emoji/Chinese output
if sys.platform == "win32":
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)  # type: ignore

load_dotenv()


def main():
    parser = argparse.ArgumentParser(
        description="DeepResearch-Lite：可溯源深度调研 Agent",
    )
    parser.add_argument(
        "query",
        nargs="+",
        help="研究问题（例如：'vLLM 与 SGLang 架构对比'）",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="输出 JSON 文件路径（默认：reports/<时间戳>.json）",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="跳过核验步骤",
    )
    args = parser.parse_args()

    query = " ".join(args.query)
    print(f"\n{'='*60}")
    print(f"  DeepResearch-Lite 深度调研")
    print(f"  查询：{query}")
    print(f"{'='*60}\n")

    # Late import so argparse is fast
    from deepresearch.graph import run_pipeline

    async def _run():
        print("[1/4] 正在分类意图 & 拆解查询...")
        report = await run_pipeline(query)
        return report

    report = asyncio.run(_run())

    # Output
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = args.output or str(reports_dir / f"{timestamp}.json")
    md_path = str(reports_dir / f"{timestamp}.md")

    # Write JSON
    report_json = report.model_dump_json(indent=2)
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(report_json)

    # Write Markdown
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report.markdown)
        f.write("\n\n---\n\n## 核验摘要\n\n")
        vs = report.verifier_summary
        f.write(f"```\n核验：共 {vs.get('total', 0)} 条论断\n")
        f.write(f"├─ 蕴含 (Entailed)：     {vs.get('entailed', 0)} ({vs.get('entailed_pct', 0)}%)\n")
        f.write(f"├─ 中立 (Neutral)：      {vs.get('neutral', 0)} ({vs.get('neutral_pct', 0)}%)\n")
        f.write(f"└─ 矛盾 (Contradicted)：{vs.get('contradicted', 0)} ({vs.get('contradicted_pct', 0)}%)\n")
        f.write(f"核验成本：${vs.get('cost_usd', 0):.4f}\n```\n")

    # Print summary
    print(f"\n{'='*60}")
    print(f"  报告生成完毕")
    print(f"{'='*60}")
    print(f"  意图：    {report.intent}")
    print(f"  论断数：  {len(report.claims)}")
    vs = report.verifier_summary
    print(f"  蕴含：    {vs.get('entailed', 0)}/{vs.get('total', 0)} ({vs.get('entailed_pct', 0)}%)")
    if vs.get('contradicted', 0) > 0:
        print(f"  [!] 矛盾：{vs.get('contradicted', 0)}")
    print(f"  耗时：    {report.elapsed_seconds:.1f}s")
    print(f"  JSON：    {json_path}")
    print(f"  Markdown：{md_path}")
    print()

    # Print markdown to stdout too (truncated)
    print(report.markdown[:2000])
    if len(report.markdown) > 2000:
        print("\n... （内容过长，完整报告请查看 Markdown 文件）")


if __name__ == "__main__":
    main()
