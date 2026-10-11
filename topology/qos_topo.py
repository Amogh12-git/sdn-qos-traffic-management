#!/usr/bin/env python3
"""Dumbbell topology; s1-eth4 is a 10 Mbps bottleneck shaped by OVS queues."""
import subprocess
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

BOTTLENECK_IFACE = 's1-eth4'
BOTTLENECK_BPS = 10000000
QUEUE_PACKETS = 40


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def tc(*args):
    res = sh('tc', *args)
    if res.returncode != 0:
        info('*** tc %s failed: %s\n' % (' '.join(args), res.stderr.strip()))


def build_net():
    net = Mininet(controller=None, switch=OVSSwitch, link=TCLink, autoSetMacs=True)
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)
    s1 = net.addSwitch('s1', protocols='OpenFlow13')
    s2 = net.addSwitch('s2', protocols='OpenFlow13')
    hosts = [net.addHost('h%d' % i) for i in range(1, 7)]   # h1..h6 = 10.0.0.1..6
    for i in range(3):
        net.addLink(hosts[i], s1, port2=i + 1)       # senders   -> s1 ports 1-3
        net.addLink(hosts[i + 3], s2, port2=i + 1)   # receivers -> s2 ports 1-3
    net.addLink(s1, s2, port1=4, port2=4)            # the bottleneck
    return net


def setup_bottleneck():
    """10 Mbps HTB shaping with 4 queues on s1-eth4 (lower priority number = served first)."""
    r = BOTTLENECK_BPS

    def queue(name, min_rate, prio):
        return ['--id=@%s' % name, 'create', 'queue',
                'other-config:min-rate=%d' % min_rate,
                'other-config:max-rate=%d' % r,
                'other-config:priority=%d' % prio]

    cmd = ['ovs-vsctl', 'set', 'port', BOTTLENECK_IFACE, 'qos=@qos', '--',
           '--id=@qos', 'create', 'qos', 'type=linux-htb',
           'other-config:max-rate=%d' % r,
           'queues:0=@q0', 'queues:1=@q1', 'queues:2=@q2', 'queues:3=@q3', '--']
    cmd += queue('q0', 500000, 4) + ['--'] + queue('q1', 2000000, 1) + ['--'] \
        + queue('q2', 3000000, 2) + ['--'] + queue('q3', 1000000, 3)
    res = sh(*cmd)
    if res.returncode != 0:
        info('*** ovs-vsctl failed: %s\n' % res.stderr)
        return

    # Tune the classes OVS created (queue N = class 1:(N+1)):
    # 1) a larger burst, so the shaper really reaches 10 Mbps inside a VM
    # 2) a short FIFO per queue, so excess packets are DROPPED when it is full
    dev = BOTTLENECK_IFACE
    tc('class', 'change', 'dev', dev, 'parent', '1:', 'classid', '1:fffe',
       'htb', 'rate', '10Mbit', 'ceil', '10Mbit', 'burst', '15k', 'cburst', '15k')
    classes = (('1:1', '500Kbit', 4), ('1:2', '2Mbit', 1),
               ('1:3', '3Mbit', 2), ('1:4', '1Mbit', 3))
    for i, (cid, rate, prio) in enumerate(classes):
        tc('class', 'change', 'dev', dev, 'parent', '1:fffe', 'classid', cid,
           'htb', 'rate', rate, 'ceil', '10Mbit', 'prio', str(prio),
           'burst', '15k', 'cburst', '15k')
        tc('qdisc', 'replace', 'dev', dev, 'parent', cid, 'handle', '%x:' % (0x10 + i),
           'pfifo', 'limit', str(QUEUE_PACKETS))
    info('*** Bottleneck %s: 10 Mbps, queues 0-3 ready\n' % BOTTLENECK_IFACE)


def cleanup_qos():
    sh('ovs-vsctl', '--all', 'destroy', 'qos')
    sh('ovs-vsctl', '--all', 'destroy', 'queue')


def start_net():
    net = build_net()
    net.start()
    if not net.waitConnected(timeout=15):
        info('*** WARNING: switches did not connect. Is ryu-manager running?\n')
    setup_bottleneck()
    return net


if __name__ == '__main__':
    setLogLevel('info')
    net = start_net()
    CLI(net)
    net.stop()
    cleanup_qos()
