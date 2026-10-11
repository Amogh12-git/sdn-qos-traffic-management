#!/usr/bin/env python3
"""Makes the graphs and tables for the report from the experiment results.

Run from the project root:
    python3 experiments/plot_results.py            (reads results/)
    python3 experiments/plot_results.py results/run1   (reads a backed-up folder)

Needs matplotlib:  sudo apt install python3-matplotlib -y
Output: <results folder>/figures/*.png, summary.md, fairness.txt
"""
import csv
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt                      # noqa: E402
from matplotlib.patches import Patch                 # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RES = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, 'results')
FIG = os.path.join(RES, 'figures')
os.makedirs(FIG, exist_ok=True)

# ---- look: one light surface, quiet grid, one colour per mode (same in every figure)
SURFACE, INK, INK2, MUTED, GRID, AXIS = '#fcfcfb', '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#c3c2b7'
MODES = ['baseline', 'static', 'adaptive']
MODE_LABEL = {'baseline': 'No QoS (baseline)', 'static': 'Static QoS (always on)',
              'adaptive': 'Adaptive QoS (our controller)'}
MODE_COLOR = {'baseline': '#2a78d6', 'static': '#eb6834', 'adaptive': '#1baf7a'}
LOADS = ['light', 'medium', 'heavy']
C_LOAD = {'light': 3, 'medium': 9, 'heavy': 20}
CLASSES = ['A', 'B', 'C']
TICK = {'A': 'A voice', 'B': 'B video', 'C': 'C bulk', 'R': 'R flood'}
OFFERED = {'A': 0.16, 'B': 2.0}

plt.rcParams.update({'font.family': 'sans-serif', 'figure.facecolor': SURFACE,
                     'axes.facecolor': SURFACE, 'savefig.facecolor': SURFACE})


# ---- read the results
def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


data, flood = {}, {}
with open(os.path.join(RES, 'results.csv')) as f:
    for r in csv.DictReader(f):
        parts = r['run'].split('_', 1)
        if len(parts) != 2:
            continue
        row = {k: (num(v) if k not in ('run', 'class') else v) for k, v in r.items()}
        if parts[0] == 'challenge':
            flood[(parts[1], r['class'])] = row
        else:
            data[(parts[0], parts[1], r['class'])] = row
if not data:
    sys.exit('No usable rows in %s/results.csv' % RES)


def val(row, key):
    return None if row is None else row.get(key)


def style(ax):
    for s in ('top', 'right', 'left'):
        ax.spines[s].set_visible(False)
    ax.spines['bottom'].set_color(AXIS)
    ax.tick_params(colors=INK2, length=0, labelsize=10)
    ax.yaxis.grid(True, color=GRID, linewidth=1)
    ax.set_axisbelow(True)


def heading(fig, title, sub):
    fig.text(0.012, 0.965, title, fontsize=14, fontweight='bold', color=INK, va='top')
    fig.text(0.012, 0.905, sub, fontsize=10, color=INK2, va='top')


def legend(fig, modes):
    handles = [Patch(facecolor=MODE_COLOR[m], label=MODE_LABEL[m]) for m in modes]
    fig.legend(handles=handles, loc='lower center', ncol=len(modes), frameon=False,
               fontsize=10, labelcolor=INK2, bbox_to_anchor=(0.5, 0.0))


# ---- Figures 1-3: one metric, three loads side by side, three modes per class
def bar_panels(metric, ylabel, title, sub, fname, fmt, label_loads=('heavy',)):
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 4.9), sharey=True)
    top = max([val(r, metric) or 0 for (m, l, c), r in data.items()] + [1e-9])
    for ax, load in zip(axes, LOADS):
        style(ax)
        for k, mode in enumerate(MODES):
            for i, cls in enumerate(CLASSES):
                v = val(data.get((mode, load, cls)), metric)
                if v is None:
                    continue
                x = i + (k - 1) * 0.27
                ax.bar(x, v, 0.25, color=MODE_COLOR[mode], edgecolor=SURFACE, linewidth=2)
                if load in label_loads:
                    ax.text(x, v + top * 0.015, fmt(v), ha='center', va='bottom',
                            fontsize=8.5, color=INK)
        ax.set_xticks(range(3))
        ax.set_xticklabels([TICK[c] for c in CLASSES])
        ax.set_title('%s load (C sends %d Mbps)' % (load.capitalize(), C_LOAD[load]),
                     fontsize=10.5, color=INK, loc='left', pad=8)
        ax.set_ylim(0, top * 1.14)
    axes[0].set_ylabel(ylabel, color=INK2, fontsize=10)
    heading(fig, title, sub)
    legend(fig, MODES)
    fig.tight_layout(rect=(0, 0.07, 1, 0.86))
    fig.savefig(os.path.join(FIG, fname), dpi=160)
    plt.close(fig)


bar_panels('loss_pct', 'Packet loss (%)', 'Packet loss by traffic class',
           'Values are labelled for the heavy-load panel. Every value is in summary.md.',
           'fig_loss.png', lambda v: '%.0f' % v)
bar_panels('avg_latency_ms', 'Average latency (ms)', 'Average latency by traffic class',
           'Values are labelled for the heavy-load panel. Every value is in summary.md.',
           'fig_latency.png', lambda v: '%.1f' % v)
bar_panels('throughput_mbps', 'Throughput (Mbps)', 'Throughput by traffic class',
           'The link carries about 9.7 Mbps in total in every mode. QoS decides who gets it.',
           'fig_throughput.png', lambda v: '%.2f' % v)


# ---- Figure 4: the flood test, classes A and B only
def flood_figure():
    pairs = [m for m in ('baseline', 'static', 'adaptive') if any((m, c) in flood for c in 'AB')]
    if not pairs:
        return
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.6))
    spec = [('loss_pct', 'Packet loss (%)', lambda v: '%.1f' % v),
            ('avg_latency_ms', 'Average latency (ms)', lambda v: '%.1f' % v)]
    for ax, (metric, ylabel, fmt) in zip(axes, spec):
        style(ax)
        top = max([val(flood.get((m, c)), metric) or 0 for m in pairs for c in 'AB'] + [1e-9])
        n = len(pairs)
        for k, mode in enumerate(pairs):
            for i, cls in enumerate('AB'):
                v = val(flood.get((mode, cls)), metric)
                if v is None:
                    continue
                x = i + (k - (n - 1) / 2) * 0.3
                ax.bar(x, v, 0.27, color=MODE_COLOR[mode], edgecolor=SURFACE, linewidth=2)
                ax.text(x, v + top * 0.015, fmt(v), ha='center', va='bottom', fontsize=9, color=INK)
        ax.set_xticks(range(2))
        ax.set_xticklabels([TICK['A'], TICK['B']])
        ax.set_ylim(0, top * 1.15)
        ax.set_ylabel(ylabel, color=INK2, fontsize=10)
    heading(fig, 'Flood test: voice and video during an unannounced 15 Mbps flood',
            'The flood starts 8 s into a 30 s run and lasts 15 s. The controller was never told about it.')
    legend(fig, pairs)
    fig.tight_layout(rect=(0, 0.08, 1, 0.86))
    fig.savefig(os.path.join(FIG, 'fig_flood.png'), dpi=160)
    plt.close(fig)


flood_figure()


# ---- Figure 5: bottleneck usage over time during the flood test
def timeline_figure():
    wp, up = os.path.join(RES, 'challenge_window.json'), os.path.join(RES, 'util_log.csv')
    if not (os.path.exists(wp) and os.path.exists(up)):
        print('Skipping the timeline figure (needs challenge_window.json and util_log.csv).')
        return
    wins = json.load(open(wp))
    rows = []
    with open(up) as f:
        for r in csv.reader(f):
            try:
                rows.append((float(r[0]), float(r[1]), int(float(r[2]))))
            except (ValueError, IndexError):
                pass
    modes = [m for m in ('baseline', 'adaptive') if m in wins]
    if not rows or not modes:
        return
    fig, axes = plt.subplots(1, len(modes), figsize=(5.6 * len(modes), 4.6), sharey=True, squeeze=False)
    for ax, mode in zip(axes[0], modes):
        w = wins[mode]
        style(ax)
        seg = [r for r in rows if w['t0'] - 1 <= r[0] <= w['end'] + 1]
        xs = [r[0] - w['t0'] for r in seg]
        ax.axvspan(w['rogue_start'] - w['t0'], w['rogue_end'] - w['t0'], color=MUTED, alpha=0.14, linewidth=0)
        ax.plot(xs, [r[1] for r in seg], color=INK, linewidth=2, solid_capstyle='round')
        on = [r for r in seg if r[2]]
        ax.plot([r[0] - w['t0'] for r in on], [r[1] for r in on], linestyle='none', marker='o',
                markersize=8, color=MODE_COLOR['adaptive'], markeredgecolor=SURFACE, markeredgewidth=2)
        ax.set_ylim(0, 12)
        ax.set_xlabel('Seconds since the run started', color=INK2, fontsize=10)
        ax.text(w['rogue_start'] - w['t0'] + 0.3, 11.2, 'flood', color=INK2, fontsize=9.5, va='top')
        title = MODE_LABEL[mode]
        if mode == 'adaptive' and w.get('reaction_s') is not None:
            title += ': QoS on %.1f s after the flood starts' % w['reaction_s']
        ax.set_title(title, fontsize=10.5, color=INK, loc='left', pad=8)
    axes[0][0].set_ylabel('Bottleneck usage (Mbps)', color=INK2, fontsize=10)
    heading(fig, 'How the controller reacts to the flood',
            'Black line: measured usage of the 10 Mbps link, once per second. Green dots: seconds with QoS switched on.')
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(os.path.join(FIG, 'fig_flood_timeline.png'), dpi=160)
    plt.close(fig)


timeline_figure()


# ---- Fairness (Jain's index) and the table of every value
def jain(xs):
    sq = sum(x * x for x in xs)
    return (sum(xs) ** 2) / (len(xs) * sq) if sq else 0.0


lines = ["Jain's fairness index (x = achieved / offered throughput, capped at 1; 1.0 = perfectly even)",
         '%-8s %-10s %-10s %-10s' % ('load', 'baseline', 'static', 'adaptive')]
for load in LOADS:
    cells = []
    for mode in MODES:
        xs = []
        for cls in CLASSES:
            t = val(data.get((mode, load, cls)), 'throughput_mbps')
            xs.append(min(1.0, t / OFFERED.get(cls, C_LOAD[load])) if t is not None else 0.0)
        cells.append('%.3f' % jain(xs))
    lines.append('%-8s %-10s %-10s %-10s' % (load, *cells))
open(os.path.join(RES, 'fairness.txt'), 'w').write('\n'.join(lines) + '\n')
print('\n'.join(lines))


def md_row(run, cls, r):
    def f(k, d):
        v = val(r, k)
        return ('%.*f' % (d, v)) if v is not None else ''
    return '| %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (
        run, cls, f('sent', 0), f('received', 0), f('loss_pct', 2), f('throughput_mbps', 3),
        f('avg_latency_ms', 2), f('max_latency_ms', 1), f('jitter_ms', 2))


md = ['# Results summary', '',
      'Every number behind the figures. One run per condition.', '',
      '| Run | Class | Sent | Received | Loss % | Throughput (Mbps) | Avg latency (ms) | Max latency (ms) | Jitter (ms) |',
      '|---|---|---|---|---|---|---|---|---|']
for load in LOADS:
    for mode in MODES:
        for cls in CLASSES:
            if (mode, load, cls) in data:
                md.append(md_row('%s_%s' % (mode, load), cls, data[(mode, load, cls)]))
for mode in ('baseline', 'static', 'adaptive'):
    for cls in ('A', 'B', 'R'):
        if (mode, cls) in flood:
            md.append(md_row('challenge_%s' % mode, cls, flood[(mode, cls)]))
md += ['', '## Fairness', '', '```'] + lines + ['```', '']
w = os.path.join(RES, 'challenge_window.json')
if os.path.exists(w):
    rs = json.load(open(w)).get('adaptive', {}).get('reaction_s')
    if rs is not None:
        md += ['Controller reaction time to the unannounced flood: %.2f s.' % rs, '']
open(os.path.join(RES, 'summary.md'), 'w').write('\n'.join(md) + '\n')
print('Saved figures to %s and the tables to %s/summary.md' % (FIG, RES))
