#!/usr/bin/env python3
"""Create the Valio Aimo test-kitchen QR code without third-party packages."""

from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path


TARGET_URL = "https://valio-front-door.onrender.com/#try"
VERSION = 3
SIZE = 17 + 4 * VERSION
DATA_CODEWORDS = 44
ECC_CODEWORDS = 26
ALIGNMENT_POSITIONS = (6, 22)


def append_bits(bits: list[int], value: int, count: int) -> None:
    for shift in range(count - 1, -1, -1):
        bits.append((value >> shift) & 1)


def data_codewords(text: str) -> list[int]:
    payload = text.encode("utf-8")
    bits: list[int] = []
    append_bits(bits, 0b0100, 4)  # byte mode
    append_bits(bits, len(payload), 8)
    for byte in payload:
        append_bits(bits, byte, 8)

    bits.extend([0] * min(4, DATA_CODEWORDS * 8 - len(bits)))
    bits.extend([0] * ((-len(bits)) % 8))
    words = [sum(bits[i + shift] << (7 - shift) for shift in range(8)) for i in range(0, len(bits), 8)]
    pad = (0xEC, 0x11)
    while len(words) < DATA_CODEWORDS:
        words.append(pad[(len(words) - len(bits) // 8) % 2])
    if len(words) != DATA_CODEWORDS:
        raise ValueError("URL does not fit in the fixed QR version")
    return words


def gf_multiply(left: int, right: int) -> int:
    if left == 0 or right == 0:
        return 0
    value = 0
    for _ in range(8):
        if right & 1:
            value ^= left
        high = left & 0x80
        left = (left << 1) & 0xFF
        if high:
            left ^= 0x1D
        right >>= 1
    return value


def reed_solomon(data: list[int], count: int) -> list[int]:
    generator = [1]
    root = 1
    for _ in range(count):
        next_generator = [0] * (len(generator) + 1)
        for index, coefficient in enumerate(generator):
            next_generator[index] ^= coefficient
            next_generator[index + 1] ^= gf_multiply(coefficient, root)
        generator = next_generator
        root = gf_multiply(root, 2)

    remainder = [0] * count
    for byte in data:
        factor = byte ^ remainder[0]
        remainder = remainder[1:] + [0]
        for index in range(count):
            remainder[index] ^= gf_multiply(generator[index + 1], factor)
    return remainder


def format_bits(mask: int) -> int:
    value = mask  # error-correction level M has format bits 00
    remainder = value << 10
    while remainder.bit_length() >= 11:
        remainder ^= 0x537 << (remainder.bit_length() - 11)
    return ((value << 10) | remainder) ^ 0x5412


def set_module(matrix: list[list[bool | None]], x: int, y: int, value: bool) -> None:
    if 0 <= x < SIZE and 0 <= y < SIZE:
        matrix[y][x] = value


def draw_finder(matrix: list[list[bool | None]], x0: int, y0: int) -> None:
    for dy in range(-1, 8):
        for dx in range(-1, 8):
            dark = (0 <= dx <= 6 and 0 <= dy <= 6 and (dx in (0, 6) or dy in (0, 6))) or (
                2 <= dx <= 4 and 2 <= dy <= 4
            )
            set_module(matrix, x0 + dx, y0 + dy, dark)


def draw_alignment(matrix: list[list[bool | None]], cx: int, cy: int) -> None:
    if matrix[cy][cx] is not None:
        return
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            set_module(matrix, cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)


def write_format(matrix: list[list[bool | None]], mask: int) -> None:
    bits = format_bits(mask)
    for index in range(15):
        value = bool((bits >> index) & 1)
        if index < 6:
            set_module(matrix, 8, index, value)
        elif index < 8:
            set_module(matrix, 8, index + 1, value)
        else:
            set_module(matrix, 8, SIZE - 15 + index, value)

        if index < 8:
            set_module(matrix, SIZE - index - 1, 8, value)
        elif index < 9:
            set_module(matrix, 15 - index, 8, value)
        else:
            set_module(matrix, 15 - index - 1, 8, value)
    set_module(matrix, 8, SIZE - 8, True)


def function_modules() -> list[list[bool | None]]:
    matrix: list[list[bool | None]] = [[None] * SIZE for _ in range(SIZE)]
    draw_finder(matrix, 0, 0)
    draw_finder(matrix, SIZE - 7, 0)
    draw_finder(matrix, 0, SIZE - 7)

    for index in range(8, SIZE - 8):
        if matrix[6][index] is None:
            matrix[6][index] = index % 2 == 0
        if matrix[index][6] is None:
            matrix[index][6] = index % 2 == 0

    for cy in ALIGNMENT_POSITIONS:
        for cx in ALIGNMENT_POSITIONS:
            draw_alignment(matrix, cx, cy)
    write_format(matrix, 0)
    return matrix


def mask_applies(mask: int, x: int, y: int) -> bool:
    if mask == 0:
        return (x + y) % 2 == 0
    if mask == 1:
        return y % 2 == 0
    if mask == 2:
        return x % 3 == 0
    if mask == 3:
        return (x + y) % 3 == 0
    if mask == 4:
        return (y // 2 + x // 3) % 2 == 0
    if mask == 5:
        return (x * y) % 2 + (x * y) % 3 == 0
    if mask == 6:
        return ((x * y) % 2 + (x * y) % 3) % 2 == 0
    return ((x * y) % 3 + (x + y) % 2) % 2 == 0


def add_data(base: list[list[bool | None]], codewords: list[int], mask: int) -> list[list[bool]]:
    matrix = [row[:] for row in base]
    bits = [(byte >> shift) & 1 for byte in codewords for shift in range(7, -1, -1)]
    bit_index = 0
    row = SIZE - 1
    upward = True

    for right_edge in range(SIZE - 1, 0, -2):
        right = right_edge - 1 if right_edge == 6 else right_edge
        while True:
            for x in (right, right - 1):
                if matrix[row][x] is None:
                    bit = bits[bit_index] if bit_index < len(bits) else 0
                    bit_index += 1
                    matrix[row][x] = bool(bit ^ mask_applies(mask, x, row))
            if upward and row == 0:
                upward = False
                break
            if not upward and row == SIZE - 1:
                upward = True
                break
            row += -1 if upward else 1

    write_format(matrix, mask)
    return [[bool(cell) for cell in row] for row in matrix]


def penalty(matrix: list[list[bool]]) -> int:
    score = 0
    for lines in (matrix, [list(column) for column in zip(*matrix)]):
        for line in lines:
            run_color = line[0]
            run_length = 1
            for value in line[1:]:
                if value == run_color:
                    run_length += 1
                else:
                    if run_length >= 5:
                        score += run_length - 2
                    run_color = value
                    run_length = 1
            if run_length >= 5:
                score += run_length - 2

    for y in range(SIZE - 1):
        for x in range(SIZE - 1):
            value = matrix[y][x]
            if matrix[y][x + 1] == value and matrix[y + 1][x] == value and matrix[y + 1][x + 1] == value:
                score += 3

    pattern = (True, False, True, True, True, False, True)
    for lines in (matrix, [list(column) for column in zip(*matrix)]):
        for line in lines:
            for index in range(SIZE - 6):
                if tuple(line[index : index + 7]) != pattern:
                    continue
                before = index >= 4 and not any(line[index - 4 : index])
                after = index + 11 <= SIZE and not any(line[index + 7 : index + 11])
                if before or after:
                    score += 40

    dark = sum(sum(row) for row in matrix)
    score += abs(dark * 20 - SIZE * SIZE * 10) // (SIZE * SIZE) * 10
    return score


def make_matrix(text: str) -> list[list[bool]]:
    data = data_codewords(text)
    codewords = data + reed_solomon(data, ECC_CODEWORDS)
    base = function_modules()
    candidates = [add_data(base, codewords, mask) for mask in range(8)]
    return min(candidates, key=penalty)


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_png(matrix: list[list[bool]], output: Path, scale: int = 10, border: int = 4) -> None:
    width = (len(matrix) + border * 2) * scale
    rows: list[bytes] = []
    for y in range(-border, len(matrix) + border):
        row = bytearray()
        for x in range(-border, len(matrix) + border):
            pixel = 0 if 0 <= x < len(matrix) and 0 <= y < len(matrix) and matrix[y][x] else 255
            row.extend(bytes((pixel, pixel, pixel)) * scale)
        for _ in range(scale):
            rows.append(b"\x00" + bytes(row))

    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, width, 8, 2, 0, 0, 0))
    png += png_chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
    png += png_chunk(b"IEND", b"")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(png)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=Path(__file__).resolve().parents[1] / "docs/try-qr.png")
    args = parser.parse_args()
    matrix = make_matrix(TARGET_URL)
    write_png(matrix, args.output)
    print(f"Wrote {args.output} for {TARGET_URL}")


if __name__ == "__main__":
    main()
