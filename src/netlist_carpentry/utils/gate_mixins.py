# mypy: disable-error-code="safe-super"
from typing import Dict, Iterable, List, Optional, Protocol, Type, runtime_checkable

from pydantic import BaseModel, NonNegativeInt, PositiveInt

from netlist_carpentry import Direction, Instance, Port, Signal
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.core.netlist_elements.port import ANY_PORT
from netlist_carpentry.core.protocols.signals import SignalOrLogicLevel
from netlist_carpentry.utils.custom_dict import CustomDict
from netlist_carpentry.utils.gate_lib_dataclasses import ClockParams, DFFParams, EnableParams, Parameters, ResetParams
from netlist_carpentry.utils.safe_format_dict import SafeFormatDict


class GateProtocol(Protocol):
    instance_type: str

    @property
    def parameters(self) -> Parameters: ...
    @property
    def ports(self) -> CustomDict[str, Port[Instance]]: ...
    @property
    def input_port(self) -> Port[Instance]: ...
    @property
    def output_port(self) -> Port[Instance]: ...
    @property
    def width(self) -> PositiveInt: ...
    @property
    def data_width(self) -> int: ...
    @property
    def verilog_net_map(self) -> Dict[str, str]: ...
    @property
    def verilog_template(self) -> str: ...
    @property
    def verilog_context_map(self) -> SafeFormatDict: ...
    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None: ...
    def update_parameters(self) -> None: ...
    def connect(
        self,
        port_name: str,
        ws_path: Optional[WireSegmentPath],
        direction: Direction = Direction.UNKNOWN,
        index: NonNegativeInt = 0,
        width: PositiveInt = 1,
    ) -> None: ...
    def p2v(self, port: ANY_PORT, exclude_indices: Optional[List[int]] = None) -> str: ...
    def _v_header(self, port: Port[Instance], polarity: Signal) -> str: ...
    def _storage_assigns(self, sig_value: str = '') -> str: ...
    def set(self, port_name: str, new_signal: SignalOrLogicLevel) -> None: ...
    def evaluate(self) -> None: ...
    def _calc_output(self, idx: NonNegativeInt = 0) -> Dict[int, Signal]: ...
    def _set_output(self, new_signals: Dict[int, Signal]) -> None: ...


@runtime_checkable
class ClockMixinProtocol(GateProtocol, Protocol):
    @property
    def parameters(self) -> ClockParams: ...
    @property
    def clk_port(self) -> Port[Instance]: ...
    @property
    def clk_polarity(self) -> Signal: ...


@runtime_checkable
class EnableMixinProtocol(GateProtocol, Protocol):
    @property
    def parameters(self) -> EnableParams: ...
    @property
    def en_port(self) -> Port[Instance]: ...
    @property
    def en_polarity(self) -> Signal: ...
    @property
    def en_signal(self) -> Signal: ...
    @property
    def _verilog_en(self) -> str: ...


@runtime_checkable
class ResetMixinProtocol(GateProtocol, Protocol):
    @property
    def parameters(self) -> ResetParams: ...
    @property
    def rst_port(self) -> Port[Instance]: ...
    @property
    def rst_polarity(self) -> Signal: ...
    @property
    def rst_val(self) -> Dict[int, Signal]: ...
    @property
    def rst_val_int(self) -> int: ...
    @property
    def _verilog_rst(self) -> str: ...
    @property
    def _verilog_rst_net(self) -> str: ...
    @property
    def _verilog_rst_sig_val(self) -> str: ...
    @property
    def _verilog_header(self) -> str: ...
    def _split_sync_params(self, slices: Iterable['ResetMixinProtocol']) -> None: ...


class ScanMixinProtocol(GateProtocol, Protocol):
    @property
    def se_port(self) -> Port[Instance]: ...
    @property
    def si_port(self) -> Port[Instance]: ...
    @property
    def so_port(self) -> Port[Instance]: ...
    @property
    def se_signal(self) -> Signal: ...
    def pre_py2v_hook(self) -> None: ...


class ClkMixin(BaseModel):
    """
    A mixin class for clocked gates. Clocked gates are gates that have a clock signal.
    This class provides a common interface for all clocked gates, including methods for evaluating the gate's output and setting its output signal.
    """

    parameters: ClockParams = ClockParams()

    @property
    def clk_polarity(self) -> Signal:
        """Which clock edge activates the flip-flop. Default is Signal.HIGH, i.e. rising edge."""
        return self.parameters.CLK_POLARITY if self.parameters.CLK_POLARITY is not None else Signal.HIGH

    @clk_polarity.setter
    def clk_polarity(self, new_signal: Signal) -> None:
        self.parameters.CLK_POLARITY = new_signal

    def model_post_init(self: ClockMixinProtocol, __context: Optional[Dict[str, object]]) -> None:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        super().model_post_init(__context)
        self.connect('CLK', None, direction=Direction.IN)

    @property
    def clk_port(self: ClockMixinProtocol) -> Port[Instance]:
        """The clock port of the gate."""
        return self.ports['CLK']

    @property
    def verilog_net_map(self: ClockMixinProtocol) -> Dict[str, str]:
        clk = self.p2v(self.clk_port) if self.p2v(self.clk_port) != "1'bx" else ''
        sigs = super().verilog_net_map
        sigs.update({'CLK': clk})
        return sigs

    def update_parameters(self: ClockMixinProtocol) -> None:
        super().update_parameters()
        self.parameters.CLK_POLARITY = self.clk_polarity

    def set_clk(self: ClockMixinProtocol, new_signal: SignalOrLogicLevel) -> None:
        """
        Sets the clock signal.

        Args:
            new_signal (Signal): The new clock signal value.
        """
        self.set(self.clk_port.name, new_signal)
        self.evaluate()


class EnMixin(BaseModel):
    @property
    def en_polarity(self: EnableMixinProtocol) -> Signal:
        """Which EN-signal level enables writing on the data storage. Default is Signal.HIGH."""
        return self.parameters.EN_POLARITY if self.parameters.EN_POLARITY is not None else Signal.HIGH

    @en_polarity.setter
    def en_polarity(self: EnableMixinProtocol, new_signal: Signal) -> None:
        self.parameters.EN_POLARITY = new_signal

    @property
    def en_port(self: EnableMixinProtocol) -> Port[Instance]:
        """The enable port of the gate."""
        return self.ports['EN']

    @property
    def en_signal(self: EnableMixinProtocol) -> Signal:
        """The enable signal of the gate."""
        return self.en_port.signal

    @property
    def verilog_net_map(self: EnableMixinProtocol) -> Dict[str, str]:
        en = self.p2v(self.en_port)
        sigs = super().verilog_net_map
        sigs.update({'EN': en})
        return sigs

    @property
    def _verilog_en(self: EnableMixinProtocol) -> str:
        """
        The verilog representation of the enable net.

        Has the form `en_net_name` or `~en_net_name`, depending on the enable polarity.
        """
        en_wire = self.p2v(self.en_port) if self.p2v(self.en_port) != "1'bx" else ''
        inv = '' if self.en_polarity == Signal.HIGH else '~'
        return inv + en_wire

    @property
    def verilog_template(self: EnableMixinProtocol) -> str:
        return super().verilog_template.replace('{set_out}', 'if ({en}) begin\n\t\t{set_out}\n\tend')

    @property
    def verilog_context_map(self: EnableMixinProtocol) -> SafeFormatDict:
        context_map = super().verilog_context_map
        context_map.update(en=self._verilog_en)
        return context_map

    def update_parameters(self: EnableMixinProtocol) -> Optional[Parameters]:
        super().update_parameters()
        self.parameters.EN_POLARITY = self.en_polarity
        return self.parameters

    def set_en(self: EnableMixinProtocol, new_signal: SignalOrLogicLevel) -> None:
        """
        Sets the enable signal.

        Args:
            new_signal (Signal): The new enable signal value.
        """
        self.set('EN', new_signal)

    def model_post_init(self: EnableMixinProtocol, __context: Optional[Dict[str, object]]) -> None:
        super().model_post_init(__context)
        self.connect('EN', None, direction=Direction.IN)

    def _calc_output(self: EnableMixinProtocol, idx: NonNegativeInt = 0) -> Dict[int, Signal]:
        if self.input_port[idx].signal.is_defined and self.en_signal.is_defined:
            return {idx: self.input_port[idx].signal if self.en_signal is self.en_polarity else self.output_port[idx].signal}
        return {idx: Signal.UNDEFINED}


class RstMixin(BaseModel):
    @property
    def rst_polarity(self: ResetMixinProtocol) -> Signal:
        """Which reset level resets the flip-flop. Default is Signal.HIGH: the flipflop is in reset, if the reset signal is HIGH."""
        return self.parameters.ARST_POLARITY if self.parameters.ARST_POLARITY is not None else Signal.HIGH

    @rst_polarity.setter
    def rst_polarity(self: ResetMixinProtocol, new_signal: Signal) -> None:
        self.parameters.ARST_POLARITY = new_signal

    @property
    def rst_val_int(self: ResetMixinProtocol) -> int:
        """Reset value of the flip-flop as integer. Default is 0."""
        return self.parameters.ARST_VALUE or 0

    @rst_val_int.setter
    def rst_val_int(self: ResetMixinProtocol, new_rst_val_int: int) -> None:
        self.parameters.ARST_VALUE = new_rst_val_int

    @property
    def rst_port(self: ResetMixinProtocol) -> Port[Instance]:
        """The reset port of the gate."""
        return self.ports['RST']

    @property
    def rst_val(self: ResetMixinProtocol) -> Dict[int, Signal]:
        """The value of the flipflop during and after reset. Default is Signal.LOW, i.e. the initial flipflop state is 0 by default."""
        return Signal.from_int(self.rst_val_int, fixed_width=self.data_width)

    @property
    def in_reset(self: ResetMixinProtocol) -> bool:
        """True if the gate is currently in reset, False otherwise."""
        return self.rst_port.signal is self.rst_polarity

    def model_post_init(self: ResetMixinProtocol, __context: Optional[Dict[str, object]]) -> None:
        super().model_post_init(__context)
        self.connect('RST', None, direction=Direction.IN)

    @property
    def verilog_net_map(self: ResetMixinProtocol) -> Dict[str, str]:
        rst = self.p2v(self.rst_port)
        sigs = super().verilog_net_map
        sigs.update({'RST': rst})
        return sigs

    @property
    def _verilog_rst(self: ResetMixinProtocol) -> str:
        """
        The verilog representation of the reset sensitivity list entry.

        Has the form `posedge rst_net_name` or `negedge rst_net_name`, depending on the reset polarity.
        """
        return self._v_header(self.rst_port, self.rst_polarity)

    @property
    def _verilog_rst_net(self: ResetMixinProtocol) -> str:
        """
        The verilog representation of the reset net.

        Has the form `rst_net_name` or `~rst_net_name`, depending on the reset polarity.
        """
        rst_net = self.p2v(self.rst_port) if self.p2v(self.rst_port) != "1'bx" else ''
        return rst_net if self.rst_polarity == Signal.HIGH else f'~{rst_net}'

    @property
    def _verilog_rst_sig_val(self: ResetMixinProtocol) -> str:
        return f"{self.output_port.width}'b{f'{Signal.dict_to_bin(self.rst_val)}'.zfill(self.output_port.width)}"

    @property
    def _verilog_header(self: ResetMixinProtocol) -> str:
        return self._verilog_rst

    @property
    def verilog_template(self: ResetMixinProtocol) -> str:
        return super().verilog_template.replace('{set_out}', 'if ({is_rst}) begin\n\t\t{rst_out}\n\tend else begin\n\t\t{set_out}\n\tend')

    @property
    def verilog_context_map(self: ResetMixinProtocol) -> SafeFormatDict:
        rst_out = super()._storage_assigns(sig_value=self._verilog_rst_sig_val)
        context_map = super().verilog_context_map
        context_map.update(header=self._verilog_header, is_rst=self._verilog_rst_net, rst_out=rst_out)
        return context_map

    def update_parameters(self: ResetMixinProtocol) -> Optional[Parameters]:
        super().update_parameters()
        self.parameters.ARST_POLARITY = self.rst_polarity
        self.parameters.ARST_VALUE = self.rst_val_int
        return self.parameters

    def set_rst(self: ResetMixinProtocol, new_signal: SignalOrLogicLevel) -> None:
        """
        Sets the reset signal.

        Args:
            new_signal (Signal): The new reset signal value.
        """
        self.set(self.rst_port.name, new_signal)
        self.evaluate()

    def _calc_output(self: ResetMixinProtocol, idx: NonNegativeInt = 0) -> Dict[int, Signal]:
        if self.rst_port.signal is self.rst_polarity:
            return {idx: self.rst_val[idx]}
        return super()._calc_output(idx)

    def _split_sync_params(self: ResetMixinProtocol, slices: Iterable[ResetMixinProtocol]) -> None:
        super()._split_sync_params(slices)
        idx = 0
        for slice in slices:
            slice.parameters.ARST_VALUE = int(self.rst_val[idx])
            idx += 1


class ScanMixin(BaseModel):
    parameters: DFFParams = DFFParams()

    @property
    def se_port(self: ScanMixinProtocol) -> Port[Instance]:
        return self.ports['SE']

    @property
    def si_port(self: ScanMixinProtocol) -> Port[Instance]:
        return self.ports['SI']

    @property
    def so_port(self: ScanMixinProtocol) -> Port[Instance]:
        return self.ports['SO']

    @property
    def se_signal(self: ScanMixinProtocol) -> Signal:
        """The scan enable signal of the gate."""
        return self.se_port.signal

    @property
    def scan_ff_equivalent(self: ScanMixinProtocol) -> Type['ClkMixin']:
        """Returns the Scan-FF type equivalent for normal FF and the FF type equivalent for Scan-FF."""
        from netlist_carpentry.utils.gate_lib import ADFF, ADFFE, DFF, DFFE

        mapping: Dict[str, Type['DFF']] = {
            '§scan_dff': DFF,
            '§scan_adff': ADFF,
            '§scan_dffe': DFFE,
            '§scan_adffe': ADFFE,
        }
        return mapping[self.instance_type]

    @property
    def verilog_template(self: ScanMixinProtocol) -> str:
        # TODO Very ugly, just like meee
        # But this property can be changed to be less ugly
        base_split = super().verilog_template.splitlines()
        base_split.insert(0, '{so}')
        for i, ln in enumerate(base_split):
            if '{set_out}' in ln:
                break
        scan_base = 'if ({se}) begin\n\t\t{si}\n\tend'
        if 'else' in base_split[i - 1]:
            base_split[i - 1] = base_split[i - 1].replace('else', f'else {scan_base} else')
        else:
            if 'if' in base_split[i - 1]:
                base_split[i - 1] = f'\t{scan_base} else ' + base_split[i - 1][1:]
            else:
                base_split[i] = f'\t{scan_base} else begin' + '\n\t\t{set_out}\n\tend'
        return '\n'.join(base_split)

    @property
    def verilog_net_map(self: ScanMixinProtocol) -> Dict[str, str]:
        se = self.p2v(self.se_port)
        si = self.p2v(self.si_port)
        so = self.p2v(self.so_port)
        sigs = super().verilog_net_map
        sigs.update({'SE': se, 'SI': si, 'SO': so})
        return sigs

    @property
    def verilog_context_map(self: ScanMixinProtocol) -> SafeFormatDict:
        se = self.verilog_net_map['SE']
        si = self.verilog_net_map['SI']
        so = self.verilog_net_map['SO']
        si_str = f'{self.p2v(self.output_port)}\t<=\t{si};'
        so_str = f'assign\t{so}\t=\t{self.p2v(self.output_port)};'

        context_map = super().verilog_context_map
        context_map.update(se=se, si=si_str, so=so_str)
        return context_map

    def set_se(self: ScanMixinProtocol, new_signal: SignalOrLogicLevel) -> None:
        """
        Sets the scan enable signal.

        Args:
            new_signal (Signal): The new scan enable signal value.
        """
        self.set('SE', new_signal)

    def model_post_init(self: ScanMixinProtocol, __context: Optional[Dict[str, object]]) -> None:
        super().model_post_init(__context)
        self.connect('SE', None, direction=Direction.IN)
        self.connect('SI', None, direction=Direction.IN, width=self.width)
        self.connect('SO', None, direction=Direction.OUT, width=self.width)

    def _calc_output(self: ScanMixinProtocol, idx: NonNegativeInt = 0) -> Dict[int, Signal]:
        if self.se_signal is Signal.HIGH:
            return {idx: self.si_port.signal_array[idx]}
        return super()._calc_output(idx)

    def _set_output(self: ScanMixinProtocol, new_signals: Dict[int, Signal]) -> None:
        for idx, sig in new_signals.items():
            self.so_port.set_signal(signal=sig, index=idx)
        return super()._set_output(new_signals)

    def pre_py2v_hook(self: ScanMixinProtocol) -> None:
        for _, ps in self.so_port:
            ps.ws.metadata.set('net_type', 'wire')
            ps.ws.parent.metadata.set('net_type', 'wire')
        return super().pre_py2v_hook()
