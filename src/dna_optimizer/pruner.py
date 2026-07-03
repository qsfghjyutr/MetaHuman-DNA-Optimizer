"""Pruning execution engine: collect safe removal indices and apply DNACalib commands.
裁剪执行引擎：收集可安全移除的索引并应用 DNACalib 命令。"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .dna_io import DNAData
from .dependency_graph import DependencyGraph
from .scoring import RawControlScore


@dataclass
class PruneResult:
    """Summary of what was pruned.
    裁剪结果摘要。"""

    # L0 results
    # L0 结果
    l0_bs_removed: List[int] = field(default_factory=list)
    l0_am_removed: List[int] = field(default_factory=list)
    l0_joint_entries_zeroed: int = 0

    # L1 results
    # L1 结果
    l1_bs_removed: List[int] = field(default_factory=list)

    # L2 results
    # L2 结果
    l2_threshold: float = 0.0

    output_path: str = ""


def _collect_l0_safe_indices(
    scores: List[RawControlScore],
    graph: DependencyGraph,
) -> Tuple[Set[int], Set[int], Set[int]]:
    """Collect BS/AM indices and joint input indices that are safe to remove/zero for L0.
    收集 L0 可安全移除的 BS/AM 索引和可置零的 joint input 索引。

    A PSD is "pure L0" only when ALL its input raw controls are L0.
    Shared PSDs (involving any non-L0 control) are left untouched.
    仅当 PSD 的所有输入 raw control 都是 L0 时，该 PSD 才算"纯 L0"。
    涉及任何非 L0 控制器的共享 PSD 不会被触碰。

    Returns:
        (safe_bs, safe_am, zero_joint_inputs)
    """
    l0_raw_indices = {s.index for s in scores if s.suggested_level == "L0"}

    # Find "pure L0" PSDs: all input raw controls are L0
    # 找出"纯 L0" PSD：所有输入 raw control 都是 L0
    pure_l0_psds = set()
    for psd_idx, raw_inputs in graph.psd_to_raw_inputs.items():
        if raw_inputs and all(r in l0_raw_indices for r in raw_inputs):
            pure_l0_psds.add(psd_idx)

    # BS channels safe to remove: driven by L0 raw controls or pure L0 PSDs
    # 可安全移除的 BS：由 L0 raw control 直接驱动或由纯 L0 PSD 驱动
    safe_bs = set()
    for rc_idx in l0_raw_indices:
        safe_bs.update(graph.input_to_bs.get(rc_idx, []))
    for psd_idx in pure_l0_psds:
        safe_bs.update(graph.input_to_bs.get(psd_idx, []))

    # AM indices safe to remove
    # 可安全移除的 AM 索引
    safe_am = set()
    for rc_idx in l0_raw_indices:
        safe_am.update(graph.input_to_am.get(rc_idx, set()))
    for psd_idx in pure_l0_psds:
        safe_am.update(graph.input_to_am.get(psd_idx, set()))

    # Joint input indices to zero out
    # 需要置零的 joint input 索引
    zero_joint_inputs = l0_raw_indices | pure_l0_psds

    return safe_bs, safe_am, zero_joint_inputs


def _collect_l1_bs_indices(
    scores: List[RawControlScore],
    graph: DependencyGraph,
    already_removed_bs: Set[int],
) -> Set[int]:
    """Collect PSD-driven BS channels for L1 and L0 controls (remove PSD corrections).
    收集 L1 和 L0 控制器的 PSD 驱动 BS（移除 PSD 修正 BS）。

    L0 controls are included because L0 should be a superset of L1.
    L0 的 "纯 L0" 安全检查仅覆盖所有输入均为 L0 的 PSD，
    共享 PSD（部分输入为 keep）的修正 BS 仍需通过此处移除。
    L0 控制器被包含在内，因为 L0 应是 L1 的超集。
    """
    l1_raw_indices = {s.index for s in scores
                      if s.suggested_level in ("L0", "L1")}
    l1_psd_bs = set()

    for rc_idx in l1_raw_indices:
        for psd_idx in graph.raw_to_psds.get(rc_idx, []):
            l1_psd_bs.update(graph.input_to_bs.get(psd_idx, []))

    # Exclude BS already removed by L0
    # 排除已被 L0 移除的 BS
    l1_psd_bs -= already_removed_bs
    return l1_psd_bs


def _compute_zeroed_joint_values(
    data: DNAData, zero_inputs: Set[int]
) -> Tuple[Dict[int, List[float]], int]:
    """Compute modified joint group values with specified columns zeroed out.
    计算将指定列置零后的 joint group values。

    DNACalibDNAReader does not expose setJointGroupValues in Python bindings,
    so we compute the modified values here and apply them via BinaryStreamWriter.
    DNACalibDNAReader 的 Python 绑定不暴露 setJointGroupValues，
    因此在此计算修改后的值，通过 BinaryStreamWriter 应用。

    Args:
        data: Original DNA data (for joint group structure).
        zero_inputs: Set of unified input indices to zero out.

    Returns:
        (modified_groups, total_zeroed) where modified_groups maps
        group_index -> modified values list.
    """
    modified_groups: Dict[int, List[float]] = {}
    total_zeroed = 0

    for g_idx, group in enumerate(data.joint_groups):
        input_indices = group["input_indices"]
        output_indices = group["output_indices"]
        values = list(group["values"])

        if not input_indices or not output_indices:
            continue

        num_cols = len(input_indices)
        num_rows = len(output_indices)

        # Find which columns correspond to zero_inputs
        # 找出需要置零的列
        cols_to_zero = []
        for col, inp_idx in enumerate(input_indices):
            if inp_idx in zero_inputs:
                cols_to_zero.append(col)

        if not cols_to_zero:
            continue

        # Zero out the values in those columns
        # 将这些列的值置零
        zeroed_in_group = 0
        for row in range(num_rows):
            for col in cols_to_zero:
                val_idx = row * num_cols + col
                if val_idx < len(values) and values[val_idx] != 0.0:
                    values[val_idx] = 0.0
                    zeroed_in_group += 1

        if zeroed_in_group > 0:
            modified_groups[g_idx] = values
            total_zeroed += zeroed_in_group

    return modified_groups, total_zeroed


def execute_pruning(
    dna_path: str,
    output_path: str,
    scores: List[RawControlScore],
    graph: DependencyGraph,
    data: DNAData,
    levels: Optional[List[str]] = None,
    l2_threshold: float = 0.001,
) -> PruneResult:
    """Execute pruning on a DNA file based on analysis scores.
    根据分析评分对 DNA 文件执行裁剪。

    Execution order (designed to avoid index remapping issues):
    执行顺序（设计上避免索引重映射问题）：
        1. Zero joint matrix columns (does not affect other indices)
           置零 joint matrix 列（不影响其他索引）
        2. Remove BS channels (L0 + L1 merged into one command)
           移除 BS 通道（L0 + L1 合并为一次命令）
        3. Remove animated maps (L0)
           移除动画贴图（L0）
        4. Prune small BS deltas (L2)
           裁剪微小 BS 位移（L2）
        5. Write output DNA
           写出 DNA

    Args:
        dna_path: Path to the input .dna file.
        output_path: Path to write the pruned .dna file.
        scores: Importance scores from analyze().
        graph: Dependency graph from analyze().
        data: DNA data from analyze().
        levels: Which pruning levels to apply. Default: ["L0", "L1", "L2"].
        l2_threshold: Delta magnitude threshold for L2 pruning.

    Returns:
        PruneResult with details of what was pruned.
    """
    from dna import (
        BinaryStreamReader,
        BinaryStreamWriter,
        DataLayer_All,
        FileStream,
        Status,
        UnknownLayerPolicy_Preserve,
    )
    from dnacalib2 import (
        CommandSequence,
        DNACalibDNAReader,
        PruneBlendShapeTargetsCommand,
        RemoveAnimatedMapCommand,
        RemoveBlendShapeCommand,
    )

    if levels is None:
        levels = ["L0", "L1", "L2"]

    result = PruneResult(output_path=output_path, l2_threshold=l2_threshold)

    # --- Collect indices to process ---
    # --- 收集待处理的索引 ---

    l0_bs = set()
    l0_am = set()
    zero_joint_inputs = set()
    l1_bs = set()

    if "L0" in levels:
        l0_bs, l0_am, zero_joint_inputs = _collect_l0_safe_indices(scores, graph)
        print(f"L0: {len(l0_bs)} BS channels, {len(l0_am)} animated maps, "
              f"{len(zero_joint_inputs)} joint input columns to process")

    if "L1" in levels:
        l1_bs = _collect_l1_bs_indices(scores, graph, already_removed_bs=l0_bs)
        print(f"L1: {len(l1_bs)} PSD correction BS channels to remove")

    # Merge L0 + L1 BS for a single removal command
    # 合并 L0 + L1 BS 为一次移除命令
    all_bs_to_remove = sorted(l0_bs | l1_bs)
    all_am_to_remove = sorted(l0_am)

    print(f"Total BS to remove: {len(all_bs_to_remove)} / {data.bs_channel_count}")
    print(f"Total AM to remove: {len(all_am_to_remove)} / {data.animated_map_count}")
    print()

    # --- Load DNA and create mutable copy ---
    # --- 加载 DNA 并创建可修改副本 ---

    print("Loading DNA for pruning...")
    stream = FileStream(dna_path, FileStream.AccessMode_Read, FileStream.OpenMode_Binary)
    reader = BinaryStreamReader(stream, DataLayer_All, UnknownLayerPolicy_Preserve)
    reader.read()

    if not Status.isOk():
        status = Status.get()
        raise RuntimeError(f"Error loading DNA: {status.message}")

    calibrated = DNACalibDNAReader(reader)

    # --- Step 1: Compute zeroed joint matrix values ---
    # --- 步骤 1：计算置零后的 joint matrix 值 ---

    modified_joint_groups: Dict[int, List[float]] = {}
    if zero_joint_inputs:
        print("Computing zeroed joint matrix columns for L0 controls...")
        modified_joint_groups, result.l0_joint_entries_zeroed = _compute_zeroed_joint_values(
            data, zero_joint_inputs
        )
        print(f"  Will zero {result.l0_joint_entries_zeroed} joint matrix entries "
              f"across {len(modified_joint_groups)} joint groups")

    # --- Step 2: Remove BS channels (L0 + L1 merged) ---
    # --- 步骤 2：移除 BS 通道（L0 + L1 合并）---

    commands = CommandSequence()

    if all_bs_to_remove:
        print(f"Removing {len(all_bs_to_remove)} BS channels...")
        remove_bs_cmd = RemoveBlendShapeCommand(all_bs_to_remove)
        commands.add(remove_bs_cmd)

    # --- Step 3: Remove animated maps ---
    # --- 步骤 3：移除动画贴图 ---

    if all_am_to_remove:
        print(f"Removing {len(all_am_to_remove)} animated maps...")
        remove_am_cmd = RemoveAnimatedMapCommand(all_am_to_remove)
        commands.add(remove_am_cmd)

    # --- Step 4: Prune small BS deltas (L2) ---
    # --- 步骤 4：裁剪微小 BS 位移（L2）---

    if "L2" in levels:
        print(f"Pruning BS deltas below threshold {l2_threshold}...")
        prune_cmd = PruneBlendShapeTargetsCommand(l2_threshold)
        commands.add(prune_cmd)

    # Execute all commands
    # 执行所有命令
    commands.run(calibrated)

    if not Status.isOk():
        status = Status.get()
        raise RuntimeError(f"Error during pruning: {status.message}")

    # --- Step 5: Write output DNA ---
    # --- 步骤 5：写出 DNA ---

    print(f"Writing pruned DNA to: {output_path}")
    out_stream = FileStream(output_path, FileStream.AccessMode_Write, FileStream.OpenMode_Binary)
    writer = BinaryStreamWriter(out_stream)
    writer.setFrom(calibrated)

    # Apply joint matrix zeroing via writer (DNACalibDNAReader doesn't expose setters in Python)
    # 通过 writer 应用 joint matrix 置零（DNACalibDNAReader 在 Python 中不暴露 setter）
    for g_idx, values in modified_joint_groups.items():
        writer.setJointGroupValues(g_idx, values)

    writer.write()

    if not Status.isOk():
        status = Status.get()
        raise RuntimeError(f"Error writing DNA: {status.message}")

    # Record results
    # 记录结果
    result.l0_bs_removed = sorted(l0_bs)
    result.l0_am_removed = all_am_to_remove
    result.l1_bs_removed = sorted(l1_bs)

    _print_pruning_summary(result, data)
    return result


def _print_pruning_summary(result: PruneResult, data: DNAData) -> None:
    """Print a summary of the pruning results.
    打印裁剪结果摘要。"""
    print()
    print("=" * 70)
    print("Pruning Summary")
    print("=" * 70)
    print()

    total_bs_removed = len(result.l0_bs_removed) + len(result.l1_bs_removed)
    print(f"L0 - Full removal:")
    print(f"  BS channels removed:       {len(result.l0_bs_removed)}")
    print(f"  Animated maps removed:     {len(result.l0_am_removed)}")
    print(f"  Joint matrix entries zeroed: {result.l0_joint_entries_zeroed}")
    print()
    print(f"L1 - PSD correction removal:")
    print(f"  BS channels removed:       {len(result.l1_bs_removed)}")
    print()
    print(f"L2 - Delta pruning:")
    print(f"  Threshold: {result.l2_threshold}")
    print()
    print(f"Total BS channels removed: {total_bs_removed} / {data.bs_channel_count} "
          f"({total_bs_removed / data.bs_channel_count * 100:.1f}%)" if data.bs_channel_count > 0 else "")
    print(f"Total AM removed: {len(result.l0_am_removed)} / {data.animated_map_count} "
          f"({len(result.l0_am_removed) / data.animated_map_count * 100:.1f}%)" if data.animated_map_count > 0 else "")
    print()
    print(f"Output: {result.output_path}")
    print("=" * 70)
