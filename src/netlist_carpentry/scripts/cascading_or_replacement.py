import datetime
import os
from pathlib import Path
from typing import Union

from netlist_carpentry.api.read.yosys_netlist import YosysNetlistReader as YNR
from netlist_carpentry.api.write.py2v import P2VTransformer as P2V
from netlist_carpentry.core.graph.constraint import CASCADING_OR_CONSTRAINT
from netlist_carpentry.core.graph.pattern_generator import PatternGenerator


def cascading_or_replacement(netlist_path: Union[str, Path], target_verilog_path: Union[str, Path]) -> None:
    """
    Replace cascading OR patterns in a Yosys netlist with optimized Verilog representation.

    Any cascading OR chain is replaced with a tree-like structure.
    A cascading OR chain is a chain of OR gates, where exactly one input of each OR instance
    is driven by the output of the previous OR instance.
    In a tree, both inputs of each OR instance are driven by the outputs of the
    preceeding OR instances (if they exist).
    This improves the total gate runtime.

    This function reads a Yosys netlist file, identifies cascading OR patterns using
    a predefined pattern matching constraint, replaces them with an optimized
    implementation, and writes the modified circuit back to a Verilog file.

    Args:
        netlist_path (Union[str, Path]): Path to the input Yosys netlist file
        target_verilog_path (Union[str, Path]): Path where the output Verilog file will be saved

    Returns:
        None: The function writes directly to the specified target file
    """
    if isinstance(netlist_path, str):
        netlist_path = Path(netlist_path)
    find_pattern_file = 'tests/files/or_pattern_find.v'
    replace_pattern_file = 'tests/files/or_pattern_replace.v'
    p = PatternGenerator.build_from_verilog(find_pattern_file, replace_pattern_file, constraints=[CASCADING_OR_CONSTRAINT])

    circuit = YNR(netlist_path).transform_to_circuit()
    for module in circuit:
        p.replace(module)
    text_to_save = P2V().circuit2v(circuit)
    os.makedirs('tests/files/gen', exist_ok=True)
    with open(target_verilog_path, 'w') as f:
        f.write(f'// Generated {datetime.datetime.now().strftime("%d. %B %Y, %H:%M:%S")}\n\n')
        f.write(text_to_save)
