from tqdm import tqdm

from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.utils.log import LOG


def opt_driverless(module: Module) -> bool:
    """
    Recursively removes driverless wires and instances from a module.

    This function iteratively checks for and removes driverless wires and instances
    until no more can be removed. It returns True if any removals occurred,
    False otherwise.

    Args:
        module (Module): The module from the netlist to be optimized.

    Returns:
        any_removed (bool): True if any optimizations were performed, False otherwise.
    """
    any_removed = False
    while True:
        any_wires_removed = opt_driverless_wires(module)
        any_insts_removed = opt_driverless_instances(module)
        any_removed |= any_wires_removed or any_insts_removed
        if not any_wires_removed and not any_insts_removed:
            break
    return any_removed


def opt_driverless_wires(module: Module) -> bool:
    marked_for_deletion = set()
    for wname, w in tqdm(module.wires.items()):
        for ws in w.segments.values():
            if ws.has_no_driver():
                LOG.debug(f'WireSegment {ws.path} has no driver!')
                marked_for_deletion.add((wname, ws.index))
    if not marked_for_deletion:
        LOG.info('No more wires to delete!')
        return False
    LOG.info(f'Removing {len(marked_for_deletion)} driverless wires...')
    for wname, idx in marked_for_deletion:
        if wname in module.wires:
            module.wires[wname].remove_wire_segment(idx)
            if not module.wires[wname].segments:  # If there are no segments anymore, remove wire
                module.remove_wire(wname)
    return True


def opt_driverless_instances(module: Module) -> bool:
    marked_for_deletion = set()
    for inst_name, inst in tqdm(module.instances.items()):
        no_driver = True  # Will switch to false if at least 1 input port has driver
        for p in inst.input_ports:
            no_driver &= all(p.raw == 'X' or p.raw == '0' or p.raw == '1' for p in p.connected_wire_segments)
        if no_driver:
            LOG.debug(f'Instance {inst_name} has no drivers!')
            marked_for_deletion.add(inst_name)
    if not marked_for_deletion:
        LOG.info('No more instances to delete!')
        return False
    LOG.info(f'Removing {len(marked_for_deletion)} driverless instances...')
    for iname in marked_for_deletion:
        module.remove_instance(iname)
    return True
