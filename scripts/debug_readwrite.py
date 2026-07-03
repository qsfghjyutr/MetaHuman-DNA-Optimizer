"""Debug script: test DNA read/write pipeline step by step.
调试脚本：逐步测试 DNA 读写管线。

Usage:
    mayapy scripts/debug_readwrite.py --dna input.dna --lib "C:/Program Files/Epic Games/MetaHumanForMaya"

This generates multiple output files to isolate where corruption occurs:
    1. test_passthrough.dna   — read → write (no modifications)
    2. test_calibrated.dna    — read → DNACalibDNAReader → write (no commands)
    3. test_remove_1bs.dna    — remove 1 BS channel only
    4. test_joint_zero.dna    — zero 1 joint group column only
"""

import argparse
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(project_root, "src"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dna", required=True)
    parser.add_argument("--lib", default=os.environ.get("MH4M_ROOT", ""))
    args = parser.parse_args()

    if args.lib:
        from dna_optimizer.lib_setup import setup_lib_paths
        setup_lib_paths(args.lib)

    from dna import BinaryStreamReader, BinaryStreamWriter, DataLayer_All, FileStream, Status, UnknownLayerPolicy_Preserve
    from dnacalib2 import DNACalibDNAReader, RemoveBlendShapeCommand

    dna_path = args.dna.replace("\\", "/")
    out_dir = os.path.dirname(dna_path) or "."

    # --- Test 1: Pure passthrough (read → write) ---
    print("=== Test 1: Pure passthrough ===")
    stream = FileStream(dna_path, FileStream.AccessMode_Read, FileStream.OpenMode_Binary)
    reader = BinaryStreamReader(stream, DataLayer_All, UnknownLayerPolicy_Preserve)
    reader.read()
    assert Status.isOk(), f"Read error: {Status.get().message}"

    out1 = os.path.join(out_dir, "test_passthrough.dna")
    out_stream = FileStream(out1, FileStream.AccessMode_Write, FileStream.OpenMode_Binary)
    writer = BinaryStreamWriter(out_stream)
    writer.setFrom(reader)
    writer.write()
    assert Status.isOk(), f"Write error: {Status.get().message}"
    print(f"  Written: {out1}")
    print(f"  Size: {os.path.getsize(out1)} bytes")

    # --- Test 2: Through DNACalibDNAReader (no commands) ---
    print("\n=== Test 2: DNACalibDNAReader passthrough ===")
    stream2 = FileStream(dna_path, FileStream.AccessMode_Read, FileStream.OpenMode_Binary)
    reader2 = BinaryStreamReader(stream2, DataLayer_All)
    reader2.read()
    calibrated = DNACalibDNAReader(reader2)

    out2 = os.path.join(out_dir, "test_calibrated.dna")
    out_stream2 = FileStream(out2, FileStream.AccessMode_Write, FileStream.OpenMode_Binary)
    writer2 = BinaryStreamWriter(out_stream2)
    writer2.setFrom(calibrated)
    writer2.write()
    assert Status.isOk(), f"Write error: {Status.get().message}"
    print(f"  Written: {out2}")
    print(f"  Size: {os.path.getsize(out2)} bytes")

    # --- Test 3: Remove 1 BS channel ---
    print("\n=== Test 3: Remove 1 BS channel ===")
    stream3 = FileStream(dna_path, FileStream.AccessMode_Read, FileStream.OpenMode_Binary)
    reader3 = BinaryStreamReader(stream3, DataLayer_All)
    reader3.read()
    calibrated3 = DNACalibDNAReader(reader3)

    bs_count = calibrated3.getBlendShapeChannelCount()
    print(f"  Original BS count: {bs_count}")
    cmd = RemoveBlendShapeCommand(0)  # remove first BS
    cmd.run(calibrated3)
    print(f"  After removal BS count: {calibrated3.getBlendShapeChannelCount()}")

    out3 = os.path.join(out_dir, "test_remove_1bs.dna")
    out_stream3 = FileStream(out3, FileStream.AccessMode_Write, FileStream.OpenMode_Binary)
    writer3 = BinaryStreamWriter(out_stream3)
    writer3.setFrom(calibrated3)
    writer3.write()
    assert Status.isOk(), f"Write error: {Status.get().message}"
    print(f"  Written: {out3}")
    print(f"  Size: {os.path.getsize(out3)} bytes")

    # --- Test 4: Zero 1 joint group column via writer ---
    print("\n=== Test 4: Zero joint group values via writer ===")
    stream4 = FileStream(dna_path, FileStream.AccessMode_Read, FileStream.OpenMode_Binary)
    reader4 = BinaryStreamReader(stream4, DataLayer_All)
    reader4.read()
    calibrated4 = DNACalibDNAReader(reader4)

    jg_count = calibrated4.getJointGroupCount()
    print(f"  Joint group count: {jg_count}")

    out4 = os.path.join(out_dir, "test_joint_zero.dna")
    out_stream4 = FileStream(out4, FileStream.AccessMode_Write, FileStream.OpenMode_Binary)
    writer4 = BinaryStreamWriter(out_stream4)
    writer4.setFrom(calibrated4)

    # Zero first column of first joint group
    if jg_count > 0:
        values = list(calibrated4.getJointGroupValues(0))
        input_indices = list(calibrated4.getJointGroupInputIndices(0))
        output_indices = list(calibrated4.getJointGroupOutputIndices(0))
        num_cols = len(input_indices)
        num_rows = len(output_indices)
        print(f"  Group 0: {num_rows} rows x {num_cols} cols = {len(values)} values")

        # Zero first column
        for row in range(num_rows):
            idx = row * num_cols + 0
            if idx < len(values):
                values[idx] = 0.0

        writer4.setJointGroupValues(0, values)
        print(f"  Zeroed column 0 of group 0")

    writer4.write()
    assert Status.isOk(), f"Write error: {Status.get().message}"
    print(f"  Written: {out4}")
    print(f"  Size: {os.path.getsize(out4)} bytes")

    # --- Summary ---
    orig_size = os.path.getsize(dna_path)
    print(f"\n=== Summary ===")
    print(f"  Original:      {orig_size:>10} bytes")
    print(f"  Passthrough:   {os.path.getsize(out1):>10} bytes")
    print(f"  Calibrated:    {os.path.getsize(out2):>10} bytes")
    print(f"  Remove 1 BS:   {os.path.getsize(out3):>10} bytes")
    print(f"  Joint zero:    {os.path.getsize(out4):>10} bytes")
    print(f"\nLoad each file in UE to check which step introduces corruption.")


if __name__ == "__main__":
    main()
