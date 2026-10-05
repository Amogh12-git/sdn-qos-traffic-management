#!/usr/bin/env python3
"""UDP traffic sender. Each packet carries a sequence number and timestamp."""
import socket
import struct
import time
import argparse

HDR = struct.Struct('!BIQ')   # type(1B), seq(4B), send time in ns (8B)
DATA, FIN = 0, 1

p = argparse.ArgumentParser()
p.add_argument('--dst', required=True, help='receiver IP')
p.add_argument('--port', type=int, required=True)
p.add_argument('--rate', type=float, default=100, help='packets per second')
p.add_argument('--size', type=int, default=200, help='packet size in bytes')
p.add_argument('--duration', type=float, default=10, help='seconds')
p.add_argument('--label', default='X', help='traffic class name')
args = p.parse_args()

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

# Send FIN several times so the receiver learns the total even if some are lost
for _ in range(10):
    sock.sendto(HDR.pack(FIN, seq, time.time_ns()), addr)
    time.sleep(0.05)

mbps = seq * args.size * 8 / args.duration / 1e6
print('[sender %s] sent %d packets (~%.2f Mbps offered)' % (args.label, seq, mbps))
