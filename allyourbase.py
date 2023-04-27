#!/usr/bin/env python3
import sys
import re
import argparse
import math
from typing import Literal
import numpy as np


def get_string_addresses(b: bytes, n: int) -> set[int]:
    """
    Finds all utf8 strings of length at least n that are NUL-terminated and returns
    the set of offsets
    """
    # this regex also matches overlong encodings and surrogates
    # this is fine because this is a heuristic anyway
    string_regex = (rb'(?:[\n\r\t\f\x20-\x7E\n]'
                    rb'|[\xC2-\xDF][\x80-\xBF]'
                    rb'|[\xE0-\xEF][\x80-\xBF]{2}'
                    rb'|[\xF0-\xF4][\x80-\xBF]{3})'
                    + f'{{{n},}}'.encode()
                    + rb'\x00')
    return {m.start() for m in re.finditer(string_regex, b)}


def get_pointed_addresses(b: bytes, endian: Literal['little', 'big'], length: int, align: int) -> set[int]:
    """
    Interprets each offset in b as a pointer to an address in memory
    and returns the set of all addresses that are pointed to.
    """
    pointed_addresses = set()
    for i in range(0, len(b) - length + 1, align):
        offset_bytes = b[i:i+length]
        offset = int.from_bytes(offset_bytes, byteorder=endian)
        pointed_addresses.add(offset)
    return pointed_addresses


def find_coprime_numbers(n: int, m: int) -> list[int]:
    """
    Returns a list of integers greater than n, whose product is greater than m and
    that are pairwise coprime.
    """
    # only use odd numbers because with unaligned pointers there
    # will be a lot of pointers that differ from each other by a
    # multiple of 256, which interacts badly with the cross-correlation
    i = n + 1 + (n % 2)
    coprimes = [i]
    product = i
    i += 2
    while product <= m:
        if math.gcd(i, product) == 1:
            coprimes.append(i)
            product *= i
        i += 2
    return coprimes


def find_max_overlap(A: set[int], B: set[int], modulos: list[int]) -> int:
    """
    Finds the probable offset between two sets of integers A and B, where the offset
    is calculated by finding out the overlap modulo each modulus in the list.
    The final offset is calculated using the Chinese remainder theorem.
    """
    offsets = []
    print(f'0/{len(modulos)}', file=sys.stderr, end='', flush=True)
    for p in modulos:
        a = np.zeros(p, dtype=np.float64)
        b = np.zeros(p, dtype=np.float64)
        for x in A:
            a[x % p] += 1
        for x in B:
            # reverse B to turn cross-correlation into convolution
            b[-(x % p)] += 1
        # circular convolution of size p (per convolution theorem)
        corr = np.fft.ifft(np.fft.fft(a) * np.fft.fft(b)).real
        offset = int(np.argmax(corr))
        offsets.append(offset)
        print(f'\r{len(offsets)}/{len(modulos)}',
              file=sys.stderr, end='', flush=True)
    print(file=sys.stderr)

    # chinese remainder theorem
    M = math.prod(modulos)
    k = sum(offset * (M // p) * pow(M // p, -1, p)
            for p, offset in zip(modulos, offsets)) % M
    return int(k)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="the file to analyze")
    parser.add_argument(
        "-n", help="the minimum length of strings to look for, in unicode codepoints", type=int, default=5)
    parser.add_argument(
        "-l", help="the length of pointers to look for, in bytes (4 = 32-bit pointers", type=int, default=8)
    parser.add_argument("-e", help="the endianness of the pointers",
                        choices=["little", "big"], default="little")
    parser.add_argument(
        "-a", help="the alignment of the pointers (defaults to pointer lengths)", type=int)
    parser.add_argument(
        "-f", help="slack factor (higher = slower and more memory but more accurate)", type=float)
    args = parser.parse_args()

    if args.a is None:
        args.a = args.l

    if args.f is None:
        # make sure the ratio (number of pointers pointers/modulo) is at most 1/16 per default
        # to make the noise floor reasonably low
        args.f = min(1.0, 16.0 / args.a)

    with open(args.file, "rb") as f:
        b = f.read()
        strings = get_string_addresses(b, args.n)
        print(f'Found {len(strings)} strings', file=sys.stderr)
        pointers = get_pointed_addresses(b, args.e, args.l, args.a)
        modulos = find_coprime_numbers(
            int(len(b) * args.f), 2**(args.l*8) + len(b))
        offset = find_max_overlap(pointers, strings, modulos)

        negative_offset = math.prod(modulos) - offset
        if negative_offset < len(b):
            print(f"Offset: -{negative_offset:#x}")
        elif offset < 2**(args.l*8):
            print(f"Offset: {offset:#x}")
        else:
            print("Offset: not found")
