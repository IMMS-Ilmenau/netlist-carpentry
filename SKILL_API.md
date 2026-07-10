# NetlistCarpentry — Complete API Reference

## Table of Contents

| # | Section | Description |
|---|---------|-------------|
| 1 | [Loading & Writing Circuits](#loading--writing-circuits) | `read()`, `read_json()`, `write()`, `ReadConfig` |
| 2 | [Circuit](#circuit) | Root container — all modules, top-level, navigation |
| 3 | [Module](#module) | Design unit — instances, ports, wires, connections |
| 4 | [Instance](#instance) | Gate or submodule instantiation |
| 5 | [Port](#port) | Module or instance I/O |
| 6 | [Wire](#wire) | Internal net connection |
| 7 | [PortSegment / WireSegment](#portsegment--wiresegment) | Per-bit elements |
| 8 | [Element Paths](#element-paths) | Hierarchical navigation types |
| 9 | [ModuleGraph](#modulegraph) | NetworkX integration |
| 10 | [Pattern Matching](#pattern-matching) | `Pattern`, `Match` |
| 11 | [Signal Model](#signal-model) | `Signal` enum, `SignalArray` |
| 12 | [Direction Enum](#direction-enum) | Port directions |
| 13 | [Configuration](#configuration) | `CFG` global settings |
| 14 | [Built-in Routines](#built-in-routines) | Optimization, checking |
| 15 | [Gate Library](#gate-library) | Primitive gate classes |
| 16 | [Equivalence Checking](#equivalence-checking) | `run_eqy`, `run_equiv`, `run_equiv_miter` |

---

## Loading & Writing Circuits

### `read()` — Load from Verilog/VHDL/JSON

```python
from netlist_carpentry import read

circuit = read("design.v")                    # Load single file
circuit = read(["design.v", "sub.v"])         # Load multiple files
circuit = read(ReadConfig(files=["design.v"], top="my_top"))  # With config
```

**Returns:** `Circuit` — fully parsed circuit object.

---

### `read_json()` — Load from JSON netlist

```python
from netlist_carpentry import read_json

circuit = read_json("netlist.json")
```

**Parameters:**
- `path` (str | Path): Path to the JSON file.

**Returns:** `Circuit`

---

### `read_via_cfg()` — Load with ReadConfig

```python
from netlist_carpentry import read_via_cfg, ReadConfig

cfg = ReadConfig(files=["design.v"], top="my_top", json_path=Path("out.json"))
circuit = read_via_cfg(cfg)
```

**Parameters:**
- `cfg` (ReadConfig): Configuration for Yosys-based reading.
- `circuit_name` (str, optional): Name for the resulting circuit.
- `verbose` (bool): Print Yosys output.

**Returns:** `Circuit`

---

### `write()` — Export to Verilog

```python
from netlist_carpentry import write

write(circuit, "output.v", overwrite=True)
```

**Parameters:**
- `circuit` (Circuit): The circuit to export.
- `output_path` (str | Path): Destination file path.
- `overwrite` (bool): Overwrite if exists.

---

### `generate_json()` — Generate JSON via Yosys

```python
from netlist_carpentry import generate_json

json_path = generate_json(["design.v"], output=Path("out.json"))
```

**Parameters:**
- `files` (List[Path]): Input RTL files.
- `output` (Path, optional): Output JSON path.
- `top` (str, optional): Top module name.

**Returns:** `Path` — path to generated JSON file.

---

## Circuit

The root container holding all modules and the top-level module.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Circuit name |
| `modules` | `CustomDict[str, Module]` | All modules by name |
| `module_count` | `NonNegativeInt` | Number of modules |
| `top_name` | `str` | Name of top-level module |
| `top` | `Module` | Top-level module (raises if no top) |
| `has_top` | `bool` | True if top module is set |
| `creator` | `str` | Circuit creator name |
| `instances` | `DefaultDict[str, List[InstancePath]]` | All instances by type across circuit |

### Methods

#### `__getitem__(key: str) -> Module`
Get a module by name.
```python
module = circuit["my_module"]
```

#### `__contains__(key: str | Module) -> bool`
Check if module exists.
```python
if "my_module" in circuit:
    ...
```

#### `__len__() -> int`
Number of modules.

#### `__iter__() -> Iterator[Module]`
Iterate over all modules.

#### `first -> Module`
Get the first module (raises IndexError if empty).

#### `add_module(module: Module, fetch_existing: bool = False) -> Module`
Add a module to the circuit.
```python
new_mod = circuit.add_module(Module(name="new"))
```

#### `remove_module(module: str | Module) -> None`
Remove a module from the circuit.
```python
circuit.remove_module("unused_module")
```

#### `create_module(name: str) -> Module`
Create and add a new module.
```python
mod = circuit.create_module("my_new_module")
```

#### `copy_module(old_module: str | Module, new_name: str) -> Module`
Duplicate a module with a new name.
```python
copied = circuit.copy_module("original", "original_copy")
```

#### `get_module(module_name: str) -> Optional[Module]`
Get a module by name, returns None if not found.

#### `get_module_at_idx(index: NonNegativeInt) -> Optional[Module]`
Get module by dictionary index order.

#### `set_top(module: str | Module | None) -> None`
Set the top-level module. Pass `None` to clear.
```python
circuit.set_top("my_design")
```

#### `add_from_circuit(other_circuit: str | Circuit) -> Dict[str, Module]`
Import all modules from another circuit or file path.
```python
imported = circuit.add_from_circuit("other_design.v")
```

#### `get_from_path(path: str | ElementPath) -> NetlistElement`
Resolve a hierarchical path to a circuit element.
```python
elem = circuit.get_from_path("top.u_adder.sum.4")  # PortSegment
elem = circuit.get_from_path("top.data_in")          # Port
elem = circuit.get_from_path("top.wire_a")           # Wire
```

#### `get_path_from_str(path_str: str, sep: str = '.') -> ElementPath`
Convert a path string to the appropriate ElementPath type.
```python
path = circuit.get_path_from_str("top.inst.port.0")
# Returns PortSegmentPath
```

#### `sync_instances() -> None`
Rebuild the `instances` dictionary from all modules. O(N*M) complexity.

#### `update_instance(instance: Instance | InstancePath, old_type: str | None = None) -> None`
Update the circuit's instance registry for a single instance.

#### `uniquify(module: str | Module | None = None, keep_original_module: bool = False) -> Dict[InstancePath, str]`
Create unique copies of each module instance.
```python
mapping = circuit.uniquify("shared_module")
# Returns {InstancePath: "shared_module_0", ...}
```

#### `flatten(skip_modules: List[str] | None = None) -> None`
Flatten all submodule instances into their parent modules.
```python
circuit.flatten(skip_modules=["blackbox"])
```

#### `create_blackbox_modules() -> None`
Create empty module definitions for all blackbox cells.

#### `set_signal(path: str, signal_value: LogicLevel | Signal) -> None`
Set signal on a port/wire/segment by path string.
```python
circuit.set_signal("top.clk", Signal.HIGH)
circuit.set_signal("top.data_in.0", '0')
```

#### `optimize() -> bool`
Optimize all modules and remove unused ones. Returns True if changes were made.

#### `check() -> CheckReport`
Validate the circuit. Returns a report with issues (combinational loops, fanout).

#### `evaluate() -> None`
Evaluate signals across the entire circuit hierarchy (top-down).

#### `write(output_file_path: str | Path, overwrite: bool = False) -> None`
Write circuit to Verilog file.

#### `prove_equivalence(gold_design: List[str] | Circuit, out_dir: str | Path, eqy_script_path: str | Path = '', gold_top_module: str = '', quiet: bool = False) -> subprocess.Popen[str]`
Formal equivalence check against a gold design using Yosys EQY.
```python
result = circuit.prove_equivalence(gold_design, out_dir=Path("eqy_out"))
```

#### `export_metadata(path: str | Path, include_empty: bool = False, sort_by: Literal['path', 'category'] = 'path', filter: Callable[[str, NESTED_DICT], bool] = ...) -> None`
Export all metadata to a JSON file.

#### `Circuit.read(cfg_or_files: ReadConfig | List[Path], circuit_name: str | None = None, verbose: bool = False) -> Circuit` *(classmethod)*
Class method to read RTL files into a Circuit.

---

## Module

A single design unit containing instances, ports, and wires.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Module name |
| `instances` | `CustomDict[str, Instance]` | All instances by name |
| `ports` | `CustomDict[str, Port[Module]]` | All ports by name |
| `wires` | `CustomDict[str, Wire]` | All internal wires |
| `parameters` | `Parameters` | Module parameters |
| `metadata` | `MetadataMixin` | User/Yosys metadata |
| `submodules` | `List[Instance]` | Submodule instances |
| `primitives` | `List[Instance]` | Primitive gate instances |
| `instances_by_types` | `DefaultDict[str, List[Instance]]` | Instances grouped by type |
| `locked` | `bool` | Structural immutability flag |
| `has_circuit` | `bool` | Whether attached to a Circuit |
| `circuit` | `Circuit` | Parent circuit |
| `path` | `ModulePath` | Hierarchical path |
| `raw_path` | `str` | Raw path string |

### Methods

#### `create_instance(interface_definition: Module | Type[Instance], name: str | None = None, params: Dict[str, object] | Parameters | None = None) -> Instance`
Create a submodule or primitive gate instance.
```python
from netlist_carpentry.utils.gate_lib import AndGate

# Submodule instance
sub = module.create_instance(circuit["sub_module"], "u_sub")

# Primitive gate
and_gate = module.create_instance(AndGate, "u_and")
```

#### `add_instance(instance: Instance) -> Instance`
Add an existing instance to the module.

#### `remove_instance(instance: str | Instance) -> None`
Remove an instance and its connections.

#### `copy_instance(instance: str | Instance, new_name: str, keep_inputs: bool = False) -> Instance`
Copy an instance within the module.

#### `refine_instance(old_instance: str | Instance, new_type_definition: Module | Type[Instance]) -> None`
Replace an instance with a different type, preserving connections.
```python
module.refine_instance("u_old", AndGate)
```

#### `substitute_instance(old_instance: str | Instance, new_instance: Instance) -> None`
Replace an instance with a pre-built instance object.

#### `create_port(name: str, direction: str | Direction = Direction.UNKNOWN, width: PositiveInt = 1, offset: NonNegativeInt = 0, is_locked: bool = False) -> Port[Module]`
Create a new port.
```python
clk_port = module.create_port("clk", Direction.IN, width=1)
data_port = module.create_port("data_in", Direction.IN, width=8)
```

#### `add_port(port: Port[Module]) -> Port[Module]`
Add an existing port.

#### `remove_port(port: str | Port[Module]) -> None`
Remove a port and its connections.

#### `get_port(name: str) -> Port[Module] | None`
Get a port by name (returns None if not found).

#### `get_ports(name: str | None = None, direction: Direction | None = None, fuzzy: bool = False) -> List[Port[Module]]`
Search for ports by name or direction.
```python
inputs = module.get_ports(direction=Direction.IN)
all_ports = module.get_ports(name="data", fuzzy=True)
```

#### `create_wire(name: str | None = None, width: PositiveInt = 1, is_locked: bool = False, offset: NonNegativeInt = 0) -> Wire`
Create a new wire. If name is None, generates `_ncgen_{i}_`.
```python
bus = module.create_wire("data_bus", width=16)
auto_wire = module.create_wire()  # Name: "_ncgen_0_"
```

#### `add_wire(wire: Wire) -> Wire`
Add an existing wire.

#### `remove_wire(wire: str | Wire) -> None`
Remove a wire and disconnect its port segments.

#### `get_wire(name: str) -> Wire | None`
Get a wire by name.

#### `get_wires(name: str | None = None, fuzzy: bool = False) -> List[Wire]`
Search for wires by name.

#### `name_occupied(name: str) -> bool`
Check if a name is already used by any instance, port, or wire.

#### `connect(source: ANY_SIGNAL_SOURCE, target: ANY_SIGNAL_TARGET, new_wire_name: str | None = None) -> None`
Connect source to target. Auto-creates wires if needed.
```python
# Connect wire segment to port segment
module.connect(wire[0], port[1])

# Connect two ports (auto-creates wire)
module.connect(port_a, port_b)

# Using path strings
module.connect("top.wire.0", "top.inst.port.1")
```

#### `disconnect(port_like: PortSegmentPath | PortPath | PortSegment | Port) -> None`
Disconnect a port segment from its wire.

#### `reconnect(source: PortPath | Port, target: PortPath | Port) -> None`
Move all wire connections from source port to target port.

#### `get_edges(instance: str | Instance) -> Dict[str, Dict[int, WireSegment]]`
Get all connections for an instance.

#### `get_outgoing_edges(instance_name: str) -> Dict[str, Dict[int, WireSegment]]`
Get only output port connections.

#### `get_incoming_edges(instance_name: str) -> Dict[str, Dict[int, WireSegment]]`
Get only input port connections.

#### `get_wire_ports(ws_path: WireSegmentPath) -> List[PortSegment]`
Get all port segments connected to a wire segment.

#### `get_neighbors(instance_name: str) -> Dict[str, Dict[int, List[PortSegment]]]`
Get neighboring port segments of an instance.

#### `get_succeeding_instances(instance_name: str) -> Dict[str, Dict[int, List[Instance | Port[Module]]]]`
Get instances connected to output ports.

#### `get_preceeding_instances(instance_name: str) -> Dict[str, Dict[int, List[Instance | Port[Module]]]]`
Get instances connected to input ports.

#### `split(instance: str | Instance) -> Dict[NonNegativeInt, Instance]`
Split an n-bit instance into n 1-bit instances.

#### `split_all(type: str = '', fuzzy: bool = True, recursive: bool = False) -> int`
Split all matching instances. Returns count of split instances.
```python
count = module.split_all("§and", fuzzy=True)
```

#### `make_chain(instances: List[Instance], input_port: str, output_port: str) -> Tuple[Port[Instance], Port[Instance]]`
Chain instances together. Returns the unconnected ends.

#### `flatten(skip_name: List[str] | None = None, skip_type: List[str] | None = None, recursive: bool = False) -> None`
Flatten submodule instances into this module.

#### `flatten_instance(instance: str | Instance) -> None`
Flatten a single instance (non-recursive).

#### `get_instances(name: str | None = None, type: str | None = None, fuzzy: bool = False, recursive: bool = False) -> List[Instance]`
Search for instances by name or type.
```python
and_gates = module.get_instances(type="§and")
all_dffs = module.get_instances(type="dff", fuzzy=True, recursive=True)
```

#### `get_from_path(path: str | ElementPath) -> NetlistElement`
Resolve a path within this module.

#### `graph() -> ModuleGraph`
Get the NetworkX MultiDiGraph for this module. **Must call as method.**
```python
G = module.graph()
import networkx as nx
paths = nx.all_simple_paths(G, "input_port", "output_port")
```

#### `optimize() -> bool`
Run constant propagation, remove driverless/loadless elements.

#### `check() -> CheckReport`
Check for combinational loops and fanout issues.

#### `evaluate() -> None`
Propagate signals through the module (breadth-first from inputs).

#### `show(interactive: bool = False, figpath: str | None = None, **fwd_params) -> Dash | None`
Visualize the module graph. Interactive mode returns a Dash app.

#### `normalize_metadata(include_empty: bool = False, sort_by: Literal['path', 'category'] = 'path', filter: Callable[[str, NESTED_DICT], bool] = ...) -> METADATA_DICT`
Normalize metadata from all elements in the module.

#### `export_metadata(path: str | Path, include_empty: bool = False, sort_by: Literal['path', 'category'] = 'path', filter: Callable[[str, NESTED_DICT], bool] = ...) -> None`
Export metadata to JSON.

#### `update_module_instances() -> None`
Update all instance interfaces in the circuit when this module's ports change.

#### `pre_py2v_hook() / post_py2v_hook()`
Hooks called before/after Verilog export.

---

## Instance

A gate or submodule instantiation within a module.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Instance name |
| `instance_type` | `str` | Module name or primitive type (e.g., `"§and"`) |
| `ports` | `CustomDict[str, Port[Instance]]` | All ports |
| `parameters` | `InstanceParams` | Instance parameters |
| `connections` | `Dict[str, Dict[int, WireSegmentPath]]` | Port → wire mappings |
| `connection_str_paths` | `Dict[str, Dict[int, str]]` | Connections as string paths |
| `input_ports` | `Tuple[Port[Instance], ...]` | Input ports only |
| `output_ports` | `Tuple[Port[Instance], ...]` | Output ports only |
| `module` | `Module` | Parent module |
| `module_definition` | `Module | None` | Referenced module (for submodules) |
| `path` | `InstancePath` | Hierarchical path |
| `raw_path` | `str` | Raw path string |
| `is_blackbox` | `bool` | True if neither primitive nor module instance |
| `is_module_instance` | `bool` | True if references a module |
| `is_primitive` | `bool` | True if from built-in gate library |
| `splittable` | `bool` | True if can be split into 1-bit instances |
| `has_unconnected_port_segments` | `bool` | True if any port segment is unconnected |
| `signals` | `Dict[str, SignalArray]` | All port signals |
| `verilog` | `str` | Generated Verilog instantiation string |
| `verilog_template` | `str` | Template: `{inst_type} {inst_name} {parameters}({ports});` |

### Methods

#### `connect(port_name: str, ws_path: WireSegmentPath | None, direction: Direction = Direction.UNKNOWN, index: NonNegativeInt = 0, width: PositiveInt = 1) -> None`
Add connections to a port.
```python
inst.connect("A", wire_seg_path, direction=Direction.IN, index=0, width=8)
```

#### `disconnect(port_name: str, index: int | None = None) -> None`
Remove connections from a port. Index=None disconnects all bits.

#### `modify_connection(port_name: str, ws_path: WireSegmentPath, index: NonNegativeInt = 0) -> None`
Update an existing connection.

#### `connect_modify(port_name: str, ws_path: WireSegmentPath, direction: Direction = Direction.UNKNOWN, index: NonNegativeInt = 0, width: PositiveInt = 1) -> None`
Add or modify a connection (idempotent).

#### `get_connection(port_name: str, index: int | None = None) -> WireSegmentPath | Dict[int, WireSegmentPath] | None`
Get connection path(s) for a port.

#### `tie_port(name: str, index: NonNegativeInt, sig_value: LogicLevel) -> None`
Tie a port segment to a constant value.

#### `has_tied_ports() / has_tied_inputs() / has_tied_outputs() -> bool`
Check if any ports are tied to constants.

#### `split() -> Dict[NonNegativeInt, Instance]`
Split n-bit instance into n 1-bit instances (if splittable).

#### `copy_object(new_name: str) -> Instance`
Create a copy with a new name (unconnected ports).

#### `update_signedness(port_name: str) -> None`
Update signedness parameter from port metadata.

#### `change_mutability(is_now_locked: bool, recursive: bool = False) -> Instance`
Lock/unlock the instance and optionally its ports.

#### `normalize_metadata(...) -> METADATA_DICT`
Normalize metadata from all ports.

---

## Port

I/O of a module or instance. Generic: `Port[Module]` or `Port[Instance]`.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Port name |
| `direction` | `Direction` | IN, OUT, IN_OUT, UNKNOWN |
| `segments` | `CustomDict[int, PortSegment]` | Per-bit segments |
| `width` | `int` | Number of bits |
| `offset` | `int | None` | Index offset (min segment index) |
| `msb_first` | `bool` | MSB-first ordering |
| `lsb_first` | `bool` | LSB-first (inverse of msb_first) |
| `signed` | `bool` | Whether port is signed |
| `unsigned` | `bool` | Whether port is unsigned |
| `signal` | `Signal` | Signal value (1-bit only, warns otherwise) |
| `signal_array` | `SignalArray` | Full multi-bit signal array |
| `signal_str` | `str` | Signal as binary string (MSB first) |
| `signal_int` | `int | None` | Signal as integer |
| `is_input` | `bool` | True if direction is IN or IN_OUT |
| `is_output` | `bool` | True if direction is OUT or IN_OUT |
| `is_driver` | `bool` | True if driving a signal (instance OUT or module IN) |
| `is_load` | `bool` | True if being driven (instance IN or module OUT) |
| `is_connected` | `bool` | All segments connected |
| `is_connected_partly` | `bool` | At least one segment connected |
| `is_unconnected` | `bool` | No segments connected |
| `is_unconnected_partly` | `bool` | At least one segment unconnected |
| `is_tied` | `bool` | All segments tied to constant |
| `is_tied_partly` | `bool` | At least one segment tied |
| `is_tied_defined` | `bool` | All tied to 0 or 1 |
| `is_tied_defined_partly` | `bool` | At least one tied to 0 or 1 |
| `is_tied_undefined` | `bool` | All tied to x or z |
| `is_tied_undefined_partly` | `bool` | At least one tied to x or z |
| `is_floating` | `bool` | All segments floating |
| `is_floating_partly` | `bool` | At least one segment floating |
| `has_undefined_signals` | `bool` | Any segment is x or z |
| `is_instance_port` | `bool` | True if instance port |
| `is_module_port` | `bool` | True if module port |
| `is_connected_1to1` | `bool` | Connected as `assign port = wire;` |
| `connected_wire_segments` | `Dict[int, WireSegmentPath]` | Connected wire paths |
| `connected_wires` | `Set[WirePath]` | Connected wire paths (unique) |
| `path` | `PortPath` | Hierarchical path |
| `raw_path` | `str` | Raw path string |

### Methods

#### `set_signal(signal: LogicLevel | Signal, index: NonNegativeInt = 0) -> None`
Set signal on a specific bit.
```python
port.set_signal(Signal.HIGH, index=0)
port.set_signal('0', index=1)
```

#### `set_signals(signal: int | str | SignalDict) -> None`
Set all bits at once.
```python
port.set_signals(0b1010)           # From integer (LSB=bit 0)
port.set_signals("1010")           # From binary string (MSB first)
port.set_signals({0: '1', 2: '1'}) # From dict
```

#### `tie_signal(signal: LogicLevel | Signal, index: NonNegativeInt = 0) -> None`
Tie a port segment to a constant value permanently.

#### `count_signals(target_signal: Signal) -> NonNegativeInt`
Count occurrences of a signal value.
```python
high_count = port.count_signals(Signal.HIGH)
```

#### `driver(single: bool = False) -> Port | Dict[int, PortSegment | None]`
Get the driving port (for load ports only).
```python
driving_port = port.driver(single=True)  # Single port if all segments driven by same
drivers = port.driver()                  # Dict of segment → driver segment
```

#### `loads() -> Dict[int, List[PortSegment]]`
Get all load port segments (for driver ports).

#### `set_signed(signed: bool) -> bool`
Change signedness. Returns True if changed.

#### `change_connection(new_wire_segment_path: WireSegmentPath, index: int | None = 0) -> None`
Change which wire a segment connects to.

#### `create_port_segment(index: NonNegativeInt) -> PortSegment`
Create and add a new segment.

#### `create_port_segments(count: PositiveInt, offset: NonNegativeInt = 0) -> Dict[int, PortSegment]`
Create multiple segments.

#### `remove_port_segment(index: NonNegativeInt) -> None`
Remove a segment.

#### `get_port_segment(index: NonNegativeInt) -> PortSegment | None`
Get a segment by index.

#### `__getitem__(index: int) -> PortSegment`
Subscript access: `port[0]`.

#### `__len__() -> int`
Port width.

#### `__iter__() -> Iterator[Tuple[int, PortSegment]]`
Iterate over (index, segment) pairs.

---

## Wire

Internal net connection between ports.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Wire name |
| `segments` | `CustomDict[int, WireSegment]` | Per-bit segments |
| `width` | `int` | Number of bits |
| `offset` | `int | None` | Index offset |
| `msb_first` | `bool` | MSB-first ordering |
| `lsb_first` | `bool` | LSB-first |
| `signed` | `bool` | Whether wire is signed |
| `unsigned` | `bool` | Whether wire is unsigned |
| `signal` | `Signal` | Signal value (1-bit only) |
| `signal_array` | `SignalArray` | Full multi-bit signal array |
| `signal_str` | `str` | Signal as binary string |
| `signal_int` | `int | None` | Signal as integer |
| `connected_port_segments` | `Dict[int, List[PortSegment]]` | Connected port segments |
| `path` | `WirePath` | Hierarchical path |
| `raw_path` | `str` | Raw path string |

### Methods

#### `set_signal(signal: LogicLevel | Signal, index: NonNegativeInt = 0) -> None`
Set signal on a specific bit.

#### `set_signals(signal: int | str | SignalDict) -> None`
Set all bits at once.

#### `set_signed(signed: bool) -> None`
Change signedness.

#### `driver() -> Dict[int, PortSegment | None]`
Get driving port segments for each bit.

#### `loads() -> Dict[int, List[PortSegment]]`
Get load port segments for each bit.

#### `has_no_driver(get_mapping: bool = False) -> bool | Dict[int, bool]`
Check if wire has no driver.

#### `has_multiple_drivers(get_mapping: bool = False) -> bool | Dict[int, bool]`
Check for multiple drivers (error condition).

#### `has_no_loads(get_mapping: bool = False) -> bool | Dict[int, bool]`
Check if wire has no loads (dangling).

#### `is_dangling(get_mapping: bool = False) -> bool | Dict[int, bool]`
Check if any segment is dangling.

#### `create_wire_segment(index: NonNegativeInt) -> WireSegment`
Create and add a new segment.

#### `create_wire_segments(count: PositiveInt, offset: NonNegativeInt = 0) -> Dict[int, WireSegment]`
Create multiple segments.

#### `remove_wire_segment(index: NonNegativeInt) -> None`
Remove a segment.

#### `get_wire_segment(index: NonNegativeInt) -> WireSegment | None`
Get a segment by index.

#### `get_wire_segments(name: str = '', fuzzy: bool = False) -> Dict[int, WireSegment]`
Search segments by name.

#### `__getitem__(index: int) -> WireSegment`
Subscript access: `wire[0]`.

#### `__len__() -> int`
Wire width.

#### `__iter__() -> Iterator[Tuple[int, WireSegment]]`
Iterate over (index, segment) pairs.

---

## PortSegment / WireSegment

The smallest addressable unit — individual bits of ports and wires.

### PortSegment Properties

| Property | Type | Description |
|----------|------|-------------|
| `signal` | `Signal` | Current signal value |
| `signal_int` | `int | None` | Signal as integer (0 or 1) |
| `is_connected` | `bool` | Connected to a wire segment |
| `is_unconnected` | `bool` | Not connected |
| `is_tied` | `bool` | Tied to constant (0, 1, x, z) |
| `is_tied_defined` | `bool` | Tied to 0 or 1 |
| `is_tied_undefined` | `bool` | Tied to x or z |
| `is_floating` | `bool` | Floating (z) |
| `is_undefined` | `bool` | Undefined (x) |
| `ws_path` | `WireSegmentPath` | Connected wire segment path |
| `ws` | `WireSegment` | Connected wire segment object |
| `wire_name` | `str` | Name of connected wire |
| `raw_ws_path` | `str` | Raw wire segment path string |
| `index` | `int` | Bit index in parent port |
| `parent` | `Port[Module] \| Port[Instance]` | Parent port |
| `grandparent` | `Module \| Instance` | Parent of parent |
| `path` | `PortSegmentPath` | Hierarchical path |

### WireSegment Properties

| Property | Type | Description |
|----------|------|-------------|
| `signal` | `Signal` | Current signal value |
| `is_constant` | `bool` | True if constant (0, 1, x, z) |
| `is_defined_constant` | `bool` | True if defined constant (0 or 1) |
| `port_segments` | `CustomList[PortSegment]` | Connected port segments |
| `nr_connected_ports` | `int` | Number of connected ports |
| `index` | `int` | Bit index in parent wire |
| `parent` | `Wire` | Parent wire |
| `grandparent` | `Module` | Parent module |
| `path` | `WireSegmentPath` | Hierarchical path |

### Shared Methods (both PortSegment and WireSegment)

#### `set_signal(signal: LogicLevel | Signal) -> None`
Set the signal value. **This is the only way to write signals.**

```python
port[0].set_signal(Signal.HIGH)
wire[3].set_signal('0')
```

#### `driver() -> List[PortSegment]` (WireSegment) / `Port | None` (Wire)
Get the driving port segment(s).

#### `loads() -> List[PortSegment]` (WireSegment) / `List[PortSegment]` (Wire)
Get the load port segment(s).

#### `has_no_driver() -> bool`
Check if no driver.

#### `has_multiple_drivers() -> bool`
Check for multiple drivers.

#### `has_no_loads() -> bool`
Check if no loads.

---

## Element Paths

Typed path objects for hierarchical navigation. All use **dot-separated** notation with **numeric segment indices**.

### Types

| Class | Example | Purpose |
|-------|---------|---------|
| `ModulePath` | `"top"` | Reference a module |
| `InstancePath` | `"top.u_adder"` | Reference an instance |
| `PortPath` | `"top.data_in"` | Reference a module port |
| `PortSegmentPath` | `"top.data_in.3"` | Reference bit 3 of a port |
| `WirePath` | `"top.addr_bus"` | Reference a wire |
| `WireSegmentPath` | `"top.addr_bus.7"` | Reference bit 7 of a wire |

### ElementPath Base Properties & Methods

| Property/Method | Type | Description |
|-----------------|------|-------------|
| `raw` | `str` | Raw path string |
| `sep` | `str` | Separator character (default `'.'`) |
| `type` | `EType` | Element type enum |
| `parts` | `List[str]` | Split path components |
| `name` | `str` | Last component (element name) |
| `parent` | `ElementPath` | Parent path |
| `hierarchy_level` | `int` | Number of hierarchy levels |
| `is_empty` | `bool` | Empty path check |
| `type_mapping` | `List[Tuple[str, EType]]` | Heuristic type mapping |

### Methods

#### `get(index: int) -> str`
Get component at index (returns `''` instead of raising).

#### `nth_parent(index: NonNegativeInt) -> ElementPath`
Get nth ancestor (0=self, 1=parent, 2=grandparent).

#### `has_parent(index: NonNegativeInt = 1) -> bool`
Check if nth parent exists.

#### `replace(old: str, new: str) -> Self`
Replace a path component.

#### `is_type(type: EType) -> bool`
Check if path type matches.

#### `get_subseq(lower_idx: int | None, upper_idx: int | None) -> List[str]`
Slice path components.

---

## ModuleGraph

A `networkx.MultiDiGraph` wrapper for module-level graph algorithms.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `nodes` | `NodeView` | NetworkX node view |
| `edges` | `EdgeView` | NetworkX edge view |

### Methods

#### `node_type(node_name: str) -> Literal['INSTANCE', 'PORT']`
Get node type.

#### `node_subtype(node_name: str) -> str`
Get node subtype (port direction or instance type).

#### `all_edges(node_name: str) -> Set[Tuple[str, str, str]]`
Get all edges connected to a node. Each tuple: `(source, target, edge_key)`.

#### `get_data(node_name: str, key: str) -> object`
Get node attribute data. Keys: `'ntype'`, `'nsubtype'`, `'ndata'`.

#### `set_data(node_name: str, val: object, key: str) -> None`
Set node attribute data.

### Usage with NetworkX

```python
G = module.graph()
import networkx as nx

# All simple paths
paths = nx.all_simple_paths(G, "input_port", "output_port")

# Cycles
cycles = nx.simple_cycles(G)

# Successors/predecessors
successors = list(G.successors("u_and"))
predecessors = list(G.predecessors("u_adder"))
```

---

## Pattern Matching

### `Pattern` — Find and Replace Subgraphs

```python
from netlist_carpentry import Pattern, ModuleGraph

pattern = Pattern(
    graph=pattern_graph,
    replacement_graph=replacement_graph,
    ignore_port_names=True,
    matching_constraints=[],
    ignore_boundary_conditions=False,
)
```

**Constructor Parameters:**
- `graph` (ModuleGraph): Pattern structure to find.
- `replacement_graph` (ModuleGraph): Replacement structure (optional).
- `ignore_port_names` (bool): Don't check port name matching.
- `matching_constraints` (List[Constraint]): Filtering constraints.
- `mapping` (Dict): Port mapping between pattern and replacement.
- `ignore_boundary_conditions` (bool): Ignore boundary checks.

### Methods

#### `find_matches(circuit_graph: ModuleGraph, max_match_count: int | None = None) -> Match`
Find all occurrences of the pattern in a circuit graph.

```python
match_result = pattern.find_matches(module.graph())
print(f"Found {match_result.count} matches")
```

**Returns:** `Match` object containing found matches.

#### `count_matches(circuit_graph: ModuleGraph) -> int`
Count matches without returning details.

#### `replace(module: Module) -> None`
Replace all matched patterns in a module (if replacement graph is set).

### Class Methods

#### `Pattern.get_mapping(pattern_module: Module, replacement_module: Module) -> Dict[Tuple[str, str, int], Tuple[str, str, int]]`
Generate port mapping between pattern and replacement modules.

---

## Signal Model

### `Signal` — 4-Value Logic Enum

```python
from netlist_carpentry import Signal

Signal.LOW        # '0' — logical zero
Signal.HIGH       # '1' — logical one
Signal.UNDEFINED  # 'x' — unknown
Signal.FLOATING   # 'z' — high-impedance
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_defined` | `bool` | True if 0 or 1 |
| `is_undefined` | `bool` | True if x or z |

### Methods

#### `Signal.get(sval: str | int | bool | Signal) -> Signal`
Convert various types to Signal.
```python
Signal.get('0')      # Signal.LOW
Signal.get(1)        # Signal.HIGH
Signal.get(True)     # Signal.HIGH
Signal.get('z')      # Signal.FLOATING
```

#### `Signal.parsable(signal_like: object) -> bool`
Check if value can be converted to Signal.

#### `~signal` (invert operator)
Invert a signal: `~Signal.LOW` → `Signal.HIGH`.

#### `signal & other` (AND operator)
Bitwise AND: `Signal.HIGH & Signal.LOW` → `Signal.LOW`.

#### `signal | other` (OR operator)
Bitwise OR: `Signal.HIGH | Signal.LOW` → `Signal.HIGH`.

#### `signal ^ other` (XOR operator)
Bitwise XOR: `Signal.HIGH ^ Signal.LOW` → `Signal.HIGH`.

#### `int(signal)` — Convert to int (only if defined).

---

### `SignalArray` — Multi-Bit Signal Container

```python
from netlist_carpentry import SignalArray

# From integer (LSB = index 0)
arr = SignalArray.from_int(0b1010, fixed_width=4)

# From binary string (MSB first by default)
arr = SignalArray.from_bin("1010")

# From list
arr = SignalArray.create([Signal.HIGH, Signal.LOW, Signal.UNDEFINED])

# From dict
arr = SignalArray.create({0: '1', 2: '1'})
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `signals` | `Dict[int, Signal]` | Index → Signal mapping |
| `is_defined` | `bool` | All bits defined (0 or 1) |
| `is_undefined` | `bool` | All bits undefined (x or z) |
| `signed` | `bool` | Whether signed |
| `msb_first` | `bool` | MSB-first ordering |

### Methods

#### `SignalArray.from_int(value: int, msb_first: bool = True, fixed_width: int | None = None) -> SignalArray`
Create from integer.

#### `SignalArray.from_bin(bin_str: str, msb_first: bool = True, fixed_width: int | None = None) -> SignalArray`
Create from binary string.

#### `SignalArray.create(data: list | dict | int | str, ...) -> SignalArray`
Create from various sources.

#### `int(signal_array)` — Convert to integer (only if all defined).

#### `str(signal_array)` — Convert to binary string (MSB first).

---

## Direction Enum

```python
from netlist_carpentry import Direction

Direction.IN      # 'input'
Direction.OUT     # 'output'
Direction.IN_OUT  # 'inout'
Direction.UNKNOWN # 'unknown'
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_input` | `bool` | True for IN or IN_OUT |
| `is_output` | `bool` | True for OUT or IN_OUT |
| `is_defined` | `bool` | True if not UNKNOWN |

### Methods

#### `Direction.get(value: str) -> Direction`
Convert string to Direction (case-insensitive).
```python
Direction.get('input')   # Direction.IN
Direction.get('OUT')     # Direction.OUT
Direction.get('InOut')   # Direction.IN_OUT
Direction.get('invalid') # Direction.UNKNOWN
```

---

## Configuration

### `CFG` — Global Settings

```python
from netlist_carpentry import CFG

CFG.log_level           # 3 (default: warnings and above)
CFG.print_source_module # False
CFG.id_external         # '__' (external naming prefix)
CFG.id_internal         # '§' (internal/primitive prefix)
CFG.allow_detached_segments  # False
CFG.yosys_executable   # 'yosys' (or 'yowasp-yosys')
```

### `ReadConfig` — Yosys Read Configuration

```python
from netlist_carpentry import ReadConfig

cfg = ReadConfig(
    files=[Path("design.v")],
    top="my_design",
    json_path=Path("out.json"),
    techmaps=None,
    share='off',              # 'off' | 'fast' | 'aggressive'
    environments=None,
    yosys_plugins=None,       # e.g., ["ghdl", "slang"]
    no_hierarchy=False,
    keep_memory_cells=False,
    insbuf=True,
)
```

**Properties:**
- `yosys_executable` — Shell command for Yosys.
- `script_template` — Yosys script template string.
- `yosys_commands()` — Formatted Yosys commands.
- `shell_script(path: Path | None)` — Generate shell script content.

---

## Built-in Routines

### Optimization

```python
from netlist_carpentry.routines.opt import (
    clean_circuit,      # Remove unused modules
    opt_constant,       # Constant propagation & mux optimization
    opt_driverless,     # Remove instances with no driver
    opt_loadless,       # Remove wires with no load
    opt_chains,         # Floodfill chain optimization
)
```

#### `opt_constant(module: Module) -> bool`
Propagate constants through the module. Returns True if changes made.

#### `opt_driverless(module: Module) -> bool`
Remove instances with no driver (all inputs tied or undriven).

#### `opt_loadless(module: Module) -> bool`
Remove wires with no load (dangling nets).

#### `clean_circuit(circuit: Circuit) -> bool`
Remove unused modules from the circuit.

#### `opt_chains(circuit: Circuit) -> ChainsResult`
Optimize chain structures (e.g., shift registers).

### Checking

```python
from netlist_carpentry.routines.check import fanout, find_comb_loops, has_comb_loops
```

#### `has_comb_loops(module: Module) -> bool`
Check for combinational loops.

#### `find_comb_loops(module: Module) -> List[List[str]]`
Find all combinational loop chains.

#### `fanout(module: Module, sort_by: str = 'number') -> Dict[str, int]`
Calculate fanout counts for all instances.

---

## Gate Library

All primitive gates are in `netlist_carpentry.utils.gate_lib`, prefixed with `§`.

### Lookup

```python
from netlist_carpentry.utils.gate_lib import get, AndGate, OrGate, DFF

gate_class = get("§and")  # Returns AndGate class
```

### Available Gate Classes

| Class | Instance Type | Ports | Description |
|-------|--------------|-------|-------------|
| `Buffer` | `§buf` | I, O | Buffer |
| `NotGate` | `§not` | I, O | Inverter |
| `AndGate` | `§and` | A, B, Y | AND |
| `OrGate` | `§or` | A, B, Y | OR |
| `XorGate` | `§xor` | A, B, Y | XOR |
| `XnorGate` | `§xnor` | A, B, Y | XNOR |
| `NorGate` | `§nor` | A, B, Y | NOR |
| `NandGate` | `§nand` | A, B, Y | NAND |
| `Adder` | `§add` | A, B, S, C_OUT | Adder |
| `Subtractor` | `§sub` | A, B, D, B_OUT | Subtractor |
| `Multiplexer` | `§mux` | D0..Dn, S, Y | MUX (bit_width param) |
| `Demultiplexer` | `§demux` | D, S0..Sn, Y0..Yn | DEMUX |
| `DFF` | `§dff` | CLK, D, Q | D flip-flop |
| `ADFF` | `§adff` | CLK, D, RST, Q | Async reset DFF |
| `DFFE` | `§dffe` | CLK, EN, D, Q | Enable DFF |
| `ScanDFF` | `§scan_dff` | CLK, D, S, Q | Scan DFF |
| `DLatch` | `§dlatch` | EN, D, Q | D latch |
| `ShiftLeft` | `§shl` | A, B, Y | Shift left logical |
| `ShiftRight` | `§shr` | A, B, Y | Shift right logical |
| `ReduceAnd` | `§reduce_and` | A, Y | AND reduction |
| `ReduceOr` | `§reduce_or` | A, Y | OR reduction |
| `ReduceXor` | `§reduce_xor` | A, Y | XOR reduction |
| `LessThan` | `§lt` | A, B, Y | Less than |
| `Equal` | `§eq` | A, B, Y | Equality |
| `GreaterThan` | `§gt` | A, B, Y | Greater than |

### Gate Mixins

Combine with gate classes for extended functionality:

```python
from netlist_carpentry.utils.gate_mixins import ClkMixin, RstMixin, EnMixin, ScanMixin, SRMixin, LoadMixin
from netlist_carpentry.utils.gate_lib import DFF

class MyDFF(ClkMixin, RstMixin, DFF):
    pass

inst = module.create_instance(MyDFF, "u_ff")
```

---

## Equivalence Checking

### `run_eqy()` — Formal Equivalence Check

```python
from netlist_carpentry import run_eqy

result = run_eqy(
    gold_files=["gold.v"],
    gate_files=["gate.v"],
    gold_top="gold_top",
    gate_top="gate_top",
    script_path=Path("script.eqy"),
    output_path=Path("out"),
    overwrite=True,
    quiet=False,
)
```

**Parameters:**
- `gold_files` (List[str]): Gold design Verilog files.
- `gate_files` (List[str]): Gate-level design Verilog files.
- `gold_top` (str): Top module of gold design.
- `gate_top` (str): Top module of gate design.
- `script_path` (Path): Output EQY script path.
- `output_path` (Path): Output directory.
- `overwrite` (bool): Overwrite existing files.
- `quiet` (bool): Suppress Yosys output.

**Returns:** `subprocess.Popen[str]` — Yosys process handle.

### `run_equiv()` — Generate Miter Circuit

```python
from netlist_carpentry import run_equiv

result = run_equiv(circuit_a, circuit_b, "top_module", out_dir=Path("miter_out"))
```

### `run_equiv_miter()` — Create Miter Circuit Object

```python
from netlist_carpentry import run_equiv_miter

miter_circuit = run_equiv_miter(circuit_a, circuit_b, "top")
```

---

## Constants & Utilities

### Wire Segment Constants

```python
from netlist_carpentry import (
    WIRE_SEGMENT_0,   # Constant 0
    WIRE_SEGMENT_1,   # Constant 1
    WIRE_SEGMENT_X,   # Undefined (x)
    WIRE_SEGMENT_Z,   # Floating (z)
    CONST_MAP_VAL2OBJ,   # String → WireSegment mapping
    CONST_MAP_VAL2VERILOG, # String → Verilog string mapping
    CONST_MAP_YOSYS2OBJ,   # Yosys → WireSegment mapping
)
```

### Other Exports

| Name | Type | Description |
|------|------|-------------|
| `EMPTY_GRAPH` | `ModuleGraph` | Empty ModuleGraph singleton |
| `EMPTY_PATTERN` | `Pattern` | Empty Pattern singleton |
| `NC_DIR` | `Path` | NetlistCarpentry package directory |
| `NC_SCRIPTS_DIR` | `Path` | Scripts directory |
| `VERILOG_KEYWORDS` | `Set[str]` | Reserved Verilog keywords |
| `HAS_VCD` | `bool` | VCD support available |
| `gate_factory` | `module` | Gate factory utilities |
| `gate_lib` | `module` | Gate library module |
