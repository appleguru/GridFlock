// MakerWorld versions of gridflock modules. build.py renames each upstream original to _gf_<name>,
// and fails the build when an override's parameters no longer match the original's.

// Lightweight plates keep a solid block around every connector, instead of growing it out of a
// single wall with air behind it.
module segment_core(trace, size, padding, connector, global_cell_index, global_cell_count) {
    difference() {
        _gf_segment_core(trace, size, padding, connector, global_cell_index, global_cell_count);
        if (Lightweight_Connector_Fill > 0)
            translate([0, 0, -_extra_height]) linear_extrude(height = _total_height)
                offset(Lightweight_Connector_Fill) {
                    if (connector_intersection_puzzle) {
                        segment_intersection_connectors(true, trace, size, padding, connector);
                        segment_intersection_connectors(false, trace, size, padding, connector);
                    }
                    if (connector_edge_puzzle) {
                        segment_edge_connectors(true, trace, size, padding, connector);
                        segment_edge_connectors(false, trace, size, padding, connector);
                    }
                }
    }
}
