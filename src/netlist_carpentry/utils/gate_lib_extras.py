import inspect
import sys
from typing import Dict, List, Literal, Optional, Tuple, Union

from pydantic import PositiveInt

from netlist_carpentry import CFG, Direction, Instance, Port, PortSegment, Signal
from netlist_carpentry.core.exceptions import UnsupportedOperationError, VerilogSyntaxError
from netlist_carpentry.core.types import SignalArray
from netlist_carpentry.utils.gate_lib_base_classes import PrimitiveGate
from netlist_carpentry.utils.gate_lib_dataclasses import BRAMParams
from netlist_carpentry.utils.gate_mixins import ClkMixin

PORT = Port[Instance]


class BRAM(ClkMixin, PrimitiveGate):
    """Represents a Yosys $mem_v2 memory cell as a primitive gate."""

    instance_type: str = '§mem_v2'
    parameters: BRAMParams = BRAMParams()

    @property
    def is_combinational(self) -> bool:
        return False

    @property
    def width(self) -> PositiveInt:
        """Data width of this BRAM (width of data input/output ports)."""
        return self.parameters.WIDTH or 8

    @property
    def abits(self) -> PositiveInt:
        """Address width of this BRAM (width of address port)."""
        return self.parameters.ABITS or 2

    @property
    def clk_port(self) -> PORT:
        """BRAM has two clock ports — use rd_clk_port / wr_clk_port instead."""
        raise UnsupportedOperationError(
            'BRAM does not have one single clock port, but rather two:\n'
            + 'To retrieve the clock port for read operations, use `BRAM.rd_clk_port`.\n'
            + 'To retrieve the clock port for write operations, use `BRAM.wr_clk_port`.\n'
        )

    @property
    def rd_clk_port(self) -> PORT:
        """Read-clock port."""
        return self.ports['RD_CLK']

    @property
    def wr_clk_port(self) -> PORT:
        """Write-clock port."""
        return self.ports['WR_CLK']

    @property
    def rd_addr_port(self) -> PORT:
        """Read-address port."""
        return self.ports['RD_ADDR']

    @property
    def wr_addr_port(self) -> PORT:
        """Write-address port."""
        return self.ports['WR_ADDR']

    @property
    def rd_data_port(self) -> PORT:
        """Read-data port."""
        return self.ports['RD_DATA']

    @property
    def wr_data_port(self) -> PORT:
        """Write-data port."""
        return self.ports['WR_DATA']

    @property
    def rd_en_port(self) -> PORT:
        """Read-enable port."""
        return self.ports['RD_EN']

    @property
    def wr_en_port(self) -> PORT:
        """Write-enable port."""
        return self.ports['WR_EN']

    def model_post_init(self, __context: object) -> None:
        self.connect('RD_ADDR', None, Direction.IN, width=self.abits)
        self.connect('RD_ARST', None, Direction.IN)
        self.connect('RD_CLK', None, Direction.IN)
        self.connect('RD_DATA', None, Direction.OUT, width=self.width)
        self.connect('RD_EN', None, Direction.IN)
        self.connect('RD_SRST', None, Direction.IN)
        self.connect('WR_ADDR', None, Direction.IN, width=self.abits)
        self.connect('WR_CLK', None, Direction.IN)
        self.connect('WR_DATA', None, Direction.IN, width=self.width)
        self.connect('WR_EN', None, Direction.IN)

    @property
    def verilog_net_map(self) -> Dict[str, str]:
        return {pname: self.p2v(p) for pname, p in self.ports.items()}

    @property
    def verilog_template(self) -> str:
        return """reg [{WORD}:0] {MEM} [{OFFSET}:{DEPTH}];
{INIT}{RD_WR}
"""

    @property
    def verilog(self) -> str:
        default_depth: PositiveInt = 2**self.abits
        depth: PositiveInt = self.parameters.SIZE or default_depth
        offset = self.parameters.OFFSET or 0
        net_map = self.verilog_net_map
        net_map.update(
            {
                'WORD': str(self.width - 1),
                'OFFSET': str(offset),
                'DEPTH': str(depth - 1 + offset),
                'MEM': self.name,
                'INIT': self._verilog_init,
            }
        )

        rd_parts = [self._read_port_verilog(i) for i in range(self.rd_clk_port.width)]
        wr_parts = [self._write_port_verilog(i) for i in range(self.wr_clk_port.width)]
        wr_parts.reverse()  # EQY requires reversed write-port order for equivalence

        net_map['RD_WR'] = '\n'.join([*wr_parts, *rd_parts])
        return self.verilog_template.format_map(net_map)

    def _read_port_verilog(self, idx: int) -> str:
        """Generate the Verilog always-block for a single read port."""
        en_ps = self.rd_en_port[idx]

        if self.rd_clk_port[idx].is_tied:
            # Asynchronous read
            data_segs = {j: self.rd_data_port[j] for j in self._data_slice_indices(idx)}
            addr_segs = {j: self.rd_addr_port[j] for j in self._addr_slice_indices(idx)}
            transparency_str = self._transparency_mask(idx)
            return f'always @* begin\n\t{transparency_str}{self.ps2v(data_segs)}\t=\t{self.name}[{self.ps2v(addr_segs)}];\nend'

        # Synchronous read
        p = self.parameters.RD_CLK_POLARITY[idx] if self.parameters.RD_CLK_POLARITY is not None else Signal.HIGH
        w = self.rd_clk_port[idx].wire_name
        header = f'negedge {w}' if p is Signal.LOW else f'posedge {w}'
        return self._format_read_vpart(idx, header, en_ps, self.rd_addr_port, self.rd_data_port)

    def _write_port_verilog(self, idx: int) -> str:
        """Generate the Verilog always-block for a single write port."""
        en_ps = self.wr_en_port[idx]
        p = self.parameters.WR_CLK_POLARITY[idx] if self.parameters.WR_CLK_POLARITY is not None else Signal.HIGH
        w = self.wr_clk_port[idx].wire_name
        header = f'negedge {w}' if p is Signal.LOW else f'posedge {w}'
        return self._format_write_vpart(idx, header, en_ps, self.wr_addr_port, self.wr_data_port)

    def _format_read_vpart(self, idx: int, header: str, en: PortSegment, addr: PORT, data: PORT) -> str:
        """Format a synchronous read-port always block.

        Priority order (when multiple features are active):
        1. Clock enable (CE) — wraps everything
        2. Synchronous reset (SRST) — inside CE or top-level
        3. Transparency mask (write-first) — inside CE/SRST or top-level
        4. Normal read from RAM
        """
        en_array = self._resolve_enable_array(en, self.rd_clk_port, port_idx=idx, slice_width=self.abits)
        if en_array is None:
            return ''  # Always inactive

        mem_addr = self._mem_addr_str(idx, addr)
        mem_data = self._mem_data_str(idx, data)

        transparency_str = self._transparency_mask(idx)
        has_transparency = bool(transparency_str.strip())

        # Feature flags
        has_clock_enable = self._has_clock_enable(idx)
        ce_over_srst, srst_value = self._ce_over_srst_info(idx)

        action = self._build_read_action(
            en_array=en_array,
            en_str=self._enable_string(en_array),
            mem_addr=mem_addr,
            mem_data=mem_data,
            has_clock_enable=has_clock_enable,
            ce_over_srst=ce_over_srst,
            srst_value=srst_value,
            srst_port=self._srst_port_name,
            transparency_str=transparency_str,
            has_transparency=has_transparency,
        )

        return f'always @({header}) begin\n{action}\nend'

    def _format_write_vpart(self, idx: int, header: str, en: PortSegment, addr: PORT, data: PORT) -> str:
        """Format a write-port always block."""
        en_array = self._resolve_enable_array(en, self.wr_clk_port, port_idx=idx, slice_width=self.width)
        if en_array is None:
            return ''

        return f'always @({header}) begin\n{self._format_vpart_if_statement(idx, en_array, "w", addr, data)}\nend'

    def _build_read_action(
        self,
        en_array: Dict[int, PortSegment],
        en_str: str,
        mem_addr: str,
        mem_data: str,
        has_clock_enable: bool,
        ce_over_srst: bool,
        srst_value: Optional[str],
        srst_port: str,
        transparency_str: str,
        has_transparency: bool,
    ) -> str:
        """Compose the nested if/else action string for a read port."""

        def _simple_ram_read(indent: str) -> str:
            return f'{indent}{mem_data} <= {self.name}[{mem_addr}];'

        # --- CE present: wraps everything ---
        if has_clock_enable and en_array:
            if ce_over_srst and srst_value:
                inner = f'\t\tif ({srst_port}) begin\n\t\t\t{mem_data} <= {srst_value};\n\t\tend\n'
                if has_transparency:
                    inner += f'\t\t{transparency_str}\n'
                inner += f'\t\telse begin\n\t\t\t{mem_data} <= {self.name}[{mem_addr}];\n\t\tend'
                return f'\tif ({en_str}) begin\n{inner}\n\tend'

            if has_transparency:
                return f'\tif ({en_str}) begin\n\t\t{transparency_str}\n\t\telse begin\n\t\t\t{mem_data} <= {self.name}[{mem_addr}];\n\t\tend\n\tend'
            return f'\tif ({en_str}) begin\n\t\t{mem_data} <= {self.name}[{mem_addr}];\n\tend'

        # --- SRST present (no CE) ---
        if ce_over_srst and srst_value:
            inner = f'\tif ({srst_port}) begin\n\t\t{mem_data} <= {srst_value};\n\tend\n'
            if has_transparency:
                inner += f'\t{transparency_str}\n'
            inner += f'\telse begin\n\t\t{mem_data} <= {self.name}[{mem_addr}];\n\tend'
            return inner

        # --- Transparency only ---
        if has_transparency:
            return f'{transparency_str}\n\telse begin\n\t\t{mem_data} <= {self.name}[{mem_addr}];\n\tend'

        # --- Simple read ---
        return f'\t{mem_data} <= {self.name}[{mem_addr}];'

    @property
    def _srst_port_name(self) -> str:
        """Verilog name of the shared SRST port."""
        return self.p2v(self.ports['RD_SRST'])

    def _transparency_mask(self, rd_idx: int) -> str:
        """Build the if/else-if chain for write-first transparency.

        Returns an empty string when no transparency is configured.
        The caller must wrap this in proper if/else structure.
        """
        if self.parameters.RD_TRANSPARENCY_MASK is None:
            return ''

        wr_ports = self.parameters.WR_PORTS or self.wr_clk_port.width
        lines: List[str] = []

        for wr_idx, mask_idx in enumerate(range(rd_idx, rd_idx + wr_ports)):
            if self.parameters.RD_TRANSPARENCY_MASK[mask_idx] is Signal.HIGH:
                we = self.ps2v({i: self.wr_en_port[i] for i in self._data_slice_indices(wr_idx)})
                addr_wr = self.ps2v(self.addr_slice(wr_idx, 'w'))
                addr_rd = self.ps2v(self.addr_slice(rd_idx, 'r'))
                data_rd = self.ps2v(self.data_slice(rd_idx, 'r'))
                data_wr = self.ps2v(self.data_slice(wr_idx, 'w'))

                clause = f'\tif ({we} && ({addr_wr} == {addr_rd})) begin\n\t\t{data_rd} <= {data_wr};\n\tend'
                lines.append(f'else\n\t{clause}' if lines else clause)

        return '\n'.join(lines)

    def _has_clock_enable(self, idx: int) -> bool:
        """Whether read port *idx* uses clock enable (RD_CLK_ENABLE)."""
        clk_en = self.parameters.RD_CLK_ENABLE
        return clk_en is not None and idx in clk_en and clk_en[idx] is Signal.HIGH

    def _ce_over_srst_info(self, idx: int) -> Tuple[bool, Optional[str]]:
        """Return (ce_over_srst_flag, srst_value_string) for a read port."""
        if (
            self.parameters.RD_CE_OVER_SRST is None
            or idx not in self.parameters.RD_CE_OVER_SRST
            or self.parameters.RD_CE_OVER_SRST[idx] is not Signal.HIGH
        ):
            return False, None

        return True, self._srst_value_string(idx)

    def _srst_value_string(self, idx: int) -> str:
        """Extract the SRST value for read port *idx* from RD_SRST_VALUE.

        RD_SRST_VALUE is a binary string (MSB first), e.g.
        ``'xxxxxxxx1101xxxxxxxx'``.  Each port's value occupies
        ``width`` bits starting at position ``idx * width`` from the left.
        """
        if self.parameters.RD_SRST_VALUE is None:
            return f"{self.width}'hx"

        w = self.width
        start = idx * w
        raw_bits = self.parameters.RD_SRST_VALUE[start : start + w]
        return f"{w}'b{raw_bits}"

    def _resolve_enable_array(self, en: PortSegment, clk_port: PORT, port_idx: int = 0, slice_width: int = 1) -> Optional[Dict[int, PortSegment]]:
        """Resolve an enable signal to a dict of bit-index → PortSegment.

        Returns ``None`` when the port is always inactive (EN tied LOW).
        Returns an empty dict when always active (EN tied HIGH).

        Args:
            en: The enable PortSegment.
            clk_port: The clock port (used to determine if EN is a wide signal).
            port_idx: The port index (0-based). Used to compute absolute bit indices.
            slice_width: Width of each slice (e.g., width for data, abits for address).
        """
        if en.is_tied:
            if en.signal is Signal.HIGH:
                return {}
            elif en.signal is Signal.LOW:
                return None
            else:
                raise VerilogSyntaxError(f'Cannot read BRAM {self.raw_path}: EN signal is tied to {en.signal.name}!')

        # EN connected to a wire
        if en.parent.width == clk_port.width:
            start = port_idx * slice_width
            return {i: en for i in range(start, start + en.parent.width)}
        else:
            start = port_idx * slice_width
            return {i: en.parent[i] for i in range(start, start + self.width)}

    def _enable_string(self, en_array: Dict[int, PortSegment]) -> str:
        """Convert an enable-array dict to a Verilog expression string."""
        if not en_array:
            return ''

        # All elements share the same wire — collapse to single signal
        first_seg = next(iter(en_array.values()))
        if all(v.ws_path == first_seg.ws_path for v in en_array.values()):
            return self.ps2v({next(iter(en_array)): first_seg})

        # Different wires — group consecutive same-wire elements
        groups = self._group_en_array(en_array)
        return self.ps2v(groups[0])

    def _group_en_array(self, en_array: Dict[int, PortSegment]) -> List[Dict[int, PortSegment]]:
        """Group consecutive enable elements that share the same wire path."""
        groups: List[Dict[int, PortSegment]] = []
        curr_group: Dict[int, PortSegment] = {}
        prev_value: Optional[PortSegment] = None

        for k, v in en_array.items():
            if prev_value is not None and v.ws_path != prev_value.ws_path and curr_group:
                groups.append(curr_group)
                curr_group = {}
            curr_group[k] = v
            prev_value = v

        if curr_group:
            groups.append(curr_group)
        return groups

    def _data_slice_indices(self, port_idx: int) -> range:
        return range(port_idx * self.width, (port_idx + 1) * self.width)

    def _addr_slice_indices(self, port_idx: int) -> range:
        return range(port_idx * self.abits, (port_idx + 1) * self.abits)

    def _mem_addr_str(self, idx: int, addr: PORT) -> str:
        addr_segs = {i: addr[i] for i in self._addr_slice_indices(idx)}
        return self.ps2v(addr_segs)

    def _mem_data_str(self, idx: int, data: PORT) -> str:
        data_segs = {i: data[i] for i in self._data_slice_indices(idx)}
        return self.ps2v(data_segs)

    def _format_vpart(self, idx: int, rw: Literal['r', 'w'], cw: str, cpol: Signal, en: PortSegment, addr: PORT, data: PORT) -> str:
        """Format a port always block (legacy/test-facing API).

        Kept for backward compatibility with existing tests.
        """
        if rw not in ('r', 'w'):
            raise ValueError(f"rw must be either 'r' (for read) or 'w' (for write). '{rw}' is illegal!")
        header = f'negedge {cw}' if cpol is Signal.LOW else f'posedge {cw}'
        if rw == 'r':
            return self._format_read_vpart(idx, header, en, addr, data)
        else:
            return self._format_write_vpart(idx, header, en, addr, data)

    def _verilog_template(self, idx: int, rw: Literal['r', 'w']) -> str:
        """Generate Verilog for a single port (legacy/test-facing API).

        Kept for backward compatibility with existing tests.
        """
        if rw == 'w':
            return self._write_port_verilog(idx)
        else:
            en_ps = self.rd_en_port[idx]
            if self.rd_clk_port[idx].is_tied:
                # Async read — delegate to _read_port_verilog
                return self._read_port_verilog(idx)
            p = self.parameters.RD_CLK_POLARITY[idx] if self.parameters.RD_CLK_POLARITY is not None else Signal.HIGH
            w = self.rd_clk_port[idx].wire_name
            header = f'negedge {w}' if p is Signal.LOW else f'posedge {w}'
            return self._format_read_vpart(idx, header, en_ps, self.rd_addr_port, self.rd_data_port)

    def _format_vpart_if_statement(self, idx: int, en_array: Dict[int, PortSegment], rw: Literal['r', 'w'], addr: PORT, data: PORT) -> str:
        """Generate an if-statement (or chunked if-statements) for a port.

        Used by write ports and also available for read ports when needed.
        """
        transparency_str = '' if rw == 'w' else self._transparency_mask(idx)
        tmpl = '\t{data} <= {mem}[{addr}]{ram_idx};' if rw == 'r' else '\t{mem}[{addr}]{ram_idx} <= {data};'

        data_segs = {i: data[i] for i in self._data_slice_indices(idx)}
        addr_segs = {i: addr[i] for i in self._addr_slice_indices(idx)}
        action = tmpl.format(data=self.ps2v(data_segs), addr=self.ps2v(addr_segs), mem=self.name, ram_idx='')

        if not en_array:
            return transparency_str + action

        # All elements share the same wire → single if
        first_seg = next(iter(en_array.values()))
        if all(v.ws_path == first_seg.ws_path for v in en_array.values()):
            en_str = self.ps2v({next(iter(en_array)): first_seg})
            return transparency_str + f'\tif ({en_str})\n\t{action}'

        # Different wires → chunked if-statements
        groups = self._group_en_array(en_array)
        elements = []
        for g in groups:
            keys = list(g.keys())
            ram_indices = [k - idx * self.width for k in reversed(keys)]
            idx_str = f'[{ram_indices[0]}]' if len(ram_indices) == 1 else f'[{ram_indices[0]}:{ram_indices[-1]}]'
            data_str = self.p2v(data, include_indices=keys)
            action = tmpl.format(data=data_str, addr=self.ps2v(addr_segs), mem=self.name, ram_idx=idx_str)
            en_str = self.ps2v(g)
            elements.append(transparency_str + f'\tif ({en_str})\n\t{action}')

        return '\n'.join(elements)

    @property
    def _verilog_init(self) -> str:
        """Generate initial values for read-port data registers."""
        template = 'initial begin\n{INITS}\nend\n'
        inits = []
        signals = self.parameters.RD_INIT_VALUE or SignalArray.from_bin('')
        w = self.width

        if not signals:
            return ''

        # Reverse the order since MSB is now the first element (LSB)
        rev_values = ''.join(s.value for s in signals.values())
        signals = SignalArray.create(rev_values)

        for i in range(self.rd_clk_port.width):
            curr_port_range = self._data_slice_indices(i)
            if all(j in signals for j in curr_port_range):
                data_segs = {j: self.rd_data_port[j] for j in curr_port_range}
                values_list = [signals[signals.size - j - 1].value for j in reversed(curr_port_range) if signals.size - j - 1 in signals]
                if any(v != 'x' for v in values_list):
                    values_str = f"{w}'b" + ''.join(values_list)
                    inits.append(f'\t{self.ps2v(data_segs)}\t<=\t{values_str};')

        return template.format(INITS='\n'.join(inits)) if inits else ''

    def data_slice(self, port_idx: int, rw: Literal['r', 'w']) -> Dict[int, PortSegment]:
        """Return a dict mapping bit-index → PortSegment for the data of *port_idx*."""
        self._check_rw(rw)
        data = self.rd_data_port if rw == 'r' else self.wr_data_port
        self._validate_slice(port_idx, data.width, self.width, 'data')
        return {i: data[i] for i in self._data_slice_indices(port_idx)}

    def addr_slice(self, port_idx: int, rw: Literal['r', 'w']) -> Dict[int, PortSegment]:
        """Return a dict mapping bit-index → PortSegment for the address of *port_idx*."""
        self._check_rw(rw)
        addr = self.rd_addr_port if rw == 'r' else self.wr_addr_port
        self._validate_slice(port_idx, addr.width, self.abits, 'address')
        return {i: addr[i] for i in self._addr_slice_indices(port_idx)}

    def en_array(self, idx: int, rw: Literal['r', 'w']) -> Dict[int, Union[Signal, PortSegment]]:
        """Return enable-array info for a port (legacy API)."""
        self._check_rw(rw)
        en = self.rd_en_port[idx] if rw == 'r' else self.wr_en_port[idx]
        if en.is_tied:
            if en.signal.is_defined:
                return {idx: en.signal}
            else:
                raise VerilogSyntaxError(f'Cannot write BRAM {self.raw_path}: EN signal is tied to {en.signal.name}!')
        active_port = self.rd_clk_port if rw == 'r' else self.wr_clk_port
        if en.parent.width == active_port.width:
            return {idx: en}
        return {i: en.parent[i] for i in range(idx * self.width, (idx + 1) * self.width)}

    @staticmethod
    def _check_rw(rw: Literal['r', 'w']) -> None:
        if rw not in ('r', 'w'):
            raise ValueError(f"Expected 'r' (read) or 'w' (write), but got {rw!r}!")

    def _validate_slice(self, port_idx: int, port_width: int, slice_width: int, name: str) -> None:
        if (port_idx + 1) * slice_width > port_width:
            raise IndexError(
                f'{name.capitalize()} port of BRAM {self.raw_path} has only '
                f'{port_width} bits ({port_width // slice_width} slices, {slice_width} bit each), '
                f'port index {port_idx} is too large (would conform to indices '
                f'{port_idx * slice_width}-{(port_idx + 1) * slice_width})!'
            )


def _build_gate_lib_map() -> Dict[str, type]:
    """Build the mapping from Yosys instance type → gate class."""
    gate_lib_map: Dict[str, type] = {}
    clsmembers: List[Tuple[str, type]] = inspect.getmembers(sys.modules[__name__], inspect.isclass)
    for _, c in clsmembers:
        if issubclass(c, PrimitiveGate):
            instance_type = str(c.model_fields['instance_type'].default)  # type: ignore[misc]
            if instance_type != CFG.id_internal:
                gate_lib_map[instance_type] = c
    return gate_lib_map
