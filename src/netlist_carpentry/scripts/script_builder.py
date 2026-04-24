"""Module for generation and execution of synthesis scripts with Yosys, creating generic JSON netlists."""

import platform
import subprocess
from pathlib import Path
from typing import Any, List, Optional

SUPPORTS_BASH = platform.system() != 'Windows'
verilog_template = """#!/bin/env bash

set -e

{source_files}
yosys {modules}-p "{yosys_cmd}"
"""

yosys_cmd = """\
{read_str}
{hierarchy}
proc
{memory}
{techmaps}
{share}
opt; clean; check
{insbuf_str}
{write_str}
"""


def _yosys_read_cmd(input_file_paths: List[Path]) -> str:
    read_lst = []
    for input_file_path in input_file_paths:
        if input_file_path.is_dir():
            raise IsADirectoryError('Input file path is a directory!')
        file_ext = input_file_path.suffix.lstrip('.').lower()
        if file_ext == 'vhdl' or file_ext == 'vhd':
            read_lst.append(f'ghdl -read {input_file_path.expanduser().resolve().as_posix()}')
        else:
            sv_ext = '-sv ' if file_ext == 'sv' else ''
            read_lst.append(f'read_verilog {sv_ext}{input_file_path.expanduser().resolve().as_posix()}')
    return '\n\t'.join(read_lst)


def _source_files_cmd(source_paths: List[str]) -> str:
    source_lst = []
    for source_path in source_paths:
        path = Path(source_path).expanduser().resolve()
        path.chmod(path.stat().st_mode | 0o111)
        if SUPPORTS_BASH:
            source_lst.append(f'source {path}\n')
        else:
            source_lst.append(f'{path}\n')
    return ''.join(source_lst)


def _get_techmap_paths(techmaps: List[Path]) -> List[str]:
    map_lst = [str(Path(techmap).expanduser().resolve()) for techmap in techmaps]
    pmux_map = str(Path(__file__).parent.resolve()) + '/hdl/pmux2mux.v'
    return [*map_lst, pmux_map]


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
    vhdl_given = any(fpath.suffix == '.vhdl' or fpath.suffix == '.vhd' for fpath in input_file_paths)
    modules = '-m ghdl ' if vhdl_given else ''
    yosys_commands = get_yosys_cmds(input_file_paths, output_file_path, top, insbuf, process_memory, techmap_paths, no_hierarchy, share)
    source_paths = source_paths or []
    sources = '\n'.join('source ' + p for p in source_paths)
    render_bash_script(script_path, sources, yosys_commands, modules)
    return yosys_commands


def get_yosys_cmds(
    input_file_paths: List[Path],
    output_file_path: Path,
    top: str = '',
    insbuf: bool = True,
    process_memory: bool = True,
    techmap_paths: List[Path] = [],
    no_hierarchy: bool = False,
    share: bool = False,
) -> str:
    vhdl_given = any(fpath.suffix == '.vhdl' or fpath.suffix == '.vhd' for fpath in input_file_paths)
    modules = '-m ghdl ' if vhdl_given else ''
    read_str = _yosys_read_cmd(input_file_paths)
    top = f'-top {top}' if top else '-auto-top' if not no_hierarchy else ''
    hierarchy = f'hierarchy {top} -libdir .'
    memory = 'memory' if process_memory else ''
    techmaps = '\n'.join(f'techmap -map {Path(techmap).expanduser().resolve()}\n' for techmap in _get_techmap_paths(techmap_paths))
    share_str = 'opt; share -aggressive' if share else ''
    insbuf_str = 'insbuf; proc' if insbuf else ''
    write_str = f'write_json {output_file_path.expanduser().resolve()}'
    yosys = yosys_cmd.format(
        modules=modules,
        read_str=read_str,
        hierarchy=hierarchy,
        memory=memory,
        techmaps=techmaps,
        share=share_str,
        insbuf_str=insbuf_str,
        write_str=write_str,
    )
    return yosys


def render_bash_script(script_path: Path, source_files: str, yosys: str, modules: str) -> None:
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
) -> subprocess.Popen[str]:
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
    yosys_args: str = build_script(script_path, input_file_paths, output_file_path, source_paths=source_paths, **kwargs)  # type: ignore[misc]
    vhdl_given = any(fpath.suffix == '.vhdl' or fpath.suffix == '.vhd' for fpath in input_file_paths)
    modules = '-m ghdl' if vhdl_given else ''
    source_paths = source_paths or []
    sources = []
    for p in source_paths:
        list_part = ['source', p, '&&'] if SUPPORTS_BASH else [p, '&&']
        sources.extend(list_part)
    yosys_payload = f'{"; ".join(yosys_args.splitlines())}'
    out_target = subprocess.PIPE if verbose else subprocess.DEVNULL
    cmd = [*sources, 'yosys', modules, f'-p "{yosys_payload}"']
    result = subprocess.Popen([' '.join(cmd)], shell=True, stdout=out_target, stderr=subprocess.STDOUT, text=True)
    if verbose and result.stdout is not None:
        for line in result.stdout:
            print(line, end='')
    result.wait()
    return result
