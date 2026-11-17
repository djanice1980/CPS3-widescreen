#!/usr/bin/env python3
"""Make wide-placed copies of the fight HUD's routines from the decomp source.

    gen_hud.py <decomp src dir> <hud.tsv> <out .c> <out hooks .tsv>

hud.tsv lists "<source file><TAB><function>". Each function's text is copied from the decomp as it is, renamed
wide_<function>, with the column arguments of the text-layer primitives it calls offset by HUD_DX: DE_X[3], the game's own
text-centring offset (7 columns, 56 pixels, in the wide screen mode; 0 in the normal one). So in the normal mode
the copies draw where the originals do, and in the wide mode the 384-pixel HUD sits in the middle of the
496-pixel screen, as New Generation's wide tables and 3rd Strike's leftover stun-gauge table (+7 each) have it.

The source files' own variables are declared extern (the copies use the stock program's), and the hooks file
sends each original to its copy.
"""
import re
import sys
from collections import OrderedDict

MACROS = '''
/* the HUD's columns, moved by the game's text-centring offset */
extern s16 DE_X[19];
#define HUD_DX (DE_X[3])
'''

# The text-layer primitives and which of their arguments are columns. The column arguments are edited in the
# copied text, not by function-like macros of the same name: SHC 5.0's preprocessor expands such a macro a
# second time when the call is written over more than one line, which moved half the vitality bar's cells 14
# columns instead of 7.
COLUMN_ARGS = {
    'tilemap_put_cell': (0,),
    'sc_ram_to_vram': (1,),
    'sc_ram_to_vram_opc': (1,),
    'sq_paint_chenge': (0,),
    'tilemap_clear_rect': (0, 2),
}


def call_args(text, open_paren):
    """Split the argument list starting at text[open_paren] == '('; returns (args, index after ')')."""
    depth, args, start, i = 0, [], open_paren + 1, open_paren
    while True:
        c = text[i]
        if c in '([':
            depth += 1
        elif c in ')]':
            depth -= 1
            if depth == 0:
                args.append(text[start:i])
                return args, i + 1
        elif c == ',' and depth == 1:
            args.append(text[start:i])
            start = i + 1
        elif c in '"\'':
            i = text.index(c, i + 1)  # no escaped quotes in these routines
        i += 1


def shift_columns(body):
    """Add HUD_DX to the column arguments of every primitive call in a function body; count the edits."""
    out, pos, edits = [], 0, 0
    pat = re.compile(r'\b(' + '|'.join(COLUMN_ARGS) + r')\s*\(')
    for m in pat.finditer(body):
        if m.start() < pos:
            continue  # inside a call already rewritten
        args, end = call_args(body, m.end() - 1)
        for k in COLUMN_ARGS[m.group(1)]:
            args[k] = f'({args[k].strip()}) + HUD_DX'
            edits += 1
        out.append(body[pos:m.start()] + m.group(1) + '(' + ', '.join(a.strip() for a in args) + ')')
        pos = end
    return ''.join(out) + body[pos:], edits

TOP_DECL = re.compile(r'^(?!extern|static|typedef|#|/\*|\s|}|{)([A-Za-z_][\w \*]*?[\s\*])(\w+)\s*(\[[^\]]*\])*\s*(=.*|;.*)$')


def function_text(text, name):
    """The definition of name: from its first line to the closing brace in column 0."""
    for m in re.finditer(rf'^[A-Za-z_][\w \*]*?\b{name}\s*\(', text, re.M):
        line_end = text.index('\n', m.start())
        if text[m.start():line_end].rstrip().endswith(';'):
            continue  # a prototype
        end = re.compile(r'^}', re.M).search(text, m.start())
        return text[m.start():end.end()] + '\n'
    sys.exit(f'{name}: no definition found')


def preamble(text):
    """#include lines, extern declarations and prototypes of a source file, and its variables made extern."""
    incs, decls = [], []
    depth = 0
    knr = False  # between a function's header and its body: K&R parameter declarations
    for line in text.split('\n'):
        if depth == 0 and not knr and re.match(r'^[A-Za-z_][\w \*]*\b\w+\s*\([^;]*$', line):
            knr = '{' not in line
        elif depth == 0 and knr:
            knr = '{' not in line
        elif depth == 0:
            if line.startswith('#include'):
                incs.append(line)
            elif line.startswith('#define'):
                decls.append(line)
            elif line.startswith('extern '):
                decls.append(line)
            elif re.match(r'^[A-Za-z_][\w \*]*\b\w+\s*\([^)]*\);', line):
                decls.append(line.split(';')[0] + ';')
            else:
                m = TOP_DECL.match(line)
                if m and '(' not in m.group(1) + m.group(2):
                    dims = re.sub(r'\[[^\]]*\]', '[]', m.group(3) or '') if m.group(3) else ''
                    decls.append(f'extern {m.group(1).strip()} {m.group(2)}{dims};')
        depth += line.count('{') - line.count('}')
    return incs, decls


def main():
    src, spec, out_c, out_hooks = sys.argv[1:5]
    want = OrderedDict()
    for line in open(spec):
        line = line.split('#')[0].strip()
        if line:
            f, fn = line.split()
            want.setdefault(f, []).append(fn)
    incs, decls, bodies, hooks = [], [], [], []
    for f, fns in want.items():
        text = open(f'{src}/{f}', encoding='latin-1').read()
        i, d = preamble(text)
        incs += [x for x in i if x not in incs]
        decls += [x for x in d if x not in decls]
        for fn in fns:
            body = function_text(text, fn)
            head = body.index('{')
            body, edits = shift_columns(body[head:])
            body = re.sub(rf'\b{fn}(\s*\()', rf'wide_{fn}\1', function_text(text, fn)[:head], count=1) + body
            if not edits:
                sys.exit(f'{fn}: no text-layer call to move')
            bodies.append(f'/* {f}: {fn}, {edits} column arguments moved by HUD_DX */\n{body}')
            hooks.append(f'{fn}\twide_{fn}')
    with open(out_c, 'w', newline='\n') as o:
        o.write('/* Generated by tools/gen_hud.py from the decomp source: do not edit. */\n')
        o.write('\n'.join(incs) + '\n\n')
        o.write('\n'.join(decls) + '\n')
        o.write(MACROS + '\n#pragma section WIDE\n\n')
        o.write('\n\n'.join(bodies))
    open(out_hooks, 'w').write('# generated by tools/gen_hud.py\n' + '\n'.join(hooks) + '\n')
    print(f'{out_c}: {len(bodies)} routines')


if __name__ == '__main__':
    main()
