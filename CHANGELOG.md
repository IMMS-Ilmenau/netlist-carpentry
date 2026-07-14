# Changelog 0.5.0

## ADDED
- Implemented missing Yosys cell abstractions, including
  - `SDFF` (synchronously resettable DFF),
  - `SDFFCE` (synchronously resettable DFF with enable, where the enable takes precedence over the reset),
  - `SDFFE` (synchronously resettable DFF with enable, where the reset takes precedence over the enable),
  - `ALDFF` (asynchronous load DFF),
  - `ALDFFE`(asynchronous load DFF with extra enable in the default use case),
  - `DFFSR` (DFF with set and clear/reset ports),
  - `DFFSRE` (DFF with set, clear/reset and enable ports),
  - `SSHL` (arithmetic left-shift),
  - `SSHR` (arithmetic right-shift),
  - `EQX` (case equality),
  - `NEX` (case inequality)
  - `POW` (exponentiator, "A to the power of B")
- Implemented factory methods for the mentioned Yosys cells
- Implemented factory methods for `DIV` (divider) and `MOD` (modulo) cells
- Added lots of docstrings
- Added `netlist_carpentry.ON_WINDOWS` flag, which is used in several places to determine the OS Netlist Carpentry is running on
- Added a Yosys reading config class `netlist_carpentry.ReadConfig`, which is now used to build the read script dynamically for more convenience - see the documentation of the class for more information
- Introduced `netlist_carpentry.read_via_cfg()` which uses a configured `ReadConfig` object to read a circuit, `netlist_carpentry.read()` now builds a `ReadConfig` object under the hood and calls `read_via_cfg()` with it
- Added `netlist_carpentry.generate_json()`, which generates a JSON netlist using a `ReadConfig` object, or plain file list
- Added `netlist_carpentry.Circuit.read()` (class method), which reads a circuit based on a `ReadConfig` or provided RTL file paths - `Circuit.read()` calls `netlist_carpentry.read()` under the hood
- Added `yowasp-yosys` as a dependency
  - The yosys executable to use is now a config parameter and can be accessed via `netlist_carpentry.CFG.yosys_executable`
  - Default Yosys command is 'yosys', which is the standard way to start Yosys in the command line
  - If 'yosys' does not start Yosys or the command is not found, Netlist Carpentry now falls back to using 'yowasp-yosys'
  - `ReadConfig.yosys_executable` returns the command used to start Yosys, which references the current `CFG.yosys_executable` - if 'yosys' does not work, `CFG.yosys_executable` now automatically references 'yowasp-yosys'
- `UnaryGate.get_result(Signal)` and `BinaryGate.get_result(Signal, Sigal)`, which returns the result (i.e. the output signal) for the given signal or signal combination
  - `UnaryGate.get_result(Signal.HIGH)` will return what happens if the input of the unary gate is 1
  - `BinaryGate.get_result(Signal.HIGH, Signal.LOW)` will return what happens if the first input of the binary gate is 1 and the second input is 0
  - Not yet implemented for reduction gates (UnaryGate with single-bit output) and logic gates (BinaryGate with single-bit output)
  - Arithmetic gates (e.g. `NegGate`) raise an `UnsupportedOperationError` as they are not evaluated bitwise and a truth table does not really make sense in such case
- `UnaryGate.truth_table` and `BinaryGate.truth_table`, which is a dictionary of signals/signal combinations
  - `UnaryGate.truth_table[Signal.HIGH]` is equivalent to `UnaryGate.get_result(Signal.HIGH)`
  - `BinaryGate.truth_table[(Signal.HIGH, Signal.LOW)]` is equivalent to `BinaryGate.get_result(Signal.HIGH, Signal.LOW)`
  - Not yet implemented for reduction gates (UnaryGate with single-bit output) and logic gates (BinaryGate with single-bit output)
- Reduction gates received a property `reduce_operation` that returns a lambda function modeling the reduction functionality of the gate
- Introduced `get_result_vector()` method for most primitive gates that returns the result of a given input signal configuration, similar to the `PrimitiveGate._calc_output()` method, except `get_result_vector()` computes the result for the given SignalArray objects, and not only for the current inputs
- Added Copilot skill files for the basics of Netlist Carpentry (accessible via /nc-basics) and for the API of Netlist Carpentry (accessible via /nc-api)
- Added lots of code examples to the docstrings - code examples are tested via doctest (as part of the pytest run) when running tox

## FIXED
- Fixed bug in signal evaluation process for DFFs with Enable, that arose whenever the Enable signal is undefined
- Fixed default port widths for factory methods (`netlist_carpentry.utils.gate_lib_factory`), so port widths are now derived from given ports by default, as long as no conflicts would occur
  - Default width is still 1 (e.g. if no ports are given at all)
  - If one port for an AND gate is given with width=4, it is assumed, the other ports also have width=4
  - If one port for an AND gate is given with width=4, and another is given with width=8, no assumption is made (default width of 1 is used)
  - This does not apply for gates with fixed port widths (e.g. CLK/RST port of a DFF or output of reduction gates, which always are 1 bit wide)
- Fixed lots of issues arising when using Netlist Carpentry on Windows
- Updated and fixed lots of docstrings
- Fixed `repr(Port)`, now also shows the direction (if given) and port width
- Fixed `repr(Wire)`, now also shows wire width
- Fixed `repr(WireSegment)` for constant wire segments, now showing explicit `"Tied to <value>"`
- Fixed issue with modules imported from foreign circuits, they are now copied into the circuit correctly
- `Port`, `Wire`, `Instance` objects now register themselves automatically in their parent Module object in the corresponding dictionary, and a warning is issued if no parent module is given
- Fixed issues with `Module.copy_instance()` and `NetlistElement.copy_object()`
- Fixed Yosys SLang plugin not being used correctly
- Fixed empty Verilog sections being written for no reason
- Fixed `Module.reconnect()` issue if one of the given parameters points outside of this module - now an appropriate exception is raised
- Fixed `Module.connect()` if the source port is a module port - now instead of a generic name `"_ncgen_..."`, the port name is used
- Fixed hidden bug in `Circuit.uniquify()`
- Fixed bug in `Circuit.create_blackbox_modules()`, now port directions and widths are copied correctly

## CHANGED
- `netlist_carpentry.utils.gate_lib_dataclasses.ResetParamsMixin.ARST_POLARITY` → `netlist_carpentry.utils.gate_lib_dataclasses.ResetParamsMixin.RST_POLARITY`
- `netlist_carpentry.utils.gate_lib_dataclasses.ResetParamsMixin.ARST_VALUE` → `netlist_carpentry.utils.gate_lib_dataclasses.ResetParamsMixin.RST_VALUE`
- `netlist_carpentry.io.read.yosys_netlist` → `netlist_carpentry.io.read.yosys.netlist_reader`
- `netlist_carpentry.io.read.yosys_netlist_types` → `netlist_carpentry.io.read.yosys.netlist_types`
- The following functions from `netlist_carpentry.scripts.script_builder` now display a deprecation warning in favor of `ReadConfig` objects and their methods:
  - `build_script()`
  - `get_yosys_cmds()`
  - `render_bash_script()`
  - Each method displays an extensive description of how the current behavior can be achieved with `ReadConfig` objects
- `netlist_carpentry.read()` now also accepts `ReadConfig` objects, but fails with a `ValueError` if additional reading parameters are set (e.g. `top`, `out`, `source_paths`, `no_hierarchy`)
- Major internal rewrite of `netlist_carpentry.io.read.yosys.YosysNetlistReader` and yosys-related typeddicts
  - `netlist_carpentry.io.read.yosys.netlist_types.PortAttributes` → `netlist_carpentry.io.read.yosys.netlist_types.PortData`
  - `netlist_carpentry.io.read.yosys.netlist_types.YosysCell` → `netlist_carpentry.io.read.yosys.netlist_types.CellData`
  - `netlist_carpentry.io.read.yosys.netlist_types.Netnames` → `netlist_carpentry.io.read.yosys.netlist_types.WireData`
  - `netlist_carpentry.io.read.yosys.netlist_types.YosysPortDirections` → `netlist_carpentry.io.read.yosys.netlist_types.PortDirections`
  - Moved most of `YosysNetlistReader._build_...()` methods to the corresponding classes in `netlist_carpentry.io.read.yosys.netlist_types`
  - Previous classes `PortAttributes`, `YosysCell`, `Netnames`, and `PortDirections` can still be referenced but show a deprecation warning
- `PrimitiveGate._calc_output()` now returns `SignalArray` objects instead of `Dict[int, Signal]` for better handling
- `PrimitiveGate._calc_output()` no longer takes an index (the array is now calculated directly)
- `PrimitiveGate._calc_output()` now takes a `SignalArray` object instead of a `Dict[int, Signal]`
- Adjusted parameter `instance_name` on some methods in the `Module` class, it is now called `instance` and accepts a string or an `Instance` object for these methods:
  - `Module.get_outgoing_edges()`
  - `Module.get_incoming_edges()`
  - `Module.get_neighbors()`
  - `Module.get_succeeding_instances()`
  - `Module.get_preceeding_instances()`
  - Previous calls with `instance_name=<value>` still work, but show a deprecation warning
- For the Verilog write-out, the `port2v()`, `wire2v()` and `instance2v()` methods no longer require a Module Parameter - the module is now retrieved from the parent of the given instance


# Older Versions

## Changelog 0.4.2 (2026-06-18)

### FIXED
- Fixed minor bug in `netlist_carpentry.Module.remove_instance()` method
- Fixed missing instance parameters in Verilog output for submodule or blackbox instances
- Fixed silent-fail of `netlist_carpentry.PortSegment.set_signal()` for tied ports - now the method explicitly raises a `SignalAssignmentError`, if an attempt is made to change the signal value of a tied port segment (previously just nothing did happen, but now the run will explicitly fail)
- The `netlist_carpentry.run_eqy()`, `run_equiv()` and `run_equiv_miter()` methods now support a broader array of parameter types - designs can either be `Circuit` objects or paths to Verilog designs (str, Path, or lists thereof)
- `PrimitiveGate.p2v()` method now also accepts an `include_indices` parameter to only transform certain slices of a port to Verilog (as a mirror to the `exclude_indices` parameter)
- `PrimitiveGate.set()` method now also accepts an `idx` parameter to set the signal values of one or multiple indices of a port
  - Providing a single integer will now set the signal value of the corresponding port segment to the given signal
  - Providing an iterable of integers will now set the signal values of all corresponding port segments to the given signal
  - For invalid indices (i.e. indices without a matching port segment), an IndexError is raised
  - For tied ports or port segments, a `SignalAssignmentError` is raised
- Fixed FutureWarning in `PrimitiveGate.sync_parameters()` (function will be removed in 1.0.0, use newly introduced `PrimitiveGate.update_parameters()`, which does the same, but without a return value), by making it a DeprecationWarning instead, to prevent technical debt in the future
- Updated faulty/added missing docstrings
- Fixed `bool(netlist_carpentry.Signal)`
  - `bool(Signal.LOW)` is now `False`
  - `bool(Signal.HIGH)` is now `True`
  - `bool(Signal.UNDEFINED)` and `bool(Signal.FLOATING)` both now raise a `SignalError`, which now extends `ValueError`
- Implemented missing `Signal.__and__()` (for `netlist_carpentry.Signal & netlist_carpentry.Signal`) for logical AND checks between signals
- Implemented missing `Signal.__or__()` (for `netlist_carpentry.Signal | netlist_carpentry.Signal`) for logical OR checks between signals
- Implemented missing `Signal.__xor__()` (for `netlist_carpentry.Signal ^ netlist_carpentry.Signal`) for logical XOR checks between signals
- Implemented missing `Signal.__int__()` (for `int(netlist_carpentry.Signal)`) for casting a `Signal` to an `int`
- Implemented missing `Signal.__invert__()` (for `~netlist_carpentry.Signal`) for inversion of a signal; `Signal.invert()` still exists but now shows a `DeprecationWarning` along with a hint
- Fixed some evaluation bugs for reduction gates



## Changelog 0.4.1 (2026-05-11)

### FIXED
- Fixed issues arising when the optional VCD dependency (i.e. `pywellen`) is not installed, now also showing an appropriate error message
- Fixed bug in the `netlist_carpentry.Port.loads()` method, causing a crash whenever Port and Wire (segments) have different offsets
- Fixed issues with renaming of port or wire segments, losing previous connections (#43)
- Fixed an issue within the `netlist_carpentry.Port.loads()` method (wrong index mappings if offsets differ)
- Whenever `netlist_carpentry.read()` is called with `process_memory=False`, Yosys will now generate a single `mem_v2` cell instead of multiple memrd, memwr and meminit cells
- Fixed missing dependency in dev mode, now the vcd option (pywellen) is also included in the dev options
- Some internal fixes regarding class hierarchies in the gate lib
  - Simplified mixin classes `ClkMixin`, `EnMixin`, `RstMixin`, `ScanMixin`
  - Moved `ClkMixin`, `EnMixin`, `RstMixin`, `ScanMixin` to `netlist_carpentry.utils.gate_mixins`, they still accessible from its previous location, but a deprecation warning will occur
  - Fixed hierarchies of several gate classes (DFF and derivatives, DLatch)
- Fixed `netlist_carpentry.Signal.get()` for mixed-case and direction abbreviations, e.g. "in" and "out"
- `netlist_carpentry.Module.create_port()` now accepts port directions as (case-insensitive) strings as well, e.g. "input", "InOut", "OUT"
- Fixed several type hints
- Fixed outdated/missing docstrings


## Changelog 0.4.0 (2026-04-27)

### ADDED
- `netlist_carpentry.utils.gate_lib.DFF` and derived classes now have properties `has_en` (has enable port, bool) and `has_rst` (has reset port, bool)
- Added `netlist_carpentry.utils.gate_lib_dataclasses.Parameters` class, which unifies all previous base parameter classes (`TypedParams`, `InstanceParams`, `_CombinationalParams`,  `_SequentialParams`, and `AllParams`) - they still exist, but are marked with a deprecation warning, referencing the new `Parameters` class

### CHANGED
- `netlist_carpentry.utils.gate_lib_base_classes.StorageGate` (i.e. sequential gates, like `DFF` and `DLatch` instances) now have a property `width`, instead of `y_width` (added deprecation warning)
- Changed functionality of gate parameters
  - Instead of `netlist_carpentry.PrimitiveGate.parameters["PARAM"]`, `netlist_carpentry.PrimitiveGate.parameters.PARAM` is now possible
  - `PrimitiveGate.parameters` now is of type `Parameters`, which is a `pydantic.BaseModel`
  - Indexing still works, but will be removed in 1.0.0 (added DeprecationWarning)
- Added several DeprecationWarnings and FutureWarnings for properties and methods that will be heavily changed or deleted in 1.0.0
- Updated a bunch of docstrings
- `pywellen` is now an optional dependency, can be installed via `pip install netlist-carpentry[vcd]`

### FIXED
- Many fixes of issues only present on Windows machines
- Fixed width parameter setting/copying issues for many gates
- Some gates that previously forced equal widths for some ports, now also support ports with different widths
- Fixed issues where reading Verilog files was not possible on Windows
- mkdocs-jupyter was moved from general dependencies to dev-dependencies in `pyproject.toml`, so it is no longer installed in the standard user version, and only in the dev version


## Changelog 0.3.8 (2026-04-15)

### FIXED
- Fixed typos and formatting in some log messages, also changed some messages from "INFO" to "DEBUG" and introduced some debug messages for better traceability during Verilog write-out
- Primitive cell instances are now correctly aligned in Verilog output, i.e. lines starting with `assign ...` are now aligned vertically, with proper indentation


## Changelog 0.3.7 (2026-04-01)

### ADDED
- `netlist_carpentry.run_equiv_miter()` to compare two Circuit objects or Verilog files (or mixed) by building a miter module in Yosys and showing equivalence within the miter module
- `netlist_carpentry.Module.flatten_instance()` to flatten a single module instance ("shallow flattening", ignoring any submodules inside the module instance), such that the content of the module is pasted into the parent module (transferring previous instance connections directly into the module) and the instance itself is removed

### CHANGED
- Refactorings in `netlist_carpentry.routines.opt.floodfill.chain_optimizer`
  - Python module is no longer executable with arguments via command line - use chain_optimizer module via `chain_optimizer.opt_chains()`
  - Removed a bunch of catches in edge cases that led the process to fail silently - now Netlist Carpentry crashes explicitly whenever unfixable issues are encountered, instead of hiding it behind `None` returns
  - Removed `remove_degenerates` step and `fix_invalid_verilog` (plus related methods) as they are no longer required
- `netlist_carpentry.run_equiv()` now has an additional parameter `out_dir` for a directory to be used as output for the script (and possibly additional temporary files) - if unset, a temporary directory is used
- Updated several docstrings

### FIXED
- `netlist_carpentry.run_equiv()` now also supports comparing two Circuit objects, or a Circuit and a Verilog file
- `netlist_carpentry.run_eqy()` now also supports comparing two Circuit objects, or a Circuit and a Verilog file
- Fixed minor issues with environment variables

### REMOVED
- `equiv.sh` from the `netlist_carpentry.scripts` package - the script is now generated dynamically at runtime
- `netlist_carpentry.Wire.ports` due to redundancy: Use `netlist_carpentry.Wire.connected_port_segments`, which does exactly the same


## Changelog 0.3.6 (2026-03-23)

### ADDED
- `netlist_carpentry.gate_lib.PrimitiveGate.a_width` to retrieve the width of the input port A directly for all gates with such port in the gate library
- `netlist_carpentry.gate_lib.BinaryGate.b_width` to retrieve the width of the port B (second input port) for binary gates of the gate library
- `netlist_carpentry.gate_lib.PosGate` implementing the Verilog pos operator (`+net`, as opposed to `-net`, e.g. used for sign-extension)

### CHANGED
- `netlist_carpentry.gate_lib.PrimitiveGate.width` → `netlist_carpentry.gate_lib.PrimitiveGate.y_width`
- Gates from the gate library can no longer get their port width assigned via `Gate.width = new_width`, instead the width is always directly coupled to the width of the corresponding port

### FIXED
- Minor fixes with equivalence checking structure, if "overwrite" parameter is False
- Fixed issue with reg-wire detection if the driving instance has a "dff" or "dlatch" in its instance type


## 0.3.5 (2026-03-11)

### ADDED
- `netlist_carpentry.NetlistElement.copy_object()` as a simple way to duplicate netlist elements (ports, wires, instances), whilst giving them a new name to prevent naming collisions
- `netlist_carpentry.NetlistElement.has_parent` property as a more convenient way to check if a netlist element has a parent object (e.g. a wire might be part of a module or not, e.g. if it was just removed from a module, but the object itself still exists in Python)
- `netlist_carpentry.PortSegment.grandparent` property returning the grandparent of the port segment, which is either a module or an instance, depending on whether the port (to which the segment belongs) is a module port or an instance port
- `netlist_carpentry.WireSegment.grandparent` property returning the grandparent of the wire segment, which is the module containing the wire to which the segment belongs
- `netlist_carpentry.read()` now supports sourcing files (e.g. activating an environment, such as the OSS CAD SUITE) via the parameter `source_paths` (expects a list of strings, being the paths to the files to source)
- `netlist_carpentry.read()` now supports reading VHDL files using the Yosys plugin GHDL
  - Yosys loads GHDL via `yosys -m ghdl`, which requires GHDL to be present in the PATH variable
  - The currently recommended way of reading VHDL files is to install and activate the OSS CAD SUITE (activation can be achieved by providing the path of the `oss_cad_suite/environment` script to the `source_paths` parameter)
  - Due to the sourcing mechanism, reading VHDL files is currently only supported on Linux systems
- `netlist_carpentry.Module.equal_connections()` to compare two modules whether they have the same connections, ignoring metadata and only focusing on the structural aspects, i.e. whether ports, wires and instances have the same connections (WIP)
- `netlist_carpentry.Circuit.flatten()` to flatten the whole circuit (supports deselecting/skipping modules) as a convenience extension to `netlist_carpentry.Module.flatten()`
- `netlist_carpentry.Port.is_connected_1to1` property that is True if the port is connected completely `1:1` to a given wire
  - The port and the wire must have the same width
  - No index of the port is connected to another wire
  - No index of the port is tied
  - Connections indices between the port and the wire are in matching order (i.e. port[0]<=>wire[0], port[1]<=>wire[1], ...), offset is preserved
  - If this property is true, the Verilog assignment matches `assign port = wire;` or `assign wire = port;`, i.e. without slicing or concatenation
- `netlist_carpentry.utils.gate_lib.ShiftX` implementing the Yosys `$shiftx` cell, i.e. the Verilog index part-select expression, e.g. `assign Y = A[B +: 4]`, which assigns Y to `[A[B+3], A[B+2], A[B+1], A[B]]`

### CHANGED
- Completely rewrote ElementPath behavior and handling
  - The path is now dynamically generated by traversing the parents of an object and now longer via `netlist_carpentry.NetlistElement.raw_path`
  - This ensures that the path is actually a "real path", since each level of the path actually exists
  - When creating `netlist_carpentry.NetlistElement` objects, now "name" parameter is required instead of "raw_path"
  - `netlist_carpentry.NetlistElement.raw_path` can no longer be changed or set - the individual elements of the path are updated if `set_name()` is called on the corresponding object
- `netlist_carpentry.read()` without a top module now auto-selects the top module
  - Precisely, instead of skipping the Yosys command "hierarchy -top top_name" if no top_name is given, "hierarchy -auto-top" is called instead
  - Accordingly, the hierarchy is now always built by default, whereas no hierarchy elaboration was executed previously if no top name was specified
  - Previous functionality can be restored by setting the "no_hierarchy" parameter to `True` (defaults to False)
- Changed a bunch of Log messages log levels from "Info" to "Debug" to decrease console spam
- `netlist_carpentry.Module.create_instance()` now automatically adds the given module to the circuit if a module definition is provided and a parent circuit is specified, raising an error if a module with the same name but different content already exists
- `netlist_carpentry.Wire.connected_port_segments` now returns a dictionary, containing the connected port segments for each wire segment index

### FIXED
- Fixed issue where `netlist_carpentry.Module.copy_instance()` would take very long because of excessive deepcopying
- Fixed crashes within `netlist_carpentry.Module.flatten()` method
- Fixed issue in `netlist_carpentry.Module.optimize()` routine for D-FF with tied D signals
- Minor runtime optimizations and internal improvements
- Fixed issues with equality operations (e.g. `==` and `!=`) for `netlist_carpentry.Port`, `netlist_carpentry.Wire`, `netlist_carpentry.PortSegment` and `netlist_carpentry.WireSegment`
- Fixed issues with support for techmaps when reading the Verilog files via Yosys, now also directly applying `pmux2mux.v` script to resolve pmux cells

### REMOVED
- `netlist_carpentry.PortSegment.parent_name`: Use `netlist_carpentry.PortSegment.parent.name` instead
- `netlist_carpentry.PortSegment.grandparent_name`: Use `netlist_carpentry.PortSegment.grandparent.name` instead
- `netlist_carpentry.WireSegment.super_wire_name`: Use `netlist_carpentry.WireSegment.parent.name` instead
- `netlist_carpentry.WireSegment.super_module_name`: Use `netlist_carpentry.WireSegment.grandparent.name` instead
- `netlist_carpentry.Wire.nr_connected_port_segments`: Use `len(netlist_carpentry.Wire.connected_port_segments)` instead


## 0.3.4 (2026-02-19)

### ADDED
- `netlist_carpentry.routines.opt.floodfill.chain_optimizer` for optimizing instance chains and rebuilding them into trees
- `netlist_carpentry.routines.opt.floodfill.chain_metrics` for optimization data collection and tracing
- `netlist_carpentry.utils.gate_lib.Divider` class modeling a Divider cell
- `netlist_carpentry.utils.gate_lib.Modulo` class modeling a Modulo cell
- Added factory methods for Adder (`adder()`), Subtractor (`subtractor()`), Multiplier (`multiplier()`), Divider (`divider()`), Modulo (`modulo()`) to `netlist_carpentry.utils.gate_factory`
- `netlist_carpentry.Module.check()` to check a module for issues - currently only combinational loops and fanout issues, returning a CheckReport object
- `netlist_carpentry.Circuit.check()` to check the whole circuit
- `netlist_carpentry.Circuit.update_instance()` to update the circuit instance dictionary (replace the previous instance path entry with the new instance path entry for the correct instance type), useful if the type of an instance gets changed
- `netlist_carpentry.Circuit.sync_instances()` to rebuild the whole instance dictionary (slow for large circuits, use `netlist_carpentry.Circuit.update_instance()` for smaller/individual changes)

### CHANGED
- `netlist_carpentry.routines.floodfill` → `netlist_carpentry.routines.opt.floodfill`

### FIXED
- Fixed issues where params get droppend after instance creation
- `netlist_carpentry.Port.set_signed()` now updates signedness in its parent instance correctly if the port is an instance port
- Fixed performance issues with `netlist_carpentry.Circuit.copy_module()` and `netlist_carpentry.Circuit.uniquify()` caused by excessive deepcopying
- Fixed issue with `netlist_carpentry.run_eqy()` failing on newly created directory, if an EQY output path is provided
- Fixed issue where arithmetic gates, where each port must have the same width, now the output can be of any width up to the sum of the width of its inputs
- Fixed issues with `netlist_carpentry.Module.refine_instance()` method if port widths increase in the new instance or module definition
- Fixed issue with `netlist_carpentry.Module.optimize()`, where Netlist Carpentry crashes for a DFFs with constant input but without Enable Port

### REMOVED
- `netlist_carpentry.routines.floodfill.cascading_or_replacement`


## 0.3.3 (2026-02-11)

### ADDED
- `netlist_carpentry.scripts.equivalence_checking.run_equiv()` to execute an equivalence check via Yosys equiv_* passes, as a more stable alternative to EQY (import via `from netlist_carpentry import run_equiv`)
- `netlist_carpentry.scripts.equivalence_checking.run_eqy()` as a standalone function to skip the creation of the Wrapper class (import via `from netlist_carpentry import run_eqy`)

### CHANGED
- `netlist_carpentry.Module.change_instance_type()` → `netlist_carpentry.Module.refine_instance()`
- `netlist_carpentry.Module.replace()` → `netlist_carpentry.Module.substitute_instance()`
- `netlist_carpentry.scripts.eqy_check` → `netlist_carpentry.scripts.equivalence_checking`
- `netlist_carpentry.scripts.eqy_check.EqyWrapper` → `netlist_carpentry.scripts.equivalence_checking.EquivalenceChecking`
- Whole interface of `netlist_carpentry.scripts.equivalence_checking.EquivalenceChecking` has been rewritten, the methods still mainly exist, but now use `netlist_carpentry.run_eqy()` instead of the class-related methods - this is far more convenient

### FIXED
- Fixed renaming issues that occurred for wires when renaming a modules
- Fixed issue with black-box instances losing all connection data if no port direction is specified for the instance
- Fixed some issues with EQY by flattening the design inside the EQY process


## 0.3.2 (2026-02-03)

### ADDED
- `netlist_carpentry.Module.reconnect()` to move the connection of one port to another, such that the first port becomes unconnected, and the second port receives the former connection of the first

### FIXED
- `netlist_carpentry.Instance.split()` was dropping reset values for D-FF
- `netlist_carpentry.Module.change_instance_type()` was destroying previous connections
- `netlist_carpentry.Module.change_instance_type()` was leaking memory due to excessive copying of the whole circuit
- Issues with renaming process were fixed, where occasionally the old name remained in the port connection dictionaries


## 0.3.1 (2026-01-29)

### ADDED
- `netlist_carpentry.Module.change_instance_type()` method to change the type of an instance (by creating a new instance under the hood and discarding the old one, as the new object may be of another class)

### CHANGED
- `netlist_carpentry.utils.gate_lib_base_classes.LibUtils.p2ws2v()` → `netlist_carpentry.utils.gate_lib_base_classes.PrimitiveGate.p2ws2v()`
- `netlist_carpentry.utils.gate_lib_base_classes.LibUtils.get_unconnected_idx()` → `netlist_carpentry.utils.gate_lib_base_classes.PrimitiveGate._get_unconnected_idx()` (now also protected)
- `netlist_carpentry.utils.initialize_logging()` no longer takes `no_file` argument, instead set `output_dir` to None for the same effect
- `netlist_carpentry.Circuit.uniquify()` now returns a mapping of instance paths to new module names

### FIXED
- `netlist_carpentry.Instance.split()` was discarding instance parameters completely, now copies parameters and updates instance width accordingly
- `netlist_carpentry.Circuit.uniquify()` no longer crashes after `netlist_carpentry.Instance.split()` was run (fixed split instances missing in `netlist_carpentry.Circuit.instances`)

### REMOVED
- `netlist_carpentry.CFG.output_dir`
- `netlist_carpentry.LOG.finish()` (unused and fragile, Log.report() can be used instead)
- `netlist_carpentry.LOG.fatal_and_exit()` (raise an appropriate exception instead)
- `netlist_carpentry.utils.gate_lib_base_classes.LibUtils` (previous methods are now integrated into `gate_lib_base_classes.PrimitiveGate`)


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
