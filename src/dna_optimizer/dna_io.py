"""DNA file reading and data extraction using BinaryStreamReader API.
使用 BinaryStreamReader API 读取 DNA 文件并提取数据。"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class DNAData:
    """All extracted data from a DNA file needed for importance analysis.
    从 DNA 文件中提取的所有重要性分析所需数据。"""

    # Counts
    # 计数
    raw_control_count: int = 0
    gui_control_count: int = 0
    psd_count: int = 0
    bs_channel_count: int = 0
    animated_map_count: int = 0
    mesh_count: int = 0
    joint_count: int = 0
    lod_count: int = 0

    # Names
    # 名称
    raw_control_names: List[str] = field(default_factory=list)
    gui_control_names: List[str] = field(default_factory=list)
    bs_channel_names: List[str] = field(default_factory=list)
    animated_map_names: List[str] = field(default_factory=list)
    joint_names: List[str] = field(default_factory=list)
    mesh_names: List[str] = field(default_factory=list)

    # PSD sparse matrix: rows=PSD output indices, columns=raw control input indices
    # PSD 稀疏矩阵：行=PSD 输出索引，列=原始控制器输入索引
    psd_rows: List[int] = field(default_factory=list)
    psd_columns: List[int] = field(default_factory=list)
    psd_values: List[float] = field(default_factory=list)

    # Blend shape channel behavior mapping
    # 混合变形通道行为映射
    bs_lods: List[int] = field(default_factory=list)
    bs_input_indices: List[int] = field(default_factory=list)
    bs_output_indices: List[int] = field(default_factory=list)

    # Animated map conditional table
    # 动画贴图条件表
    am_lods: List[int] = field(default_factory=list)
    am_input_indices: List[int] = field(default_factory=list)
    am_output_indices: List[int] = field(default_factory=list)

    # Joint groups: list of (input_indices, output_indices, values) per group
    # 关节组：每组包含 (输入索引, 输出索引, 值) 的列表
    joint_group_count: int = 0
    joint_groups: List[Dict] = field(default_factory=list)

    # LOD mappings
    # LOD 映射
    bs_indices_per_lod: List[List[int]] = field(default_factory=list)
    am_indices_per_lod: List[List[int]] = field(default_factory=list)

    # Geometry: per BS channel -> (total_vertex_count, total_delta_magnitude)
    # 几何数据：每个 BS 通道 -> (总顶点数, 总位移幅度)
    bs_geometry: Dict[int, Tuple[int, float]] = field(default_factory=dict)


def load_dna(dna_path: str, load_geometry: bool = True) -> DNAData:
    """Load a DNA file and extract all data needed for importance analysis.
    加载 DNA 文件并提取重要性分析所需的所有数据。

    Args:
        dna_path: Path to the .dna file.
                  DNA 文件路径。
        load_geometry: If True, also load geometry layer for delta magnitude
                       calculation. Set False for faster loading when only
                       behavior data is needed.
                       若为 True，同时加载几何层以计算位移幅度。
                       仅需行为数据时设为 False 可加快加载速度。
    """
    from dna import (
        BinaryStreamReader,
        DataLayer_All,
        DataLayer_Behavior,
        FileStream,
        Status,
    )

    layer = DataLayer_All if load_geometry else DataLayer_Behavior
    stream = FileStream(dna_path, FileStream.AccessMode_Read, FileStream.OpenMode_Binary)
    reader = BinaryStreamReader(stream, layer)
    reader.read()

    if not Status.isOk():
        status = Status.get()
        raise RuntimeError(f"Error loading DNA: {status.message}")

    data = DNAData()

    # Counts
    # 计数
    data.raw_control_count = reader.getRawControlCount()
    data.gui_control_count = reader.getGUIControlCount()
    data.psd_count = reader.getPSDCount()
    data.bs_channel_count = reader.getBlendShapeChannelCount()
    data.animated_map_count = reader.getAnimatedMapCount()
    data.mesh_count = reader.getMeshCount()
    data.joint_count = reader.getJointCount()
    data.lod_count = reader.getLODCount()

    # Names
    # 名称
    data.raw_control_names = [reader.getRawControlName(i) for i in range(data.raw_control_count)]
    data.gui_control_names = [reader.getGUIControlName(i) for i in range(data.gui_control_count)]
    data.bs_channel_names = [reader.getBlendShapeChannelName(i) for i in range(data.bs_channel_count)]
    data.animated_map_names = [reader.getAnimatedMapName(i) for i in range(data.animated_map_count)]
    data.joint_names = [reader.getJointName(i) for i in range(data.joint_count)]
    data.mesh_names = [reader.getMeshName(i) for i in range(data.mesh_count)]

    # PSD matrix
    # PSD 矩阵
    data.psd_rows = list(reader.getPSDRowIndices())
    data.psd_columns = list(reader.getPSDColumnIndices())
    data.psd_values = list(reader.getPSDValues())

    # Blend shape channel behavior
    # 混合变形通道行为
    data.bs_lods = list(reader.getBlendShapeChannelLODs())
    data.bs_input_indices = list(reader.getBlendShapeChannelInputIndices())
    data.bs_output_indices = list(reader.getBlendShapeChannelOutputIndices())

    # Animated map conditionals
    # 动画贴图条件
    data.am_lods = list(reader.getAnimatedMapLODs())
    data.am_input_indices = list(reader.getAnimatedMapInputIndices())
    data.am_output_indices = list(reader.getAnimatedMapOutputIndices())

    # Joint groups
    # 关节组
    data.joint_group_count = reader.getJointGroupCount()
    for g in range(data.joint_group_count):
        data.joint_groups.append({
            "input_indices": list(reader.getJointGroupInputIndices(g)),
            "output_indices": list(reader.getJointGroupOutputIndices(g)),
            "values": list(reader.getJointGroupValues(g)),
            "lods": list(reader.getJointGroupLODs(g)),
            "joint_indices": list(reader.getJointGroupJointIndices(g)),
        })

    # LOD mappings
    # LOD 映射
    for lod in range(data.lod_count):
        data.bs_indices_per_lod.append(list(reader.getBlendShapeChannelIndicesForLOD(lod)))
        data.am_indices_per_lod.append(list(reader.getAnimatedMapIndicesForLOD(lod)))

    # Geometry: compute per-BS-channel delta magnitude
    # 几何数据：计算每个 BS 通道的位移幅度
    if load_geometry:
        _extract_geometry(reader, data)

    return data


def _extract_geometry(reader, data: DNAData) -> None:
    """Extract blend shape target geometry metrics per BS channel.
    提取每个 BS 通道的混合变形目标几何指标。"""
    for mesh_idx in range(data.mesh_count):
        bs_target_count = reader.getBlendShapeTargetCount(mesh_idx)
        total_verts = reader.getVertexPositionCount(mesh_idx)

        for bt in range(bs_target_count):
            channel_idx = reader.getBlendShapeChannelIndex(mesh_idx, bt)
            delta_count = reader.getBlendShapeTargetDeltaCount(mesh_idx, bt)

            if delta_count == 0:
                continue

            # Use batch API for performance
            # 使用批量 API 以提升性能
            dxs = list(reader.getBlendShapeTargetDeltaXs(mesh_idx, bt))
            dys = list(reader.getBlendShapeTargetDeltaYs(mesh_idx, bt))
            dzs = list(reader.getBlendShapeTargetDeltaZs(mesh_idx, bt))

            magnitude = sum(
                math.sqrt(dx * dx + dy * dy + dz * dz)
                for dx, dy, dz in zip(dxs, dys, dzs)
            )

            prev_count, prev_mag = data.bs_geometry.get(channel_idx, (0, 0.0))
            data.bs_geometry[channel_idx] = (prev_count + delta_count, prev_mag + magnitude)
