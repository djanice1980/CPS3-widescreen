#!/usr/bin/env python3
"""Which halfwords of a plain CPS3 SH-2 program are instructions, from the program alone.

    from sh2map import analyze
    f = analyze(image bytes)
    f.flow_code   instruction addresses reached from references
    f.code        the same plus the unreferenced stretches that explore cleanly ('sweep')
    f.lit         PC-relative data (halfword address -> the instruction that reads it)
    f.table_hw    halfwords of switch tables

Recursive descent from every reference: the vector table, bsr targets, code addresses in literals a reached mov.l
loads, pointers to code held anywhere in the image at 4-aligned addresses, and the case labels of switch tables
(mova + mov.w @(r0,rn) + braf). Every seed is explored on its own first and dropped when the path from it runs into
something that cannot be code: an opcode the SH-2 does not have, a branch in a delay slot, a halfword already
known as PC-relative data, or an address outside the code.

Data that happens to hold a code-like address makes false seeds, and data can decode as valid instructions for a
while. So the work is done twice: a first pass over the whole image shows where the code is (4 KB pages that are
mostly reached code and its literals), and the second pass accepts code only inside those regions.

Last, the stretches of the code regions nothing refers to are swept from their start (routines no one calls, or
called through something this does not see): a stretch that explores cleanly is taken as code.

Checked against Darksoft's own Custom SH2 files of the banks whose Custom file is the Standard program with the
instructions encrypted (the split is Standard XOR Custom): tools/custom_map.py --validate.
"""
import bisect
import struct
from collections import defaultdict

BASE = 0x06000000
RTS, RTE = 0x000B, 0x002B
PAGE = 0x1000


def s(v, bits):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


def _valid_table():
    ok = bytearray(65536)
    for op in range(65536):
        t, lo4, lo8 = op >> 12, op & 0xF, op & 0xFF
        n = (op >> 8) & 0xF
        v = False
        if t == 0:
            if lo4 in (4, 5, 6, 7, 0xC, 0xD, 0xE, 0xF):
                v = True
            elif op in (0x0008, 0x0018, 0x0028, 0x0009, 0x0019, 0x000B, 0x001B, 0x002B):
                v = True
            elif lo8 in (0x29, 0x0A, 0x1A, 0x2A, 0x02, 0x12, 0x22, 0x03, 0x23):
                v = True
        elif t in (1, 5, 6, 7, 9, 0xA, 0xB, 0xD, 0xE):
            v = True
        elif t == 2:
            v = lo4 != 3
        elif t == 3:
            v = lo4 not in (1, 9)
        elif t == 4:
            v = lo4 == 0xF or lo8 in (
                0x00, 0x10, 0x20, 0x01, 0x11, 0x21, 0x02, 0x12, 0x22, 0x03, 0x13, 0x23, 0x04, 0x24, 0x05, 0x15, 0x25,
                0x06, 0x16, 0x26, 0x07, 0x17, 0x27, 0x08, 0x18, 0x28, 0x09, 0x19, 0x29, 0x0A, 0x1A, 0x2A, 0x0B, 0x1B,
                0x2B, 0x0E, 0x1E, 0x2E)
        elif t == 8:
            v = n in (0, 1, 4, 5, 8, 9, 0xB, 0xD, 0xF)
        elif t == 0xC:
            v = True
        ok[op] = v
    return ok


VALID = _valid_table()


def is_branch(op):
    """Instructions that may not sit in a delay slot."""
    t = op >> 12
    return (t in (0xA, 0xB) or op & 0xF900 == 0x8900 or op in (RTS, RTE) or op & 0xF0DF == 0x400B
            or op & 0xF0DF == 0x0003 or op & 0xFF00 == 0xC300)


class Bad(Exception):
    pass


class Flow:
    def __init__(self, data, base=BASE, regions=None):
        self.data, self.base = data, base
        self.end = base + len(data)
        self.regions = regions        # [(lo, hi)] where code may be; None: anywhere from base + 0x400
        self.code = set()             # instruction addresses
        self.lit = {}                 # halfword address of a PC-relative literal -> the instruction that reads it
        self.tables = {}              # switch table address -> (braf site, number of entries)
        self.table_hw = set()         # halfword addresses of switch tables
        self.computed = set()         # braf / jmp sites
        self.mova = {}                # site -> target
        self.seed_src = {}            # accepted seed -> why
        self.rejected = {}            # seed -> (why, reason)
        self.owner = {}               # instruction -> the seed whose path first took it
        self.parent = {}              # seed -> the seed whose path gave it (None: a root)
        self.banned = set()           # seeds not to take (they lost a conflict in an earlier round)
        self.evict = set()            # seeds that lost a conflict in this round
        self.conflicts = []           # (seed, why, reason) left undecided
        self.blocked = []             # (seed, why, reason, [blocking weak seeds])
        self.holders = set()          # halfwords of 4-aligned words that hold the address of accepted code
        self.data_start = set()       # addresses in the code that code refers to as data (mova, literal pointers)

    def h(self, a):
        return struct.unpack_from('>H', self.data, a - self.base)[0]

    def l(self, a):
        return struct.unpack_from('>I', self.data, a - self.base)[0]

    def in_code(self, v):
        if v & 1:
            return False
        if self.regions is None:
            return self.base + 0x400 <= v < self.end
        return any(lo <= v < hi for lo, hi in self.regions)

    def explore(self, seed, dry=False):
        """Follow the branches from seed. Returns (code, literals, bsr, mov.l, mova, computed jumps) or raises
        Bad. dry: do not stop at what earlier seeds claimed; return (code, [(address, kind of clash)])."""
        code, lits, bsr, movl, mova, comp = set(), {}, [], [], [], []
        todo = [seed]
        clash = []

        def take(a, slot=False):
            if not self.in_code(a):
                raise Bad(f'{a:08X} outside the code')
            if a in lits:
                raise Bad(f'{a:08X} is PC-relative data of this path')
            if a in self.lit or a in self.table_hw:
                if not dry:
                    raise Bad(f'{a:08X} is PC-relative data')
                clash.append((a, 'code-on-data'))
            op = self.h(a)
            if not VALID[op]:
                raise Bad(f'{a:08X}: {op:04X} is not an SH-2 instruction')
            if slot and is_branch(op):
                raise Bad(f'{a:08X}: branch {op:04X} in a delay slot')
            code.add(a)
            t = op >> 12
            if t == 0x9:
                lits[a + 4 + 2 * (op & 0xFF)] = a
            elif t == 0xD:
                x = (a & ~3) + 4 + 4 * (op & 0xFF)
                lits[x] = a
                lits[x + 2] = a
                movl.append((a, x))
            elif op & 0xFF00 == 0xC700:
                mova.append((a, (a & ~3) + 4 + 4 * (op & 0xFF)))
            return op

        while todo:
            a = todo.pop()
            while a not in code and a not in self.code:
                op = take(a)
                t = op >> 12
                if t == 0xA:      # bra
                    take(a + 2, True)
                    a = a + 4 + 2 * s(op & 0xFFF, 12)
                elif t == 0xB:    # bsr
                    take(a + 2, True)
                    bsr.append((a, a + 4 + 2 * s(op & 0xFFF, 12)))
                    a += 4
                elif op & 0xFD00 == 0x8900:   # bt bf
                    todo.append(a + 4 + 2 * s(op & 0xFF, 8))
                    a += 2
                elif op & 0xFD00 == 0x8D00:   # bt/s bf/s
                    take(a + 2, True)
                    todo.append(a + 4 + 2 * s(op & 0xFF, 8))
                    a += 4
                elif op in (RTS, RTE):
                    take(a + 2, True)
                    break
                elif op & 0xF0FF in (0x402B, 0x0023):   # jmp braf
                    take(a + 2, True)
                    comp.append(a)
                    break
                elif op & 0xF0FF in (0x400B, 0x0003):   # jsr bsrf
                    take(a + 2, True)
                    a += 4
                else:
                    a += 2
        for x in lits:
            if x in code:
                raise Bad(f'literal at {x:08X} (read by {lits[x]:08X}) is an instruction of this path')
            if x in self.code:
                if not dry:
                    raise Bad(f'literal at {x:08X} (read by {lits[x]:08X}) is an instruction')
                clash.append((x, 'data-on-code'))
            if not (self.base <= x < self.end):
                raise Bad(f'literal at {x:08X} outside the image')
        if dry:
            return code, clash, lits
        return code, lits, bsr, movl, mova, comp

    def conflict(self, seed, why, reason):
        """seed's path is blocked by what an earlier seed claimed. A word of data that happens to hold the address
        of a literal pool makes a false seed there: if the blocking path came from a pointer in data or from the
        sweep and its first or second instruction is a halfword this path reads as a literal, it loses and the
        analysis is run again without it. Anything else is left as it is and listed."""
        try:
            code, clash, lits = self.explore(seed, dry=True)
        except Bad:
            return
        owners = defaultdict(list)
        other = [(x, kind) for x, kind in clash if kind != 'data-on-code']
        for x, kind in clash:
            if kind == 'data-on-code':
                owners[self.owner[x]].append(x)
        for o, xs in owners.items():
            if self.weak_seed(o) and (o in lits or min(xs) - o <= 2):
                self.evict.add(o)
            else:
                other += [(x, 'data-on-code') for x in xs]
        if other:
            self.conflicts.append((seed, why, reason, other))

    def weak_seed(self, seed):
        why = self.seed_src.get(seed, '')
        return why.startswith('pointer') or why == 'sweep'

    def switch_bound(self, site):
        """The number of cases, from the bounds check before a switch: mov #n,rx / cmp/hs rx,r0 / bt (or bf)."""
        for k in range(2, 14):
            a = site - 2 * k
            op = self.h(a)
            if op & 0xF00F == 0x3002 and a in self.code:        # cmp/hs rm,rn
                m = (op >> 4) & 0xF
                for q in range(1, 4):
                    o2 = self.h(a - 2 * q)
                    if o2 >> 12 == 0xE and (o2 >> 8) & 0xF == m:
                        return o2 & 0xFF if o2 & 0x80 == 0 else None
                    if o2 >> 12 == 0x9 and (o2 >> 8) & 0xF == m:   # mov.w @(disp,PC),rm
                        return self.h(a - 2 * q + 4 + 2 * (o2 & 0xFF))
                return None
        return None

    def switch_table(self, site):
        """The case labels of a switch (SHC), two forms:
            mova table,r0 / mov.w @(r0,rm),r0 / braf r0             offsets from the braf + 4
            mova table,r0 / mov.l @(r0,rm),r0 / braf r0             the same with 32-bit offsets
            mov.l #table,rt / mov.w @(r0,rt),rn / add rt,rn / jmp @rn   offsets from the table
            mova table,r0 / mov.w @(r0,rm),rt / add rt,r0 / jmp @r0      offsets from the table
        The number of entries comes from the bounds check before it; without one the table ends where the first
        case label after it starts, or at the first halfword that is known code. Returns (table, [labels])."""
        op = self.h(site)
        n = (op >> 8) & 0xF
        table = base = None
        size = 2
        if op & 0xF0FF == 0x0023:
            prev = self.h(site - 2)
            if prev & 0xF00F not in (0x000D, 0x000E) or (prev >> 8) & 0xF != n:
                return None
            size = 2 if prev & 0xF == 0xD else 4
            for k in range(2, 6):
                a = site - 2 * k
                if a in self.mova:
                    table = self.mova[a]
                    break
            base = site + 4
        elif op & 0xF0FF == 0x402B:
            p1, p2 = self.h(site - 2), self.h(site - 4)
            if p1 & 0xF00F != 0x300C or (p1 >> 8) & 0xF != n or p2 & 0xF00F != 0x000D:
                return None
            t = (p1 >> 4) & 0xF                     # add rt,rn
            if n == 0 and (p2 >> 8) & 0xF == t:      # mova table,r0 / mov.w @(r0,rm),rt / add rt,r0 / jmp @r0
                for k in range(3, 7):
                    a = site - 2 * k
                    if a in self.mova:
                        table = self.mova[a]
                        break
            elif (p2 >> 8) & 0xF == n and (p2 >> 4) & 0xF == t:   # mov.l #table,rt / mov.w @(r0,rt),rn / add rt,rn
                for k in range(3, 10):
                    a = site - 2 * k
                    o = self.h(a)
                    if o >> 12 == 0xD and (o >> 8) & 0xF == t and a in self.code:
                        table = self.l((a & ~3) + 4 + 4 * (o & 0xFF))
                        break
            base = table
        if table is None or not (self.base <= table < self.end - 1) or table & 1:
            return None
        count = self.switch_bound(site)
        labels, a, first = [], table, None
        while a < self.end - 3 and len(labels) < 2048:
            if count is not None:
                if len(labels) >= count:
                    break
            elif (first is not None and a >= first) or a in self.code:
                break
            t = base + (s(self.h(a), 16) if size == 2 else s(self.l(a), 32))
            if t & 1 or not self.in_code(t):
                if count is not None:
                    return None
                break
            labels.append(t)
            if t > table:
                first = t if first is None else min(first, t)
            a += size
        return (table, labels, size) if labels else None

    def add(self, seed, why, parent=None):
        """Explore seed and take its code if the path is clean. Returns the seeds that follow from it."""
        if seed in self.code or seed in self.rejected or seed in self.banned:
            return []
        try:
            code, lits, bsr, movl, mova, comp = self.explore(seed)
        except Bad as e:
            self.rejected[seed] = (why, str(e))
            if 'of this path' not in str(e) and ('is PC-relative data' in str(e) or 'is an instruction' in str(e)):
                self.conflict(seed, why, str(e))
            return []
        for a in code:
            self.owner[a] = seed
        self.code |= code
        self.lit.update(lits)
        self.seed_src[seed] = why
        self.parent[seed] = parent
        if why.startswith('pointer at '):
            x = int(why[11:], 16)
            self.holders |= {x, x + 2}
        out = []
        for a, t in bsr:
            out.append((t, f'bsr at {a:08X}'))
        for a, x in movl:
            v = self.l(x)
            if self.in_code(v):
                out.append((v, f'literal at {x:08X}'))
        for a, t in mova:
            self.mova[a] = t
            self.data_start.add(t)
        for a in comp:
            self.computed.add(a)
            sw = self.switch_table(a)
            if sw:
                table, labels, size = sw
                hw = set(range(table, table + size * len(labels), 2))
                if hw & self.code:
                    continue
                self.tables[table] = (a, len(labels))
                self.table_hw |= hw
                out += [(t, f'switch at {a:08X}') for t in labels]
        return [(t, w, seed) for t, w in out]

    def run_seeds(self, seeds):
        todo = [(sd, why, None) for sd, why in seeds]
        while todo:
            seed, why, parent = todo.pop()
            todo += self.add(seed, why, parent)

    def vectors(self, n=256):
        return [(self.l(self.base + 4 * i), f'vector {i}') for i in range(n) if self.in_code(self.l(self.base + 4 * i))]

    def pointer_seeds(self):
        out = []
        code = self.code
        top = self.base >> 24
        for a in range(self.base, self.end, 4):
            v = struct.unpack_from('>I', self.data, a - self.base)[0]
            if (v >> 24) == top and v not in code and v not in self.rejected and a not in code \
                    and a + 2 not in code and self.in_code(v):
                out.append((v, f'pointer at {a:08X}'))
        return out

    def run(self):
        self.run_seeds(self.vectors())
        while True:
            n = len(self.code)
            self.run_seeds(self.pointer_seeds())
            if len(self.code) == n:
                break

    def sweep(self):
        """Explore what nothing refers to: in each region, every stretch that is neither code nor known data, from
        its start. A stretch that code refers to as data (a mova target, the target of a literal that is not
        code, a word holding a code address) is left alone up to the next known halfword. Returns the number of
        entries taken."""
        for sd, (why, reason) in self.rejected.items():
            if why.startswith('literal at ') and self.in_code(sd):
                self.data_start.add(sd)
        holders = self.holders - self.code

        def known(a):
            return a in self.code or a in self.lit or a in self.table_hw
        taken = 0
        for lo, hi in self.regions:
            a = lo
            while a < hi:
                if known(a):
                    a += 2
                    continue
                if a in self.data_start or a in holders:
                    while a < hi and not known(a):      # a data table: its length is not known
                        a += 2
                    continue
                n = len(self.code)
                self.rejected.pop(a, None)
                self.run_seeds([(a, 'sweep')])
                if len(self.code) > n and a in self.code:
                    taken += 1
                a += 2
        return taken


def code_regions(flow, page=PAGE, dense=0.5, join=1024):
    """[(lo, hi)]: runs of pages that are mostly reached code and its literals, each widened over the reached code
    that continues past its first and last page."""
    known = flow.code | set(flow.lit) | flow.table_hw
    count = defaultdict(int)
    for a in known:
        count[a // page] += 1
    pages = sorted(p for p, n in count.items() if n >= dense * page / 2)
    regions = []
    for p in pages:
        if regions and regions[-1][1] == p * page:
            regions[-1][1] = (p + 1) * page
        else:
            regions.append([p * page, (p + 1) * page])
    out = []
    srt = sorted(known)
    for lo, hi in regions:
        i = bisect.bisect_left(srt, hi)
        while i < len(srt) and srt[i] - hi <= join:
            hi = srt[i] + 2
            i += 1
        i = bisect.bisect_left(srt, lo) - 1
        while i >= 0 and lo - (srt[i] + 2) <= join:
            lo = srt[i]
            i -= 1
        lo = max(lo, flow.base + 0x400)
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(hi, out[-1][1]))
        else:
            out.append((lo, hi))
    return out


def extend_regions(data, base, regions, log, slack=32, reach=0x10000):
    """Code the references do not reach can continue past a region's end (a run of routines nothing visible
    calls): from each region's end, explore the next halfwords as code, as the sweep does, and move the end
    over every stretch that explores cleanly, until `slack` bytes in a row do not."""
    out = []
    for k, (lo, hi) in enumerate(regions):
        limit = min(regions[k + 1][0] if k + 1 < len(regions) else base + len(data), hi + reach)
        while True:
            f = Flow(data, base, [r for r in regions if r != (lo, hi) and r[0] != lo] + [(lo, limit)])
            a, end, miss = hi, hi, 0
            while a < limit and miss < slack:
                if a in f.code or a in f.lit or a in f.table_hw:
                    end = a + 2
                    a += 2
                    miss = 0
                    continue
                n = len(f.code)
                f.rejected.pop(a, None)
                f.run_seeds([(a, 'sweep')])
                if len(f.code) > n and a in f.code:
                    miss = 0
                    end = max([end] + [x + 2 for x in f.code if x >= hi] + [x + 2 for x in f.lit if hi <= x < limit])
                else:
                    miss += 2
                a += 2
            if end == hi:
                break
            log(f'region end {hi:08X} moved to {min(end, limit):08X} (unreferenced code continues)')
            hi = min(end, limit)
            if hi >= limit:
                break
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(hi, out[-1][1]))
        else:
            out.append((lo, hi))
    return out


def run_flow(data, base, regions, log, name, sweep=False):
    """The flow analysis (and the sweep), run again without each seed that turned out to sit on a literal. A seed
    stays dropped only if accepted code then really reads its first or second halfword as a literal; otherwise
    it is put back and never dropped again."""
    banned, protected = set(), set()
    for _ in range(60):
        f = Flow(data, base, regions)
        f.banned = set(banned)
        f.run()
        f.flow_code = set(f.code)
        f.swept = f.sweep() if sweep else 0
        new = f.evict - banned - protected
        if new:
            banned |= new
            continue
        data_hw = lambda a: a in f.lit or a in f.table_hw
        unjust = {o for o in banned if not (data_hw(o) or data_hw(o + 2))}
        if not unjust:
            break
        banned -= unjust
        protected |= unjust
    if banned:
        log(f'{name}: {len(banned)} false seed(s) on a literal dropped: '
            + ', '.join(f'{x:08X}' for x in sorted(banned)[:12]))
    f.dropped, f.protected = banned, protected
    return f


def analyze(data, base=BASE, log=print):
    first = run_flow(data, base, None, log, 'first pass')
    regions = code_regions(first)
    log(f'first pass: {len(first.code)} instructions; code regions: '
        + ', '.join(f'{lo:08X}-{hi:08X}' for lo, hi in regions))
    regions = extend_regions(data, base, regions, log)
    f = run_flow(data, base, regions, log, 'second pass', sweep=True)
    log(f'second pass: {len(f.flow_code)} instructions, {len(f.lit)} literal halfwords, {len(f.tables)} switch '
        f'tables ({len(f.table_hw)} halfwords), {len(f.rejected)} seeds dropped, {len(f.conflicts)} conflicts left')
    log(f'sweep: {f.swept} entries, {len(f.code) - len(f.flow_code)} more instructions')
    return f
