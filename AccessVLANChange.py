#
# Title:	AccessVLANChange.py
# Author:	Niels Friis-Hansen
# Version:	1.0
#
# Revisions:	1.0	First version
#               1.1	Added support for changing voice VLAN on a port
#
# Descripion:
# Python script changing access VLAN in Cisco IOS switches
#
# The script logs into each device for which login credentials are provided in the "devices.txt" file,
# lists the running config, parses it looking for switchports that needs to have their vlan changed.
# The script changes the access VLAN according to the settings in the file "vlan.txt"
#
# Only switchports in access-mode are changed and only interfaces that are not part of a port-channel are changed
# Port-channel interfaces are changed if in access-mode.
#
# Arguments: The script must be run with the argument "force" if the commands are to be provisioned to the devices
#            If the "force" argument is omitted, the script only simulates the changes.

import sys
import csv
import re
from netmiko import ConnectHandler
from datetime import datetime
from time import strftime
from ciscoconfparse import CiscoConfParse

# Define the names of input files
CSVDATA_FILENAME = 'devices.txt'
VLAN_FILENAME    = 'vlan.txt'

# Default mode
MODE="SIMULATE"

# Read first command line argument
if len(sys.argv) == 2:
    if sys.argv[1] == "force":
        MODE = "FORCE"

# Record start-time
start_time = datetime.now()
start_time_text = start_time.strftime('%Y%m%d-%H%M%S')


# Define functions
def get_data(row):
	# Reads parameters from the CSV input-file
	data_fields = {
		field_name: field_value
		for field_name, field_value in row.items()
	}

# Main loop, log into each device for which credentials are included in the input CSV-file
for row in csv.DictReader(open(CSVDATA_FILENAME)):
    get_data(row)

	# Create a device object for input to netmikos ConnectHandler function
    device = {
        'device_type': row['DEVICETYPE'],
        'ip':   row['IP'],
        'username': row['USERNAME'],
        'password': row['PASSWORD'],
        'verbose': False,
    }

    # Connect to the device
    net_connect = ConnectHandler(**device)
	# ... and fetch the current running configuration into output
    output = net_connect.send_command("show run")

    # Read through the config, convert to list and look for hostname, if found, store the hostname
    hostname = ""
    config = []
    for line in output.split('\n'):
        config.append(line)
        matchObj = re.match( r'hostname (.+)', line)
        if matchObj:
            hostname = matchObj.group(1)
            print "Checking device", matchObj.group(1), "with IP address", device['ip'], ":\n"

    # Parse the config
    ccp = CiscoConfParse(config)

    configset = []
    for row in csv.DictReader(open(VLAN_FILENAME)):
        get_data(row)

        oldvlan = row['OLDVLAN']
        newvlan = row['NEWVLAN']

        # Find all interfaces that are potentially access ports in the old VLAN
        interfaces = ccp.find_parents_w_child('^interface ','^ switchport access vlan ' + oldvlan + '$')

        # Check that the interface actually is an access-port (that the "switchport access vlan" command is not "lingering") and
        # that it is not a port-channel member (port-channels should be changed only at the port-channel interface)
        changelist = []
        for interface in interfaces:
            if  ccp.find_children_w_parents(interface,'^ switchport mode access') and \
            not ccp.find_children_w_parents(interface,'^ channel-group '):
                changelist.append(interface)
                print "  ", interface + ": Changing VLAN " + oldvlan + "->" + newvlan

            if not ccp.find_children_w_parents(interface,'^ switchport mode access') and \
               not ccp.find_children_w_parents(interface,'^ switchport mode trunk'):
                print "   WARNING: Interface", interface, " is in mode dymamic auto (VLAN not changed)"

        # Construct the commands required to change the access VLAN for each interface
        for interface in changelist:
            configset.append(interface)
            configset.append(" switchport access vlan " + newvlan)

        # Find all interfaces that uses old VLAN as voice VLAN
        interfaces = ccp.find_parents_w_child('^interface ','^ switchport voice vlan ' + oldvlan + '$')

        # Check that the interface actually is an access-port (that the "switchport access vlan" command is not "lingering") and
        # that it is not a port-channel member (port-channels should be changed only at the port-channel interface)
        changelist = []
        for interface in interfaces:
            changelist.append(interface)
            print "  ", interface + ": Changing voice VLAN " + oldvlan + "->" + newvlan

        # Construct the commands required to change the access VLAN for each interface
        for interface in changelist:
            configset.append(interface)
            configset.append(" switchport voice vlan " + newvlan)

    if len(configset) > 0:
        print "\n   List of configuration changes, mode=", MODE
    
        for line in configset:
            print "  ", line
        print ""

        if MODE == "FORCE":
            net_connect.send_config_set(configset)
            net_connect.send_command("wr mem")
    else:
        print "No changes for this device..."

    net_connect.disconnect()

end_time = datetime.now()

total_time = end_time - start_time
print "\n\nTotal run time: ", total_time
