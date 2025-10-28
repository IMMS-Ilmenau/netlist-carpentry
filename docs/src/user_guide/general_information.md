# General Information

Netlist Carpentry is a framework for digital circuit analysis and modification.
Verilog designs can be read, modified, analyzed, and written back to Verilog using Netlist Carpentry.
Below is a representation of the workflow of Netlist Carpentry[^1].

![Test](../assets/tool_workflow_nc.png)

[^1]: The synthesis step, where Yosys generates a JSON netlist from Verilog, is also handled by Netlist Carpentry. However, it is also possible to provide custom synthesis scripts, or your own JSON netlist to Netlist Carpentry.

!!! info "More information"
    All configuration and execution is done in Python.
    A detailed tutorial with executable code examples in form of Jupyter Notebooks is provided as well, starting with `01. Getting Started`.
