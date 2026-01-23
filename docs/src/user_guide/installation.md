# Installation

Install the package via:

```bash
pip install netlist-carpentry
```

The package requires at least Python 3.9.
However, the recommended version is Python 3.12.

Alternatively, you can clone this repository and install the package in editable mode.
Refer to the development instructions.

```bash
pip install -e <path-to-cloned-netlist-carpentry-directory>
```

Netlist Carpentry also requires [Yosys](https://yosyshq.readthedocs.io/en/latest/install.html) for reading Verilog designs!
Netlist Carpentry could theoretically be used without Yosys (e.g. for manual exploration of the framework's basic functionality), but reading Verilog designs would not be possible.
