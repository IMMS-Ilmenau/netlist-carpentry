"""A very basic scan chain insertion algorithm implementation."""

from typing import List

from netlist_carpentry import LOG, Direction, Instance, Module
from netlist_carpentry.utils.gate_lib import DFF, ScanDFF


def create_scan_ports(m: Module, scan_enable: str = 'SE', scan_in: str = 'SI', scan_out: str = 'SO') -> None:
    """Creates the ports required for implementing scan chains in the given module.

    These ports are `Scan-Enable` (to enable the scan shift process), `Scan-In`,
    (to shift scan values into the chain) and `Scan-Out` (to shift scan values out of the chain).
    After adding the ports to the given module, all module instances are updated accordingly,
    so that they all also have these three ports, that are unconnected initially and must be
    connected during the scan-chain creation process.

    Args:
        m (Module): The module, which should receive the scan ports.
        scan_enable (str, optional): The desired name of the Scan-Enable port. Defaults to 'SE'.
        scan_in (str, optional): The desired name of the Scan-In port. Defaults to 'SI'.
        scan_out (str, optional): The desired name of the Scan-Out port. Defaults to 'SO'.
    """
    m.create_port(scan_enable, Direction.IN)
    m.create_port(scan_in, Direction.IN)
    m.create_port(scan_out, Direction.OUT)
    m.update_module_instances()  # All instances of module m are now updated to receive the 3 ports as well
    LOG.debug(f'Created scan ports in module {m.name}!')


def replace_ff_with_scan_ff(m: Module) -> List[ScanDFF]:
    """Replaces all Flip-Flops inside the given module with their Scan-Variant.

    Each normal DFF becomes a Scan-DFF (with the additional ports `SE`, `SI` and `SO`,
    each 1-bit wide), an ADFF becomes a Scan-ADFF and so on.

    Also, all n-bit wide Flip-Flops are split into n 1-bit Flip-Flops, before the replacement.
    This is due to the Shifting mechanism, which can always only shift a single bit in or out
    during a single clock cycle.

    Args:
        m (Module): The module, in which all Flip-Flops should be replaced with their shift variants.

    Returns:
        List[ScanDFF]: A list containing all newly implemented Scan-Flip-Flops.
    """
    m.split_all('dff')
    dffs: List[DFF] = m.get_instances(type='dff', fuzzy=True)  # type: ignore[assignment]
    for dff in dffs:
        m.replace(dff, dff.get_scanff(), silent=True)
    scan_ffs: List[ScanDFF] = m.get_instances(type='dff', fuzzy=True)  # type: ignore[assignment]
    return scan_ffs  # These are the scan flip-flops just replaced


def _implement_scanff_in_submodules(m: Module) -> List[Instance]:
    sub_insts_with_dff = []
    for sub in m.submodules:
        # Check if there are flip-flops anywhere in this submodule
        sub_module: Module = sub.module_definition  # type: ignore[assignment]
        dffs_in_submodule = sub_module.get_instances(type='dff', fuzzy=True, recursive=True)
        if len(dffs_in_submodule) > 0:
            # This is the main method, which is now called with the submodule definition
            # The method itself is defined later for simplicity
            implement_scan_chain(sub_module)
            sub_insts_with_dff.append(sub)
    return sub_insts_with_dff


def connect_all_scan_elements(m: Module, list_of_scan_elements: List[Instance], scan_in: str, scan_out: str, scan_enable: str) -> None:
    """Connect the given instances inside the module to a chain of scan elements, and connect them to the module's scan ports.

    Args:
        m (Module): The current module.
        list_of_scan_elements (List[Instance]): A list of instances, which should be connected to a chain,
            connecting each output "SO" to the subsequent "SI" port.
        scan_in (str): The name of the "scan-in" module port.
        scan_out (str): The name of the "scan-out" module port.
        scan_enable (str): The name of the "scan-enable" module port.
    """
    LOG.info(f'Scan Chain contains {len(list_of_scan_elements)} element(s) in module {m.name}!')
    for inst in list_of_scan_elements:
        # Connect the Scan-Enable port of the module to each scan chain element
        m.connect(m.ports[scan_enable], inst.ports[scan_enable])

    if list_of_scan_elements:  # There is at least one element in the list
        m.connect(m.ports[scan_in], list_of_scan_elements[0].ports['SI'])
        m.make_chain(list_of_scan_elements, 'SI', 'SO')
        m.connect(list_of_scan_elements[-1].ports['SO'], m.ports[scan_out])


def skip_module(m: Module) -> bool:
    """Whether this module should be skipped from the scan chain insertion process.

    One case is if neither the given module nor its submodules have flip-flops.

    Another case is if the module was already modified previously (i.e. another instance
    of this module was encountered, and the module was modified back then already).
    This is tracked via module metadata.

    Args:
        m (Module): The module to check if it should be excluded from scan-chain insertion.

    Returns:
        bool: True, if this module should not receive a scan chain. False otherwise.
    """
    if not m.get_instances(type='dff', fuzzy=True, recursive=True):
        LOG.info(f'Skipping module {m.name}: No DFF in {m.name} or submodules!')
        return True  # No dff in this module or submodules
    if 'scan_chains' in m.metadata and 'insertion_in_progress' in m.metadata['scan_chains']:
        LOG.info(f'Skipping module {m.name}: Already implemented scan chain in module {m.name}...')
        return True  # Encountered an instance of this module previously
    return False


def implement_scan_chain(m: Module) -> None:
    """Main entry point for scan chain implementation.

    Takes the given module and checks if scan chain insertion is applicable.
    If applicable, replaces all flip-flops with their scan variants.
    This is also done recursively for submodules inside the given module.
    The scan ports of the flip-flops (and the submodules, if they contain flip-flops)
    are then connected into a chain via their "SI" and "SO" ports.
    Also, the scan-enable signal ("SE") is forwarded to all scan instances and submodules.

    Args:
        m (Module): The module, in which scan chains should be implemented.
    """
    if skip_module(m):
        return
    m.metadata.set('insertion_in_progress', True, category='scan_chains')
    create_scan_ports(m)
    scanff_insts = replace_ff_with_scan_ff(m)
    sub_insts = _implement_scanff_in_submodules(m)
    all_chain_elements = scanff_insts + sub_insts
    connect_all_scan_elements(m, all_chain_elements, scan_in='SI', scan_out='SO', scan_enable='SE')
