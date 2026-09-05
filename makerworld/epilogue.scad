// Maps simplified MakerWorld options onto GridFlock's real variables.
// Appended after the parameter block; OpenSCAD uses a variable's last assignment, so these win.

_BUILD_PLATES = [
    [250, 220], // 0: Custom, overridden below
    [180, 180], // 1: Bambu Lab A1 mini
    [256, 256], // 2: Bambu Lab A1 / P1 / X1
    [300, 320], // 3: Bambu Lab H2D
    [340, 340], // 4: Bambu Lab H2S
    [250, 220], // 5: Prusa MK4 / Core One
    [300, 330], // 6: Prusa Core One L
    [180, 180], // 7: Prusa MINI+
    [220, 220], // 8: Creality Ender 3 / K1
    [260, 260], // 9: Creality K2
    [256, 256], // 10: Elegoo Centauri Carbon
    [320, 320], // 11: Elegoo Neptune 4 Plus
];

assert(Width > 42 && Depth > 42, "The plate has to be big enough for at least one 42mm cell.");
assert(Clearance >= 0, "Clearance may not be negative.");

// The clearance is taken off every side, so it comes off each dimension twice.
plate_size = [Width - Clearance*2, Depth - Clearance*2];
bed_size = Build_Plate == 0 ? Build_Plate_Custom : _BUILD_PLATES[Build_Plate];

connector_intersection_puzzle = Connector_Style == 1;
connector_edge_puzzle = Connector_Style == 2;

click = Click_Latch;
// A skeletonized plate has no material left to hold any of these, so they win over Lightweight.
lightweight = Lightweight && !Click_Latch && !magnets && solid_base == 0;

// An open edge is one dynamic filler cell of exactly the leftover width; a solid edge is plain padding.
filler_x = Edge_Style == 1 ? 2 : 0;
filler_y = Edge_Style == 1 ? 2 : 0;
filler_fraction = [2, 2];
filler_minimum_size = [15, 15];
filler_solid = false;

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

function _mw_shelf(items, i, bed, gap, shelves, acc) =
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
    ) _mw_shelf(items, i + 1, bed, gap,
        hit >= 0 ? _mw_replace(shelves, hit, moved) : concat(shelves, [moved]),
        concat(acc, [[items[i][3], shelf[0], shelf[3], shelf[1], w, h, items[i][2]]]));

// Centre each plate's content on the bed, so a partly filled plate is not stuck in one corner.
function _mw_extent(placed, plate, axis) =
    max([for (p = placed) if (p[1] == plate) p[2 + axis] + p[4 + axis]]);

function mw_pack(sizes, bed, gap) = let(
    upright = [for (i = [0:len(sizes) - 1]) let(o = _mw_upright(sizes[i])) [o[0], o[1], o[2], i]],
    tallest_first = quicksort(upright, lte = function (a, b) a[1] >= b[1]),
    placed = _mw_shelf(tallest_first, 0, bed, gap, [], [])
) [for (i = [0:len(sizes) - 1]) let(p = [for (q = placed) if (q[0] == i) q][0]) [
    p[1],
    [p[2] + p[4]/2 - _mw_extent(placed, p[1], 0)/2, p[3] + p[5]/2 - _mw_extent(placed, p[1], 1)/2, 0],
    p[6],
]];

