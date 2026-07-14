# MetaHuman DNA Optimizer

A tool for analyzing and optimizing MetaHuman DNA expression curves. It ranks each expression by importance and suggests tiered pruning strategies to reduce file size, GPU morph target cost, and CPU joint evaluation overhead.

MetaHuman DNA 表情曲线分析与优化工具。对每条表情按重要性排序，并建议分层裁剪策略，以减少文件大小、GPU morph target 开销和 CPU 关节计算负担。

## Demo / 效果展示

The demo below uses an official MetaHuman **LOD4** character. Five heads are shown side by side: the leftmost is the untouched original DNA (**zero pruning**), and the remaining four apply progressively more aggressive pruning from left to right. The **Loss** value floating above each head quantifies how far that pruned rig has drifted from the original — the higher the Loss, the more aggressive the pruning.

下面的演示使用 MetaHuman 官方 **LOD4** 级别角色。视频中并排展示了五个头部：最左边是未经改动的原始 DNA（**零裁剪**），其余四个从左到右应用逐步增强的裁剪。每个头部上方悬浮的 **Loss** 值量化了裁剪后的模型绑定相对原始模型绑定的偏离程度 —— Loss 越高，裁剪越激进。

[![MetaHuman DNA Optimizer — Pruning Demo](https://img.youtube.com/vi/Qq--bZNZmT8/maxresdefault.jpg)](https://www.youtube.com/watch?v=Qq--bZNZmT8)

> ▶️ Click the thumbnail to watch on YouTube / 点击缩略图在 YouTube 观看

## How It Works / 工作原理

MetaHuman DNA files encode a complex evaluation pipeline:

MetaHuman DNA 文件编码了一条复杂的求值管线：

```
GUI Controls (168)
  → Raw Controls (258)  ──→ Joint Matrix (CPU bottleneck, ~85-90% of RigLogic cost)
                             关节矩阵（CPU 瓶颈，占 RigLogic 约 85-90% 开销）
    → PSD (476)         ──→ Joint Matrix (same)
                             关节矩阵（同上）
      → BS Channels (687) ──→ GPU Morph Target deformation
                               GPU Morph Target 变形
      → Animated Maps (82) ──→ Material parameters
                                材质参数
```

This tool analyzes the dependency graph and scores each raw control (expression) across 6 dimensions to determine its importance, then suggests one of three pruning levels:

本工具分析依赖图，对每个原始控制器（表情）进行 6 个维度的评分以确定其重要性，然后建议以下三种裁剪级别之一：

| Level / 级别 | Action / 操作 | CPU Benefit / CPU 收益 | GPU Benefit / GPU 收益 | File Size / 文件大小 |
|-------|--------|------------|------------|-----------|
| **L0** | Remove entire expression (raw control + PSD + BS + AM + joint matrix columns) / 删除整条表情（原始控制器 + PSD + BS + AM + 关节矩阵列） | High / 高 | High / 高 | High / 高 |
| **L1** | Keep base BS, remove PSD correction BS / 保留基础 BS，删除 PSD 修正 BS | None / 无 | Medium / 中 | Medium / 中 |
| **L2** | Prune small deltas from remaining BS / 裁剪剩余 BS 中的微小位移 | None / 无 | Low / 低 | Medium / 中 |

## Scoring Dimensions / 评分维度

| Dimension / 维度 | Weight / 权重 | Description / 描述 |
|-----------|--------|-------------|
| Geometry Impact / 几何影响 | 0.35 | Total vertex displacement magnitude across all downstream BS / 所有下游 BS 的总顶点位移幅度 |
| Joint Drive / 关节驱动 | 0.25 | Non-zero entries in joint matrix for this control / 该控制器在关节矩阵中的非零条目数 |
| Downstream Fanout / 下游扇出 | 0.15 | Number of PSDs + BS channels + Animated Maps driven / 驱动的 PSD + BS 通道 + 动画贴图数量 |
| PSD Correction Ratio / PSD 修正占比 | 0.10 | Proportion of BS driven through PSD corrections / 通过 PSD 修正驱动的 BS 占比 |
| LOD Coverage / LOD 覆盖 | 0.05 | Number of LODs containing downstream BS/AM / 包含下游 BS/AM 的 LOD 层级数 |
| Runtime Cost / 运行时开销 | 0.10 | Estimated per-frame computation cost / 预估的每帧计算开销 |

## Keep List (Filter) / 保留列表（过滤器）

Some expression curves are visually critical but may receive low importance scores (e.g. eye blink controls). The **Keep List** mechanism lets you protect these curves from pruning — they still participate in scoring and ranking, but are always classified as `keep` regardless of threshold settings.

某些表情曲线在视觉上非常关键，但计算出的重要性分数可能较低（例如眨眼控制器）。**保留列表**机制允许你保护这些曲线不被裁剪 — 它们仍然参与评分和排序，但无论阈值如何设置，都始终被分类为 `keep`。

**Matching rule / 匹配规则**: Substring match — entering `eyeBlinkL` will match `CTRL_expressions.eyeBlinkL`.

**匹配规则**：子串匹配 — 输入 `eyeBlinkL` 即可匹配 `CTRL_expressions.eyeBlinkL`。

```powershell
# CLI: protect eye blink curves from pruning / CLI：保护眨眼曲线不被裁剪
& "path/to/mayapy.exe" scripts/prune.py `
  --dna character.dna -o pruned.dna `
  --keep eyeBlinkL eyeBlinkR browRaise eyeLook
```

In the GUI, the Keep List section provides an input field to add/remove patterns. Default entries: `eyeBlinkL`, `eyeBlinkR`, `browRaise`, `eyeLook`. Filtered rows are highlighted in blue.

在 GUI 中，保留列表区域提供输入框来添加/移除匹配模式。默认条目：`eyeBlinkL`、`eyeBlinkR`、`browRaise`、`eyeLook`。被过滤保护的行以蓝色高亮显示。

## Project Structure / 项目结构

```
MetaHuman-DNA-Optimizer/
├── README.md
├── LICENSE
├── requirements.txt
│
├── src/
│   └── dna_optimizer/
│       ├── __init__.py            # Package init / 包初始化
│       ├── lib_setup.py           # MetaHuman for Maya lib path auto-discovery
│       │                          # MetaHuman for Maya 库路径自动发现
│       ├── dna_io.py              # DNA file reading via BinaryStreamReader API
│       │                          # 通过 BinaryStreamReader API 读取 DNA 文件
│       ├── dependency_graph.py    # Dependency graph: raw control → PSD → BS/AM/Joint
│       │                          # 依赖图：原始控制器 → PSD → BS/AM/关节
│       ├── scoring.py             # 6-dimension scoring engine + keep list filter
│       │                          # 6 维评分引擎 + 保留列表过滤
│       ├── analyzer.py            # Orchestrator: load → graph → score → report → prune
│       │                          # 编排器：加载 → 建图 → 评分 → 报告 → 裁剪
│       ├── pruner.py              # Pruning execution engine (L0/L1/L2)
│       │                          # 裁剪执行引擎（L0/L1/L2）
│       └── reporter.py            # CSV export and console summary output
│                                  # CSV 导出和控制台摘要输出
│
├── scripts/
│   ├── analyze.py                 # Analysis CLI entry point / 分析命令行入口
│   ├── prune.py                   # Pruning CLI entry point / 裁剪命令行入口
│   ├── gui.py                     # PySide6 GUI application / PySide6 图形界面应用
│   └── debug_readwrite.py         # DNA read/write pipeline diagnostic / DNA 读写管线诊断
│
├── tests/
└── docs/
```

## Prerequisites / 前置要求

- **Maya 2022–2025** with `mayapy` (Maya's Python interpreter)
- Maya 2022–2025 及其 `mayapy`（Maya 的 Python 解释器）
- **[MetaHuman for Maya](https://www.fab.com/) plugin** (provides PyDNA 9.4.4 + PyDNACalib2 3.2.0, supports DNA v2.1–v2.5)
- [MetaHuman for Maya](https://www.fab.com/) 插件（提供 PyDNA 9.4.4 + PyDNACalib2 3.2.0，支持 DNA v2.1–v2.5）
- **PySide6** (only required for GUI mode; bundled with Maya 2025's `mayapy`) / **PySide6**（仅 GUI 模式需要；Maya 2025 的 `mayapy` 已内置）

The plugin is available on [Fab](https://www.fab.com/) (search "MetaHuman for Maya") and installs to:

插件可在 [Fab](https://www.fab.com/) 上获取（搜索"MetaHuman for Maya"），默认安装位置为：

```
C:\Program Files\Epic Games\MetaHumanForMaya\
```

**Note / 注意**: `mayapy` is not typically in the system PATH. Use the full path to your Maya installation's `mayapy.exe`:

**注意**：`mayapy` 通常不在系统 PATH 中，需要使用 Maya 安装目录下的完整路径：

```powershell
# Windows PowerShell example / Windows PowerShell 示例
& "D:\Program Files (x86)\Autodesk\Maya2025\bin\mayapy.exe" scripts/analyze.py --dna character.dna

# Or add Maya's bin directory to your PATH once / 或者将 Maya 的 bin 目录添加到 PATH
$env:PATH = "D:\Program Files (x86)\Autodesk\Maya2025\bin;" + $env:PATH
```

## Usage / 使用方式

> All commands below use **PowerShell** syntax: `&` call operator, `` ` `` line continuation, `$env:` for environment variables.
>
> 以下所有命令均使用 **PowerShell** 语法：`&` 调用运算符、`` ` `` 续行符、`$env:` 设置环境变量。

### Basic Analysis / 基本分析

```powershell
& "path/to/mayapy.exe" scripts/analyze.py `
  --dna path/to/character.dna `
  --lib "C:/Program Files/Epic Games/MetaHumanForMaya" `
  --output report.csv
```

### Pruning Execution / 裁剪执行

Analyze the DNA file and generate a pruned output. The **source file is never modified** — a new pruned DNA file is written to `--output`.

分析 DNA 文件并生成裁剪后的输出。**源文件不会被修改** — 裁剪后的 DNA 写入 `--output` 指定的新文件。

```powershell
# Full pruning (L0 + L1 + L2) / 完整裁剪
& "path/to/mayapy.exe" scripts/prune.py `
  --dna path/to/character.dna `
  --lib "C:/Program Files/Epic Games/MetaHumanForMaya" `
  --output pruned.dna

# L0 only (most aggressive, for testing) / 仅 L0（最激进，用于测试）
& "path/to/mayapy.exe" scripts/prune.py `
  --dna path/to/character.dna `
  --lib "C:/Program Files/Epic Games/MetaHumanForMaya" `
  --output pruned_l0.dna `
  --levels L0

# Custom thresholds / 自定义阈值
& "path/to/mayapy.exe" scripts/prune.py `
  --dna path/to/character.dna `
  --lib "C:/Program Files/Epic Games/MetaHumanForMaya" `
  --output pruned.dna `
  --l0-threshold 15.0 --l1-threshold 40.0 --l2-delta 0.005
```

### Analysis Options / 分析参数

| Option / 参数 | Description / 描述 |
|--------|-------------|
| `--dna` | Path to input .dna file (required) / 输入 .dna 文件路径（必填） |
| `--lib` | Path to MetaHuman for Maya installation directory. Can also use `MH4M_ROOT` env var / MetaHuman for Maya 安装目录路径，也可通过 `MH4M_ROOT` 环境变量设置 |
| `--output`, `-o` | Output CSV file path. If omitted, only prints console summary / 输出 CSV 文件路径，省略则仅打印控制台摘要 |
| `--no-geometry` | Skip geometry layer loading for faster analysis (disables delta magnitude scoring) / 跳过几何层加载以加快分析（禁用位移幅度评分） |
| `--l0-threshold` | Importance score threshold for L0 suggestion (default: 20.0) / L0 建议的重要性分数阈值（默认：20.0） |
| `--l1-threshold` | Importance score threshold for L1 suggestion (default: 50.0) / L1 建议的重要性分数阈值（默认：50.0） |
| `--keep` | Curve name patterns to always keep (substring match, multiple values) / 始终保留的曲线名称模式（子串匹配，可指定多个） |

### Pruning Options / 裁剪参数

| Option / 参数 | Description / 描述 |
|--------|-------------|
| `--dna` | Path to input .dna file (required) / 输入 .dna 文件路径（必填） |
| `--output`, `-o` | Path to write pruned .dna file (required) / 输出裁剪后的 .dna 文件路径（必填） |
| `--lib` | Path to MetaHuman for Maya installation directory / MetaHuman for Maya 安装目录路径 |
| `--levels` | Pruning levels to apply: `L0` `L1` `L2` (default: all three) / 要应用的裁剪级别（默认：全部三级） |
| `--l0-threshold` | Importance score threshold for L0 (default: 20.0) / L0 重要性分数阈值 |
| `--l1-threshold` | Importance score threshold for L1 (default: 50.0) / L1 重要性分数阈值 |
| `--l2-delta` | Delta magnitude threshold for L2 pruning (default: 0.001) / L2 位移幅度阈值 |
| `--no-geometry` | Skip geometry layer loading / 跳过几何层加载 |
| `--keep` | Curve name patterns to always keep (substring match, multiple values) / 始终保留的曲线名称模式（子串匹配，可指定多个） |
| `--report` | Optional: write analysis report CSV / 可选：输出分析报告 CSV |

### Environment Variable / 环境变量

```powershell
# Set once, use everywhere / 设置一次，到处使用
$env:MH4M_ROOT = "C:\Program Files\Epic Games\MetaHumanForMaya"
& "path/to/mayapy.exe" scripts/prune.py --dna character.dna -o pruned.dna
```

### GUI Mode / 图形界面模式

A PySide6-based GUI for interactive analysis and pruning (requires PySide6).

基于 PySide6 的图形界面，支持交互式分析与裁剪（需要 PySide6）。

```powershell
& "path/to/mayapy.exe" scripts/gui.py
```

Features / 功能特性：

- Sortable table with all raw controls, color-coded by pruning level (red=L0, yellow=L1, green=keep, blue=filtered)
- 可排序的表格，按裁剪级别着色显示所有原始控制器（红色=L0，黄色=L1，绿色=keep，蓝色=被保留列表保护）
- Per-row level editing via dropdown (L0/L1/keep) and checkbox selection
- 每行可通过下拉菜单（L0/L1/keep）和复选框单独调整裁剪级别
- Real-time L0/L1 threshold sliders that reclassify all rows instantly
- 实时 L0/L1 阈值滑块，即时重新分类所有行
- Live pruning impact estimates (BS/AM/Joint removal percentages) that update as you adjust selections
- 实时裁剪影响预估（BS/AM/Joint 移除百分比），随选择调整实时更新
- Keep List with default entries (`eyeBlinkL`, `eyeBlinkR`, `browRaise`, `eyeLook`) — protected curves are always kept and highlighted in blue
- 保留列表，预设 `eyeBlinkL`、`eyeBlinkR`、`browRaise`、`eyeLook` — 被保护的曲线始终保留并以蓝色高亮
- Name search and level filter
- 名称搜索和级别筛选
- Background thread execution for analysis and pruning (non-blocking UI)
- 分析和裁剪在后台线程执行（界面不卡顿）

### Debug Read/Write Pipeline / 调试读写管线

A diagnostic script that tests the DNA read/write pipeline step by step, generating multiple output files to isolate where corruption might occur. Useful for verifying DNACalib operations independently.

逐步测试 DNA 读写管线的诊断脚本，生成多个输出文件以定位可能发生损坏的环节。适用于独立验证 DNACalib 操作。

```powershell
& "path/to/mayapy.exe" scripts/debug_readwrite.py `
  --dna path/to/character.dna `
  --lib "C:/Program Files/Epic Games/MetaHumanForMaya"
```

The script produces 4 test files in the same directory as the input DNA:

脚本在输入 DNA 同目录下生成 4 个测试文件：

| Output File / 输出文件 | Test / 测试内容 |
|--------|-------------|
| `test_passthrough.dna` | Pure read → write with no modifications / 纯读写，无任何修改 |
| `test_calibrated.dna` | Read → DNACalibDNAReader → write (no commands) / 经过 DNACalibDNAReader，不执行命令 |
| `test_remove_1bs.dna` | Remove 1 BS channel only / 仅移除 1 个 BS 通道 |
| `test_joint_zero.dna` | Zero 1 joint group column only / 仅置零 1 个关节组列 |

## Example Output / 示例输出

### Analysis / 分析

```
======================================================================
MetaHuman DNA Optimizer - Expression Importance Analysis
======================================================================

Total raw controls analyzed: 258

Pruning level distribution:
  L0 (full removal):     172 controls
  L1 (simplify PSD):      79 controls
  keep:                    7 controls

Estimated savings if all suggestions applied:
  BS channels removed (L0):        138 / 687 (20.1%)
  PSD BS channels removed (L1):    445 / 687 (64.8%)
  Total BS reduction:              583 / 687 (84.9%)
  Joint matrix entries removed:   89061 / 2026261 (4.4%)

----------------------------------------------------------------------
Bottom 10 (lowest importance - best L0 candidates):
  Rank   Score Level  Name
  1        0.0 L0     CTRL_expressions.teethUpU
  2        0.0 L0     CTRL_expressions.teethDownU
  ...

Top 10 (highest importance - must keep):
  1       99.9 keep   CTRL_expressions.jawOpen
  2       62.2 keep   CTRL_expressions.mouthStretchR
  ...
======================================================================
```

### Pruning / 裁剪

```
======================================================================
Pruning Summary
======================================================================

L0 - Full removal:
  BS channels removed:       138
  Animated maps removed:      12
  Joint matrix entries zeroed: 89061

L1 - PSD correction removal:
  BS channels removed:       445

L2 - Delta pruning:
  Threshold: 0.001

Total BS channels removed: 583 / 687 (84.9%)
Total AM removed: 12 / 82 (14.6%)

Output: pruned.dna
======================================================================
```

## CSV Output Format / CSV 输出格式

The output CSV contains one row per raw control, sorted by importance (ascending):

输出 CSV 每行对应一个原始控制器，按重要性升序排列：

| Column / 列 | Description / 描述 |
|--------|-------------|
| `rank` | Rank (1 = least important) / 排名（1 = 最不重要） |
| `raw_control_index` | Index in DNA file / DNA 文件中的索引 |
| `name` | Control name (e.g. `CTRL_expressions.jawOpen`) / 控制器名称 |
| `importance` | Composite importance score (0-100) / 综合重要性评分（0-100） |
| `geometry_score` | Geometry impact dimension (0-100) / 几何影响维度（0-100） |
| `joint_score` | Joint drive dimension (0-100) / 关节驱动维度（0-100） |
| `fanout_score` | Downstream fanout dimension (0-100) / 下游扇出维度（0-100） |
| `psd_ratio_score` | PSD correction ratio dimension (0-100) / PSD 修正占比维度（0-100） |
| `lod_score` | LOD coverage dimension (0-100) / LOD 覆盖维度（0-100） |
| `runtime_score` | Runtime cost dimension (0-100) / 运行时开销维度（0-100） |
| `direct_bs_count` | BS channels directly driven / 直接驱动的 BS 通道数 |
| `psd_bs_count` | BS channels driven via PSD corrections / 通过 PSD 修正驱动的 BS 通道数 |
| `psd_count` | Number of PSD expressions involved / 涉及的 PSD 表达式数量 |
| `joint_attrs` | Joint matrix non-zero entries / 关节矩阵非零条目数 |
| `am_count` | Animated maps driven / 驱动的动画贴图数 |
| `suggested_level` | Suggested pruning level: `L0`, `L1`, or `keep` / 建议裁剪级别 |
| `filtered` | Whether protected by keep list (`True`/`False`) / 是否被保留列表保护 |

## Roadmap / 路线图

- [x] **Expression importance analysis / 表情重要性分析**: 6-dimension scoring with dependency graph / 基于依赖图的 6 维评分
- [x] **L0 pruning execution / L0 裁剪执行**: Remove downstream BS + AM, zero joint matrix columns / 移除下游 BS + AM，置零关节矩阵列
- [x] **L1 pruning execution / L1 裁剪执行**: Remove PSD correction BS via `RemoveBlendShapeCommand` / 使用 `RemoveBlendShapeCommand` 移除 PSD 修正 BS
- [x] **L2 pruning execution / L2 裁剪执行**: Apply `PruneBlendShapeTargetsCommand` with configurable threshold / 使用可配置阈值应用 `PruneBlendShapeTargetsCommand`
- [x] **GUI application / 图形界面应用**: Interactive PySide6 GUI with sortable table, threshold sliders, per-row level editing, and real-time pruning estimates / 交互式 PySide6 图形界面，支持可排序表格、阈值滑块、逐行级别编辑和实时裁剪预估
- [x] **Keep List filter / 保留列表过滤**: Protect visually critical curves from pruning regardless of score (CLI `--keep` + GUI) / 保护视觉关键曲线不被裁剪，无论评分高低（CLI `--keep` + GUI）

## License / 许可证

MIT License - see [LICENSE](LICENSE) for details.

MIT 许可证 - 详见 [LICENSE](LICENSE)。
