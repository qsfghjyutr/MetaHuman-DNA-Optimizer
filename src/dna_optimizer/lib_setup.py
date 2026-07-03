"""Setup library paths for MetaHuman for Maya plugin (PyDNA 9.4.4 + PyDNACalib2 3.2.0).
设置 MetaHuman for Maya 插件的库路径（PyDNA 9.4.4 + PyDNACalib2 3.2.0）。

The MetaHuman for Maya plugin installs to:
    C:\\Program Files\\Epic Games\\MetaHumanForMaya\\

Its lib/ directory contains versioned, platform-specific packages:
    lib/PyDNA/9.4.4/platform-windows/arch-AMD64/.sanitizers-off/.json-0/python-3.11/lib/
    lib/PyDNACalib2/3.2.0/platform-windows/arch-AMD64/.sanitizers-off/python-3.11/lib/
    lib/PyRDF/6.3.5/platform-windows/arch-AMD64/.sanitizers-off/python-3.11/lib/
    lib/DNACalib2/3.2.0/platform-windows/arch-AMD64/.sanitizers-off/lib/  (DLLs)
"""

import os
import sys


def _find_dirs(root: str, target_name: str):
    """Walk directory tree to find all directories with a given name.
    遍历目录树，查找所有指定名称的目录。

    Unlike glob, this matches directories starting with '.' (e.g. .sanitizers-off).
    与 glob 不同，此函数会匹配以 '.' 开头的目录（如 .sanitizers-off）。
    """
    results = []
    for dirpath, dirnames, _ in os.walk(root):
        if os.path.basename(dirpath) == target_name:
            results.append(dirpath)
    return results


def setup_lib_paths(mh4m_root: str) -> None:
    """Add MetaHuman for Maya library paths to sys.path and DLL search paths.
    将 MetaHuman for Maya 库路径添加到 sys.path 和 DLL 搜索路径。

    Args:
        mh4m_root: Path to the MetaHumanForMaya installation directory,
                   e.g. "C:\\Program Files\\Epic Games\\MetaHumanForMaya".
    """
    lib_root = os.path.join(mh4m_root, "lib")

    if not os.path.isdir(lib_root):
        raise RuntimeError(
            f"MetaHuman for Maya lib directory not found: {lib_root}\n"
            f"Please verify the --lib path points to the MetaHumanForMaya installation."
        )

    py_ver = f"python-{sys.version_info.major}.{sys.version_info.minor}"

    # Discover Python module directories for PyDNA, PyDNACalib2, PyRDF
    # 自动发现 PyDNA、PyDNACalib2、PyRDF 的 Python 模块目录
    # Use os.walk instead of glob because glob's ** skips dot-prefixed directories
    # 使用 os.walk 而非 glob，因为 glob 的 ** 会跳过以 . 开头的目录
    py_module_dirs = []
    for pkg in ("PyDNA", "PyDNACalib2", "PyRDF"):
        pkg_root = os.path.join(lib_root, pkg)
        if not os.path.isdir(pkg_root):
            raise RuntimeError(f"Package directory not found: {pkg_root}")

        # Find directories named "python-X.Y" then look for "lib" inside
        # 查找名为 "python-X.Y" 的目录，然后查找其中的 "lib" 子目录
        matches = _find_dirs(pkg_root, py_ver)
        lib_matches = [os.path.join(m, "lib") for m in matches if os.path.isdir(os.path.join(m, "lib"))]

        if not lib_matches:
            raise RuntimeError(
                f"Cannot find {pkg} for {py_ver} under {pkg_root}.\n"
                f"Available Python versions may not include {py_ver}."
            )
        py_module_dirs.append(lib_matches[0])

    # Discover native DLL directories (DNACalib2 has all needed DLLs)
    # 自动发现原生 DLL 目录（DNACalib2 包含所有需要的 DLL）
    dll_dirs = []
    for pkg in ("DNACalib2",):
        pkg_root = os.path.join(lib_root, pkg)
        if not os.path.isdir(pkg_root):
            continue
        # Find "lib" dirs that are NOT under a "python-*" parent
        # 查找不在 "python-*" 父目录下的 "lib" 目录
        for match in _find_dirs(pkg_root, "lib"):
            parent = os.path.basename(os.path.dirname(match))
            if not parent.startswith("python"):
                dll_dirs.append(match)
                break

    # Add Python module directories to sys.path
    # 将 Python 模块目录添加到 sys.path
    for d in py_module_dirs:
        d_normalized = os.path.normpath(d)
        if d_normalized not in sys.path:
            sys.path.insert(0, d_normalized)

    # Add DLL directories to search path
    # 将 DLL 目录添加到搜索路径
    for d in dll_dirs:
        d_normalized = os.path.normpath(d)
        # For Python 3.8+, use os.add_dll_directory
        # 对于 Python 3.8+，使用 os.add_dll_directory
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(d_normalized)
        # Also add to PATH for older Python / subprocess compatibility
        # 同时添加到 PATH 以兼容旧版 Python 和子进程
        current_path = os.environ.get("PATH", "")
        if d_normalized not in current_path:
            os.environ["PATH"] = d_normalized + os.pathsep + current_path
