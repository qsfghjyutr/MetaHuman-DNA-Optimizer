"""Output formatting: CSV export and console summary.
输出格式化：CSV 导出和控制台摘要。"""

import csv
from typing import List, TextIO

from .scoring import RawControlScore


CSV_HEADERS = [
    "rank",
    "raw_control_index",
    "name",
    "importance",
    "geometry_score",
    "joint_score",
    "fanout_score",
    "psd_ratio_score",
    "lod_score",
    "runtime_score",
    "direct_bs_count",
    "psd_bs_count",
    "psd_count",
    "joint_attrs",
    "am_count",
    "suggested_level",
    "filtered",
]


def export_csv(scores: List[RawControlScore], output_path: str) -> None:
    """Write scored results to CSV file.
    将评分结果写入 CSV 文件。"""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)

        for rank, s in enumerate(scores, 1):
            writer.writerow([
                rank,
                s.index,
                s.name,
                f"{s.importance:.1f}",
                f"{s.geometry_score:.1f}",
                f"{s.joint_score:.1f}",
                f"{s.fanout_score:.1f}",
                f"{s.psd_ratio_score:.1f}",
                f"{s.lod_score:.1f}",
                f"{s.runtime_score:.1f}",
                s.direct_bs_count,
                s.psd_bs_count,
                s.psd_count,
                s.joint_attr_count,
                s.am_count,
                s.suggested_level,
                s.filtered,
            ])


def print_summary(scores: List[RawControlScore], total_bs_channels: int = 0) -> None:
    """Print analysis summary to console.
    将分析摘要打印到控制台。"""
    total = len(scores)
    l0_count = sum(1 for s in scores if s.suggested_level == "L0")
    l1_count = sum(1 for s in scores if s.suggested_level == "L1")
    keep_count = sum(1 for s in scores if s.suggested_level == "keep")
    filtered_count = sum(1 for s in scores if s.filtered)

    # Use sets to deduplicate BS channels shared across raw controls
    # 使用集合去重跨原始控制器共享的 BS 通道
    l0_bs_set = set()
    l1_psd_bs_set = set()
    total_joint_attrs = sum(s.joint_attr_count for s in scores)
    l0_joint_attrs = sum(s.joint_attr_count for s in scores if s.suggested_level == "L0")

    for s in scores:
        if s.suggested_level == "L0":
            l0_bs_set.update(s.direct_bs_indices)
            l0_bs_set.update(s.psd_bs_indices)
        elif s.suggested_level == "L1":
            l1_psd_bs_set.update(s.psd_bs_indices)

    print("=" * 70)
    print("MetaHuman DNA Optimizer - Expression Importance Analysis")
    print("=" * 70)
    print()

    # Summary stats
    # 摘要统计
    print(f"Total raw controls analyzed: {total}")
    print()
    print("Pruning level distribution:")
    print(f"  L0 (full removal):     {l0_count:3d} controls")
    print(f"  L1 (simplify PSD):     {l1_count:3d} controls")
    print(f"  keep:                  {keep_count:3d} controls")
    if filtered_count > 0:
        print(f"    (filtered/forced):   {filtered_count:3d} controls")
    print()

    # Estimated savings
    # 预估节省
    l0_bs_count = len(l0_bs_set)
    l1_psd_bs_count = len(l1_psd_bs_set - l0_bs_set)  # exclude already removed by L0
    # 排除已被 L0 移除的部分
    total_removed = l0_bs_count + l1_psd_bs_count
    print("Estimated savings if all suggestions applied:")
    if total_bs_channels > 0:
        print(f"  BS channels removed (L0):       {l0_bs_count:4d} / {total_bs_channels} ({l0_bs_count / total_bs_channels * 100:.1f}%)")
        print(f"  PSD BS channels removed (L1):   {l1_psd_bs_count:4d} / {total_bs_channels} ({l1_psd_bs_count / total_bs_channels * 100:.1f}%)")
        print(f"  Total BS reduction:             {total_removed:4d} / {total_bs_channels} ({total_removed / total_bs_channels * 100:.1f}%)")
    if total_joint_attrs > 0:
        print(f"  Joint matrix entries removed:   {l0_joint_attrs:4d} / {total_joint_attrs} ({l0_joint_attrs / total_joint_attrs * 100:.1f}%)")
    print()

    # Bottom 10 (best pruning candidates)
    # 后 10 名（最佳裁剪候选）
    print("-" * 70)
    print("Bottom 10 (lowest importance - best L0 candidates):")
    print(f"  {'Rank':<5} {'Score':>6} {'Level':<6} {'Name'}")
    print(f"  {'----':<5} {'-----':>6} {'-----':<6} {'----'}")
    for rank, s in enumerate(scores[:10], 1):
        print(f"  {rank:<5} {s.importance:>6.1f} {s.suggested_level:<6} {s.name}")
    print()

    # Top 10 (most important)
    # 前 10 名（最重要）
    print("-" * 70)
    print("Top 10 (highest importance - must keep):")
    print(f"  {'Rank':<5} {'Score':>6} {'Level':<6} {'Name'}")
    print(f"  {'----':<5} {'-----':>6} {'-----':<6} {'----'}")
    top10 = list(reversed(scores[-10:]))
    for rank, s in enumerate(top10, 1):
        print(f"  {rank:<5} {s.importance:>6.1f} {s.suggested_level:<6} {s.name}")
    print()
    print("=" * 70)
