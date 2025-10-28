"""
This module provides a set of classes for modeling digital circuits at the gate level.
It currently includes base classes for primitive gates, unary gates, binary gates, and clocked gates,
as well as methods for evaluating the output signals of these gates.
They provide a common interface for working with different types of gates,
including methods for setting input signals, evaluating output signals, and updating gate states.
See the gate_lib.py module for further information.
"""

from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, PositiveInt

from netlist_carpentry import CFG, LOG
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.wire_segment import CONST_MAP_VAL2OBJ, WIRE_SEGMENT_X, WireSegment
from netlist_carpentry.core.port_direction import PortDirection
from netlist_carpentry.core.signal import Signal


class LibUtils:
    """Class for some methods related to handling elements from the Gate Library.

    This class contains information about the currently selected module.
    Furthermore, this class provides methods for collecting wire segments connected
    to a port segment and transforming them into Verilog syntax.

    More functionality may be added later as needed.
    """

    _gatelib_current_module: Optional[Module] = None
    _tmp_reg_idx: int = 0

    @classmethod
    def curr_module(cls) -> Optional[Module]:
        return LibUtils._gatelib_current_module

    @classmethod
    def change_current_module(cls, new_module: Module) -> None:
        if LibUtils.curr_module() != new_module:
            # Required for write-out to keep track to which module an instance (and the connected wires) belong to
            LOG.debug(f'Changing current module in the gate library to {new_module.name}...')
            LibUtils._gatelib_current_module = new_module

    @classmethod
    def p2ws2v(cls, port: Port, exclude_indices: List[int] = []) -> str:
        """
        Converts a Port object to its corresponding Verilog structure by using the connected wire segments.

        This method takes the connected wire segments of a Port object and converts them to their corresponding
        Verilog signal structure (p2ws2v -> Port to WireSegment to Verilog signal syntax).
        The method requires that the currently selected module matches the module of the Port object,
        which is derived from the design path of the Port object.
        For each segment of the port, it checks whether a corresponding connected wire segment exists in the current module.
        If the port is set to a constant, the corresponding constant wire segment placeholder is used instead.
        Port segments can be excluded from the conversion by providing a list of indices,
        indicating which segments should be excluded from the conversion (e.g. segments that are known to be unconnected).

        Args:
            port (Port): The Port object to convert.
            exclude_indices (List[int], optional): A list of indices to exclude from the conversion. Defaults to an empty list.

        Returns:
            str: The Verilog signal structure as a string.

        Raises:
            AttributeError: If the currently selected module does not match the module of the port.
        """
        curr_module = LibUtils.curr_module()
        if curr_module is None:
            raise AttributeError('No module currently selected!')
        if curr_module.name not in port.raw_path:
            raise AttributeError(f'Currently selected module ("{curr_module.raw_path}") does not match the module of port {port.raw_path}!')
        wsegs: List[WireSegment] = []
        for idx, ps in reversed(port.segments.items()):
            if idx not in exclude_indices:
                if not ps.is_tied:
                    ws = curr_module.get_from_path(ps.ws_path)
                    if ws is not None:
                        wsegs.append(ws)
                    else:
                        raise ValueError(f'No wire found for path {ps.ws_path}!')
                else:
                    wsegs.append(CONST_MAP_VAL2OBJ.get(ps.raw_ws_path, WIRE_SEGMENT_X))
        return LibUtils._ws2v(wsegs)

    @classmethod
    def _ws2v(cls, wsegs: List[WireSegment]) -> str:
        """
        Transforms a list of WireSegments into Verilog code.

        Args:
            wsegs (List[WireSegment]): The list of WireSegments to be transformed into Verilog code.

        Returns:
            str: A string representing the Verilog code corresponding to the input list of WireSegments.
        """
        from netlist_carpentry.api.write.py2v import P2VTransformer as P2V

        module = LibUtils.curr_module()
        if module is not None:
            return P2V.simplify_wire_segments(module, wsegs)
        raise ValueError(
            'Cannot transform wire segments to Verilog code: No module set in gate library as current module.'
            + f'Wire segments are: {", ".join(str(ws) for ws in wsegs)}'
        )

    @classmethod
    def get_unconnected_idx(cls, port: Port) -> List[int]:
        exclude_indices = [idx for idx, ps in port.segments.items() if ps.is_unconnected]
        if exclude_indices:
            LOG.warn(f'Excluding these segments from port {port.raw_path} from write-out, since they are unconnected: {exclude_indices}')
        return exclude_indices


class _PrimitiveGate(Instance, BaseModel):
    """
    A base class for all primitive gates.

    Primitive gates are the basic building blocks of digital circuits, and they can be combined to create more complex circuits.
    This class provides a common interface for all primitive gates, including methods for evaluating the gate's output and setting its output signal.
    """

    width: PositiveInt = 1
    is_primitive: bool = True
    instance_type: str = CFG.id_internal

    @property
    def is_combinatorial(self) -> bool:
        return True

    @property
    def is_sequential(self) -> bool:
        return not self.is_combinatorial

    @property
    def output_port(self) -> Port:
        """
        The output port of the gate.

        Returns:
            Port: The output port of the gate.
        """
        raise NotImplementedError('Not implemented in base class!')

    @property
    def data_width(self) -> int:
        """
        The data width of this instance.

        Defaults to the data width of the output port.
        Can be overwritten in extended classes.

        In contrast to `self.width`, which is used for the creation and initialization,
        this property is linked to the data width of the output port.
        This property is useful when the data width of the output port can be changed.
        """
        return self.output_port.width

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1};'

    def evaluate(self) -> None:
        """
        Evaluates the gate's output signal based on its input signals.

        This method is called when the gate's input signals change, and it updates the gate's output signal accordingly.
        """
        new_signals = {}
        for i in range(self.data_width):
            new_signals.update(self._calc_output(i))
        self._set_output(new_signals=new_signals)

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal based on its input signals.

        This method is implemented by each specific gate class, and it returns the gate's output signal.
        """
        raise NotImplementedError(f'Not implemented for objects of type {type(self)}')

    def _set_output(self, new_signals: Dict[int, Signal]) -> None:
        """
        Sets the gate's output signal.

        This method is called when the gate's output signal needs to be updated, and it sets the gate's output signal to the specified value.

        Args:
            new_signals (Dict[int, Signal]): A dictionary mapping the new output signal values to the indices of the output port.
        """
        for idx, sig in new_signals.items():
            self.output_port.set_signal(signal=sig, index=idx)


class _UnaryGate(_PrimitiveGate, BaseModel):
    """
    A base class for unary gates.

    Unary gates are gates that have a single input signal, and they produce a single output signal.
    This class provides a common interface for all unary gates, including methods for evaluating the gate's output and setting its output signal.
    """

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        self.connect('A', None, direction=PortDirection.IN, width=self.width)
        self.connect('Y', None, direction=PortDirection.OUT, width=self.width)
        return super().model_post_init(__context)

    @property
    def input_port(self) -> Port:
        """
        The input port of the gate.

        Returns:
            Port: The input port of the gate.
        """
        return self.ports['A']

    @property
    def output_port(self) -> Port:
        """
        The output port of the gate.

        Returns:
            Port: The output port of the gate.
        """
        return self.ports['Y']

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1};'

    def _check_signal_signed(self, a: str) -> str:
        if self.parameters.get('A_SIGNED', False):
            a = f'$signed({a})'
        return a

    @property
    def verilog(self) -> str:
        if any(self.ports['Y'][i].is_connected for i in self.ports['Y'].segments):
            exclude_indices = LibUtils.get_unconnected_idx(self.ports['Y'])
            out_str = LibUtils.p2ws2v(self.ports['Y'], exclude_indices)
            in1_str = LibUtils.p2ws2v(self.ports['A'], exclude_indices)
            in1_str = self._check_signal_signed(in1_str)
            return self.verilog_template.format(out=out_str, in1=in1_str)
        return ''

    def signal_in(self, idx: int = 0) -> Signal:
        """
        The input signal of the gate.

        Returns:
            Signal: The input signal of the gate.
        """
        return self.input_port.signal_array[idx]

    def signal_out(self, idx: int = 0) -> Signal:
        """
        The output signal of the gate.

        Returns:
            Signal: The output signal of the gate.
        """
        return self.output_port.signal_array[idx]


class _ReduceGate(_UnaryGate, BaseModel):
    """
    A base class for reduce gates.

    Reduce gates are gates that have an n-bit input signal, and they produce a 1-bit output signal by performing a given reducing operation.
    This class provides a common interface for all reduce gates, including methods for evaluating the gate's output and setting its output signal.
    """

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        self.connect('A', None, direction=PortDirection.IN, width=self.width)
        self.connect('Y', None, direction=PortDirection.OUT)

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {operator}{in1};'

    @property
    def verilog(self) -> str:
        exclude_indices = LibUtils.get_unconnected_idx(self.ports['A'])
        in1 = LibUtils.p2ws2v(self.ports['A'], exclude_indices)
        # Check whether output is connected (i.e. LibUtils.p2ws2v(self.ports["Y"]) != "1'bx"), do not transform outgoing segments without connection
        return self.verilog_template.format(out=LibUtils.p2ws2v(self.ports['Y']), in1=in1) if LibUtils.p2ws2v(self.ports['Y']) != "1'bx" else ''

    def signal_out(self) -> Signal:  # type: ignore[override]
        """
        The output signal of the gate.

        Returns:
            Signal: The output signal of the gate.
        """
        return self.output_port.signal


class _BinaryGate(_PrimitiveGate, BaseModel):
    """
    A base class for binary gates.

    Binary gates are gates that have two input signals, and they produce a single output signal.
    This class provides a common interface for all binary gates, including methods for evaluating the gate's output and setting its output signal.
    """

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        self.connect('A', None, direction=PortDirection.IN, width=self.width)
        self.connect('B', None, direction=PortDirection.IN, width=self.width)
        self.connect('Y', None, direction=PortDirection.OUT, width=self.width)
        return super().model_post_init(__context)

    @property
    def input_ports(self) -> Tuple[Port, Port]:
        """
        The input ports of the gate.

        Returns:
            Tuple[Port, Port]: The input ports of the gate.
        """
        return (self.ports['A'], self.ports['B'])

    @property
    def output_port(self) -> Port:
        """
        The output port of the gate.

        Returns:
            Port: The output port of the gate.
        """
        return self.ports['Y']

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} {operator} {in2};'

    @property
    def verilog(self) -> str:
        if any(self.ports['Y'][i].is_connected for i in self.ports['Y'].segments):
            exclude_indices = LibUtils.get_unconnected_idx(self.ports['Y'])
            out_str = LibUtils.p2ws2v(self.ports['Y'], exclude_indices)
            in1_str = LibUtils.p2ws2v(self.ports['A'], exclude_indices)
            in2_str = LibUtils.p2ws2v(self.ports['B'], exclude_indices)
            in1_str, in2_str = self._check_signal_signed(in1_str, in2_str)
            return self.verilog_template.format(out=out_str, in1=in1_str, in2=in2_str)
        return ''

    def _check_signal_signed(self, a: str, b: str) -> Tuple[str, str]:
        if self.parameters.get('A_SIGNED', False):
            a = f'$signed({a})'
        if self.parameters.get('B_SIGNED', False):
            b = f'$signed({b})'
        return (a, b)

    def signals_in(self, idx: int = 0) -> Tuple[Signal, Signal]:
        """
        The input signals of the gate.

        Returns:
            Tuple[Signal, Signal]: The input signals of the gate.
        """
        return (self.input_ports[0].signal_array[idx], self.input_ports[1].signal_array[idx])

    def signal_out(self, idx: int = 0) -> Signal:
        """
        The output signal of the gate.

        Returns:
            Signal: The output signal of the gate.
        """
        return self.output_port.signal_array[idx]


class _ShiftGate(_BinaryGate, BaseModel):
    def _check_signal_signed(self, a: str, b: str) -> Tuple[str, str]:
        if self.parameters.get('A_SIGNED', False):
            a = f'$signed({a})'
        # Do not modify b to $signed({b}), because second operator of shift gates cannot be signed.
        return a, b


class _ArithmeticGate(_PrimitiveGate, BaseModel):
    """
    A base class for arithmetic gates.

    Arithmetic gates are gates that have two input signals representing numeric values, and they produce a single output signal.
    This class provides a common interface for all arithmetic gates, including methods for evaluating the gate's output and setting its output signal.
    """

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        self.connect('A', None, direction=PortDirection.IN, width=self.width)
        self.connect('B', None, direction=PortDirection.IN, width=self.width)
        self.connect('Y', None, direction=PortDirection.OUT, width=self.width)
        return super().model_post_init(__context)

    def _check_signal_signed(self, a: str, b: str) -> Tuple[str, str]:
        if self.parameters.get('A_SIGNED', False):
            a = f'$signed({a})'
        if self.parameters.get('B_SIGNED', False):
            b = f'$signed({b})'
        return (a, b)

    def evaluate(self) -> None:
        """
        Evaluates the gate's output signal based on its input signals.

        This method is called when the gate's input signals change, and it updates the gate's output signal accordingly.
        """
        new_signal_array = self._calc_output()
        self._set_output(new_signals=new_signal_array)

    @property
    def verilog(self) -> str:
        if any(self.ports['Y'][i].is_unconnected for i in self.ports['Y'].segments):
            raise ValueError(
                f'Cannot transform gate {self.raw_path} ({self.instance_type}) to Verilog: at least one bit of output {self.ports["Y"].raw_path} is Z!'
            )
        out = LibUtils.p2ws2v(self.output_port, [])
        in1 = LibUtils.p2ws2v(self.input_ports[0], [])
        in2 = LibUtils.p2ws2v(self.input_ports[1], [])
        in1_str, in2_str = self._check_signal_signed(in1, in2)
        return self.verilog_template.format(out=out, in1=in1_str, in2=in2_str)


class _BinaryNto1Gate(_BinaryGate, BaseModel):
    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        super().model_post_init(__context)
        self.ports.pop('Y')
        self.connect('Y', None, direction=PortDirection.OUT)

    @property
    def verilog(self) -> str:
        input_ps1 = LibUtils.p2ws2v(self.ports['A'])
        input_ps2 = LibUtils.p2ws2v(self.ports['B'])
        input_ps1, input_ps2 = self._check_signal_signed(input_ps1, input_ps2)
        out = LibUtils.p2ws2v(self.output_port)
        # Check whether output is connected, do not transform if output port is unconnected
        return self.verilog_template.format(out=out, in1=input_ps1, in2=input_ps2) if out != "1'bx" else ''

    def evaluate(self) -> None:
        new_signal = self._calc_output()
        self._set_output(new_signals=new_signal)


class _StorageGate(_PrimitiveGate, BaseModel):
    en_polarity: Signal = Signal.HIGH
    """Which EN-signal level enables writing on the data storage. Default is Signal.HIGH.
    """

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        self.connect('D', None, direction=PortDirection.IN, width=self.width)
        self.connect('EN', None, direction=PortDirection.IN)
        self.connect('Q', None, direction=PortDirection.OUT, width=self.width)

        return super().model_post_init(__context)

    @property
    def input_port(self) -> Port:
        """
        The input port of the gate.

        Returns:
            Port: The input port of the gate.
        """
        return self.ports['D']

    @property
    def en_port(self) -> Port:
        """
        The enable port of the gate.

        Returns:
            Port: The enable port of the gate.
        """
        return self.ports['EN']

    @property
    def output_port(self) -> Port:
        """
        The output port of the gate.

        Returns:
            Port: The output port of the gate.
        """
        return self.ports['Q']

    @property
    def en_signal(self) -> Signal:
        """
        The enable signal of the gate.

        Returns:
            Signal: The enable signal of the gate.
        """
        return self.en_port.signal


class _ClockedGate(_StorageGate, BaseModel):
    """A base class for clocked gates.Clocked gates are gates that have a clock signal and a reset signal.
    This class provides a common interface for all clocked gates, including methods for evaluating the gate's output and setting its output signal.

    Attributes:
        rst_val (Signal): The value of the reset signal.
        clk_polarity (Signal): The polarity of the clock signal.
        rst_polarity (Signal): The polarity of the reset signal.
    """

    rst_val_int: int = 0
    clk_polarity: Signal = Signal.HIGH
    """Which clock edge activates the flip-flop. Default is Signal.HIGH, i.e. rising edge."""
    rst_polarity: Signal = Signal.HIGH
    """Which reset level resets the flip-flop. Default is Signal.HIGH: the flipflop is in reset, if the reset signal is HIGH."""
    _clk_redge: bool = False
    _clk_fedge: bool = False
    _rst_redge: bool = False
    _rst_fedge: bool = False

    @property
    def rst_val(self) -> Dict[int, Signal]:
        """The value of the flipflop during and after reset. Default is Signal.LOW, i.e. the initial flipflop state is 0 by default."""
        return Signal.from_int(self.rst_val_int, fixed_width=self.data_width)

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        super().model_post_init(__context)
        self.connect('CLK', None, direction=PortDirection.IN)
        self.connect('RST', None, direction=PortDirection.IN)
        # Add listener after connection is added
        # Otherwise the hash value would change because of the structural change of the instance
        # Then the set would no longer directly reference the flip-flop
        # TODO reference listeners via ID (Dict[ID, Listener]) and not in Set (and hash calculation)!
        self.clk_port.add_listener(self)
        self.clk_port[0].add_listener(self)
        self.rst_port.add_listener(self)
        self.rst_port[0].add_listener(self)

        self._init_finished = False
        self._prev_clk = Signal.UNDEFINED
        self._curr_clk = Signal.UNDEFINED
        self._prev_rst = Signal.UNDEFINED
        self._curr_rst = Signal.UNDEFINED

        self._curr_out = [Signal.UNDEFINED for i in range(self.data_width)]

    @property
    def is_combinatorial(self) -> bool:
        return False

    @property
    def clk_port(self) -> Port:
        """
        The clock port of the gate.

        Returns:
            Port: The clock port of the gate.
        """
        return self.ports['CLK']

    @property
    def rst_port(self) -> Port:
        """
        The reset port of the gate.

        Returns:
            Port: The reset port of the gate.
        """
        return self.ports['RST']

    @property
    def clk_signal(self) -> Signal:
        """
        The clock signal of the gate.

        Returns:
            Signal: The clock signal of the gate.
        """
        return self.clk_port.signal

    @property
    def clk_redge(self) -> bool:
        """
        Whether the clock signal has a rising edge.

        Returns:
            bool: True if the clock signal has a rising edge, False otherwise.
        """
        return self._clk_redge

    @property
    def clk_fedge(self) -> bool:
        """
        Whether the clock signal has a falling edge.

        Returns:
            bool: True if the clock signal has a falling edge, False otherwise.
        """
        return self._clk_fedge

    @property
    def rst_redge(self) -> bool:
        """
        Whether the reset signal has a rising edge.

        Returns:
            bool: True if the reset signal has a rising edge, False otherwise.
        """
        return self._rst_redge

    @property
    def rst_fedge(self) -> bool:
        """
        Whether the reset signal has a falling edge.

        Returns:
            bool: True if the reset signal has a falling edge, False otherwise.
        """
        return self._rst_fedge

    @property
    def verilog_template(self) -> str:
        return 'always @({clk} or {rst}) begin\n\t{behavior}\nend'
