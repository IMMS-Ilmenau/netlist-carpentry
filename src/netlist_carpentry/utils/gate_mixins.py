# mypy: disable-error-code="safe-super"
from typing import Dict, Iterable, List, Optional, Protocol, Type, Union, runtime_checkable

from pydantic import BaseModel, NonNegativeInt, PositiveInt

from netlist_carpentry import Direction, Instance, Port, Signal, SignalArray
from netlist_carpentry.core.exceptions import WidthMismatchError
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.core.netlist_elements.port import ANY_PORT
from netlist_carpentry.core.protocols.signals import SignalOrLogicLevel
from netlist_carpentry.utils.custom_dict import CustomDict
from netlist_carpentry.utils.gate_lib_dataclasses import ClockParams, DFFParams, EnableParams, LoadParams, Parameters, ResetParams, SRParams
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
    def model_post_init(self, __context: object) -> None: ...
    def update_parameters(self) -> None: ...
    def connect(
        self,
        port_name: str,
        ws_path: Optional[WireSegmentPath],
        direction: Direction = Direction.UNKNOWN,
        index: NonNegativeInt = 0,
        width: PositiveInt = 1,
    ) -> None: ...
    def p2v(self, port: ANY_PORT, exclude_indices: Optional[List[int]] = None, include_indices: Optional[List[int]] = None) -> str: ...
    def _v_header(self, port: Port[Instance], polarity: Signal, idx: int = 0) -> str: ...
    def _storage_assigns(self, sig_value: str = '') -> str: ...
    def set(self, port_name: str, new_signal: SignalOrLogicLevel, idx: Union[int, List[int]] = 0) -> None: ...
    def evaluate(self) -> None: ...
    def _calc_output(self, idx: NonNegativeInt = 0) -> SignalArray: ...
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


@runtime_checkable
class LoadMixinProtocol(GateProtocol, Protocol):
    @property
    def parameters(self) -> LoadParams: ...
    @property
    def al_port(self) -> Port[Instance]: ...
    @property
    def ad_port(self) -> Port[Instance]: ...
    @property
    def load_polarity(self) -> Signal: ...
    @property
    def load_val(self) -> Dict[int, Signal]: ...
    @property
    def load_val_int(self) -> Optional[int]: ...
    @property
    def _verilog_load(self) -> str: ...
    @property
    def _verilog_load_net(self) -> str: ...
    @property
    def _verilog_load_sig_val(self) -> str: ...
    @property
    def _verilog_clk(self) -> str: ...
    @property
    def _verilog_header(self) -> str: ...


@runtime_checkable
class SRMixinProtocol(GateProtocol, Protocol):
    @property
    def parameters(self) -> SRParams: ...
    @property
    def clr_port(self) -> Port[Instance]: ...
    @property
    def clr_polarity(self) -> Signal: ...
    @property
    def set_port(self) -> Port[Instance]: ...
    @property
    def set_polarity(self) -> Signal: ...
    def _verilog_clr_net(self, idx: int) -> str: ...
    def _verilog_set_net(self, idx: int) -> str: ...
    def _verilog_header_sr(self, idx: int) -> str: ...
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

    def model_post_init(self: ClockMixinProtocol, __context: object) -> None:
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

    def model_post_init(self: EnableMixinProtocol, __context: object) -> None:
        super().model_post_init(__context)
        self.connect('EN', None, direction=Direction.IN)

    def _calc_output(self: EnableMixinProtocol) -> SignalArray:
        signals = {}
        for idx in range(self.data_width):
            if self.en_signal.is_undefined or (self.en_signal is self.en_polarity and self.input_port[idx].signal.is_undefined):
                signals[idx] = Signal.UNDEFINED
            elif self.en_signal is self.en_polarity:
                signals[idx] = self.input_port[idx].signal if self.en_signal is self.en_polarity else self.output_port[idx].signal
            else:
                signals[idx] = self.output_port[idx].signal
        return SignalArray(signals=signals)


class RstMixin(BaseModel):
    @property
    def rst_polarity(self: ResetMixinProtocol) -> Signal:
        """Which reset level resets the flip-flop. Default is Signal.HIGH: the flipflop is in reset, if the reset signal is HIGH."""
        return self.parameters.RST_POLARITY if self.parameters.RST_POLARITY is not None else Signal.HIGH

    @rst_polarity.setter
    def rst_polarity(self: ResetMixinProtocol, new_signal: Signal) -> None:
        self.parameters.RST_POLARITY = new_signal

    @property
    def rst_val_int(self: ResetMixinProtocol) -> int:
        """Reset value of the flip-flop as integer. Default is 0."""
        return self.parameters.RST_VALUE or 0

    @rst_val_int.setter
    def rst_val_int(self: ResetMixinProtocol, new_rst_val_int: int) -> None:
        self.parameters.RST_VALUE = new_rst_val_int

    @property
    def rst_port(self: ResetMixinProtocol) -> Port[Instance]:
        """The reset port of the gate."""
        return self.ports['RST']

    @property
    def rst_val(self: ResetMixinProtocol) -> SignalArray:
        """The value of the flipflop during and after reset. Default is Signal.LOW, i.e. the initial flipflop state is 0 by default."""
        return SignalArray.from_int(self.rst_val_int, fixed_width=self.data_width)

    @property
    def in_reset(self: ResetMixinProtocol) -> bool:
        """True if the gate is currently in reset, False otherwise."""
        return self.rst_port.signal is self.rst_polarity

    def model_post_init(self: ResetMixinProtocol, __context: object) -> None:
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
        self.parameters.RST_POLARITY = self.rst_polarity
        self.parameters.RST_VALUE = self.rst_val_int
        return self.parameters

    def set_rst(self: ResetMixinProtocol, new_signal: SignalOrLogicLevel) -> None:
        """
        Sets the reset signal.

        Args:
            new_signal (Signal): The new reset signal value.
        """
        self.set(self.rst_port.name, new_signal)
        self.evaluate()

    def _calc_output(self: ResetMixinProtocol) -> SignalArray:
        if self.rst_port.signal is self.rst_polarity:
            return SignalArray(signals={idx: self.rst_val[idx] for idx in range(self.data_width)})
        return super()._calc_output()

    def _split_sync_params(self: ResetMixinProtocol, slices: Iterable[ResetMixinProtocol]) -> None:
        super()._split_sync_params(slices)
        idx = 0
        for slice in slices:
            slice.parameters.RST_VALUE = int(self.rst_val[idx])
            idx += 1


class LoadMixin(BaseModel):
    @property
    def load_polarity(self: LoadMixinProtocol) -> Signal:
        """Which load level loads the load value into flip-flop. Default is Signal.HIGH: the flipflop will load, if the load signal is HIGH."""
        return self.parameters.LOAD_POLARITY if self.parameters.LOAD_POLARITY is not None else Signal.HIGH

    @load_polarity.setter
    def load_polarity(self: LoadMixinProtocol, new_signal: Signal) -> None:
        self.parameters.LOAD_POLARITY = new_signal

    @property
    def al_port(self: LoadMixinProtocol) -> Port[Instance]:
        """The asynchronous load enable port of the gate, i.e. the port that toggles whether to load data into the flip-flop."""
        return self.ports['AL']

    @property
    def ad_port(self: LoadMixinProtocol) -> Port[Instance]:
        """The asynchronous data load port of the gate, i.e. the port that holds the data to load into the flip-flop."""
        return self.ports['AD']

    @property
    def load_val(self: LoadMixinProtocol) -> SignalArray:
        """The value of the flipflop during and after reset, retrieved from the load data port."""
        return self.ad_port.signal_array

    @property
    def load_val_int(self: LoadMixinProtocol) -> Optional[int]:
        """The value of the flipflop during and after reset as an integer, retrieved from the load data port."""
        return self.ad_port.signal_int

    @property
    def in_load(self: LoadMixinProtocol) -> bool:
        """True if the gate is currently in "load-value" mode, False otherwise."""
        return self.al_port.signal is self.load_polarity

    def model_post_init(self: LoadMixinProtocol, __context: object) -> None:
        super().model_post_init(__context)
        self.connect('AL', None, direction=Direction.IN)
        self.connect('AD', None, direction=Direction.IN, width=self.width)

    @property
    def verilog_net_map(self: LoadMixinProtocol) -> Dict[str, str]:
        al = self.p2v(self.al_port)
        ad = self.p2v(self.ad_port)
        sigs = super().verilog_net_map
        sigs.update({'AL': al, 'AD': ad})
        return sigs

    @property
    def _verilog_load(self: LoadMixinProtocol) -> str:
        """
        The verilog representation of the load sensitivity list entry.

        Has the form `posedge load_en_net_name` or `negedge load_en_net_name`, depending on the load polarity.
        """
        return self._v_header(self.al_port, self.load_polarity)

    @property
    def _verilog_load_net(self: LoadMixinProtocol) -> str:
        """
        The verilog representation of the reset net.

        Has the form `load_net_name` or `~load_net_name`, depending on the reset polarity.
        """
        load_net = self.p2v(self.al_port) if self.p2v(self.al_port) != "1'bx" else ''
        return load_net if self.load_polarity == Signal.HIGH else f'~{load_net}'

    @property
    def _verilog_load_sig_val(self: LoadMixinProtocol) -> str:
        return f"{self.output_port.width}'b{f'{Signal.dict_to_bin(self.load_val)}'.zfill(self.output_port.width)}"

    @property
    def _verilog_header(self: LoadMixinProtocol) -> str:
        return self._verilog_load

    @property
    def verilog_context_map(self: LoadMixinProtocol) -> SafeFormatDict:
        ad = super()._storage_assigns(sig_value=self.p2v(self.ad_port))
        context_map = super().verilog_context_map
        header = f'{self._verilog_clk} or {self._verilog_header}'
        context_map.update(header=header, is_al=self._verilog_load_net, ad=ad)
        return context_map

    @property
    def verilog_template(self: LoadMixinProtocol) -> str:
        return super().verilog_template.replace('{set_out}', 'if ({is_al}) begin\n\t\t{ad}\n\tend else begin\n\t\t{set_out}\n\tend')

    def update_parameters(self: LoadMixinProtocol) -> None:
        super().update_parameters()
        self.parameters.LOAD_POLARITY = self.load_polarity

    def set_al(self: LoadMixinProtocol, new_signal: SignalOrLogicLevel) -> None:
        """
        Sets the asynchronous load enable signal.

        Args:
            new_signal (Signal): The new asynchronous load enable signal value.
        """
        self.set(self.al_port.name, new_signal)
        self.evaluate()

    def _calc_output(self: LoadMixinProtocol) -> SignalArray:
        if self.al_port.signal is self.load_polarity:
            return SignalArray(signals={idx: self.load_val[idx] for idx in range(self.data_width)})
        return super()._calc_output()


class SRMixin(BaseModel):
    @property
    def clr_polarity(self: SRMixinProtocol) -> Signal:
        """Which clear level clears the flip-flop. Default is Signal.HIGH: the flipflop goes to 0, if the clear signal is HIGH."""
        return self.parameters.CLR_POLARITY if self.parameters.CLR_POLARITY is not None else Signal.HIGH

    @clr_polarity.setter
    def clr_polarity(self: SRMixinProtocol, new_signal: Signal) -> None:
        self.parameters.CLR_POLARITY = new_signal

    @property
    def clr_port(self: SRMixinProtocol) -> Port[Instance]:
        """The clear port of the gate."""
        return self.ports['CLR']

    @property
    def set_polarity(self: SRMixinProtocol) -> Signal:
        """Which set level sets the flip-flop. Default is Signal.HIGH: the flipflop goes to 1, if the set signal is HIGH."""
        return self.parameters.SET_POLARITY if self.parameters.SET_POLARITY is not None else Signal.HIGH

    @set_polarity.setter
    def set_polarity(self: SRMixinProtocol, new_signal: Signal) -> None:
        self.parameters.SET_POLARITY = new_signal

    @property
    def set_port(self: SRMixinProtocol) -> Port[Instance]:
        """The set port of the gate."""
        return self.ports['SET']

    def model_post_init(self: SRMixinProtocol, __context: object) -> None:
        super().model_post_init(__context)
        self.connect('CLR', None, direction=Direction.IN, width=self.width)
        self.connect('SET', None, direction=Direction.IN, width=self.width)

    @property
    def verilog_net_map(self: SRMixinProtocol) -> Dict[str, str]:
        clr_v = self.p2v(self.clr_port)
        set_v = self.p2v(self.set_port)
        sigs = super().verilog_net_map
        sigs.update({'CLR': clr_v, 'SET': set_v})
        return sigs

    def _verilog_clr_net(self: SRMixinProtocol, idx: int) -> str:
        """
        The verilog representation of the clear net.

        Has the form `clr_net_name` or `~clr_net_name`, depending on the clear polarity.
        """
        clr_net = self.p2v(self.clr_port, include_indices=[idx])
        clr_net = clr_net if clr_net != "1'bx" else ''
        return clr_net if self.clr_polarity == Signal.HIGH else f'~{clr_net}'

    def _verilog_set_net(self: SRMixinProtocol, idx: int) -> str:
        """
        The verilog representation of the set net.

        Has the form `set_net_name` or `~set_net_name`, depending on the set polarity.
        """
        set_net = self.p2v(self.set_port, include_indices=[idx])
        set_net = set_net if set_net != "1'bx" else ''
        return set_net if self.set_polarity == Signal.HIGH else f'~{set_net}'

    def _verilog_header_sr(self: SRMixinProtocol, idx: int) -> str:
        return self._v_header(self.clr_port, self.clr_polarity, idx) + ' or ' + self._v_header(self.set_port, self.set_polarity, idx)

    @property
    def verilog_context_map(self: SRMixinProtocol) -> SafeFormatDict:
        context_map = super().verilog_context_map
        if set(self.clr_port.segments.keys()) != set(self.set_port.segments.keys()):
            raise WidthMismatchError('CLR and SET port differ in width and/or offset!')
        self.update_parameters()
        for idx in self.clr_port.segments:
            context_map[f'header{idx}'] = self._verilog_header_sr(idx)
            context_map[f'is_clr{idx}'] = self._verilog_clr_net(idx)
            context_map[f'is_set{idx}'] = self._verilog_set_net(idx)
            in1 = self.p2v(self.input_port, include_indices=[idx])
            out = self.p2v(self.output_port, include_indices=[idx])
            context_map[f'clr_out{idx}'] = f"{out}\t<=\t1'b0;"
            context_map[f'set_out{idx}'] = f"{out}\t<=\t1'b1;"
            context_map[f'd_out{idx}'] = f'{out}\t<=\t{in1};'
            if 'EN' in self.ports and 'EN_POLARITY' in self.parameters and isinstance(self.parameters['EN_POLARITY'], Signal):
                en = self.p2v(self.ports['EN'], include_indices=[idx])
                en_pol = '~' if self.parameters['EN_POLARITY'] is Signal.LOW else ''
                context_map[f'en{idx}'] = en_pol + en
        return context_map

    @property
    def verilog(self: SRMixinProtocol) -> str:
        context_map = self.verilog_context_map
        sr_instances = []
        for idx in self.clr_port.segments:
            header = context_map[f'header{idx}']
            is_clr = context_map[f'is_clr{idx}']
            is_set = context_map[f'is_set{idx}']
            clr_out = context_map[f'clr_out{idx}']
            set_out = context_map[f'set_out{idx}']
            d_out = context_map[f'd_out{idx}']
            if f'en{idx}' in context_map:
                en = context_map[f'en{idx}']
                v = self.verilog_template.format(header=header, is_clr=is_clr, is_set=is_set, clr_out=clr_out, set_out=set_out, d_out=d_out, en=en)
            else:
                v = self.verilog_template.format(header=header, is_clr=is_clr, is_set=is_set, clr_out=clr_out, set_out=set_out, d_out=d_out)
            sr_instances.append(v)
        return '\n'.join(sr_instances)

    def update_parameters(self: SRMixinProtocol) -> None:
        super().update_parameters()
        self.parameters.CLR_POLARITY = self.clr_polarity
        self.parameters.SET_POLARITY = self.set_polarity

    def set_clr(self: SRMixinProtocol, new_signal: SignalOrLogicLevel, idx: Union[int, List[int]]) -> None:
        """
        Sets the clear signal.

        Args:
            new_signal (Signal): The new clear signal value.
            idx (Union[int, List[int]], optional): The index (or indices) to apply the given signal to.
                Can either be an integer (single index to set) or an iterable of integers (e.g. a list of indices).
                For every integer of the iterable the signal value of the corresponding port index is set to the given `new_signal`.
                Defaults to 0.
        """
        self.set(self.clr_port.name, new_signal, idx)
        self.evaluate()

    def set_set(self: SRMixinProtocol, new_signal: SignalOrLogicLevel, idx: Union[int, List[int]]) -> None:
        """
        Sets the set signal.

        Args:
            new_signal (Signal): The new set signal value.
            idx (Union[int, List[int]], optional): The index (or indices) to apply the given signal to.
                Can either be an integer (single index to set) or an iterable of integers (e.g. a list of indices).
                For every integer of the iterable the signal value of the corresponding port index is set to the given `new_signal`.
                Defaults to 0.
        """
        self.set(self.set_port.name, new_signal, idx)
        self.evaluate()

    def _calc_output(self: SRMixinProtocol) -> SignalArray:
        signals = {}
        for idx in range(self.data_width):
            if self.clr_port[idx].signal is self.clr_polarity:
                signals[idx] = Signal.LOW
            elif self.set_port[idx].signal is self.set_polarity:
                signals[idx] = Signal.HIGH
            else:
                signals[idx] = super()._calc_output().signals[idx]
        return SignalArray(signals=signals)


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

    def model_post_init(self: ScanMixinProtocol, __context: object) -> None:
        super().model_post_init(__context)
        self.connect('SE', None, direction=Direction.IN)
        self.connect('SI', None, direction=Direction.IN, width=self.width)
        self.connect('SO', None, direction=Direction.OUT, width=self.width)

    def _calc_output(self: ScanMixinProtocol) -> SignalArray:
        if self.se_signal is Signal.HIGH:
            return self.si_port.signal_array
        return super()._calc_output()

    def _set_output(self: ScanMixinProtocol, new_signals: Dict[int, Signal]) -> None:
        for idx, sig in new_signals.items():
            self.so_port.set_signal(signal=sig, index=idx)
        return super()._set_output(new_signals)

    def pre_py2v_hook(self: ScanMixinProtocol) -> None:
        for _, ps in self.so_port:
            ps.ws.metadata.set('net_type', 'wire')
            ps.ws.parent.metadata.set('net_type', 'wire')
        return super().pre_py2v_hook()
