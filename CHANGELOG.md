# Changelog 0.3.1

## ADDED
- `netlist_carpentry.Module.change_instance_type()` method to change the type of an instance (by creating a new instance under the hood and discarding the old one, as the new object may be of another class)

## CHANGED
- `netlist_carpentry.utils.gate_lib_base_classes.LibUtils.p2ws2v()` → `netlist_carpentry.utils.gate_lib_base_classes.PrimitiveGate.p2ws2v()`
- `netlist_carpentry.utils.gate_lib_base_classes.LibUtils.get_unconnected_idx()` → `netlist_carpentry.utils.gate_lib_base_classes.PrimitiveGate._get_unconnected_idx()` (now also protected)
- `netlist_carpentry.utils.initialize_logging()` no longer takes `no_file` argument, instead set `output_dir` to None for the same effect
- `netlist_carpentry.Circuit.uniquify()` now returns a mapping of instance paths to new module names

## FIXED
- `netlist_carpentry.Instance.split()` was discarding instance parameters completely, now copies parameters and updates instance width accordingly
- `netlist_carpentry.Circuit.uniquify()` no longer crashes after `netlist_carpentry.Instance.split()` was run (fixed split instances missing in `netlist_carpentry.Circuit.instances`)

## REMOVED
- `netlist_carpentry.CFG.output_dir`
- `netlist_carpentry.LOG.finish()` (unused and fragile, Log.report() can be used instead)
- `netlist_carpentry.LOG.fatal_and_exit()` (raise an appropriate exception instead)
- `netlist_carpentry.utils.gate_lib_base_classes.LibUtils` (previous methods are now integrated into `gate_lib_base_classes.PrimitiveGate`)

# Older Versions

## 0.3.0 (2026-01-22)

### Highlights
- Improved graph visualization by extending the current implementation with interactive graphs, powered by [Dash Cytoscape](https://dash.plotly.com/cytoscape)
    - Graphs can be visualized both as static images and interactive widgets
    - Supported in both Jupyter notebooks and web applications
    - Multiple ways to customize graphs, including node/edge labels, colors, sizes
- Support for VCD data annotation and analysis
- Various API simplifications and bug fixes

### ADDED
- Interactive circuit graphs powered by **dash‑cytoscape** (see `netlist_carpentry.core.graph.visualization` package)
- `netlist_carpentry.ModuleGraph` class (sub‑class of `networkx.MultiDiGraph`) with helper methods `get_data()`/`set_data()` (for additional node and edge data)
- `netlist_carpentry.Circuit.uniquify()` - generates a unique module definition per instance
- `PrimitiveGate.verilog_net_map` property to each gate of the gate lib, which returns a dictionary mapping instance ports to Verilog wire names (i.e. the wire connected to this specific port of the gate instance)
- VCD parsing/annotation support via `netlist_carpentry.io.vcd` (uses **pywellen**)
- Log‑level control: `netlist_carpentry.LOG.set_log_level()`
- Constant propagation for FFs and latches
- New `netlist_carpentry.routines.check` package with `comb_loops` and `fanout_analysis` modules

### CHANGED
- `netlist_carpentry.io.read.gen_nl.generate_json_netlist()` → `netlist_carpentry.io.read.read_utils.generate_json_netlist()`
- `netlist_carpentry.routines.opt.loadless_wires` → `netlist_carpentry.routines.opt.loadless`
- `netlist_carpentry.routines.opt.driverless_instances` → `netlist_carpentry.routines.opt.driverless`
- `netlist_carpentry.utils.gate_lib_factory` → `netlist_carpentry.utils.gate_factory`
- `netlist_carpentry.Module.graph` is no longer a plain `networkx.MultiDiGraph`; it is now `netlist_carpentry.ModuleGraph`, which extends `networkx.MultiDiGraph` and adds convenience methods
- Removed `netlist_carpentry.core.graph.utils.all_edges()` - now a method of `netlist_carpentry.ModuleGraph`
- Renamed attribute `ntype_info` on `netlist_carpentry.ModuleGraph` to `nsubtype`
- `netlist_carpentry.Circuit.module_instances` → `netlist_carpentry.Circuit.instances`
- `netlist_carpentry.core.graph.visualization` is now a package rather than a single module, containing the former plotting code
- `netlist_carpentry.Module`

### FIXED
- Multiple bugs in the Verilog rendering of generated Scan‑FFs
- Elements were limited to names that are valid Verilog identifiers - now all names are sanitized
- Documentation notebooks have been restructured and expanded (see built Documentation or the raw notebooks in `docs/src/user_guide` and in `docs/src/dev_guide`)

### REMOVED
- Graph caching logic - was unreliable, graph is now always rebuilt upon calling, dropped caching completely


## 0.2.0 (2025-11-27)

### ADDED
- **Gate‑library enhancements**
  - `a_signed` (and `b_signed` for two‑input gates) properties on every gate from `netlist_carpentry.utils.gate_lib` that supports signed inputs
  - New D‑FF factory helpers in `netlist_carpentry.utils.gate_factory`
  - Scan‑FF gate added to the library
- **Convenience properties**
  - `netlist_carpentry.Port.module` - returns the containing module for any port
    - For a Module Port, this is the direct parent of the port
    - For an Instance Port, this is the parent of the instance to which this port belongs
  - `netlist_carpentry.Module.circuit` - gives the circuit owning the module
  - `netlist_carpentry.Instance.module_definition` - returns the module definition for a module instance (or `None` for gate instances)
  - `netlist_carpentry.NetlistElement.has_circuit` - flags whether the object is attached to a circuit (could be false if the object was just created for exploration purposes)
  - `netlist_carpentry.Instance.signals` - dictionary of current signals on each port
  - `netlist_carpentry.Instance.has_unconnected_port_segments` - checks for any unconnected ports
  - `netlist_carpentry.Module.copy_instance()` - clones an instance under a new name
  - `netlist_carpentry.Module.replace()` - substitutes an instance with another
  - `netlist_carpentry.Instance.split()` - splits an n‑bit instance into n 1‑bit instances, given that the instance type supports splitting (e.g. standard binary gates do, arithmetic gates do not)
  - `netlist_carpentry.PortSegment.ws` - returns the wire segment connected to the port segment
  - `netlist_carpentry.PortSegment.loads()` - returns the loads of a port segment
  - `netlist_carpentry.Port.connected_wire_segments` - now returns a dictionary `{segment-index: wire‑segment‑path}` instead of just the wire segment paths as a set
- **Graph & traversal helpers**
  - `netlist_carpentry.Module.make_chain()` - builds a chain of instances by connecting specified ports
  - `netlist_carpentry.Module.flatten()` - flattens all sub‑modules (optionally recursively)
- **New routine & package**
  - `netlist_carpentry.routines.dft.scan_chain_insertion` - predefined scan‑chain insertion routine
  - Package `netlist_carpentry.routines.floodfill` contains the former `cascading_or_replacement` script
- **Core enum refactor**
  - `netlist_carpentry.core.direction`, `netlist_carpentry.core.signal`, and `netlist_carpentry.core.netlist_elements.element_type` moved to `netlist_carpentry.core.enums`

### CHANGED
- `netlist_carpentry.api` → `netlist_carpentry.io`
- `netlist_carpentry.core.opt` → `netlist_carpentry.routines`
- `cascading_or_replacement` script moved to `netlist_carpentry.routines.floodfill`
- `netlist_carpentry.NetlistElement.set_name()` now updates the name in all parent hierarchies (removes the old entry entirely)
- `netlist_carpentry.Port.connected_wire_segments` now returns a mapping instead of a set of paths
- `netlist_carpentry.Instance.is_primitive` / `Instance.is_primitive_from_gatelib` renamed to `is_blackbox` / `is_primitive`
- `netlist_carpentry.CFG.simplify_escaped_identifiers` removed - escaped identifiers are now always simplified

### FIXED
- Wrong gate types were instantiated in the gate factory
- Wire handling: `netlist_carpentry.Wire.driver()` and `netlist_carpentry.WireSegment.driver()` behaved incorrectly
- `tie_signal` - now accepts integer values in `Port` and `PortSegment`
- Several bugs in the generated Verilog output
- `netlist_carpentry.PortSegment.loads()` now returns loads correctly
- `netlist_carpentry.Port.connected_wire_segments` returns now a dictionary of index‑path pairs instead of an unordered set (whoopsie)
- Missing parent references fixed in various utilities

### REMOVED
- `netlist_carpentry.utils.gate_lib.LibUtils.current_module` - traversal is now handled via the `parent` attribute of each instance
- Hashing support in `NetlistElement` and all subclasses (prevents accidental mutation in collections, since they can no longer be keys or set elements)


## 0.1.0 (2025-10-28)

### ADDED
- Initial Release
