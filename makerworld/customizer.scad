// Parameter layout for MakerWorld, built by makerworld/build.py into the generated model's parameter block.
// Lines starting with `@` are directives; every gridflock.scad parameter must appear in exactly one:
//   @include <name>...        copy the parameter's declaration verbatim from gridflock.scad
//   @include? <name>...       same, but skip a parameter gridflock.scad does not declare
//   @include <name> = <value> copy the declaration but change its default
//   @drop <name>...           this gridflock parameter is deliberately not exposed
// A comment directly above a single-parameter @include replaces gridflock's own description.
// Descriptions share one line with the label in the MakerWorld UI, so keep them short; `/` is stripped.
// Parameters are exposed under a capitalized label; the build maps them back to gridflock's names.
// MakerWorld shows parameters before the first section header, then one tab per section, in order.

// Width of the space or drawer, in mm
Width = 312;
// Depth of the space or drawer, in mm
Depth = 277;
// Some wiggle room so plate fits. 2mm recommended
Clearance = 2; // 0.1
// Size of the build plate on your printer
Build_Plate = 2; // [0:Custom, 1:Bambu Lab A1 mini (180x180), 2:Bambu Lab A1 / P1 / X1 (256x256), 3:Bambu Lab H2D (300x320), 4:Bambu Lab H2S (340x340), 5:Prusa MK4 / Core One (250x220), 6:Prusa Core One L (300x330), 7:Prusa MINI+ (180x180), 8:Creality Ender 3 / K1 (220x220), 9:Creality K2 (260x260), 10:Elegoo Centauri Carbon (256x256), 11:Elegoo Neptune 4 Plus (320x320)]
// Thin-wall plate. Off with magnets or latch
Lightweight = true;
// Grip bins without magnets. Use PETG
Click_Latch = false;
// What fills the leftover space
Edge_Style = 1; // [0:Solid, 1:Open]

/* [Custom Build Plate] */

// Bed size, mm. For Custom only
Build_Plate_Custom = [250, 220];

/* [Connectors] */

// How the printed pieces lock together
Connector_Style = 1; // [0:None, 1:Intersection puzzle, 2:Edge puzzle]
// 0 loose, 1 tight
@include intersection_puzzle_fit

/* [Edges] */

// Only applies to a solid edge
Edge_Position = 0; // [0:Centered, 1:One side]

/* [Lightweight] */

// Horizontal wall thickness, mm
@include? lightweight_wall
// Anchor around connectors
@include? lightweight_connector_fill
// Drop the 0.7mm lip, no overhang
@include? remove_bottom_lip

/* [Magnets] */

// Friction-fit magnets in each cell
@include magnets
@include magnet_style magnet_frame_style magnet_diameter magnet_height
// Wall above. Keep small
@include magnet_top
// Floor below. Keep small
@include magnet_bottom
// Frame strength around the magnet
@include magnet_border
@include magnet_release_width

/* [Numbering] */

// Emboss a segment number
@include numbering
@include number_depth number_size number_font
// Reduced size on narrow segments
@include number_squeeze_size

/* [Plate Wall] */

// Per edge: N, E, S, W. Added to size
@include plate_wall_thickness
// Above and below the plate
@include plate_wall_height
// Per corner: SW, NW, NE, SE
@include plate_wall_above
// Per corner: SW, NW, NE, SE
@include plate_wall_below

/* [Screws] */

// At the plate corners
@include vertical_screw_plate_corners
// At the plate edges
@include vertical_screw_plate_edges
// Not plate corners
@include vertical_screw_segment_corners
// Interferes with connectors
@include vertical_screw_segment_edges
@include vertical_screw_other vertical_screw_diameter
// Head diameter, height
@include vertical_screw_countersink_top
// Head diameter, height
@include vertical_screw_counterbore_top
// Cells from the edge
@include vertical_screw_plate_corner_inset
// Cells from the edge
@include vertical_screw_segment_corner_inset
// Screws on the north edge
@include horizontal_screw_wall_north
// Screws on the east edge
@include horizontal_screw_wall_east
// Screws on the south edge
@include horizontal_screw_wall_south
// Screws on the west edge
@include horizontal_screw_wall_west
// Radius of horizontal screws
@include horizontal_screw_diameter
// Head diameter, height
@include horizontal_screw_countersink_top
// Head diameter, height
@include horizontal_screw_counterbore_top
// Shift the screw location
@include horizontal_screw_offset
// Gridfinity Refined cutouts
@include thumbscrews
@include thumbscrew_diameter

/* [Click Latch] */

// Arc is more robust than ClickGroove
@include click_style = 0
@include clickgroove_gap_length
// Tab that engages the groove
@include clickgroove_tab_length
// Thickness, from the profile bottom
@include clickgroove_strength
// Wall behind the latch
@include clickgroove_wall_strength
// How far the tab protrudes
@include clickgroove_depth
// Reach into the bin area
@include click1_distance
@include click1_steepness click1_outer_length
// Straight middle piece
@include click1_inner_length
@include click1_height
// Thickness, from the profile bottom
@include click1_strength
// Wall behind the latch
@include click1_wall_strength

/* [Advanced] */

@include solid_base
// 4mm matches the gridfinity cell
@include plate_corner_radius
// Per edge: N, E, S, W
@include bottom_chamfer
// Per edge: N, E, S, W
@include top_chamfer
// Cut the top, for upside-down prints
@include top_slice
// Per edge: N, E, S, W. Can be negative
@include edge_adjust
// Per cell: c normal, s solid, e empty
@include cell_override
@include edge_puzzle_count
// Male connector, main piece
@include edge_puzzle_dim
// Male connector, bridge to plate
@include edge_puzzle_dim_c
// Extra clearance on the female side
@include edge_puzzle_gap
// Border on the female socket
@include edge_puzzle_magnet_border
@include edge_puzzle_magnet_border_width
// Keep every piece connected!
@include edge_puzzle_height_female
// Male is smaller by this
@include edge_puzzle_height_male_delta
// Ideal is equal, Incremental full-size
@include x_segment_algorithm
// Incremental only. 0 is automatic
@include x_column_count_first
// Odd and even columns. 0 is automatic
@include y_row_count_first
// Print edge padding separately
@include separate_edge_padding
// Stack segments in one print
@include stacked_print
// Segments align to this multiple
@include stacked_print_layer_height
// In layers
@include stacked_print_min_gap
// Copies of each segment in the stack
@include stacked_print_duplicates
@include stacked_print_flip_first stacked_print_flip
// Cut from the top for contact area
@include stacked_print_slice
// Experimental peel-away layer
Stacked_Separator = false;
// PETG under PLA, or PLA under PETG
Stacked_Separator_Color = "#00A0A0"; // color

/* [Hidden] */

// Replaced by Width / Depth / Clearance and Build Plate / Build Plate Custom above.
@drop plate_size bed_size
// Replaced by Connector_Style above.
@drop connector_intersection_puzzle connector_edge_puzzle
// Replaced by Lightweight and Click_Latch above.
@drop? lightweight
@drop click
// Replaced by Edge_Style and Edge_Position above.
@drop filler_x filler_y filler_fraction filler_minimum_size alignment
@drop? filler_solid
// Debugging aid, not useful in a customizer.
@drop test_pattern
// openGrid adapters import() 3mf files; MakerWorld only allows a model's own uploaded defaults, so use the web generator instead.
@drop adapter_north adapter_east adapter_south adapter_west adapter_mode
