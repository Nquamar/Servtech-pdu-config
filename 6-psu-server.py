#!/usr/bin/env python3

def load_file(filename):
    with open(filename, "r") as f:
        return [line.strip() for line in f if line.strip() or line == "\n"]

def generate_config(pdu_name, ip, dc_abr, dc_id, hostnames, ports):
    print("\n===== CONFIG FOR {} ({}) =====".format(pdu_name, ip))
    print("""set dhcp disabled
set ipv4 address {}
set gateway 10.{}.0.1
set dns1 10.{}.1.12
set dns2 10.{}.1.13
set subnet 255.255.0.0
set location {}
set telnet disabled
set ssl enabled
set snmp v2 enabled
set snmp v2 getcomm public
set snmp sysname {}
set snmp syslocation {}
""".format(ip, dc_id, dc_id, dc_id, pdu_name, pdu_name, pdu_name))

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

    # --- Servers (6 PSU each, 3 ports) ---
    for host in server_hosts:
        commands.append("create group {}".format(host))

        # Take next 3 ports from server_ports
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

            count += 2
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

    hostnames = load_file("hostname.txt")
    ports = load_file("port.txt")

    generate_config(pdu_name, ip, dc_abr, dc_id, hostnames, ports)


