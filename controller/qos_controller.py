"""Ryu app: learning switch + dynamic QoS for the UDP traffic classes.

* Learning switch (same idea as simple_switch_13) gives basic connectivity.
* Senders register (class, UDP port, rate) over a Unix datagram socket.
* On the bottleneck switch (s1, port 4) the controller installs high-priority
  flows with a set_queue action, mapping each class to an OVS queue.
* QoS is switched ON when declared demand OR measured port utilisation is high,
  and OFF again after the link has been calm for CALM_POLLS polls.
* controller/policy.json is re-read every second (mode: off | always | adaptive).
"""
import csv
import json
import os
import time

from eventlet.green import socket
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (CONFIG_DISPATCHER, MAIN_DISPATCHER,
                                    DEAD_DISPATCHER, set_ev_cls)
from ryu.lib import hub
from ryu.lib.packet import packet, ethernet, ether_types
from ryu.ofproto import ofproto_v1_3

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
POLICY_FILE = os.path.join(HERE, 'policy.json')
EVENT_LOG = os.path.join(ROOT, 'results', 'controller_events.csv')
UTIL_LOG = os.path.join(ROOT, 'results', 'util_log.csv')
CTRL_SOCK = '/tmp/qos_ctrl.sock'

BOTTLENECK_DPID = 1      # s1
BOTTLENECK_PORT = 4      # s1-eth4, towards s2
QOS_PRIORITY = 100       # above the learning-switch flows (priority 1)
POLL_SECONDS = 1.0
CALM_POLLS = 3

DEFAULT_POLICY = {'mode': 'adaptive', 'capacity_mbps': 10.0, 'high_pct': 80,
                  'low_pct': 50, 'queues': {'A': 1, 'B': 2, 'C': 3}}


class QoSController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}
        self.flows = {}          # udp port -> {'cls':..., 'rate': Mbps}
        self.installed = set()   # udp ports that currently have a QoS rule
        self.active = False
        self.util = 0.0
        self.prev = None
        self.calm = 0
        self.policy = dict(DEFAULT_POLICY)
        self.policy_raw = None
        os.makedirs(os.path.dirname(EVENT_LOG), exist_ok=True)
        hub.spawn(self._monitor)
        hub.spawn(self._control_server)

    # ------------------------------------------------------------ logging
    def _event(self, kind, detail=''):
        self.logger.info('%s %s', kind, detail)
        with open(EVENT_LOG, 'a', newline='') as f:
            csv.writer(f).writerow([round(time.time(), 3), kind, detail])

    # ------------------------------------------------- switch connection
    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change(self, ev):
        dp = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[dp.id] = dp
        else:
            self.datapaths.pop(dp.id, None)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _features(self, ev):
        dp = ev.msg.datapath
        ofp, parser = dp.ofproto, dp.ofproto_parser
        # table-miss: send unknown packets to the controller
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
        self._add_flow(dp, 0, parser.OFPMatch(), actions)
        if dp.id == BOTTLENECK_DPID:       # fresh switch: forget old rule state
            self.installed.clear()
            self.active = False
            self.prev = None

    def _add_flow(self, dp, priority, match, actions):
        parser = dp.ofproto_parser
        inst = [parser.OFPInstructionActions(dp.ofproto.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(parser.OFPFlowMod(datapath=dp, priority=priority,
                                      match=match, instructions=inst))

    # ----------------------------------------------------- learning switch
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp, parser = dp.ofproto, dp.ofproto_parser
        in_port = msg.match['in_port']
        eth = packet.Packet(msg.data).get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        table = self.mac_to_port.setdefault(dp.id, {})
        table[eth.src] = in_port
        out_port = table.get(eth.dst, ofp.OFPP_FLOOD)
        actions = [parser.OFPActionOutput(out_port)]
        if out_port != ofp.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=eth.dst, eth_src=eth.src)
            self._add_flow(dp, 1, match, actions)
        data = msg.data if msg.buffer_id == ofp.OFP_NO_BUFFER else None
        dp.send_msg(parser.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id,
                                        in_port=in_port, actions=actions, data=data))

    # ------------------------------------------------------- QoS rules
    @staticmethod
    def _match(parser, port):
        return parser.OFPMatch(eth_type=0x0800, ip_proto=17, udp_dst=port)

    def _install_one(self, port):
        dp = self.datapaths.get(BOTTLENECK_DPID)
        flow = self.flows.get(port)
        if dp is None or flow is None or port in self.installed:
            return
        queue = self.policy['queues'].get(flow['cls'])
        if queue is None:
            return
        parser = dp.ofproto_parser
        actions = [parser.OFPActionSetQueue(int(queue)),
                   parser.OFPActionOutput(BOTTLENECK_PORT)]
        self._add_flow(dp, QOS_PRIORITY, self._match(parser, port), actions)
        self.installed.add(port)
        self._event('RULE_ADD', 'udp_dst=%d class=%s queue=%s' % (port, flow['cls'], queue))

    def _remove_one(self, port):
        dp = self.datapaths.get(BOTTLENECK_DPID)
        if dp is None or port not in self.installed:
            return
        ofp, parser = dp.ofproto, dp.ofproto_parser
        dp.send_msg(parser.OFPFlowMod(datapath=dp, command=ofp.OFPFC_DELETE_STRICT,
                                      priority=QOS_PRIORITY, out_port=ofp.OFPP_ANY,
                                      out_group=ofp.OFPG_ANY,
                                      match=self._match(parser, port)))
        self.installed.discard(port)
        self._event('RULE_DEL', 'udp_dst=%d' % port)

    def _install_all(self):
        for port in list(self.flows):
            self._install_one(port)

    def _remove_all(self):
        for port in list(self.installed):
            self._remove_one(port)

    # ------------------------------------------------------ the decision
    def _decide(self, poll=False):
        p = self.policy
        cap = float(p['capacity_mbps'])
        high = cap * p['high_pct'] / 100.0
        low = cap * p['low_pct'] / 100.0
        demand = sum(f['rate'] for f in self.flows.values())
        if p['mode'] == 'off':
            want, why = False, 'mode=off'
        elif p['mode'] == 'always':
            want, why = True, 'mode=always'
        elif not self.active:
            want = self.util >= high or demand >= high
            why = 'util=%.1f demand=%.1f threshold=%.1f Mbps' % (self.util, demand, high)
        else:
            calm = self.util < low and demand < low
            if poll:
                self.calm = self.calm + 1 if calm else 0
            want = self.calm < CALM_POLLS
            why = 'calm for %d polls' % self.calm
        if want and not self.active:
            self.active = True
            self.calm = 0
            self._event('QOS_ON', why)
            self._install_all()
        elif not want and self.active:
            self.active = False
            self._event('QOS_OFF', why)
            self._remove_all()

    # --------------------------------------------- policy file (runtime)
    def _load_policy(self):
        try:
            with open(POLICY_FILE) as f:
                raw = f.read()
        except OSError:
            raw = json.dumps(DEFAULT_POLICY)
        if raw == self.policy_raw:
            return
        self.policy_raw = raw
        try:
            new = dict(DEFAULT_POLICY)
            new.update(json.loads(raw))
        except ValueError:
            self.logger.warning('policy.json is not valid JSON; keeping old policy')
            return
        old_mode = self.policy.get('mode')
        self.policy = new
        self._event('POLICY', ' '.join(raw.split()))
        if new['mode'] != old_mode and self.active:   # clean slate on mode change
            self.active = False
            self._remove_all()
        elif self.active:                             # queue map may have changed
            self._remove_all()
            self._install_all()
        self.calm = 0
        self._decide()

    # --------------------------------------------- port-statistics polling
    def _monitor(self):
        while True:
            self._load_policy()
            dp = self.datapaths.get(BOTTLENECK_DPID)
            if dp is not None:
                dp.send_msg(dp.ofproto_parser.OFPPortStatsRequest(dp, 0, BOTTLENECK_PORT))
            hub.sleep(POLL_SECONDS)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _stats_reply(self, ev):
        if ev.msg.datapath.id != BOTTLENECK_DPID:
            return
        for st in ev.msg.body:
            if st.port_no != BOTTLENECK_PORT:
                continue
            now = time.time()
            if self.prev is not None and now > self.prev[0]:
                self.util = (st.tx_bytes - self.prev[1]) * 8 / (now - self.prev[0]) / 1e6
            self.prev = (now, st.tx_bytes)
            self._decide(poll=True)
            with open(UTIL_LOG, 'a', newline='') as f:
                csv.writer(f).writerow([round(now, 3), round(self.util, 3), int(self.active)])

    # ----------------------------------- application registration (socket)
    def _control_server(self):
        if os.path.exists(CTRL_SOCK):
            os.unlink(CTRL_SOCK)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        srv.bind(CTRL_SOCK)
        os.chmod(CTRL_SOCK, 0o777)
        self.logger.info('Listening for application registrations on %s', CTRL_SOCK)
        while True:
            data, _ = srv.recvfrom(4096)
            self._handle_message(data)

    def _handle_message(self, raw):
        try:
            m = json.loads(raw.decode())
            port = int(m['port'])
        except (ValueError, KeyError):
            return
        if m.get('event') == 'start':
            self.flows[port] = {'cls': m.get('cls', '?'), 'rate': float(m.get('rate_mbps', 0))}
            self._event('REGISTER', 'port=%d class=%s rate=%.2f Mbps'
                        % (port, self.flows[port]['cls'], self.flows[port]['rate']))
            self._decide()
            if self.active:
                self._install_one(port)
        elif m.get('event') == 'stop':
            self._remove_one(port)
            self.flows.pop(port, None)
            self._event('UNREGISTER', 'port=%d' % port)
            self._decide()
