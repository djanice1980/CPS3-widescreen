#!/usr/bin/env python3
"""Recursive-descent control flow for SH-2 code in a CPS3 program image (no decomp needed).

    from sh2flow import Prog
    p = Prog(open(bin, 'rb').read(), 0x06000000)
    code, refs, unknown = p.reach([entry, ...])

code: set of instruction addresses reachable from the entries (following branches, not calls into other
functions unless follow_calls=True); refs: list of (insn addr, target addr, kind) for every PC-relative reference
(kinds: bra, bsr, bt, bf, movw, movl, mova); unknown: addresses of computed jumps (BRAF/BSRF/JMP) that end a path.
"""
import struct

RTS, RTE = 0x000B, 0x002B


def s(v, bits):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


class Prog:
    def __init__(self, data, base):
        self.data, self.base = data, base

    def h(self, a):
        return struct.unpack_from('>H', self.data, a - self.base)[0]

    def l(self, a):
        return struct.unpack_from('>I', self.data, a - self.base)[0]

    def step(self, a):
        """(next addrs to follow, refs, is_delayed_branch, ends) for the instruction at a."""
        op = self.h(a)
        refs, nxt, ends = [], [a + 2], False
        delayed = False
        top = op >> 12
        if top == 0xA:  # BRA
            t = a + 4 + 2 * s(op & 0xFFF, 12)
            refs.append((a, t, 'bra')); nxt = [t]; delayed = True
        elif top == 0xB:  # BSR
            t = a + 4 + 2 * s(op & 0xFFF, 12)
            refs.append((a, t, 'bsr')); delayed = True
        elif op & 0xFF00 in (0x8900, 0x8B00, 0x8D00, 0x8F00):  # BT BF BT/S BF/S
            t = a + 4 + 2 * s(op & 0xFF, 8)
            refs.append((a, t, 'bt' if op & 0x0200 == 0 else 'bf'))
            nxt = [a + 2, t] if op & 0x0400 == 0 else [a + 4, t]
            delayed = bool(op & 0x0400)
        elif top == 0x9:  # MOV.W @(d,PC)
            refs.append((a, a + 4 + 2 * (op & 0xFF), 'movw'))
        elif top == 0xD:  # MOV.L @(d,PC)
            refs.append((a, (a & ~3) + 4 + 4 * (op & 0xFF), 'movl'))
        elif op & 0xFF00 == 0xC700:  # MOVA
            refs.append((a, (a & ~3) + 4 + 4 * (op & 0xFF), 'mova'))
        elif op in (RTS, RTE):
            nxt = []; delayed = True; ends = True
        elif op & 0xF0FF == 0x402B:  # JMP @Rm
            nxt = []; delayed = True; ends = True
        elif op & 0xF0FF == 0x0023:  # BRAF
            nxt = []; delayed = True; ends = True
        elif op & 0xF0FF in (0x400B, 0x0003):  # JSR, BSRF
            delayed = True
        return nxt, refs, delayed, ends

    def reach(self, entries, limit=None):
        code, refs, unknown = set(), [], []
        todo = list(entries)
        while todo:
            a = todo.pop()
            while a not in code:
                if limit and not (limit[0] <= a < limit[1]):
                    unknown.append(('leaves', a)); break
                code.add(a)
                nxt, r, delayed, ends = self.step(a)
                refs += r
                op = self.h(a)
                if delayed:  # the delay slot executes too
                    code.add(a + 2)
                    _, r2, _, _ = self.step(a + 2)
                    refs += r2
                    if ends:
                        if op & 0xF0FF in (0x402B, 0x0023):
                            unknown.append(('computed', a))
                        break
                    if op >> 12 == 0xA:  # BRA
                        a = nxt[0]; continue
                    if op >> 12 == 0xB or op & 0xF0FF in (0x400B, 0x0003):  # calls: continue after the slot
                        a = a + 4; continue
                    # BT/S BF/S: both the target and after the slot
                    todo.append(nxt[1]); a = a + 4; continue
                if not nxt:
                    break
                if len(nxt) == 2:
                    todo.append(nxt[1])
                a = nxt[0]
        return code, refs, unknown
