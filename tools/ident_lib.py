import numpy as np
def rotl16(v, n):
    return ((v << n) | (v >> (16 - n))) & 0xFFFF


def rotxor(val, xorval):
    res = (val + rotl16(val, 2)) & 0xFFFF
    return rotl16(res, 4) ^ (res & (val ^ xorval))


def mask_np(addr, key1, key2):
    # vectorised cps3_mask over a uint32 array of addresses
    a = (addr ^ np.uint32(key1)).astype(np.uint32)
    lo = (a & 0xFFFF).astype(np.uint32)
    hi = (a >> 16).astype(np.uint32)

    def rx(val, xv):
        res = (val + (((val << 2) | (val >> 14)) & 0xFFFF)) & 0xFFFF
        r4 = ((res << 4) | (res >> 12)) & 0xFFFF
        return (r4 ^ (res & (val ^ xv))) & 0xFFFF

    val = lo ^ 0xFFFF
    val = rx(val, key2 & 0xFFFF)
    val = val ^ hi ^ 0xFFFF
    val = rx(val, key2 >> 16)
    val = val ^ lo ^ (key2 & 0xFFFF)
    val = val.astype(np.uint32)
    return (val | (val << 16)).astype(np.uint32)


def load_words(u9, u10):
    a = np.frombuffer(open(u9, 'rb').read(), dtype='<u2').astype(np.uint32)
    b = np.frombuffer(open(u10, 'rb').read(), dtype='<u2').astype(np.uint32)
    return (a << 16) | b  # program words, per bank contiguous


