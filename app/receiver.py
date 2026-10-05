#!/usr/bin/env python3
"""UDP receiver. Measures throughput, loss, latency and jitter."""
import socket
import struct
import time
import argparse
import csv
import os

HDR = struct.Struct('!BIQ')
DATA, FIN = 0, 1

p = argparse.ArgumentParser()
p.add_argument('--port', type=int, required=True)
p.add_argument('--label', default='X')
p.add_argument('--idle', type=float, default=15, help='give up after this many idle seconds')
p.add_argument('--out', default='results/results.csv')
p.add_argument('--run', default='run', help='experiment name, e.g. baseline_heavy')
args = p.parse_args()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', args.port))
sock.settimeout(args.idle)

recv = nbytes = 0
total_sent = None
latencies = []
jitter = 0.0
prev_transit = None
t_first = t_last = None

while True:
    try:
        data, _ = sock.recvfrom(65535)
    except socket.timeout:
        break
    now_ns = time.time_ns()
    mtype, seq, sent_ns = HDR.unpack(data[:HDR.size])
    if mtype == FIN:
        total_sent = seq
        break
    now = time.perf_counter()
    if t_first is None:
        t_first = now
    t_last = now
    recv += 1
    nbytes += len(data)
    transit = (now_ns - sent_ns) / 1e6          # one-way delay in ms
    latencies.append(transit)
    if prev_transit is not None:               # RFC 3550 jitter
        jitter += (abs(transit - prev_transit) - jitter) / 16
    prev_transit = transit

if recv == 0:
    print('[receiver %s] nothing received' % args.label)
    raise SystemExit(1)

total_sent = total_sent if total_sent is not None else recv
loss_pct = 100.0 * (total_sent - recv) / total_sent if total_sent else 0.0
duration = max(t_last - t_first, 1e-9)
thr = nbytes * 8 / duration / 1e6
avg_lat = sum(latencies) / len(latencies)
max_lat = max(latencies)

print('[receiver %s] recv=%d/%d loss=%.2f%% thr=%.2f Mbps '
      'lat(avg/max)=%.2f/%.2f ms jitter=%.2f ms'
      % (args.label, recv, total_sent, loss_pct, thr, avg_lat, max_lat, jitter))

os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
new_file = not os.path.exists(args.out)
with open(args.out, 'a', newline='') as f:
    w = csv.writer(f)
    if new_file:
        w.writerow(['run', 'class', 'sent', 'received', 'loss_pct',
                    'throughput_mbps', 'avg_latency_ms', 'max_latency_ms', 'jitter_ms'])
    w.writerow([args.run, args.label, total_sent, recv, round(loss_pct, 2),
                round(thr, 3), round(avg_lat, 3), round(max_lat, 3), round(jitter, 3)])
