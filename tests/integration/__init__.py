import subprocess
from pathlib import Path

omsp_modules = [
    'omsp_alu',
    'omsp_clock_module',
    'omsp_dbg',
    'omsp_dbg_uart',
    'omsp_execution_unit',
    'omsp_frontend',
    'omsp_mem_backbone',
    'omsp_multiplier',
    'omsp_register_file',
    'omsp_sfr',
    'omsp_sync_cell',
    'omsp_sync_reset',
    'omsp_watchdog',
    'openMSP430',
]


def gen_omsp(top: str) -> None:
    in_path = Path('openmsp430/core/rtl/verilog').resolve()
    out_path = Path('tests/files/gen').resolve()
    yosys_cmd = [
        'yosys',
        '-p',
        f"""
    read_verilog {in_path}/*.v
    hierarchy -top {top} -libdir .
    proc; memory
    pmuxtree; opt; clean
    insbuf; proc
    write_json {out_path}/openMSP430.json
    write_verilog {out_path}/openMSP430.v
    """,
    ]
    subprocess.run(yosys_cmd)
