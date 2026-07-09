# NetlistCarpentry — Digital Circuit Analysis & Modification Library

## What It Is

**NetlistCarpentry** is a Python library for loading, navigating, analyzing, modifying, and exporting digital circuits (Verilog/VHDL netlists). It converts RTL descriptions into a rich, Pythonic object model backed by a [NetworkX MultiDiGraph](https://networkx.org), enabling graph algorithms, pattern matching, optimization, and equivalence checking.

**Key stack:** Python 3.9+, [Yosys](https://github.com/YosysHQ/yosys) (via `yowasp-yosys`) for RTL→JSON conversion, Pydantic models, NetworkX, Z3 solver.

---

## Entry Point — Loading a Circuit

```python
from netlist_carpentry import read

# Load from one or more Verilog/VHDL files
circuit = read("my_design.v")

# Optionally set the top module
circuit.set_top("my_design")

# Or load with custom Yosys configuration
from netlist_carpentry import ReadConfig, read_via_cfg
cfg = ReadConfig(files=["design.v"], top="my_design")
circuit = read_via_cfg(cfg)
```

The `read()` function:
1. Calls Yosys to convert RTL → JSON netlist
2. Parses the JSON into a `Circuit` object with full Pythonic access
3. Returns a `Circuit` ready for analysis or modification

You can also load from an existing JSON file directly:
```python
from netlist_carpentry import read_json
circuit = read_json("netlist.json")
```

---

## Core Data Model

### Circuit — The Root Container

A `Circuit` holds all modules and tracks the top-level module.

```python
circuit.name                    # Circuit name
circuit.modules                 # CustomDict[str, Module] — all modules by name
circuit.top                     # Module — the top-level module
circuit.has_top                 # bool
circuit.instances               # DefaultDict[str, List[InstancePath]] — all instances by type
circuit.creator                 # Creator string

# Navigation
circuit["module_name"]          # Get a module by name
circuit.get_from_path("top.inst.subinst")  # Resolve hierarchical paths
circuit.get_path_from_str("top.inst.port.0")  # String → ElementPath

# Module management
circuit.add_module(module)
circuit.remove_module("name")
circuit.copy_module("old", "new_name")
circuit.create_module("new_name")
circuit.set_top("top_module")

# I/O — Reading and Writing
Circuit.read(["design.v"])      # Class method: read Verilog → Circuit (returns Circuit)
Circuit.read(cfg)               # Class method: read with ReadConfig
circuit.write("output.v")       # Instance method: write Circuit → Verilog file
circuit.write("output.v", overwrite=True)  # Overwrite if exists
```

### Module — A Single Design Unit

A `Module` represents one Verilog module/VHDL entity. It contains instances, ports, and wires.

```python
module.name                     # Module name
module.instances                # CustomDict[str, Instance] — submodule/gate instances
module.ports                    # CustomDict[str, Port[Module]] — module ports
module.wires                    # CustomDict[str, Wire] — internal wires

# Search
module.get_instances(name="foo", type="§and", fuzzy=True, recursive=True)
module.get_ports(direction=Direction.IN, fuzzy=False)
module.get_wires(name="data_bus", fuzzy=True)

# Submodules (instances that reference other modules in the circuit)
module.submodules               # List of Instance objects that are submodules

# BFS/DFS traversal
for inst in module.bfs_instances(): ...
for inst in module.dfs_instances(): ...

# Evaluation (signal propagation simulation)
module.evaluate()               # Propagate signals through the module
```

### Instance — A Gate or Submodule Instantiation

```python
inst.name                       # Instance name (e.g., "u_adder")
inst.instance_type              # Type string (e.g., "§and" for primitive gates, or a module name)
inst.parameters                 # Parameters (width, delay, etc.)
inst.connections                # Dict[str, Dict[int, WireSegmentPath]] — port → wire mappings
inst.ports                      # CustomDict[str, Port[Instance]] — instance ports

# Port access
inst.input_ports                # List of input Port[Instance]
inst.output_ports               # List of output Port[Instance]
inst.port["clk"]                # Get a specific port
```

### Port — Module or Instance I/O

```python
port.name                       # Port name
port.direction                  # Direction.IN / Direction.OUT / Direction.IN_OUT
port.width                      # Bit width (PositiveInt)
port.segments                   # CustomDict[int, PortSegment] — per-bit segments
port.signal                     # Signal (LOW/HIGH/UNDEFINED/FLOATING)

# Subscripting for bit access (also works on Wire)
port[0]                         # PortSegment at index 0 (returns PortSegment object)
len(port)                       # Number of segments (= width)
```

### Wire — Internal Net Connection

```python
wire.name                       # Wire name
wire.width                      # Bit width
wire.segments                   # CustomDict[int, WireSegment] — per-bit segments
wire.connected_port_segments    # Dict mapping port segments connected to this wire
```

### WireSegment / PortSegment — Per-Bit Elements

The lowest level: individual bits of wires and ports.

```python
seg.raw                         # Signal value: '0', '1', 'x', 'z'
seg.ws_path                     # WireSegmentPath — what this segment connects to
seg.is_connected / seg.is_unconnected
seg.loads()                     # PortSegments that load from this wire segment
seg.driver()                    # The driver of this segment
```

---

## Element Paths — Hierarchical Navigation

NetlistCarpentry uses typed path objects for precise hierarchical access. Paths use **dot-separated** components with **numeric segment indices** (not bracket notation).

| Path Type | Example | Purpose |
|-----------|---------|---------|
| `ModulePath` | `"top"` | Reference a module |
| `InstancePath` | `"top.u_adder"` | Reference an instance |
| `PortPath` | `"top.data_in"` | Reference a module port |
| `PortSegmentPath` | `"top.data_in.3"` | Reference bit 3 of a port (NOT `"top.data_in[3]"`) |
| `WirePath` | `"top.addr_bus"` | Reference a wire |
| `WireSegmentPath` | `"top.addr_bus.7"` | Reference bit 7 of a wire (NOT `"top.addr_bus[7]"`) |

The path format is: `module_name.instance_name.port_or_wire_name.segment_index`

```python
from netlist_carpentry import Circuit

circuit = read("design.v")
elem = circuit.get_from_path("top.u_adder.sum.4")  # Returns PortSegment at index 4
path = circuit.get_path_from_str("top.u_adder.clk")  # Returns PortPath
```

**Key details:**
- Segment indices are **dot-separated integers**, not bracket notation
- The path hierarchy is: `module → instance(s) → port/wire → segment_index`
- For module-level ports (no instance): `"top.data_in.3"`
- For instance ports: `"top.u_adder.sum.4"`
- Path strings can be resolved automatically via `circuit.get_path_from_str()` which infers the correct path type

---

## Modifying Circuits

### Creating Elements

```python
module = circuit["my_module"]

# Create a port
port = module.create_port("new_signal", Direction.IN, width=8)

# Create a wire
wire = module.create_wire("internal_net", width=4)

# Create an instance (submodule or primitive gate)
inst = module.create_instance(module.circuit["sub_module"], "u_sub")
# Or use a primitive gate from the built-in library:
from netlist_carpentry.utils.gate_lib import AndGate
inst = module.create_instance(AndGate, "u_and")
```

### Connecting Elements

```python
# Connect source → target (auto-creates wires if needed)
module.connect(source_port, target_port)
module.connect(wire_segment, port_segment)
module.connect("top.wire.0", "top.inst.port.1")  # Path strings work too (dot-separated segment indices)

# Disconnect
module.disconnect(port_segment)
```

### Removing Elements

```python
module.remove_instance("u_inst")
module.remove_port("old_signal")
module.remove_wire("unused_net")
circuit.remove_module("unused_module")
```

### Substituting Instances

```python
# Replace an instance with a different type, preserving connections
module.refine_instance("u_old", NewGateClass)
module.substitute_instance("u_old", new_instance)
```

---

## Built-in Gate Library

The `gate_lib` module provides primitive gate classes, all prefixed with `§` (configurable via `CFG.id_internal`). These are the actual classes available:

### Unary Gates
| Class | Instance Type | Description |
|-------|--------------|-------------|
| `Buffer` | `§buf` | Buffer (pass-through) |
| `NotGate` | `§not` | Inverter |
| `PosGate` | `§pos` | Arithmetic plus (sign extend) |
| `NegGate` | `§neg` | Arithmetic negator (two's complement) |

### Binary Gates
| Class | Instance Type | Description |
|-------|--------------|-------------|
| `AndGate` | `§and` | AND |
| `OrGate` | `§or` | OR |
| `XorGate` | `§xor` | XOR |
| `XnorGate` | `§xnor` | XNOR |
| `NorGate` | `§nor` | NOR |
| `NandGate` | `§nand` | NAND |
| `BitwiseCaseEquality` | `§caseeq` | Case equality (handles x/z) |

### Shift Gates
| Class | Instance Type | Description |
|-------|--------------|-------------|
| `ShiftLeft` | `§sll` | Shift left logical |
| `ShiftRight` | `§srl` | Shift right logical |
| `ArithmeticShiftLeft` | `§asl` | Arithmetic shift left |
| `ArithmeticShiftRight` | `§asr` | Arithmetic shift right |
| `ShiftSigned` | `§ssll` | Signed shift left |
| `ShiftX` | `§sxl` | Shift with x fill |

### Reduction Gates
| Class | Instance Type | Description |
|-------|--------------|-------------|
| `ReduceAnd` | `§reduce_and` | AND of all bits |
| `ReduceOr` | `§reduce_or` | OR of all bits |
| `ReduceBool` | `§reduce_bool` | NOR of all bits |
| `ReduceXor` | `§reduce_xor` | XOR of all bits |
| `ReduceXnor` | `§reduce_xnor` | XNOR of all bits |
| `LogicNot` | `§logic_not` | Logical NOT (non-zero → 1) |

### Comparison Gates (Binary N-to-1)
| Class | Instance Type | Description |
|-------|--------------|-------------|
| `LogicAnd` | `§logic_and` | Logical AND of two operands |
| `LogicOr` | `§logic_or` | Logical OR of two operands |
| `LessThan` | `§lt` | Less than |
| `LessEqual` | `§le` | Less or equal |
| `Equal` | `§eq` | Equality |
| `CaseEqual` | `§caseeq_cmp` | Case equality comparison |
| `NotEqual` | `§ne` | Not equal |
| `CaseNotEqual` | `§caseneq` | Case not-equal comparison |
| `GreaterThan` | `§gt` | Greater than |
| `GreaterEqual` | `§ge` | Greater or equal |

### Arithmetic Gates
| Class | Instance Type | Description |
|-------|--------------|-------------|
| `Adder` | `§add` | Adder |
| `Subtractor` | `§sub` | Subtractor |
| `Multiplier` | `§mul` | Multiplier |
| `Divider` | `§div` | Divider |
| `Modulo` | `§mod` | Modulo |
| `Exponentiator` | `§exp` | Exponentiation |

### Multiplexer / Demultiplexer
| Class | Instance Type | Description |
|-------|--------------|-------------|
| `Multiplexer` | `§mux` | N-to-1 MUX (configurable via `bit_width` parameter: 2^bit_width inputs) |
| `Demultiplexer` | `§demux` | 1-to-N DEMUX (configurable via `bit_width` parameter) |

### Storage Elements (Flip-Flops & Latches)
| Class | Instance Type | Description |
|-------|--------------|-------------|
| `DFF` | `§dff` | D flip-flop (CLK, D, Q) |
| `ADFF` | `§adff` | DFF with async reset (CLK, D, RST, Q) |
| `DFFE` | `§dffe` | DFF with enable (CLK, EN, D, Q) |
| `ADFFE` | `§adffe` | DFF with async reset + enable |
| `SDFF` | `§sdff` | DFF with sync reset (CLK, RST, D, Q) |
| `SDFFCE` | `§sdffce` | DFF with sync reset + enable |
| `SDFFE` | `§sdffe` | DFF with sync reset + enable (alt.) |
| `ALDFF` | `§aldff` | DFF with async load (CLK, LD, D, Q) |
| `ALDFFE` | `§aldffe` | DFF with async load + enable |
| `DFFSR` | `§sdffsr` | DFF with set/reset (CLK, S, R, Q) |
| `DFFSRE` | `§sdffsre` | DFF with set/reset + enable |
| `DLatch` | `§dlatch` | D latch (EN, D, Q) |

### Scan Flip-Flops
| Class | Instance Type | Description |
|-------|--------------|-------------|
| `ScanDFF` | `§scan_dff` | Scan-capable DFF |
| `ScanADFF` | `§scan_adff` | Scan DFF with async reset |
| `ScanDFFE` | `§scan_dffe` | Scan DFF with enable |
| `ScanADFFE` | `§scan_adffe` | Scan DFF with async reset + enable |

### Mixins (combine with gate classes)

Gate classes inherit from mixins for additional functionality:
- `ClkMixin` — clock port (inherited by DFF and variants)
- `RstMixin` — reset port
- `EnMixin` — enable port
- `ScanMixin` — scan chain support
- `SRMixin` — set/reset ports
- `LoadMixin` — async load port

Use them directly as interface definitions for `create_instance()`:

```python
from netlist_carpentry.utils.gate_lib import DFF, AndGate, Multiplexer
from netlist_carpentry.utils.gate_mixins import ClkMixin, RstMixin

# Create a D flip-flop with clock and reset
class MyDFF(ClkMixin, RstMixin, DFF):
    pass

inst = module.create_instance(MyDFF, "u_ff")

# Create a 4-to-1 multiplexer (bit_width=2 → 2^2=4 inputs)
mux = module.create_instance(Multiplexer, "u_mux")
mux.parameters.BIT_WIDTH = 2   # 4 data inputs: D0, D1, D2, D3
mux.parameters.WIDTH = 8       # 8-bit data width
```

---

## ModuleGraph — NetworkX Integration

Every module has an associated `ModuleGraph` (a `networkx.MultiDiGraph`) for graph algorithms:

```python
from netlist_carpentry import ModuleGraph

graph = module.graph  # ModuleGraph instance

# Node types: 'INSTANCE' or 'PORT'
graph.node_type("u_and")           # 'INSTANCE'
graph.node_subtype("u_and")        # '§and'

# Edges represent connections between nodes
all_edges = graph.all_edges("u_and")  # Set of (src, dst, edge_key)

# Use any NetworkX algorithm
import networkx as nx
paths = nx.all_simple_paths(graph, source="input_port", target="output_port")
cycles = nx.simple_cycles(graph)
```

---

## Pattern Matching & Replacement

Define a pattern as a subgraph and find/replace it in the circuit:

```python
from netlist_carpentry import Pattern, ModuleGraph

# Build a pattern graph (the subgraph to search for)
pattern_graph = ModuleGraph()
# ... add nodes and edges representing the pattern ...

# Optionally define a replacement graph
replacement_graph = ModuleGraph()
# ... the simplified/replacement circuit ...

pattern = Pattern(pattern_graph, replacement_graph)

# Find all matches in a module
matches = pattern.match(module)
print(f"Found {matches.count} occurrences")

# Replace all matches
pattern.replace(module)
```

Constraints can filter matches:
```python
from netlist_carpentry import CASCADING_OR_CONSTRAINT
# Constraints ensure structural properties of matches
```

---

## Built-in Routines

### Analysis (read-only checks)

```python
from netlist_carpentry.routines.check import fanout, find_comb_loops, has_comb_loops

# Check for combinational loops
if has_comb_loops(module):
    loops = find_comb_loops(module)  # List of loop chains

# Fanout analysis
fanout_counts = fanout(module)
```

### Optimization

```python
from netlist_carpentry.routines.opt import (
    clean_circuit,      # Remove unused modules
    opt_constant,       # Constant propagation & mux optimization
    opt_driverless,     # Remove instances with no driver
    opt_loadless,       # Remove wires with no load
    opt_chains,         # Floodfill chain optimization
)

# Optimize a single module
opt_constant(module)
opt_driverless(module)

# Clean entire circuit (removes unused modules)
clean_circuit(circuit)
```

### Design-For-Test

```python
from netlist_carpentry.routines.dft import scan_chain_insertion
# Automatic scan-chain insertion for testability
```

---

## Equivalence Checking

NetlistCarpentry integrates with [eqy](https://github.com/alexghergh/equivalence-checking) (via `yosys-eqy`) for formal equivalence checking:

```python
from netlist_carpentry import run_eqy, run_equiv, run_equiv_miter

# Run eqy equivalence check between two circuits
result = run_eqy(original_netlist, modified_netlist, top_module="my_design")

# Or generate a miter circuit for external verification
miter = run_equiv_miter(circuit_a, circuit_b, "top")
```

---

## Writing Output

Export the modified circuit back to Verilog:

```python
from netlist_carpentry import write

write(circuit, "output_design.v", overwrite=True)
```

---

## Signal Model

Digital signals use a 4-value logic system:

```python
from netlist_carpentry import Signal

Signal.LOW        # '0' — logical zero
Signal.HIGH       # '1' — logical one
Signal.UNDEFINED  # 'x' — unknown/undefined
Signal.FLOATING   # 'z' — high-impedance

# Parsing from various sources
Signal.get('0')           # Signal.LOW
Signal.get(True)          # Signal.HIGH
Signal.get(1)             # Signal.HIGH
Signal.parsable('x')      # True
```

---

## Signal Handling & Evaluation

### Key Principle: Read vs. Write

**Reading signals is always direct attribute access.** **Writing signals requires calling `set_signal()` — direct assignment like `port[0].signal = Signal.HIGH` does NOT work.**

```python
# ✅ READ — direct attribute access on segments, ports, wires
seg_signal = port[0].signal           # Returns Signal enum value
wire_signal = wire[3].signal          # Returns Signal enum value
port_all_signals = port.signal        # Returns Signal (dominant signal of all segments)
port_array = port.signal_array        # Returns SignalDict — full multi-bit state
wire_array = wire.signal_array        # Returns SignalArray — full multi-bit state

# ✅ WRITE on PortSegment / WireSegment — use set_signal() method
port[0].set_signal(Signal.HIGH)       # Set bit 0 of port to HIGH
port[0].set_signal('1')               # String shorthand also works
port[0].set_signal(1)                 # Integer shorthand also works

wire[3].set_signal(Signal.LOW)        # Set wire bit 3 to LOW

# ✅ WRITE on Port (multi-bit) — use set_signal(index) or set_signals()
port.set_signal(Signal.HIGH, index=0) # Set bit 0 of port to HIGH
port.set_signal(Signal.LOW, index=1)  # Set bit 1 of port to LOW

port.set_signals(0b1010)              # Set all bits from integer (LSB=bit 0)
port.set_signals("1010")              # Set all bits from binary string
port.set_signals({0: '1', 2: '1'})    # Set specific bits from dict

# ✅ WRITE on Wire (multi-bit) — same as Port
wire.set_signal(Signal.HIGH, index=0)
wire.set_signals(0b1100)              # Set all bits from integer

# ✅ WRITE via Circuit — set signals by path string
circuit.set_signal("top.in1", Signal.HIGH)       # Set entire port
circuit.set_signal("top.in1.0", Signal.LOW)      # Set specific segment
circuit.set_signal("top.wire_a.3", 'z')          # String shorthand

# ❌ WRONG — direct assignment does NOT work
port[0].signal = Signal.HIGH    # This is a READ, not a write!
wire[3].signal = Signal.LOW     # This is a READ, not a write!
```

### Tying Signals to Constants

Use `tie_signal()` to permanently tie a port segment to a constant value (0, 1, x, z). This is different from `set_signal()` — tied signals cannot be overwritten during evaluation:

```python
# Tie a port bit to a constant
port[0].tie_signal('0')           # Tie to LOW (constant 0)
port[1].tie_signal('1')           # Tie to HIGH (constant 1)
port[2].tie_signal('z')           # Tie to floating (high-impedance)
port[3].tie_signal('x')           # Tie to undefined (unconnected)

# Tie on Port object (specify index)
port.tie_signal('1', index=0)     # Same as port[0].tie_signal('1')

# Tie on Circuit via path
circuit.set_signal("top.in1", Signal.HIGH)  # Sets signal (not tied)
```

**When to use `set_signal()` vs `tie_signal()`:**
- `set_signal()` — temporary signal setting, overwritten during evaluation if driven by a wire
- `tie_signal()` — permanent constant binding, survives evaluation (used for constant propagation)

### Signal Evaluation Process

The evaluation process propagates signals through the circuit in breadth-first order, starting from input ports:

```python
from netlist_carpentry import read

circuit = read("design.v")
module = circuit["my_module"]

# Step 1: Set input signals (use set_signal, NOT direct assignment)
module.ports['clk'].set_signal(Signal.HIGH)
module.ports['data_in'].set_signal(Signal.LOW)
module.ports['data_in'].set_signal(Signal.HIGH, index=1)  # Set bit 1

# Step 2: Evaluate — propagates signals through all instances and wires
module.evaluate()

# Step 3: Read results
assert module.ports['out'].signal == Signal.LOW           # Output port signal
assert module.wires['internal'].signal_array[0] == Signal.HIGH  # Wire bit state
assert module.get_instance('u_and').ports['Y'].signal == Signal.LOW  # Instance port
```

**Evaluation flow:**
1. Starts from input ports and constant-driven instances
2. Evaluates wire segments (propagates driver signal to loads)
3. Evaluates instances (computes gate logic, propagates to output ports)
4. Recursively evaluates downstream wires and instances
5. For hierarchical modules: evaluates submodules in-place

**For sequential elements (DFF, etc.):** Evaluation updates outputs on clock edges based on input states. Call `evaluate()` multiple times for multi-cycle simulation.

### Multi-Bit Signal Handling with SignalArray

```python
from netlist_carpentry import SignalArray

# Create from integer (LSB = index 0)
arr = SignalArray.from_int(0b1010, fixed_width=4)
# arr.signals = {0: HIGH, 1: LOW, 2: HIGH, 3: LOW}

# Create from binary string (MSB first by default)
arr = SignalArray.from_bin("1010")
# arr.signals = {0: LOW, 1: HIGH, 2: LOW, 3: HIGH}

# Create from list
arr = SignalArray.create([Signal.HIGH, Signal.LOW, Signal.UNDEFINED])

# Create from dict
arr = SignalArray.create({0: '1', 2: '1'})

# Read as integer (only if all signals are defined)
value = int(arr)  # Returns Python int

# Read as binary string
str(arr)  # Returns "1010" (MSB first)

# Check signal states
arr.is_defined      # True if all bits are 0 or 1
arr.is_undefined    # True if all bits are x or z
```

### Practical Evaluation Examples

**Example 1: Simulating a combinational circuit**
```python
circuit = read("alu.v")
alu = circuit["alu"]

# Set inputs
alu.ports['a'].set_signals(0b0011)    # a = 3
alu.ports['b'].set_signals(0b1100)    # b = 12
alu.ports['op'].set_signal('0', index=0)  # op = ADD

# Evaluate
alu.evaluate()

# Read output
result = int(alu.ports['result'].signal_array)  # result = 15
```

**Example 2: Simulating a sequential circuit (DFF)**
```python
circuit = read("counter.v")
cnt = circuit["counter"]

# Initial state: set clock low, data high
cnt.ports['clk'].set_signal(Signal.LOW)
cnt.ports['data'].set_signal(Signal.HIGH)
cnt.evaluate()

# Clock cycle 1: rising edge
cnt.ports['clk'].set_signal(Signal.HIGH)
cnt.evaluate()
# Q now reflects the data input

# Clock cycle 2: falling edge
cnt.ports['clk'].set_signal(Signal.LOW)
cnt.evaluate()

# Clock cycle 3: rising edge with new data
cnt.ports['data'].set_signal(Signal.LOW)
cnt.ports['clk'].set_signal(Signal.HIGH)
cnt.evaluate()
```

**Example 3: Using Circuit.set_signal for quick input setting**
```python
circuit = read("design.v")

# Set multiple inputs via path strings
circuit.set_signal("top.in_a", Signal.HIGH)
circuit.set_signal("top.in_b.0", Signal.LOW)
circuit.set_signal("top.in_b.1", Signal.HIGH)

# Evaluate and check
circuit.evaluate()
output = circuit.get_from_path("top.out")
```

**Example 4: Constant propagation optimization**
```python
from netlist_carpentry.routines.opt import opt_constant

circuit = read("design.v")
module = circuit["top"]

# Tie some inputs to constants (simulating known input conditions)
module.ports['mode'].tie_signal('1')
module.ports['enable'].tie_signal('0')

# Run constant propagation — eliminates dead logic
opt_constant(module)

# The circuit is now simplified based on the constant inputs
```

---

## Typical Workflow

```python
from netlist_carpentry import read, write, Circuit
from netlist_carpentry.routines.opt import opt_constant, clean_circuit
from netlist_carpentry.routines.check import has_comb_loops

# 1. Load
circuit = read("design.v")
circuit.set_top("design")

# 2. Analyze
if has_comb_loops(circuit):
    loops = find_comb_loops(circuit)
    print(f"Combinational loops: {loops}")

# 3. Navigate & inspect
top = circuit.top
for inst_name, inst in top.instances.items():
    print(f"  {inst_name}: type={inst.instance_type}, ports={list(inst.ports.keys())}")

# 4. Modify
new_inst = top.create_instance(AndGate, "u_new_and")
top.connect(top.wires["net_a"][0], new_inst.ports["A"][0])   # Connect bit 0 of wire to port A
top.connect(top.wires["net_b"][0], new_inst.ports["B"][0])   # Connect bit 0 of wire to port B
top.connect(new_inst.ports["Y"][0], top.wires["net_out"][0]) # Connect output Y bit 0 to wire

# 5. Optimize
opt_constant(top)
clean_circuit(circuit)

# 6. Export
write(circuit, "design_modified.v", overwrite=True)
```

---

## Where It's Helpful

- **RTL analysis**: Navigate complex designs, understand signal flow, find combinational loops, analyze fanout
- **Automated optimization**: Constant propagation, dead logic removal, chain optimization
- **Pattern-based refactoring**: Find and replace circuit patterns (e.g., replace multi-level logic with LUTs)
- **Design-for-test**: Automatic scan chain insertion
- **Circuit transformation**: Modify netlists programmatically (add wrappers, insert debug logic, restructure)
- **Equivalence checking**: Verify that modifications preserve functionality
- **Research & education**: Experiment with synthesis/optimization algorithms in Python
- **Pre/post-synthesis comparison**: Load synthesized netlists and compare with RTL descriptions

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `src/netlist_carpentry/__init__.py` | Public API exports (`read`, `write`, `Circuit`, `Module`, etc.) |
| `src/netlist_carpentry/core/circuit.py` | `Circuit` class — root container |
| `src/netlist_carpentry/core/netlist_elements/module.py` | `Module` class — design unit |
| `src/netlist_carpentry/core/netlist_elements/instance.py` | `Instance` class — gate/submodule |
| `src/netlist_carpentry/core/netlist_elements/port.py` | `Port` class — I/O ports |
| `src/netlist_carpentry/core/netlist_elements/wire.py` | `Wire` class — internal nets |
| `src/netlist_carpentry/core/graph/module_graph.py` | `ModuleGraph` — NetworkX wrapper |
| `src/netlist_carpentry/core/graph/pattern.py` | `Pattern` — pattern matching |
| `src/netlist_carpentry/utils/gate_lib.py` | Built-in primitive gate library |
| `src/netlist_carpentry/io/read/read_utils.py` | `read()`, `read_json()` entry points |
| `src/netlist_carpentry/io/write/write_utils.py` | `write()` — export to Verilog |
| `src/netlist_carpentry/routines/opt/` | Optimization routines |
| `src/netlist_carpentry/routines/check/` | Analysis/checking routines |
| `src/netlist_carpentry/routines/dft/` | Design-for-test routines |

---

## Configuration

```python
from netlist_carpentry import CFG

CFG.id_internal       # Internal identifier prefix (default: §) — distinguishes primitives from modules
CFG.nc_identifier_internal  # Same as id_internal
```

---

## Notes for AI Agents

- **Always start with `read()`** — this is the single entry point to load any circuit
- **Use `circuit.set_top()`** after loading if the top module isn't automatically detected
- **Path strings** like `"top.inst.port.0"` (dot-separated, NOT bracket notation) are convenient but use typed `ElementPath` objects for robustness
- **Connections require matching widths** — multi-bit connections need segment-by-segment wiring or equal-width ports
- **Elements are locked after certain operations** — check `element.locked` before modifying
- **The gate library uses `§` prefix** — primitive gates have types like `"§and"`, `"§dff"`, etc.
- **Signal propagation via `module.evaluate()`** performs one-step simulation; call iteratively for multi-level propagation
- **Pattern matching operates on ModuleGraph** — build pattern graphs with the same node/edge structure as circuit graphs
- **Modifications are tracked internally** — the library maintains consistency across changes
