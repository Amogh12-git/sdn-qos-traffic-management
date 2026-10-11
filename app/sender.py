#!/usr/bin/env python3
"""UDP traffic sender. Registers its flow with the SDN controller (optional)."""
import socket
import struct
import time
import argparse
import json

HDR = struct.Struct('!BIQ')   # type(1B), seq(4B), send time ns (8B)
DATA, FIN = 0, 1

p = argparse.ArgumentParser()
p.add_argument('--dst', required=True)
p.add_argument('--port', type=int, required=True)
p.add_argument('--rate', type=float, default=100, help='packets per second')
p.add_argument('--size', type=int, default=200, help='packet size in bytes')
p.add_argument('--duration', type=float, default=10)
p.add_argument('--label', default='X', help='traffic class: A, B, C ...')
p.add_argument('--start-delay', type=float, default=0)
p.add_argument('--no-register', action='store_true', help='do not tell the controller')
p.add_argument('--ctrl-sock', default='/tmp/qos_ctrl.sock')
args = p.parse_args()


def notify(msg):
    if args.no_register:
        return
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s.sendto(json.dumps(msg).encode(), args.ctrl_sock)
        s.close()
    except OSError:
        pass   # controller not running: carry on unregistered


time.sleep(args.start_delay)
rate_mbps = args.rate * args.size * 8 / 1e6
notify({'event': 'start', 'port': args.port, 'cls': args.label, 'rate_mbps': rate_mbps})
if not args.no_register:
    time.sleep(0.3)   # let the controller install rules before data flows

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
addr = (args.dst, args.port)
padding = b'x' * max(0, args.size - HDR.size)
interval = 1.0 / args.rate

seq = 0
start = time.perf_counter()
next_send = start
while time.perf_counter() - start < args.duration:
    sock.sendto(HDR.pack(DATA, seq, time.time_ns()) + padding, addr)
    seq += 1
    next_send += interval
    delay = next_send - time.perf_counter()
    if delay > 0:
        time.sleep(delay)

for _ in range(10):
    sock.sendto(HDR.pack(FIN, seq, time.time_ns()), addr)
    time.sleep(0.05)

notify({'event': 'stop', 'port': args.port})
print('[sender %s] sent %d packets (~%.2f Mbps offered)' % (args.label, seq, rate_mbps))
