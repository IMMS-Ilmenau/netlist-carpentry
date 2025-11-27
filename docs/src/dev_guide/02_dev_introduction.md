# Introduction to Development with Netlist Carpentry

This developer guide is intended for engineers (both software and digital circuitry) and researchers working with digital circuits (primarily Verilog).
Basic familiarity with Python is required.
This guide aims to provide you with enough knowledge to extend the framework with new capabilities.
While the user documentation focuses on how to **use** the existing classes, methods, and tools to build circuit-processing workflows, this guide is for contributors who want to go deeper: implementing custom analyses, transformation passes, data structures, file format handlers, or other internal components.
If you plan to modify or extend the framework’s internals rather than simply assembling functionality from its public API, this guide is for you!

# Design Philosophies of Netlist Carpentry

There are several design philosophies that were followed more or less closely during the development of the Netlist Carpentry Framework.
Accordingly, it is also advisable to continue to follow these principles in general terms when expanding this framework.

-   **Graph-centric Representation**:
    Instead of using Regex to parse and patch text files (which is fragile), the tool parses netlists into a graph object (nodes = instances/ports, edges = wires).
    This allows for robust topological analysis (e. g. finding paths, detecting loops, identifying sub-circuit patterns), regardless of how they are written in the source file.
-   **Semantic Validation via Formal Methods**:
    The project includes basic semantic verification, currently executed by Yosys EQY.
    In the future, tools like **z3** may also be supported.
-   **Robust, Schema-Driven Data Modeling**:
    Data inputs (e.g. netlists, design rules) are validated against strict schemas at runtime.
    This ensures that if a netlist is malformed or a property is missing, the tool fails early and explicitly, rather than propagating undefined behavior (e.g. if a wire has multiple drivers, the framework raises an appropriate error instead of continuing).
    This aligns with modern "Type-Safe Python" practices.
-   **Interactive Tooling**:
    The framework focuses on utility, experimentation, and interactive workflows.
    The tool is designed to be documented and used within Jupyter Notebooks, allowing the documentation of "netlist cleaning" workflows step-by-step (see the example notebooks in the **User Guide** section).
-   **No "quick-and-dirty" text-processing**:
    A *software-engineering-first* approach is targeted, treating netlists as typed graphs subject to formal constraints, while providing a modern, interactive interface.
