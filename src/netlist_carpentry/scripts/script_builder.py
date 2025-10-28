import subprocess
from pathlib import Path
from typing import Any, List

template_str = """#!/bin/bash

yosys -p "
    {read_str}
    {hierarchy}
    proc
    {memory}
    {techmaps}
    opt; clean; check
    {insbuf_str}
    {write_str}
"
"""


def build_script(
    script_path: Path,
    input_file_paths: List[Path],
    output_file_path: Path,
    top: str = '',
    insbuf: bool = True,
    process_memory: bool = True,
    techmap_paths: List[Path] = [],
) -> None:
    """
    Build a Yosys script for synthesis.

    This function generates a Yosys script that reads the paths to the input Verilog files,
    performs hierarchy management (in Yosys), procedural transformations, memory
    processing, techmap application, optimization, and writes the output in JSON format.
    This function **does not run the generated script**.
    Run the script in the terminal, e.g. via `sh <script_name>`.

    Args:
        script_path (Path): Desired path to the output script file.
        input_file_paths (List[Path]): List of paths to input Verilog files.
        output_file_path (Path): Path to the output JSON file.
        top (str, optional): Name of the top module. Defaults to ''.
        insbuf (bool, optional): Whether to insert buffers whenever wires are directly assigned to other wires. Defaults to True.
        process_memory (bool, optional): Whether to process memory (split into primitive cells). Defaults to True.
        techmap_paths (List[Path], optional): List of paths to techmap files. Defaults to [].
    """
    read_str = ''
    for input_file_path in input_file_paths:
        if input_file_path.is_dir():
            raise IsADirectoryError('Input file path is a directory!')
        file_ext = input_file_path.suffix.lstrip('.').lower()
        sv_ext = '-sv ' if file_ext == 'sv' else ''
        read_str += f'read_verilog {sv_ext}{input_file_path.expanduser().resolve()}\n'
    top = f'-top {top}' if top else ''
    hierarchy = f'hierarchy {top} -libdir .'
    memory = 'memory' if process_memory else ''
    techmaps = '\n'.join(f'techmap -map {techmap.expanduser().resolve()}\n' for techmap in techmap_paths)
    insbuf_str = 'insbuf; proc' if insbuf else ''
    write_str = f'write_json {output_file_path.expanduser().resolve()}'
    yosys = template_str.format(read_str=read_str, hierarchy=hierarchy, memory=memory, techmaps=techmaps, insbuf_str=insbuf_str, write_str=write_str)
    with open(script_path, 'w') as f:
        f.write(yosys)


def build_and_execute(
    script_path: Path, input_file_paths: List[Path], output_file_path: Path, verbose: bool = False, **kwargs: Any
) -> subprocess.CompletedProcess[bytes]:
    """
    Build a Yosys script and execute it.

    This function builds a Yosys script using the provided parameters and then
    executes it using the subprocess library. It can optionally control output verbosity.

    Args:
        script_path (Path): Path to the script file to be executed.
        input_file_paths (List[Path]): List of paths to input Verilog files.
        output_file_path (Path): Path to the output JSON file.
        verbose (bool, optional): If True, print output to stdout.
            Defaults to False, which suppresses output and only prints errors.
        **kwargs: Additional arguments passed to build_script.

    Returns:
        subprocess.CompletedProcess[bytes]: The result of the subprocess execution.
    """
    build_script(script_path, input_file_paths, output_file_path, **kwargs)  # type: ignore[misc]
    stdout = None if verbose else subprocess.PIPE
    subprocess.call(['chmod', 'u+x', script_path])
    return subprocess.run(script_path, stdout=stdout, stderr=subprocess.PIPE)
