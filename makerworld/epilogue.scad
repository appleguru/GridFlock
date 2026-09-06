// Maps simplified MakerWorld options onto GridFlock's real variables.
// Appended after the parameter block; OpenSCAD uses a variable's last assignment, so these win.

// [bed size, cutter keep-out, prime line strip off the front]. Bambu figures come from
// printable_area, bed_exclude_area and the start gcode template in BambuStudio's machine profiles.
// 12mm is the fallback where the purge geometry could not be read.
_BUILD_PLATES = [
    [[250, 220], [0, 0],   0],   // 0: Custom, overridden below
    [[180, 180], [0, 0],   0],   // 1: Bambu Lab A1 mini, purges off the front of the bed
    [[256, 256], [0, 0],   2],   // 2: Bambu Lab A1, purge line at y<=1
    [[256, 256], [18, 28], 12],  // 3: Bambu Lab P1P / P1S / X1C / X1E, purge lines to y=12
    [[256, 256], [0, 0],   12],  // 4: Bambu Lab P2S
    [[330, 320], [0, 0],   12],  // 5: Bambu Lab A2L
    [[350, 320], [0, 0],   0],   // 6: Bambu Lab H2D, purges off the front of the bed
    [[340, 320], [0, 0],   0],   // 7: Bambu Lab H2S, purges off the front of the bed
    [[250, 220], [0, 0],   12],  // 8: Prusa MK4 / Core One
    [[300, 330], [0, 0],   12],  // 9: Prusa Core One L
    [[180, 180], [0, 0],   12],  // 10: Prusa MINI+
    [[220, 220], [0, 0],   12],  // 11: Creality Ender 3 / K1
    [[260, 260], [0, 0],   12],  // 12: Creality K2
    [[256, 256], [0, 0],   12],  // 13: Elegoo Centauri Carbon
    [[320, 320], [0, 0],   12],  // 14: Elegoo Neptune 4 Plus
];

assert(Width > 42 && Depth > 42, "The plate has to be big enough for at least one 42mm cell.");
assert(Clearance >= 0, "Clearance may not be negative.");
assert(Plate_Margin >= 0, "Plate Margin may not be negative.");

// The clearance is taken off every side, so it comes off each dimension twice.
_mw_asked = [Width - Clearance*2, Depth - Clearance*2];
// gridflock splits x into evenly sized segments but lets y run to the full bed, so the same plate
// cuts into smaller pieces with its long side on x. The result is that rectangle turned a quarter
// turn, which fits the same space.
_mw_turned = _mw_asked.x < _mw_asked.y;
_mw_space = _mw_turned ? [_mw_asked.y, _mw_asked.x] : _mw_asked;
// 'Nothing' rounds down to whole cells, so there is no leftover to fill or pad in the first place.
plate_size = Edge_Style == 2
    ? [floor(_mw_space.x / _MW_GRID) * _MW_GRID, floor(_mw_space.y / _MW_GRID) * _MW_GRID]
    : _mw_space;
// Keeping clear of the bed edge covers both the prime line and cutter keep-outs and the poor
// adhesion right at the edge. It shrinks the bed for splitting and for packing alike.
// Presets lose a strip off the front to the prime and purge lines, and keep the cutter's corner
// clear. A custom size is taken at face value, for anyone who manages those themselves.
_mw_preset = _BUILD_PLATES[Build_Plate];
bed_size = (Build_Plate == 0 ? Build_Plate_Custom : _mw_preset[0] - [0, _mw_preset[2]])
    - [Plate_Margin, Plate_Margin] * 2;
_mw_keepout = Build_Plate == 0 ? [0, 0] : [_mw_preset[1].x, max(0, _mw_preset[1].y - _mw_preset[2])];

assert(bed_size.x > 42 && bed_size.y > 42, "Plate Margin leaves too little of the bed to fit a cell.");

connector_intersection_puzzle = Connector_Style == 1;
connector_edge_puzzle = Connector_Style == 2;

click = Click_Latch;
// A skeletonized plate has no material left to hold any of these, so they win over Lightweight.
lightweight = Lightweight && !Click_Latch && !magnets && solid_base == 0;

// An open edge is one dynamic filler cell of exactly the leftover width; the others leave no leftover.
filler_x = Edge_Style == 1 ? 2 : 0;
filler_y = Edge_Style == 1 ? 2 : 0;
filler_fraction = [2, 2];
// As small as gridfinity can cut, so a leftover becomes its own cell rather than being merged into
// the previous one, which would make that cell wider than a 42mm grid unit.
filler_minimum_size = [_MW_MIN_FILLER, _MW_MIN_FILLER];

// Padding all goes east/north, so the grid itself sits in the west/south corner.
alignment = Edge_Position == 0 ? [0.5, 0.5] : [0, 0];

// Not exposed: the test patterns are a development aid.
test_pattern = 0;

// Not exposed: openGrid adapters import() 3mf files that MakerWorld can't ship alongside the model.
adapter_north = false;
adapter_east = false;
adapter_south = false;
adapter_west = false;
adapter_mode = 11;

// Shelf-pack the segments onto build plates, rotating pieces upright, so the export needs as few
// plates as possible. Returns one [plate, position, rotated] per segment, in the order given.
function _mw_upright(s) = s.x > s.y ? [s.y, s.x, true] : [s.x, s.y, false];

function _mw_fit(shelves, w, h, bed_x, i) =
    i >= len(shelves) ? -1 :
    (shelves[i][2] >= h && shelves[i][3] + w <= bed_x ? i : _mw_fit(shelves, w, h, bed_x, i + 1));

function _mw_replace(list, idx, value) = [for (k = [0:len(list) - 1]) k == idx ? value : list[k]];

function _mw_shelf(items, i, bed, gap, keepout, shelves, acc) =
    i >= len(items) ? acc :
    let(
        w = items[i][0],
        h = items[i][1],
        hit = _mw_fit(shelves, w, h, bed.x, 0),
        last = len(shelves) - 1,
        stacked_y = last < 0 ? 0 : shelves[last][1] + shelves[last][2] + gap,
        fresh_plate = last >= 0 && stacked_y + h > bed.y,
        shelf = hit >= 0 ? shelves[hit] : [
            last < 0 ? 0 : (fresh_plate ? shelves[last][0] + 1 : shelves[last][0]),
            last < 0 || fresh_plate ? 0 : stacked_y, h, 0],
        moved = [shelf[0], shelf[1], shelf[2], shelf[3] + w + gap]
    ) _mw_shelf(items, i + 1, bed, gap, keepout,
        hit >= 0 ? _mw_replace(shelves, hit, moved) : concat(shelves, [moved]),
        concat(acc, [[items[i][3], shelf[0], shelf[3], shelf[1], w, h, items[i][2]]]));

// Centre each plate's content on the bed, so a partly filled plate is not stuck in one corner.
function _mw_extent(placed, plate, axis) =
    max([for (p = placed) if (p[1] == plate) p[2 + axis] + p[4 + axis]]);

// Nudge a plate away from the cutter's corner. Clearing either axis takes the corner out of play,
// so use whichever the plate has the slack for; packing is left alone and costs no extra plate.
function _mw_nudge(extent, bed, keepout) = let(
    slack = [bed.x - extent.x, bed.y - extent.y],
    need = [keepout.x - slack.x/2, keepout.y - slack.y/2]
) need.x <= 0 || need.y <= 0 ? [0, 0]
    : need.y <= slack.y/2 ? [0, need.y]
    : need.x <= slack.x/2 ? [need.x, 0]
    : [0, max(0, slack.y/2)];

function mw_pack(sizes, bed, gap, keepout = [0, 0]) = let(
    upright = [for (i = [0:len(sizes) - 1]) let(o = _mw_upright(sizes[i])) [o[0], o[1], o[2], i]],
    tallest_first = quicksort(upright, lte = function (a, b) a[1] >= b[1]),
    placed = _mw_shelf(tallest_first, 0, bed, gap, keepout, [], [])
) [for (i = [0:len(sizes) - 1]) let(
    p = [for (q = placed) if (q[0] == i) q][0],
    extent = [_mw_extent(placed, p[1], 0), _mw_extent(placed, p[1], 1)],
    nudge = _mw_nudge(extent, bed, keepout)
) [
    p[1],
    [p[2] + p[4]/2 - extent.x/2 + nudge.x, p[3] + p[5]/2 - extent.y/2 + nudge.y, 0],
    p[6],
]];

