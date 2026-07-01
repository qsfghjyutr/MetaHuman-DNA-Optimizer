"""CLI entry point for DNA expression importance analysis.
DNA 表情重要性分析的命令行入口。

Usage / 用法:
    mayapy analyze.py --dna path/to/character.dna --lib path/to/dna_calibration/lib/Maya2023/windows
    python analyze.py --dna path/to/character.dna --lib path/to/dna_calibration/lib/Maya2023/windows

Environment variable alternative / 环境变量替代方式:
    set DNA_CALIB_LIB=path/to/dna_calibration/lib/Maya2023/windows
    python analyze.py --dna path/to/character.dna
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
        default=os.environ.get("DNA_CALIB_LIB", ""),
        help="Path to DNA Calibration lib directory (e.g. lib/Maya2023/windows). "
             "Can also be set via DNA_CALIB_LIB env var.",
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

    args = parser.parse_args()

    # Setup library path
    # 设置库路径
    if args.lib:
        lib_path = args.lib.replace("\\", "/")
        sys.path.insert(0, lib_path)

    # Add project src to path
    # 将项目 src 目录添加到路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    sys.path.insert(0, os.path.join(project_root, "src"))

    # Verify dna module is available
    # 验证 dna 模块是否可用
    try:
        import dna
    except ImportError:
        print("Error: Cannot import 'dna' module.")
        print("Please specify the DNA Calibration lib path:")
        print("  --lib path/to/dna_calibration/lib/Maya2023/windows")
        print("  or set DNA_CALIB_LIB environment variable.")
        sys.exit(1)

    from dna_optimizer.analyzer import analyze

    analyze(
        dna_path=args.dna.replace("\\", "/"),
        output_csv=args.output,
        l0_threshold=args.l0_threshold,
        l1_threshold=args.l1_threshold,
        load_geometry=not args.no_geometry,
    )


if __name__ == "__main__":
    main()
