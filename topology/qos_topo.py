#!/usr/bin/env python3
"""Bottleneck topology for the QoS project.

 h1 (Class A) \                         / h4 (receiver A)
 h2 (Class B)  -- s1 ===bottleneck=== s2 -- h5 (receiver B)
 h3 (Class C) /                         \ h6 (receiver C)
"""
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel


def build():
    net = Mininet(controller=None, switch=OVSSwitch,
                  link=TCLink, autoSetMacs=True)

    net.addController('c0', controller=RemoteController,
                      ip='127.0.0.1', port=6653)

    s1 = net.addSwitch('s1', protocols='OpenFlow13')
    s2 = net.addSwitch('s2', protocols='OpenFlow13')

    # Senders then receivers, so IPs are h1=10.0.0.1 ... h6=10.0.0.6
    senders = [net.addHost('h%d' % i) for i in (1, 2, 3)]
    receivers = [net.addHost('h%d' % i) for i in (4, 5, 6)]

    for h in senders:
        net.addLink(h, s1, bw=100)      # fast access links
    for h in receivers:
        net.addLink(h, s2, bw=100)

    # s1-s2 is the bottleneck. We deliberately do NOT set bw here;
    # the 10 Mbps limit is applied later with Open vSwitch queues.
    net.addLink(s1, s2)

    net.start()
    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    build()
