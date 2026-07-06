"""CLI entry point for DNA expression importance analysis.
DNA 表情重要性分析的命令行入口。

Usage / 用法:
    mayapy analyze.py --dna path/to/character.dna --lib "C:/Program Files/Epic Games/MetaHumanForMaya"

Environment variable alternative / 环境变量替代方式:
    set MH4M_ROOT=C:\Program Files\Epic Games\MetaHumanForMaya
    mayapy analyze.py --dna path/to/character.dna
"""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Analyze MetaHuman DNA expression curves and rank by importance.",
    )
    parser.add_argument(
        "--dna", required=True,
        help="Path to the input .dna file.",
    )
    parser.add_argument(
        "--lib",
        default=os.environ.get("MH4M_ROOT", ""),
        help="Path to MetaHuman for Maya installation directory "
             "(e.g. 'C:/Program Files/Epic Games/MetaHumanForMaya'). "
             "Can also be set via MH4M_ROOT env var.",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output CSV file path. If omitted, only prints console summary.",
    )
    parser.add_argument(
        "--no-geometry",
        action="store_true",
        help="Skip geometry layer loading for faster analysis (disables delta magnitude scoring).",
    )
    parser.add_argument(
        "--l0-threshold",
        type=float, default=20.0,
        help="Importance score threshold for L0 (full removal) suggestion. Default: 20.0",
    )
    parser.add_argument(
        "--l1-threshold",
        type=float, default=50.0,
        help="Importance score threshold for L1 (simplify PSD) suggestion. Default: 50.0",
    )
    parser.add_argument(
        "--keep", nargs="+", default=None,
        help="Curve name patterns to always keep regardless of score (substring match). "
             "Example: --keep eyeBlinkL eyeBlinkR",
    )

    args = parser.parse_args()

    # Add project src to path
    # 将项目 src 目录添加到路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    sys.path.insert(0, os.path.join(project_root, "src"))

    # Setup MetaHuman for Maya library paths
    # 设置 MetaHuman for Maya 库路径
    if args.lib:
        from dna_optimizer.lib_setup import setup_lib_paths
        try:
            setup_lib_paths(args.lib)
        except RuntimeError as e:
            print(f"Error: {e}")
            sys.exit(1)

    # Verify dna module is available
    # 验证 dna 模块是否可用
    try:
        import dna
    except ImportError:
        print("Error: Cannot import 'dna' module.")
        print("Please specify the MetaHuman for Maya installation path:")
        print('  --lib "C:/Program Files/Epic Games/MetaHumanForMaya"')
        print("  or set MH4M_ROOT environment variable.")
        sys.exit(1)

    from dna_optimizer.analyzer import analyze

    analyze(
        dna_path=args.dna.replace("\\", "/"),
        output_csv=args.output,
        l0_threshold=args.l0_threshold,
        l1_threshold=args.l1_threshold,
        load_geometry=not args.no_geometry,
        keep_list=args.keep,
    )


if __name__ == "__main__":
    main()
