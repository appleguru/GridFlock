# GridFlock for MakerWorld

Packages GridFlock for [MakerWorld's Parametric Model Maker](https://makerworld.com/en/makerlab/parametricModelMaker) (PMM), which takes a single `.scad` file. Same geometry, flattened into one file, with the options re-ordered for the customizer.

## Building

```sh
just makerworld        # -> build/makerworld/GridFlock.scad
just test-makerworld   # build it and check that it renders
```

Upload `build/makerworld/GridFlock.scad` to the Parametric Model Maker.

## Options

Always visible: **Width**, **Depth**, **Clearance**, **Build Plate**, **Lightweight**, **Click Latch**, **Edge Style**. The rest sit in tabs: Build Plate, Connectors, Edges, Lightweight, Magnets, Numbering, Plate Wall, Screws, Click Latch, Advanced.

- **Width**, **Depth** - inner size of the space the plate has to fit, in mm.
- **Clearance** - taken off all four sides. `Width 312, Clearance 2` gives a 308mm plate.
- **Edge Style** - what happens to the space left over after whole 42mm cells. `Open` puts it in one narrow cell that still holds a bin, `Solid` leaves plain plate, `Nothing` rounds the plate down instead.
- **Edge Position** - centres a solid edge, or pushes the grid into the south-west corner. An open edge cell always sits at the far side, so this does not apply to it.
- **Click Latch** - magnet-free bin grip, Arc style by default. ClickGroove is under the Click Latch tab.
- **Lightweight** - on by default, and ignored when magnets, a solid base or the latch are on, since those need the material it would remove.

Four options replace gridflock's own; everything else is exposed as declared. [`epilogue.scad`](epilogue.scad) maps them back.

| MakerWorld | GridFlock |
| --- | --- |
| `Width`, `Depth`, `Clearance` | `plate_size` |
| `Build_Plate`, `Build_Plate_Custom`, `Plate_Margin` | `bed_size` |
| `Connector_Style` | `connector_intersection_puzzle`, `connector_edge_puzzle` |
| `Edge_Style`, `Edge_Position` | `filler_x`/`filler_y`, `filler_fraction`, `filler_minimum_size`, `filler_solid`, `alignment` |
| `Click_Latch`, `Lightweight` | `click`, `lightweight` |

## How the layout is defined

[`customizer.scad`](customizer.scad) is the parameter layout, not a renderable file:

- Ordinary lines are copied into the generated parameter block verbatim.
- `@include <names>` copies declarations out of `gridflock.scad`, so defaults and ranges stay in sync.
- `@include <name> = <value>` changes a default.
- A comment above a single-parameter `@include` replaces gridflock's description.
- `@drop <names>` marks a parameter as deliberately not exposed.
- Every gridflock parameter must appear in exactly one directive, so the build fails when a new one turns up unhandled.

Worth knowing when editing it:

- Labels are capitalized (`magnet_diameter` becomes `Magnet_Diameter`) because the customizer shows the variable name.
- Descriptions share a line with the label, wrap at roughly 30 characters, and lose any `/`.
- PMM cannot show a parameter conditionally, which is why the custom bed size has its own tab.
- `build.py` patches `main()` to render one plate at a time and strips the `test_pattern` dispatch PMM must not see. The patches are anchored on exact lines of `gridflock.scad` and fail loudly if upstream moves them.

## Plates

- Segments go onto `mw_plate_N()` modules, replacing PMM's auto-arrange, which fails much above one bed.
- First-fit-decreasing shelf packing, pieces rotated upright: two plates for the 312x277 default on a 256x256 bed, eleven for 600x400 on an A1 mini.
- PMM discards empty plates, so the count follows the options.
- Footprints include twice the connector margin; parts sit 2mm apart and 2mm clear of the bed edge.
- **Plate Margin** shrinks the bed before both splitting and packing, keeping parts away from the prime line, the cutter and the poorly adhering edge. It defaults to 0, because raising it often costs an extra plate without changing how the plate is split.
- `mw_plate_1` to `mw_plate_24`. Needing more fails the render rather than dropping pieces.
- `mw_assembly_view()` previews the assembled plate and is not exported.
- Stacked printing skips packing and stays on one plate.

## Experimental: multimaterial separator

**Stacked Separator** fills the gap between stacked pieces with `Stacked_Separator_Color`, so they peel apart instead of fusing - PETG under PLA, or PLA under PETG. PMM turns each colour in the model into its own filament.

- Only where the two pieces actually touch, never spanning a cell opening, so nothing prints in mid air.
- 0.19cm3 across three interfaces on the 312x277 default, 0.25mm thick, one layer at 0.2mm.
- Contact area follows the options: skeletonized plates touch along their walls only.
- Purge volumes cannot be set from the script, so raise them in Studio.
- [Filament order is not stable between exports](https://forum.bambulab.com/t/parametric-model-maker-colour-bug/173000), so check it after each generate.

## Known limitations

- **No STL download.** Defining `mw_plate_*` modules makes PMM offer 3MF only. The [web generator](https://gridflock.yawk.at/) still produces STLs.
- **openGrid adapters are unavailable.** They `import()` `.3mf` files that PMM cannot ship alongside the model.
- **The preview's build plate is not the Build Plate option.** The viewport printer picker is viewer-side and a script cannot set it, so pick the same printer in both.

## Uploading

Upload as a **Derivative/Remix**, not an Original, and link this repository as the source. GridFlock is dual-licensed under MIT and CC-BY 4.0; the generated file carries that notice along with the MIT notice for the bundled [Gridfinity Rebuilt](https://github.com/kennetek/gridfinity-rebuilt-openscad), and both must stay in the model description.
