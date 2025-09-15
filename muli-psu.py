"""
This script can configure fabric-v2 or fabric v3 pdu config with 2,4,6 psu per server. To run this script you need hostname.txt and port.txt 
file in same location. remember to give an empty line between switch and servers in hostname and in port.txt an empty line between switch port and server ports.
"""

#!/usr/bin/env python3

import ipaddress

def calculate_gateway(ip_str, subnet_str):
    network = ipaddress.IPv4Network("{}/{}".format(ip_str, subnet_str), strict=False)
    return str(list(network.hosts())[0])  # first usable host as gateway


def load_file(filename):
    with open(filename, "r") as f:
        return [line.strip() for line in f if line.strip() or line == "\n"]

def generate_config(pdu_name, ip, dc_abr, dc_id, hostnames, ports, fabric_ver, subnet, psu_count):

    # Calculate gateway based on IP + subnet
    gateway = calculate_gateway(ip, subnet)

    print("\n===== CONFIG FOR {} ({}) =====".format(pdu_name, ip))
    print("""set dhcp disabled
set ipv4 address {}
set gateway {}
set subnet {}
set location {}
set telnet disabled
set ssl enabled

set banner

**IMPORTANT** This is a Pro Series PDU that has 1 master and 1 slave, Outlet groups are set up on here so you can just type reboot hostname to reboot a server or piece of gear.

create user admin

set user access admin admin

set snmp v2 enabled
y
set snmp v2 getcomm public
set snmp sysname {}
set snmp syslocation {}
""".format(ip, gateway, subnet, dc_abr, pdu_name, pdu_name, pdu_name))

    # Only include DNS if fabric v2
    if fabric_ver == "v2":
        print("set dns1 10.{}.1.12".format(dc_id))
        print("set dns2 10.{}.1.13".format(dc_id))

    # Split switch section and server section
    if "" in ports:
        split_index = ports.index("")
        switch_ports = [p for p in ports[:split_index] if p]
        server_ports = [p for p in ports[split_index + 1:] if p]
        switch_hosts = []
        server_hosts = []
        empty_index = hostnames.index("") if "" in hostnames else len(hostnames)
        switch_hosts = [h for h in hostnames[:empty_index] if h]
        server_hosts = [h for h in hostnames[empty_index + 1:] if h]
    else:
        switch_ports, server_ports = ports, []
        switch_hosts, server_hosts = hostnames, []

    commands = []
    delay = 0
    count = 0

    # --- Switches (2 PSU each) ---
    for host, port in zip(switch_hosts, switch_ports):
        commands.append("create group {}".format(host))
        commands.append("set outlet name AA{} {}_PSU1".format(port, host))
        commands.append("set outlet name BA{} {}_PSU2".format(port, host))
        commands.append("add outlettogroup AA{} {}".format(port, host))
        commands.append("add outlettogroup BA{} {}".format(port, host))

        # assign delays
        commands.append("set outlet ondelay AA{} {}".format(port, delay))
        commands.append("set outlet extondelay AA{} {}".format(port, delay))
        commands.append("set outlet ondelay BA{} {}".format(port, delay))
        commands.append("set outlet extondelay BA{} {}".format(port, delay))

        count += 2
        if count > 4 and count % 2 == 0:
            delay += 5

    # --- Servers ---
    for host in server_hosts:
        commands.append("create group {}".format(host))

        if psu_count == 2:
            # Take 1 port, assign PSU1 to A, PSU2 to B
            port = server_ports.pop(0)
            commands.append("set outlet name AA{} {}_PSU1".format(port, host))
            commands.append("set outlet name BA{} {}_PSU2".format(port, host))
            commands.append("add outlettogroup AA{} {}".format(port, host))
            commands.append("add outlettogroup BA{} {}".format(port, host))
            commands.append("set outlet ondelay AA{} {}".format(port, delay))
            commands.append("set outlet extondelay AA{} {}".format(port, delay))
            commands.append("set outlet ondelay BA{} {}".format(port, delay))
            commands.append("set outlet extondelay BA{} {}".format(port, delay))
            count += 2

        elif psu_count == 4:
            # Take 2 ports, map (PSU1,PSU3) -> A, (PSU2,PSU4) -> B
            psu_ports = server_ports[:2]
            server_ports = server_ports[2:]
            port_num = 1
            for port in psu_ports:
                commands.append("set outlet name AA{} {}_PSU{}".format(port, host, port_num))
                commands.append("add outlettogroup AA{} {}".format(port, host))
                commands.append("set outlet ondelay AA{} {}".format(port, delay))
                commands.append("set outlet extondelay AA{} {}".format(port, delay))
                port_num += 2

            port_num = 2
            for port in psu_ports:
                commands.append("set outlet name BA{} {}_PSU{}".format(port, host, port_num))
                commands.append("add outlettogroup BA{} {}".format(port, host))
                commands.append("set outlet ondelay BA{} {}".format(port, delay))
                commands.append("set outlet extondelay BA{} {}".format(port, delay))
                port_num += 2
            count += 4

        elif psu_count == 6:
            # Existing logic (3 port pairs, A/B)
            psu_ports = server_ports[:3]
            server_ports = server_ports[3:]
            psu_num = 1
            for port in psu_ports:
                # PDU-A odd PSU
                commands.append("set outlet name AA{} {}_PSU{}".format(port, host, psu_num))
                commands.append("add outlettogroup AA{} {}".format(port, host))
                commands.append("set outlet ondelay AA{} {}".format(port, delay))
                commands.append("set outlet extondelay AA{} {}".format(port, delay))
                psu_num += 1

                # PDU-B even PSU
                commands.append("set outlet name BA{} {}_PSU{}".format(port, host, psu_num))
                commands.append("add outlettogroup BA{} {}".format(port, host))
                commands.append("set outlet ondelay BA{} {}".format(port, delay))
                commands.append("set outlet extondelay BA{} {}".format(port, delay))
                psu_num += 1
            count += 6

        if count > 4 and count % 2 == 0:
            delay += 5

    # Print all commands
    print("\n".join(commands))

    print("""
set syslog host1 infra-{}.linode.com
remove user admn
restart
""".format(dc_abr))


if __name__ == "__main__":
    pdu_name = input("Enter PDU name: ").strip()
    ip = input("Enter PDU IP: ").strip()
    dc_abr = input("Enter DC abbreviation: ").strip()
    dc_id = input("Enter DC ID: ").strip()

    # Ask fabric version
    while True:
        fabric_ver = input("Enter fabric version (v2/v3): ").strip().lower()
        if fabric_ver == "v2":
            subnet = "255.255.0.0"
            break
        elif fabric_ver == "v3":
            subnet = "255.255.255.224"
            break
        else:
            print("❌ Invalid choice. Please choose fabric-version as either 'v2' or 'v3'.")

    print("\n✅ Selected Fabric Version: {} | Subnet: {}\n".format(fabric_ver.upper(), subnet))

    # Ask PSU count
    while True:
        try:
            psu_count = int(input("Enter number of PSUs per server (2/4/6): ").strip())
            if psu_count in (2, 4, 6):
                break
            else:
                print("❌ Please enter either 2, 4, or 6.")
        except ValueError:
            print("❌ Invalid input. Please enter a number (2, 4, or 6).")

    hostnames = load_file("hostname.txt")
    ports = load_file("port.txt")

    generate_config(pdu_name, ip, dc_abr, dc_id, hostnames, ports, fabric_ver, subnet, psu_count)
