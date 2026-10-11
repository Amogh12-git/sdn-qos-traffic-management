#!/usr/bin/env python3
"""Runs the experiments. From the project root:
  sudo python3 experiments/run_experiments.py quick   (about 2 min: heavy load, baseline vs adaptive)
  sudo python3 experiments/run_experiments.py         (full set, about 8 min)
"""
import csv
import json
import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'topology'))
from qos_topo import start_net, cleanup_qos          # noqa: E402
from mininet.log import setLogLevel                  # noqa: E402

APP = os.path.join(ROOT, 'app')
RESULTS = os.path.join(ROOT, 'results', 'results.csv')
WINDOWS = os.path.join(ROOT, 'results', 'challenge_window.json')
EVENTS = os.path.join(ROOT, 'results', 'controller_events.csv')
POLICY = os.path.join(ROOT, 'controller', 'policy.json')
HEADER = ['run', 'class', 'sent', 'received', 'loss_pct', 'throughput_mbps',
          'avg_latency_ms', 'max_latency_ms', 'jitter_ms']

MODES = {'baseline': 'off', 'static': 'always', 'adaptive': 'adaptive'}
LOADS = {'light': 3, 'medium': 9, 'heavy': 20}      # offered Mbps of class C
DURATION = 20


def flow(label, src, dst, ip, port, size, mbps, duration=DURATION, delay=0, register=True):
    return dict(label=label, src=src, dst=dst, ip=ip, port=port, size=size, mbps=mbps,
                duration=duration, delay=delay, register=register)


def base_flows(duration=DURATION):
    return [flow('A', 'h1', 'h4', '10.0.0.4', 5001, 200, 0.16, duration),    # voice-like
            flow('B', 'h2', 'h5', '10.0.0.5', 5002, 1000, 2.0, duration)]    # video-like


def set_policy(mode):
    pol = {'mode': mode, 'capacity_mbps': 10.0, 'high_pct': 80, 'low_pct': 50,
           'queues': {'A': 1, 'B': 2, 'C': 3}}
    with open(POLICY + '.tmp', 'w') as f:
        json.dump(pol, f, indent=1)
    os.chmod(POLICY + '.tmp', 0o666)
    os.replace(POLICY + '.tmp', POLICY)
    time.sleep(2.5)          # the controller re-reads the policy every second


def run_experiment(net, run, mode, flows):
    print('\n=== %s (mode=%s) ===' % (run, mode))
    set_policy(MODES.get(mode, mode))
    recvs, sends = [], []
    for f in flows:
        cmd = ['python3', os.path.join(APP, 'receiver.py'), '--port', str(f['port']),
               '--label', f['label'], '--run', run, '--out', RESULTS,
               '--idle', str(f['delay'] + 10)]
        recvs.append(net.get(f['dst']).popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT))
    time.sleep(1)
    t0 = time.time()
    for f in flows:
        pps = f['mbps'] * 1e6 / 8 / f['size']
        cmd = ['python3', os.path.join(APP, 'sender.py'), '--dst', f['ip'],
               '--port', str(f['port']), '--rate', '%.2f' % pps, '--size', str(f['size']),
               '--duration', str(f['duration']), '--label', f['label'],
               '--start-delay', str(f['delay'])]
        if not f['register']:
            cmd.append('--no-register')
        sends.append(net.get(f['src']).popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT))
    for p in sends + recvs:
        print(p.communicate()[0].decode().strip())
    time.sleep(5)            # let the controller remove its rules again
    return t0


def reaction_time(rogue_start):
    try:
        with open(EVENTS) as f:
            ons = [float(r[0]) for r in csv.reader(f) if r[1] == 'QOS_ON' and float(r[0]) >= rogue_start]
        return round(min(ons) - rogue_start, 2) if ons else None
    except OSError:
        return None


def print_summary():
    print('\n%-22s %-5s %8s %10s %12s %10s' %
          ('run', 'class', 'loss %', 'Mbps', 'avg lat ms', 'jitter ms'))
    with open(RESULTS) as f:
        for r in csv.DictReader(f):
            print('%-22s %-5s %8s %10s %12s %10s' %
                  (r['run'], r['class'], r['loss_pct'], r['throughput_mbps'],
                   r['avg_latency_ms'], r['jitter_ms']))


def main():
    quick = len(sys.argv) > 1 and sys.argv[1] == 'quick'
    loads = {'heavy': LOADS['heavy']} if quick else LOADS
    modes = ['baseline', 'adaptive'] if quick else list(MODES)

    os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
    if os.path.exists(RESULTS):
        os.rename(RESULTS, RESULTS + '.%d.bak' % int(time.time()))
    with open(RESULTS, 'w', newline='') as f:
        csv.writer(f).writerow(HEADER)
    os.chmod(RESULTS, 0o666)

    net = start_net()
    net.pingAll()            # teach the switches where everyone is
    time.sleep(1)
    windows = {}
    try:
        # Part 1: load levels x modes
        for load, c_mbps in loads.items():
            for mode in modes:
                flows = base_flows() + [flow('C', 'h3', 'h6', '10.0.0.6', 5003, 1400, c_mbps)]
                run_experiment(net, '%s_%s' % (mode, load), mode, flows)

        # Part 2: challenge - an unregistered 15 Mbps flood appears at t = 8 s
        if not quick:
            for mode in ('baseline', 'adaptive'):
                flows = base_flows(30) + [flow('R', 'h3', 'h6', '10.0.0.6', 5004, 1400, 15,
                                               duration=15, delay=8, register=False)]
                t0 = run_experiment(net, 'challenge_%s' % mode, mode, flows)
                windows[mode] = {'t0': t0, 'rogue_start': t0 + 8, 'rogue_end': t0 + 23,
                                 'end': t0 + 30}
                if mode == 'adaptive':
                    windows[mode]['reaction_s'] = reaction_time(t0 + 8)
                    print('Controller reaction time to the flood: %s s' % windows[mode]['reaction_s'])
            with open(WINDOWS, 'w') as f:
                json.dump(windows, f)
    finally:
        set_policy('adaptive')
        net.stop()
        cleanup_qos()
    print_summary()
    print('\nDone. Results are in results/results.csv')


if __name__ == '__main__':
    setLogLevel('warning')
    main()
