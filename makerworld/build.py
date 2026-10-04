#!/usr/bin/env python3
"""Package GridFlock for MakerWorld's Parametric Model Maker (PMM), which takes one self-contained .scad file.

Every MakerWorld change to GridFlock is made here, at build time, so nothing outside makerworld/ differs
from upstream and merging upstream never conflicts. Nothing is matched by upstream text: a small OpenSCAD
parser locates definitions and statements by name, so upstream may reformat, comment, reorder or add code
freely. Only removing or renaming a symbol listed in UPSTREAM breaks the build, with an error naming it.

The build makes these transformations, in order:

  1. Connector fill: upstream's segment_core is renamed _gf_segment_core, and overrides.scad defines a
     segment_core wrapping it that keeps Lightweight_Connector_Fill mm of solid material around every
     connector, so a lightweight plate does not grow them out of a single wall with air behind it.
  2. Multi-plate: mw_main(mw_plate) is generated from main(): every statement of main() is copied except its
     segment-placement loop. The preview and stacked prints reuse that loop as is; otherwise the segments are
     packed onto build plates around the loop's own `segment(...)` call. main() itself is left alone.
  3. Test pattern strip: top-level geometry (the test_pattern dispatch) is dropped, as PMM must see none.
  4. Parameter block: gridflock's parameters are replaced by customizer.scad, which
     - re-orders them: the always-visible options first, then one tab per section;
     - adds simplified options: Width, Depth, Clearance, Build_Plate, Build_Plate_Custom, Plate_Margin,
       Lightweight, Click_Latch, Edge_Style, Edge_Position, Connector_Style, Lightweight_Connector_Fill and
       Stacked_Separator;
     - changes defaults: Lightweight on (gridflock: off), Click_Style Arc (gridflock: ClickGroove);
     - shortens the descriptions to fit PMM, and capitalizes every label, aliased back to gridflock's name;
     - drops the parameters the simplified options replace, the test patterns and the openGrid adapters.
  5. Epilogue: epilogue.scad assigns the dropped parameters from the simplified options, turns Lightweight off
     where it cannot work, and defines the build plate packer mw_main uses.
  6. Flattening: every file gridflock.scad includes or uses is inlined, keeping only definitions from `use`.
  7. Header: provenance and the MIT / CC-BY licence notices, ahead of everything.
  8. Entry points: mw_plate_1() .. mw_plate_24(), one build plate each, and mw_assembly_view().

Every gridflock parameter must be accounted for in customizer.scad, and the epilogue may only assign parameters
customizer.scad drops, so a renamed parameter cannot go unnoticed either.

Usage (from the repository root; runs `just paths` when paths/ is missing):
  uv run makerworld/build.py [build] [-o OUT]   build build/makerworld/GridFlock.scad
  uv run makerworld/build.py test [-D k=v ...]  build, render the entry points with --hardwarnings, and check
                                                that the preview matches gridflock's own main()
  uv run makerworld/build.py docs               render the images referenced by listing.html
"""

import argparse
import os
import pathlib
import re
import shlex
import string
import subprocess
import sys
import tempfile
from typing import NamedTuple

ROOT = pathlib.Path(__file__).resolve().parent.parent
HERE = ROOT / "makerworld"
OUTPUT = "build/makerworld/GridFlock.scad"

# Every upstream symbol makerworld/ relies on, beyond the parameters customizer.scad and epilogue.scad name,
# which the build checks separately. Checked before anything else is done.
UPSTREAM = {
    "parameters": ["magnets", "solid_base", "stacked_print", "bed_size",
                   "connector_intersection_puzzle", "connector_edge_puzzle"],
    "constants": ["BASEPLATE_DIMENSIONS", "_profile_height", "_extra_height", "_total_height"],
    "functions": ["quicksort"],
    "modules": ["main", "segment", "segment_core", "flip_segment_conditional",
                "segment_intersection_connectors", "segment_edge_connectors"],
    "main() locals": ["segments_in_order", "duplicates", "connector_margin",
                      "compute_segment_size", "compute_segment_position_stacked"],
    "main() segment loop locals": ["segi", "flip"],
}
# Renamed so overrides.scad can wrap them under their own name.
WRAPPED = {"segment_core": "_gf_segment_core"}
# makerworld's own options that overrides.scad reads; `docs` needs their customizer.scad defaults.
OVERRIDE_OPTIONS = ["Lightweight_Connector_Fill"]

INCLUDE_RE = re.compile(r"^\s*(include|use)\s*<([^>]+)>\s*;?\s*$")
SECTION_RE = re.compile(r"^\s*/\*\s*\[(.+?)\]\s*\*/\s*$")
PARAM_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s*=")
DIRECTIVE_RE = re.compile(r"^@(include|drop)\s+(.*)$")
DECL_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)(\s*=\s*)(.*?)(;\s*)(//.*)?$")

MW_PLATE_COUNT = 24
MW_PART_GAP = 2
MW_BED_MARGIN = 2
MW_GRID = 42  # mirrors gridfinity's BASEPLATE_DIMENSIONS, asserted in mw_main()
MW_MIN_FILLER = 8.5  # gridfinity's cutter asserts a cell is wider than BASEPLATE_OUTER_DIAMETER (8)

HEADER = """/**
 * GridFlock - a Gridfinity baseplate generator for small printer beds.
 *
 * Generated by makerworld/build.py; do not edit. Source, issues and full documentation:
 *   https://github.com/yawkat/GridFlock
 *
 * GridFlock is dual-licensed under MIT and CC-BY 4.0, Copyright (c) Jonas Konrad.
 * Bundles Gridfinity Rebuilt (MIT, Copyright (c) Kenneth Ruszkowski and contributors),
 *   https://github.com/kennetek/gridfinity-rebuilt-openscad
 * Both license notices are reproduced above the code they cover, below.
 */

"""

# Filled from gridflock's main(): $params its parameters, $planning its statements but the segment loop,
# $loop that loop, $header its `(i = ...)`, $i its variable, $locals the loop's own assignments, $lets the
# same as let() bindings, $segment the loop's `segment(...)` call.
MW_MAIN = """\
module mw_main($params) {
$planning

    // MakerWorld: pack the segments onto build plates, rotating pieces upright.
    mw_placement = stacked_print ? [] : mw_pack(
        [for (segi = segments_in_order) compute_segment_size(segi) + [connector_margin, connector_margin] * 2],
        bed_size - [_MW_BED_MARGIN, _MW_BED_MARGIN] * 2, _MW_PART_GAP, _mw_keepout);
    assert(is_undef(mw_plate) || stacked_print || max([for (p = mw_placement) p[0]]) < _MW_PLATE_COUNT,
        "This plate needs more build plates than MakerWorld can show. Pick a larger printer, or a smaller plate.");
    assert(BASEPLATE_DIMENSIONS == [_MW_GRID, _MW_GRID], "makerworld/build.py has the wrong grid size.");

    // The segment loop's own locals, for loop index $i.
    function mw_locals($i) = let(
$lets
    ) [segi, flip];
    function mw_segi($i) = mw_locals($i)[0];
    function mw_flip($i) = mw_locals($i)[1];
    function mw_stack_pitch() = compute_segment_position_stacked(1, mw_segi(0), mw_flip(0))[2];

    // One piece in its own frame; callers do the placing.
    module mw_piece($i) {
$locals
        flip_segment_conditional(flip) $segment;
    }

    // The preview and stacked prints place the pieces exactly as gridflock does.
    if (is_undef(mw_plate) || (stacked_print && mw_plate == 0))
        $loop
    else if (!stacked_print)
        for $header
            if (mw_placement[$i][0] == mw_plate)
            translate(mw_placement[$i][1]) rotate([0, 0, mw_placement[$i][2] ? 90 : 0]) mw_piece($i);

    // The separator is only where the top of one piece actually meets the bottom of the next,
    // so it never prints over a cell opening.
    if (stacked_print && Stacked_Separator && (is_undef(mw_plate) || mw_plate == 0))
        for (i = [0:len(segments_in_order) * duplicates - 2]) {
            pitch = mw_stack_pitch();
            lower_at = compute_segment_position_stacked(i, mw_segi(i), mw_flip(i));
            upper_at = compute_segment_position_stacked(i + 1, mw_segi(i + 1), mw_flip(i + 1));
            band_bottom = pitch * i + _profile_height;
            band_top = pitch * (i + 1) - _extra_height;
            color(Stacked_Separator_Color) intersection() {
                translate([lower_at.x, lower_at.y, band_top - _profile_height]) mw_piece(i);
                translate([upper_at.x, upper_at.y, band_bottom + _extra_height]) mw_piece(i + 1);
            }
        }
}"""

TEST_ENTRIES = ["mw_assembly_view", "mw_plate_1"]
# gridflock parameter sets under which mw_assembly_view must match gridflock's own main().
UPSTREAM_CHECKS = [
    {},
    {"hollow": "true", "connector_edge_puzzle": "true", "connector_intersection_puzzle": "false"},
    {"stacked_print": "true", "stacked_print_duplicates": "2"},
    {"magnets": "true", "plate_size": "[200, 150]", "bed_size": "[120, 120]"},
    {"vertical_screw_style": "1", "vertical_screw_plate_corners": "true", "vertical_screw_other": "true"},
]


class BuildError(Exception):
    pass


# ---- OpenSCAD parser ----

TOKEN_RE = re.compile(r"""
    (?P<ws>\s+)
  | (?P<comment>//[^\n]*|/\*.*?\*/)
  | (?P<inc>\b(?:include|use)\s*<[^>\n]*>)
  | (?P<str>"(?:\\.|[^"\\])*")
  | (?P<num>(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)
  | (?P<id>\$?[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op><=|>=|==|!=|&&|\|\||.)
""", re.S | re.X)
OPEN, CLOSE = {"(": ")", "[": "]", "{": "}"}, {")", "]", "}"}


class Tok(NamedTuple):
    kind: str
    text: str
    start: int
    end: int


class Stmt(NamedTuple):
    kind: str  # include, module, function, assign or geometry
    name: str  # the name defined, or the first one instantiated
    lo: int  # token range [lo, hi)
    hi: int


class Scad:
    """Significant tokens of one OpenSCAD source, with helpers to find its structure by name."""

    def __init__(self, text, origin):
        self.text, self.origin, self.toks = text, origin, []
        for m in TOKEN_RE.finditer(text):
            if m.lastgroup not in ("ws", "comment"):
                self.toks.append(Tok(m.lastgroup, m.group(), m.start(), m.end()))

    def fail(self, what, i):
        line = self.text.count("\n", 0, self.toks[min(i, len(self.toks) - 1)].start) + 1
        raise BuildError(f"{self.origin}:{line}: {what}")

    def span(self, lo, hi):
        return self.text[self.toks[lo].start:self.toks[hi - 1].end]

    def match(self, i):
        """Index of the bracket closing the one at token i."""
        want, depth = OPEN[self.toks[i].text], 0
        for j in range(i, len(self.toks)):
            t = self.toks[j].text
            depth += t in OPEN
            depth -= t in CLOSE
            if depth == 0:
                if t != want:
                    break
                return j
        self.fail(f"unbalanced {self.toks[i].text!r}", i)

    def statements(self, lo=0, hi=None):
        """Split [lo, hi) into statements: each ends at a `;` or a `{...}` block outside any brackets."""
        hi = len(self.toks) if hi is None else hi
        out, i = [], lo
        while i < hi:
            start = i
            while True:
                if i >= hi:
                    self.fail("unterminated statement", start)
                t = self.toks[i].text
                i = self.match(i) + 1 if t in OPEN else i + 1
                if t in (";", "{") and not (i < hi and self.toks[i].text == "else"):
                    break
            out.append(self.classify(start, i))
        return out

    def classify(self, lo, hi):
        t = self.toks
        if t[lo].kind == "inc":
            return Stmt("include", "", lo, hi)
        if t[lo].text in ("module", "function") and t[lo + 1].kind == "id":
            return Stmt(t[lo].text, t[lo + 1].text, lo, hi)
        if t[lo].kind == "id" and lo + 1 < hi and t[lo + 1].text == "=":
            return Stmt("assign", t[lo].text, lo, hi)
        return Stmt("geometry", next((x.text for x in t[lo:hi] if x.kind == "id"), ""), lo, hi)

    def params(self, stmt):
        """Parameter names of a module or function definition, and the token range of its parentheses."""
        open_ = stmt.lo + 2
        close = self.match(open_)
        names, i = [], open_ + 1
        while i < close:
            names.append(self.toks[i].text)
            while i < close and self.toks[i].text != ",":
                i = self.match(i) + 1 if self.toks[i].text in OPEN else i + 1
            i += 1
        return names, open_, close

    def body(self, stmt):
        """Statements inside a module definition's, or a for/if's, braces, and the braces' positions."""
        open_ = next((i for i in range(stmt.lo, stmt.hi) if self.toks[i].text == "{"), None)
        if open_ is None:
            self.fail(f"expected a {{...}} block in {stmt.name}", stmt.lo)
        close = self.match(open_)
        return self.statements(open_ + 1, close), open_, close

    def calls(self, name, lo, hi):
        """Token ranges of every call to `name` within [lo, hi)."""
        return [(i, self.match(i + 1) + 1) for i in range(lo, hi - 1)
                if self.toks[i].text == name and self.toks[i + 1].text == "("
                and (i == 0 or self.toks[i - 1].text not in ("module", "function"))]

    def value(self, stmt):
        """Expression of an assignment, without the trailing `;`."""
        return self.span(stmt.lo + 2, stmt.hi - 1)


def edit(text, edits):
    """Apply non-overlapping (start, end, replacement) character edits."""
    for start, end, new in sorted(edits, reverse=True):
        text = text[:start] + new + text[end:]
    return text


def indent_tail(text, prefix):
    """Indent every line but the first, which continues an already indented line."""
    first, *rest = text.split("\n")
    return "\n".join([first] + [prefix + l if l.strip() else l for l in rest])


# ---- gridflock transforms ----

class Upstream(NamedTuple):
    source: str  # gridflock.scad with segment_core renamed and top-level geometry dropped
    mw_main: str
    docs_source: str  # gridflock.scad with only segment_core renamed, still renderable on its own


def locate_loop(scad, main):
    """main()'s statements, and the one placing the segments: the `for` whose body calls segment()."""
    stmts = scad.body(main)[0]
    loops = [s for s in stmts if scad.toks[s.lo].text == "for" and scad.calls("segment", s.lo, s.hi)]
    if len(loops) != 1:
        scad.fail(f"main() has {len(loops)} `for` loops calling segment(), expected one", main.lo)
    return stmts, loops[0]


def check_upstream(scad, deps):
    """Report every symbol listed in UPSTREAM that gridflock no longer defines, all at once."""
    top = scad.statements() + [s for d in deps for s in d.statements()]
    defined = {k: {s.name for s in top if s.kind == k} for k in ("assign", "function", "module")}
    missing = []
    for group, kind in [("parameters", "assign"), ("constants", "assign"), ("functions", "function"),
                        ("modules", "module")]:
        missing += [f"{group}: {n}" for n in UPSTREAM[group] if n not in defined[kind]]
    main = next((s for s in scad.statements() if s.kind == "module" and s.name == "main"), None)
    if main is not None:
        stmts, loop = locate_loop(scad, main)
        main_names = {s.name for s in stmts if s.kind in ("assign", "function")}
        loop_names = {s.name for s in scad.body(loop)[0] if s.kind == "assign"}
        missing += [f"main() locals: {n}" for n in UPSTREAM["main() locals"] if n not in main_names]
        missing += [f"main() segment loop locals: {n}" for n in UPSTREAM["main() segment loop locals"]
                    if n not in loop_names]
    if missing:
        raise BuildError("gridflock no longer defines what makerworld/ depends on:\n  " + "\n  ".join(missing))


def generate_mw_main(scad, main):
    params, p_open, p_close = scad.params(main)
    stmts, loop = locate_loop(scad, main)
    _, open_, close = scad.body(main)
    loop_start, loop_end = scad.toks[loop.lo].start, scad.toks[loop.hi - 1].end
    planning = scad.text[scad.toks[open_].end:loop_start] + scad.text[loop_end:scad.toks[close].start]

    header_open = loop.lo + 1
    loop_body = scad.body(loop)[0]
    assigns = [s for s in loop_body if s.kind == "assign"]
    segment = [c for s in loop_body for c in scad.calls("segment", s.lo, s.hi)]
    if len(segment) != 1:
        scad.fail(f"main()'s segment loop calls segment() {len(segment)} times, expected once", loop.lo)

    inner = " " * 8
    return string.Template(MW_MAIN).substitute(
        params=", ".join(([scad.span(p_open + 1, p_close)] if params else []) + ["mw_plate = undef"]),
        planning="    " + planning.strip(),
        loop=indent_tail(scad.span(loop.lo, loop.hi), "    "),
        header=scad.span(header_open, scad.match(header_open) + 1),
        i=scad.toks[header_open + 1].text,
        locals="\n".join(inner + scad.span(s.lo, s.hi) for s in assigns),
        lets=",\n".join(inner + f"{s.name} = {scad.value(s)}" for s in assigns),
        segment=scad.span(*segment[0]),
    )


def check_overrides(scad, overrides):
    """An override must take exactly the parameters of the upstream module it wraps."""
    ups = {s.name: s for s in scad.statements() if s.kind == "module"}
    ours = {s.name: s for s in overrides.statements() if s.kind == "module"}
    for name in WRAPPED:
        if name not in ours:
            raise BuildError(f"overrides.scad: does not define {name}")
        theirs_p, ours_p = scad.params(ups[name])[0], overrides.params(ours[name])[0]
        if theirs_p != ours_p:
            raise BuildError(f"overrides.scad: {name}({', '.join(ours_p)}) no longer matches "
                             f"gridflock's {name}({', '.join(theirs_p)})")


def transform(deps):
    text = (ROOT / "gridflock.scad").read_text()
    scad = Scad(text, "gridflock.scad")
    check_upstream(scad, deps)
    check_overrides(scad, Scad((HERE / "overrides.scad").read_text(), "makerworld/overrides.scad"))
    top = scad.statements()
    main = next(s for s in top if s.kind == "module" and s.name == "main")
    renames = [(scad.toks[s.lo + 1].start, scad.toks[s.lo + 1].end, WRAPPED[s.name])
               for s in top if s.kind == "module" and s.name in WRAPPED]
    # Keep asserts and echos; anything else instantiated at top level is geometry PMM would render.
    geometry = [(scad.toks[s.lo].start, scad.toks[s.hi - 1].end, "")
                for s in top if s.kind == "geometry" and s.name not in ("assert", "echo")]
    return Upstream(edit(text, renames + geometry), generate_mw_main(scad, main), edit(text, renames))


# ---- flattening and parameter layout ----

def read(path):
    return path.read_text().splitlines()


DEFINITION_RE = re.compile(r"^\s*(module\s|function\s|\$?[A-Za-z_][A-Za-z0-9_]*\s*=)")


def strip_comments(line, state):
    """Blank out comments in `line`. `state` is a one-element list holding 'inside block comment'."""
    out = ""
    i = 0
    while i < len(line):
        if state[0]:
            end = line.find("*/", i)
            if end < 0:
                return out
            state[0], i = False, end + 2
        elif line.startswith("//", i):
            return out
        elif line.startswith("/*", i):
            state[0], i = True, i + 2
        else:
            out += line[i]
            i += 1
    return out


def definitions_only(lines):
    """Drop top-level geometry: `use` imports defs only, but some libraries have demo geometry at top level."""
    out, pending, statement, depth, state = [], [], [], 0, [False]
    for line in lines:
        code = strip_comments(line, state)
        if not statement and not code.strip():
            pending.append(line)
            continue
        statement.append(line)
        depth += sum(code.count(c) for c in "{([") - sum(code.count(c) for c in "})]")
        if depth > 0 or not code.rstrip().endswith((";", "}")):
            continue
        if DEFINITION_RE.match(statement[0]):
            out.extend(pending + statement)
        pending, statement = [], []
    return out + pending + statement


def flatten(path, seen, out, definitions=False):
    """Inline `include`/`use` recursively, emitting each file at most once."""
    path = path.resolve()
    if path in seen:
        return
    seen.add(path)
    body = []
    for line in read(path):
        m = INCLUDE_RE.match(line)
        if m:
            flatten(path.parent / m.group(2), seen, out, definitions=m.group(1) == "use")
        else:
            body.append(line)
    out.append(f"// ---- begin {path.relative_to(ROOT)} ----")
    out.extend(definitions_only(body) if definitions else body)
    out.append(f"// ---- end {path.relative_to(ROOT)} ----")


def split_params(lines):
    """Split gridflock.scad into (includes, params, body); a param's `//` comments above it are its customizer description."""
    end = next(i for i, l in enumerate(lines) if SECTION_RE.match(l) and SECTION_RE.match(l).group(1) == "Hidden")
    head, params, comment = [], {}, []
    for line in lines[:end]:
        if INCLUDE_RE.match(line):
            head.append(line)
            comment = []
        elif line.strip().startswith("//"):
            comment.append(line)
        elif (m := PARAM_RE.match(line)) and not line.startswith("_"):
            params[m.group(1)] = comment + [line]
            comment = []
        else:
            comment = []
    return head, params, lines[end:]


def drop_file_header(lines):
    """Drop the leading comment block of customizer.scad, which documents the build, not the model."""
    i = 0
    while i < len(lines) and lines[i].strip().startswith("//"):
        i += 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    return lines[i:]


def label(name):
    """Title_Case a parameter name; the customizer shows the variable name as the label."""
    return "_".join(word.capitalize() for word in name.split("_"))


def declare(name, line, value, alias=None):
    """Re-emit a gridflock declaration under its label, optionally with a different default."""
    m = DECL_RE.match(line)
    return f"{alias or label(name)}{m.group(2)}{m.group(3) if value is None else value}{m.group(4)}{m.group(5) or ''}".rstrip()


class Layout(NamedTuple):
    spec: list
    aliases: list
    dropped: set
    overridden: set


def expand(spec_lines, params):
    """Expand @include/@drop directives, tracking which parameters were accounted for."""
    out, aliases, used, dropped, overridden, errors, pending = [], [], set(), set(), set(), [], []
    for line in spec_lines:
        m = DIRECTIVE_RE.match(line.strip())
        if not m:
            if line.strip().startswith("//"):
                pending.append(line)
            else:
                out.extend(pending)
                pending = []
                out.append(line)
            continue
        kind, rest = m.group(1), m.group(2)
        names, _, value = (v.strip() for v in rest.partition("="))
        names, value, alias = names.split(), value or None, None
        # `as <Label>` keeps a published label when upstream renames the parameter behind it.
        if len(names) == 3 and names[1] == "as":
            names, alias = names[:1], names[2]
        if value is not None and len(names) != 1:
            errors.append(f"customizer.scad: a default may only be overridden for a single parameter: {rest!r}")
        # A comment directly above a single-parameter @include replaces gridflock's own description.
        description = pending if pending and len(names) == 1 and kind == "include" else None
        if description is None:
            out.extend(pending)
        pending = []
        for name in names:
            if name not in params:
                errors.append(f"customizer.scad: gridflock.scad has no parameter {name!r}")
                continue
            if name in used:
                errors.append(f"customizer.scad: parameter {name!r} listed twice")
            used.add(name)
            if kind == "include":
                out.extend(params[name][:-1] if description is None else description)
                out.append(declare(name, params[name][-1], value, alias))
                aliases.append(f"{name} = {alias or label(name)};")
                if value is not None:
                    overridden.add(name)
            else:
                dropped.add(name)
    out.extend(pending)
    for name in params:
        if name not in used:
            errors.append(f"customizer.scad: parameter {name!r} is neither @include'd nor @drop'ped")
    if errors:
        raise BuildError("\n".join(errors))
    return Layout(out, aliases, dropped, overridden)


def check_epilogue(lines, params, dropped):
    """The epilogue may only assign parameters customizer.scad drops; anything else is a typo or a rename."""
    errors = []
    for line in lines:
        m = PARAM_RE.match(line)
        if not m:
            continue
        name = m.group(1)
        if name not in params:
            errors.append(f"epilogue.scad: gridflock.scad has no parameter {name!r}")
        elif name not in dropped:
            errors.append(f"epilogue.scad: assigns {name!r}, which customizer.scad exposes instead of dropping")
    if errors:
        raise BuildError("\n".join(errors))


def drop_empty_sections(lines):
    """Remove section headers that ended up with no parameters under them."""
    out, i = [], 0
    while i < len(lines):
        if SECTION_RE.match(lines[i]):
            j = i + 1
            while j < len(lines) and not SECTION_RE.match(lines[j]):
                j += 1
            body = lines[i + 1:j]
            if any(PARAM_RE.match(b) for b in body):
                out.extend(lines[i:j])
            i = j
        else:
            out.append(lines[i])
            i += 1
    return out


def plate_modules():
    """PMM renders each mw_plate_N() on its own build plate and discards the empty ones."""
    out = [f"module mw_plate_{n}() {{ mw_main(mw_plate = {n - 1}); }}" for n in range(1, MW_PLATE_COUNT + 1)]
    # Turn the preview back to the orientation the user asked for; the plates themselves do not care.
    out += ["", "module mw_assembly_view() { rotate([0, 0, _mw_turned ? 90 : 0]) mw_main(); }"]
    return out


def ensure_paths():
    if not (ROOT / "paths" / "puzzle.scad").exists():
        subprocess.run(["just", "paths"], cwd=ROOT, check=True)


def gridflock():
    """gridflock.scad's parameters, its flattened includes as lines, and the transformed source."""
    ensure_paths()
    head, params, _ = split_params(read(ROOT / "gridflock.scad"))
    deps, seen = [], set()
    for line in head:
        m = INCLUDE_RE.match(line)
        flatten(ROOT / m.group(2), seen, deps, definitions=m.group(1) == "use")
    return params, deps, transform([Scad("\n".join(deps), "gridflock.scad's includes")])


def layout(params):
    return expand(drop_file_header(read(HERE / "customizer.scad")), params)


def build(output):
    params, deps, upstream = gridflock()
    spec = layout(params)
    epilogue = read(HERE / "epilogue.scad")
    check_epilogue(epilogue, params, spec.dropped)
    body = split_params(upstream.source.split("\n"))[2]
    while body and not body[-1].strip():
        body.pop()

    out = [HEADER.rstrip("\n"), ""]
    out += drop_empty_sections(spec.spec)
    # Everything below is implementation detail hidden from the customizer.
    out += ["", "/* [Hidden] */", ""]
    # Ahead of the epilogue: a top-level assignment can only see names defined before it.
    out += [f"_MW_PLATE_COUNT = {MW_PLATE_COUNT};", f"_MW_PART_GAP = {MW_PART_GAP};",
            f"_MW_BED_MARGIN = {MW_BED_MARGIN};", f"_MW_MIN_FILLER = {MW_MIN_FILLER};", f"_MW_GRID = {MW_GRID};", ""]
    out += ["// Map the capitalized customizer labels back onto gridflock's own variable names."]
    out += spec.aliases + [""]
    out += ["// ---- begin makerworld/epilogue.scad ----"]
    out += epilogue
    out += ["// ---- end makerworld/epilogue.scad ----", ""]
    out += deps
    out += body
    out += ["", "// ---- begin makerworld/overrides.scad ----"]
    out += read(HERE / "overrides.scad")
    out += ["// ---- end makerworld/overrides.scad ----", ""]
    out += ["// gridflock's main(), one build plate at a time; generated by makerworld/build.py."]
    out += upstream.mw_main.split("\n")
    out += ["", "// One segment per build plate; MakerWorld drops the plates that come out empty.",
            "// mw_assembly_view is the preview of the whole plate and is not part of the exported 3MF."]
    out += plate_modules()

    dest = ROOT / output
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(out) + "\n")
    exposed = sum(1 for l in spec.spec if PARAM_RE.match(l))
    print(f"{dest.relative_to(ROOT)}: {len(out)} lines, {exposed} exposed parameters, "
          f"{dest.stat().st_size / 1024:.0f} KiB")
    return dest


# ---- test and docs ----

def openscad(args, **kw):
    cmd = ["openscad", *map(str, args)]
    print("Running: " + shlex.join(cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


def stl_facets(path):
    """Facets of an ASCII STL as sorted vertex triples, so equal geometry compares equal in any order."""
    verts = [l.split()[1:] for l in path.read_text().splitlines() if l.strip().startswith("vertex")]
    return sorted(tuple(map(tuple, verts[i:i + 3])) for i in range(0, len(verts), 3))


def defines(values):
    return [a for k, v in values.items() for a in ("-D", f"{k}={v}")]


def check_against_upstream(model):
    """With makerworld's own options neutral, the preview must be exactly gridflock's main()."""
    params = split_params(read(ROOT / "gridflock.scad"))[1]
    spec = layout(params)
    defaults = {n: DECL_RE.match(params[n][-1]).group(3) for n in sorted(spec.dropped | spec.overridden)}
    neutral = {"Lightweight_Connector_Fill": "0", "_mw_turned": "false"}
    probe = model.with_name("upstream-check.scad")
    probe.write_text(model.read_text() + "mw_assembly_view();\n")
    with tempfile.TemporaryDirectory() as tmp:
        ours, theirs = pathlib.Path(tmp) / "ours.stl", pathlib.Path(tmp) / "theirs.stl"
        for config in UPSTREAM_CHECKS:
            unknown = set(config) - set(params)
            if unknown:
                raise BuildError(f"UPSTREAM_CHECKS: gridflock.scad has no parameter {', '.join(sorted(unknown))}")
            openscad(["-o", ours, "--export-format=asciistl", *defines(defaults | neutral | config), probe])
            openscad(["-o", theirs, "--export-format=asciistl", *defines(config), ROOT / "gridflock.scad"])
            a, b = stl_facets(ours), stl_facets(theirs)
            if a != b:
                raise BuildError(f"mw_assembly_view differs from gridflock's main() with {config or 'the defaults'}: "
                                 f"{len(a)} facets against {len(b)}")
            print(f"Matches gridflock's main() with {config or 'the defaults'}: {len(a)} facets", flush=True)


def test(extra):
    """Render each entry point PMM uses, failing on any warning, then compare the preview with upstream."""
    model = build(OUTPUT)
    probe = model.with_name("render-test.scad")
    for entry in TEST_ENTRIES:
        probe.write_text(model.read_text() + f"{entry}();\n")
        openscad(["-o", "/dev/null", "--export-format=stl", "--hardwarnings", *extra, probe])
    check_against_upstream(model)


def docs():
    """Render listing.html's images from gridflock.scad with the connector fill, which is what MakerWorld shows."""
    params, _, upstream = gridflock()
    options = [l for l in layout(params).spec if (m := PARAM_RE.match(l)) and m.group(1) in OVERRIDE_OPTIONS]
    model = ROOT / "build" / "makerworld" / "docs-model.scad"
    model.parent.mkdir(parents=True, exist_ok=True)
    model.write_text("\n".join([upstream.docs_source, *options, (HERE / "overrides.scad").read_text()]))
    # The model lives under build/, so its includes resolve against the repository root instead.
    env = dict(os.environ, OPENSCADPATH=str(ROOT))
    pattern = re.compile(r"^\s*<!--\s*openscad (.+?)\s*-->\s*$")
    images = HERE / "images"
    images.mkdir(exist_ok=True)
    written = []
    for line in read(HERE / "listing.html"):
        match = pattern.match(line)
        if not match:
            continue
        args = shlex.split(match.group(1))
        names = [a.split("=")[0] for p, a in zip(args, args[1:]) if p == "-D"]
        unknown = [n for n in names if n not in params and n not in OVERRIDE_OPTIONS]
        if unknown:
            raise BuildError(f"listing.html: gridflock.scad has no parameter {', '.join(map(repr, unknown))}")
        size = [] if any(a.startswith("--imgsize") for a in args) else ["--imgsize=1600,900"]
        cmd = ["--hardwarnings", "--projection=ortho", "--colorscheme=Starnight", "--render", *size, *args]
        if not any(".scad" in c for c in cmd):
            cmd.append(model)
        openscad(cmd, cwd=ROOT, env=env)
        written.append((ROOT / cmd[cmd.index("-o") + 1]).resolve())
    for f in images.iterdir():
        if f.resolve() not in written:
            f.unlink()


def main():
    ap = argparse.ArgumentParser(description="Package GridFlock for MakerWorld's Parametric Model Maker.")
    sub = ap.add_subparsers(dest="command")
    p_build = sub.add_parser("build", help="build the single-file model (default)")
    p_build.add_argument("-o", "--output", default=OUTPUT)
    p_test = sub.add_parser("test", help="build, render the entry points, and compare the preview with gridflock")
    p_test.add_argument("-D", dest="defines", action="append", default=[], metavar="VAR=VALUE",
                        help="passed on to openscad for the entry point renders, e.g. -D Magnets=true")
    sub.add_parser("docs", help="render the images referenced by listing.html")
    argv = sys.argv[1:]
    if not argv or argv[0] not in ("build", "test", "docs", "-h", "--help"):
        argv = ["build", *argv]
    args = ap.parse_args(argv)

    try:
        if args.command == "test":
            test([a for v in args.defines for a in ("-D", v)])
        elif args.command == "docs":
            docs()
        else:
            build(args.output)
    except BuildError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        print(f"error: {shlex.join(map(str, e.cmd))} failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
