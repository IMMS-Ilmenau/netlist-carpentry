from tqdm import tqdm

from netlist_carpentry import LOG
from netlist_carpentry.core.netlist_elements.module import Module


def opt_loadless(module: Module) -> bool:
    """
    Recursively removes unused wires and instances from a module.

    This function iteratively checks for and removes unused wires and instances
    until no more can be removed. It returns True if any removals occurred,
    False otherwise.

    Args:
        module (Module): The module from the netlist to be optimized.

    Returns:
        any_removed (bool): True if any optimizations were performed, False otherwise.
    """
    any_removed = False
    while True:
        any_wires_removed = opt_loadless_wires(module)
        any_insts_removed = opt_loadless_instances(module)
        any_removed |= any_wires_removed or any_insts_removed
        if not any_wires_removed and not any_insts_removed:
            return any_removed


def opt_loadless_wires(module: Module) -> bool:
    """Identifies and removes wires with no associated loads from a module.

    Iterates through the module's wires, identifies those without loads,
    and removes them.

    Args:
        module: The module from the netlist to be optimized.

    Returns:
        True if any wires were removed, False otherwise.
    """
    marked_for_deletion = set()
    for wname, w in tqdm(module.wires.items()):
        if w.has_no_loads():
            LOG.debug(f'Wire {w.name} has no loads!')
            marked_for_deletion.add(wname)
    if not marked_for_deletion:
        LOG.info('No more wires to delete!')
        return False
    LOG.info(f'Removing {len(marked_for_deletion)} loadless wires...')
    for wname in marked_for_deletion:
        module.remove_wire(wname)
    return True


def opt_loadless_instances(module: Module) -> bool:
    """Identifies and removes instances with no associated loads.

    Iterates through the module's instances, identifies those without loads,
    and removes them. An instance is considered to have no loads if all
    output ports are unconnected.

    Args:
        module: The module from the netlist to be optimized.

    Returns:
        True if any instances were removed, False otherwise.
    """
    marked_for_deletion = set()
    for inst_name, inst in tqdm(module.instances.items()):
        no_load = True  # Will switch to false if at least 1 output port has load
        for p in inst.output_ports:
            no_load &= all(p.raw.lower() == 'x' or p.raw == '' for p in p.connected_wire_segments)
        if no_load:
            LOG.debug(f'Instance {inst_name} has no loads!')
            marked_for_deletion.add(inst_name)
    if not marked_for_deletion:
        LOG.info('No more instances to delete!')
        return False
    LOG.info(f'Removing {len(marked_for_deletion)} loaadleless instances...')
    for iname in marked_for_deletion:
        module.remove_instance(iname)
    return True
