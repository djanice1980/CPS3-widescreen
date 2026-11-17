"""CPS3 program encryption mask (MAME's cps3_mask), with the key as a parameter.

Darksoft's "Custom SH2" images are for a security cart running key 0 (a "dead" cart re-armed): the SH-2 decrypts
the words it fetches as instructions, so those halfwords are stored XORed with mask16(address of their 32-bit
word, 0, 0) and data (literal pools, tables) is stored plain.
"""
import numpy as np


def _rol16(v, n):
    v &= 0xFFFF
    return ((v << n) | (v >> (16 - n))) & 0xFFFF


def _rotxor(val, x):
    res = (val + _rol16(val, 2)) & 0xFFFF
    return (_rol16(res, 4) ^ (res & (val ^ x))) & 0xFFFF


def mask16(addr, key1=0, key2=0):
    """The 16-bit mask for the 32-bit word at addr (both halfwords of the word use the same value)."""
    addr = (addr & ~3) ^ key1
    v = (addr & 0xFFFF) ^ 0xFFFF
    v = _rotxor(v, key2 & 0xFFFF)
    v ^= ((addr >> 16) & 0xFFFF) ^ 0xFFFF
    v = _rotxor(v, key2 >> 16)
    v ^= (addr & 0xFFFF) ^ (key2 & 0xFFFF)
    return v & 0xFFFF


def mask_table(base, nbytes, key1=0, key2=0):
    """mask16 for every halfword of base .. base + nbytes (numpy uint16, one per halfword)."""
    words = np.array([mask16(base + 4 * i, key1, key2) for i in range(nbytes // 4)], dtype=np.uint16)
    return np.repeat(words, 2)
