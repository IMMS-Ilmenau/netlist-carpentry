"""Module for generation and execution of synthesis scripts with Yosys, creating generic JSON netlists."""

import subprocess
import warnings
from pathlib import Path
from typing import Any, List, Optional

import netlist_carpentry.scripts.script_caller as sc
from netlist_carpentry import ReadConfig

verilog_template = """#!/bin/env bash

set -e

{source_files}
yosys {modules}-p "{yosys_cmd}"
"""


def build_script(
    script_path: Path,
    input_file_paths: List[Path],
    output_file_path: Path,
    top: str = '',
    insbuf: bool = True,
    process_memory: bool = True,
    techmap_paths: List[Path] = [],
    source_paths: Optional[List[str]] = None,
    no_hierarchy: bool = False,
    share: bool = False,
) -> str:
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
        source_paths (Optional[List[str]], optional): A list of paths to files to source before running Yosys.
            Can be used to enable plugins or activate environments, e.g. the OSS CAD SUITE.
            Defaults to None, in which case no additional files are sourced.
        no_hierarchy (bool, optional): Whether to resolve the hierarchy of the given circuit or not.
            If True, the yosys "hierarchy" path is skipped. Defaults to False.
        share (bool, optional): Whether to execute the Yosys `share` pass to share the same
            instances for mutually exclusive operations. May decrease area demands, but worsen timing. Defaults to False.
    """
    warnings.warn(
        "'build_script()' is deprecated and will be removed in v1.0.0. Create a `ReadConfig` object with the corresponding data and call `shell_script(script_path)` on it instead!",
        DeprecationWarning,
        stacklevel=2,
    )
    for input_file_path in input_file_paths:
        if input_file_path.is_dir():
            raise IsADirectoryError('Input file path is a directory!')
    vhdl_given = any(fpath.suffix == '.vhdl' or fpath.suffix == '.vhd' for fpath in input_file_paths)
    modules = ['ghdl'] if vhdl_given else None
    source_paths = source_paths or []
    sources = [Path(s) for s in source_paths]
    share_strategy = 'aggressive' if share else 'off'
    rc = ReadConfig(
        files=input_file_paths,
        output=output_file_path,
        top=top if top else None,
        environments=sources,
        yosys_plugins=modules,
        techmaps=techmap_paths,
        share=share_strategy,  # type: ignore
        no_hierarchy=no_hierarchy,
        keep_memory_cells=not process_memory,
        insbuf=insbuf,
    )
    return rc.shell_script(script_path)[-1]


def get_yosys_cmds(
    input_file_paths: List[Path],
    output_file_path: Path,
    top: str = '',
    insbuf: bool = True,
    process_memory: bool = True,
    techmap_paths: Optional[List[Path]] = None,
    no_hierarchy: bool = False,
    share: bool = False,
) -> str:
    warnings.warn(
        "'get_yosys_cmds()' is deprecated and will be removed in v1.0.0. Create a `ReadConfig` object with the corresponding data and call `yosys_commands()` on it instead!",
        DeprecationWarning,
        stacklevel=2,
    )
    vhdl_given = any(fpath.suffix == '.vhdl' or fpath.suffix == '.vhd' for fpath in input_file_paths)
    modules = ['ghdl'] if vhdl_given else None
    return ReadConfig(
        files=input_file_paths,
        output=output_file_path,
        top=top if top else None,
        yosys_plugins=modules,
        keep_memory_cells=not process_memory,
        techmaps=techmap_paths,
        no_hierarchy=no_hierarchy,
        share='aggressive' if share else 'off',
        insbuf=insbuf,
    ).yosys_commands()


def render_bash_script(script_path: Path, source_files: str, yosys: str, modules: str) -> None:
    warnings.warn(
        "'render_bash_script()' is deprecated and will be removed in v1.0.0. Create a `ReadConfig` object with the corresponding data and call `shell_script(script_path)` on it instead!",
        DeprecationWarning,
        stacklevel=2,
    )
    script_content = verilog_template.format(source_files=source_files, yosys_cmd=yosys, modules=modules)
    with open(script_path, 'w') as f:
        f.write(script_content)


def build_and_execute(
    script_path: Path,
    input_file_paths: List[Path],
    output_file_path: Path,
    verbose: bool = False,
    *,
    source_paths: Optional[List[str]] = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
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
        source_paths (Optional[List[str]], optional): A list of paths to files to source before running Yosys.
            Can be used to enable plugins or activate environments, e.g. the OSS CAD SUITE.
            Defaults to None, in which case no additional files are sourced.
        **kwargs: Additional arguments passed to build_script.

    Returns:
        subprocess.CompletedProcess[bytes]: The result of the subprocess execution.
    """
    vhdl_given = any(fpath.suffix == '.vhdl' or fpath.suffix == '.vhd' for fpath in input_file_paths)
    modules = ['ghdl'] if vhdl_given else None
    source_paths = source_paths or []
    sources = [Path(s) for s in source_paths]
    rc = ReadConfig(files=input_file_paths, output=output_file_path, environments=sources, yosys_plugins=modules, **kwargs)  # type: ignore[misc]
    return sc.call(rc.shell_script(script_path), verbose)
