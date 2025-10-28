import os

from netlist_carpentry.api.read.gen_nl import generate_json_netlist

# Get the directory of the script
script_dir = os.path.dirname(os.path.abspath(__file__))

# List all files in the directory
files = [f for f in os.listdir(script_dir) if os.path.isfile(os.path.join(script_dir, f)) and f.endswith('.v')]

blacklist = ['netlist_generic_flattened.v', 'adderWrapper.v', 'simpleAdder.v', 'ahb_master.v']

for file in files:
    if file in blacklist:
        continue
    generate_json_netlist(f'{script_dir}/{file}', f'{script_dir}/{file[:-2]}.json')
