# Netlist Carpentry

Netlist Carpentry is a Python library that allows you to access and modify a digital circuit in an accessible way. It covers the following use cases:

* Navigate through your circuit and introduce custom checks
* Create a new algorithm that does some new optimization with your circuit
* ...

It uses Yosys (https://github.com/YosysHQ/yosys) to get the circuit from a behavioral code and converts it into a pythonic structure along with a networkx graph (https://networkx.org). This allows for using standard graph algorithms on the circuit as well as pretty-printing facilities.

Once in Python, the structure can be examined and modified. Netlist carpentry internally tracks all the changes and lets you write out your modified circuit to Verilog.
Back in verilog, the most simulation or synthesis tools can be used.

Example:
```python
import netlist_carpentry

# Load your Circuit
circuit = netlist_carpentry.read("simpleAdder.v")
# Define your top module
circuit.set_top('simpleAdder')

print(f"The top module '{top_module.name}' has the following items:")
for instance_name, instance_object in top_module.instances.items():
    print(f"\tInstance '{instance_name}'.")

for port_name, port_object in top_module.ports.items():
    print(f"\tPort '{port_name}', which is an {port_object.direction} port and {port_object.width} bit wide!")

for wire_name, wire_object in top_module.wires.items():
    print(f"\tWire '{wire_name}', which is {wire_object.width} bit wide!")
```

Netlist carpentry is designed for making the access to the circuit as easy as possible. The runtime-performance was not always in focus -- so don't expect it to work as fast as a custom-knitted C++ software. If you want to propose changes, please submit an issue or even a pull request.


## Installation

Install the package via...

```bash
pip install netlist-carpentry
```

... and have fun!

The package requires at least Python 3.9.

Alternatively, you can clone this repository and install the package in editable mode.


## Examples
The examples are located in `docs/src/user_guide` along with the documentation.


## Acknowledgement

The DI-Meta-X project where this software has been developed is funded by the German Federal Ministry of Research, Technology and Space under the reference 16ME0976. Responsibility for the content of this publication lies with the author.
