#!/usr/bin/env python3
"""
UR twin bridge for ML2305 Lab 3.

Connects one Universal Robots arm to the UR twin web page through a shared
MQTT server. The page and the bridge only need outgoing internet, so students
on eduroam and the lab laptop on the robot network can meet on the server.

  robot  <--RTDE or sockets-->  this bridge  <--MQTT over WebSocket-->  web page

Install once:   pip install paho-mqtt          (ur_rtde is optional)
Test without a robot:
    python ur_bridge.py --room team1 --sim
Real robot (lab laptop on the robot network):
    python ur_bridge.py --room team1 --robot-ip 192.168.56.98

The bridge starts DISARMED. Students can watch (shadow) at once, but commands
are rejected until you type  arm  in this terminal. Type  disarm  or  stop  at
any time. Keep a hand near the emergency stop while the robot is armed.

Terminal commands:  arm  disarm  free [seconds]  stop  home  status  quit
  free 20   makes the arm hand guidable for 20 s (freedrive), also in remote
            mode, so you can move it by hand while the twin follows.
            Commands from the web are refused while freedrive is on.

Only you should steer while students watch the same room:
    python ur_bridge.py --room teacher --robot-ip 192.168.56.98 --allow Yongkuk
"""
import argparse, json, math, os, queue, socket, ssl, struct, sys, threading, time

try:
    import paho.mqtt.client as mqtt
except ImportError:
    sys.exit("paho-mqtt is missing. Run:  pip install paho-mqtt")

BROKERS = {
    "emqx":   dict(host="broker.emqx.io",        port=8084, ws=True, tls=True, path="/mqtt"),
    "hivemq": dict(host="broker.hivemq.com",     port=8884, ws=True, tls=True, path="/mqtt"),
    "mosq":   dict(host="test.mosquitto.org",    port=8081, ws=True, tls=True, path="/"),
    "shiftr": dict(host="public.cloud.shiftr.io", port=443, ws=True, tls=True, path="/", user="public", pw="public"),
}
D2R = math.pi / 180.0


def parse_broker(s):
    if s in BROKERS:
        return dict(BROKERS[s])
    # ws://host:port/path  wss://...  mqtt://host:port
    proto, rest = s.split("://", 1) if "://" in s else ("mqtt", s)
    hostport, _, path = rest.partition("/")
    host, _, port = hostport.partition(":")
    ws = proto in ("ws", "wss")
    tls = proto in ("wss", "mqtts")
    default = {"ws": 80, "wss": 443, "mqtt": 1883, "mqtts": 8883}[proto]
    return dict(host=host, port=int(port or default), ws=ws, tls=tls, path="/" + path)


# ---------------------------------------------------------------- robots
class SimRobot:
    """Moves joints towards the target with a speed limit. No hardware."""
    src = "sim"

    def __init__(self, home):
        self.q = list(home)
        self.target = list(home)
        self.speed = 0.6
        self.lock = threading.Lock()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        last = time.time()
        while True:
            time.sleep(0.02)
            now = time.time(); dt = now - last; last = now
            with self.lock:
                for i in range(6):
                    d = self.target[i] - self.q[i]
                    step = self.speed * dt
                    self.q[i] += max(-step, min(step, d))

    def get_q(self):
        with self.lock:
            return list(self.q)

    def movej(self, q, v, a):
        with self.lock:
            self.target = list(q); self.speed = v

    def stop(self):
        with self.lock:
            self.target = list(self.q)

    def busy(self):
        with self.lock:
            return max(abs(t - q) for t, q in zip(self.target, self.q)) > 0.005

    def freedrive(self, secs):
        print("    (simulated robot, freedrive has no effect)")


class RTDERobot:
    """Uses ur_rtde (pip install ur_rtde), the same library as the lab system."""
    src = "real"

    def __init__(self, ip):
        from rtde_receive import RTDEReceiveInterface
        from rtde_control import RTDEControlInterface
        self.r = RTDEReceiveInterface(ip)
        self.c = None
        self.ip = ip
        self._ctl = RTDEControlInterface

    def _control(self):
        if self.c is None:
            self.c = self._ctl(self.ip)
        return self.c

    def get_q(self):
        return list(self.r.getActualQ())

    def movej(self, q, v, a):
        self._control().moveJ(list(q), v, a, True)   # asynchronous

    def stop(self):
        if self.c is not None:
            self.c.stopJ(2.0)

    def busy(self):
        try:
            return max(abs(x) for x in self.r.getActualQd()) > 0.01
        except Exception:
            return False

    def freedrive(self, secs):
        c = self._control()
        c.freedriveMode()
        threading.Timer(secs, lambda: c.endFreedriveMode()).start()


class SocketRobot:
    """No extra library. Reads the 125 Hz real time stream on port 30003 and
    sends single URScript lines to port 30002. The robot must be in remote
    control mode on e-Series."""
    src = "real"

    def __init__(self, ip):
        self.ip = ip
        self.q = None
        self.qd = [0.0] * 6
        self.lock = threading.Lock()
        threading.Thread(target=self._reader, daemon=True).start()
        t0 = time.time()
        while self.q is None and time.time() - t0 < 5:
            time.sleep(0.05)
        if self.q is None:
            raise RuntimeError("no data from %s:30003" % ip)

    def _reader(self):
        expected, last_err = None, 0.0
        while True:
            s = None
            try:
                s = socket.create_connection((self.ip, 30003), timeout=10)
                buf = b""
                while True:
                    chunk = s.recv(8192)
                    if not chunk:
                        break
                    buf += chunk
                    while len(buf) >= 4:
                        n = struct.unpack(">i", buf[:4])[0]
                        if n < 348 or n > 4096 or (expected and n != expected):
                            # lost the packet boundary, look for the next packet start
                            k = buf.find(struct.pack(">i", expected), 1) if expected else -1
                            buf = buf[k:] if k > 0 else buf[-3:]
                            if k <= 0:
                                break
                            continue
                        if len(buf) < n:
                            break
                        msg, buf = buf[:n], buf[n:]
                        expected = expected or n
                        q = struct.unpack(">6d", msg[252:300])
                        qd = struct.unpack(">6d", msg[300:348])
                        with self.lock:
                            self.q, self.qd, self.t = list(q), list(qd), time.time()
            except Exception as e:
                if time.time() - last_err > 30:
                    print("[robot] state stream interrupted (%s), reconnecting" % e)
                    last_err = time.time()
                time.sleep(0.5)
            finally:
                try:
                    s and s.close()
                except Exception:
                    pass

    def _script(self, line):
        with socket.create_connection((self.ip, 30002), timeout=3) as s:
            s.sendall((line + "\n").encode())

    def get_q(self):
        with self.lock:
            return list(self.q)

    def movej(self, q, v, a):
        self._script("movej([%s], a=%.3f, v=%.3f)" % (",".join("%.5f" % x for x in q), a, v))

    def stop(self):
        self._script("stopj(2.0)")

    def busy(self):
        with self.lock:
            return max(abs(x) for x in self.qd) > 0.01

    def freedrive(self, secs):
        prog = "def ml2305_free():\n  freedrive_mode()\n  sleep(%.1f)\n  end_freedrive_mode()\nend\n" % secs
        with socket.create_connection((self.ip, 30002), timeout=3) as s:
            s.sendall(prog.encode())


# ---------------------------------------------------------------- bridge
class Bridge:
    def __init__(self, args):
        self.args = args
        self.home = [float(x) * D2R for x in args.home.split(",")]
        self.box = [[h - args.box * D2R, h + args.box * D2R] for h in self.home]
        if args.sim:
            self.robot = SimRobot(self.home)
        else:
            self.robot = None
            if args.backend in ("auto", "rtde"):
                try:
                    self.robot = RTDERobot(args.robot_ip); print("[robot] connected with ur_rtde")
                except Exception as e:
                    if args.backend == "rtde":
                        sys.exit("ur_rtde failed: %s" % e)
                    print("[robot] ur_rtde not available (%s), using sockets" % e)
            if self.robot is None:
                self.robot = SocketRobot(args.robot_ip); print("[robot] connected with sockets 30002/30003")
        self.armed = args.start_armed
        self.free_until = 0.0
        self.allow = [a.strip().lower() for a in (args.allow or "").split(",") if a.strip()]
        self.last_cmd = 0.0
        self.last_info = None
        args.room = "".join(ch for ch in args.room if ch.isalnum() or ch in "_-").lower() or "demo"
        self.base = "ml2305/%s/ur/" % args.room
        b = parse_broker(args.broker)
        transport = "websockets" if b["ws"] else "tcp"
        cid = "ur-bridge-%s-%d" % (args.room, os.getpid())
        try:
            self.mq = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cid, transport=transport)
        except AttributeError:
            self.mq = mqtt.Client(client_id=cid, transport=transport)
        if b["ws"]:
            self.mq.ws_set_options(path=b["path"])
        if b["tls"]:
            self.mq.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        if b.get("user"):
            self.mq.username_pw_set(b["user"], b.get("pw"))
        self.mq.on_connect = self.on_connect
        self.mq.on_message = self.on_message
        self.mq.on_disconnect = lambda *a: print("[mqtt] disconnected, retrying")
        self.cmds = queue.Queue()
        print("[mqtt] connecting to %s:%d (%s)" % (b["host"], b["port"], transport))
        self.mq.connect_async(b["host"], b["port"], keepalive=30)
        self.mq.loop_start()

    def on_connect(self, c, u, flags, rc, *extra):
        print("[mqtt] connected (rc=%s), room '%s'" % (rc, self.args.room))
        c.subscribe(self.base + "cmd", qos=0)

    def on_message(self, c, u, msg):
        try:
            self.cmds.put(json.loads(msg.payload.decode("utf-8")))
        except Exception:
            pass

    def ack(self, cmd, ok, text=""):
        self.last_info = {"id": cmd.get("id"), "by": cmd.get("by"), "ok": ok, "msg": text}
        self.mq.publish(self.base + "ack", json.dumps(self.last_info))
        print("[cmd] %-10s %-6s %s %s" % (str(cmd.get("by"))[:10], cmd.get("type"), "OK " if ok else "NO ", text))

    def handle(self, cmd):
        typ = cmd.get("type")
        if self.allow and str(cmd.get("by", "")).strip().lower() not in self.allow:
            self.ack(cmd, False, "only the teacher can steer this robot"); return
        if typ == "stop":
            self.robot.stop(); self.free_until = 0.0; self.ack(cmd, True, "stopped"); return
        if typ != "movej":
            self.ack(cmd, False, "unknown command"); return
        if not self.armed:
            self.ack(cmd, False, "robot is not armed by the teacher"); return
        if time.time() < self.free_until:
            self.ack(cmd, False, "the robot is in freedrive, someone moves it by hand"); return
        now = time.time()
        if now - self.last_cmd < self.args.min_interval:
            self.ack(cmd, False, "too fast, wait %.1f s between commands" % self.args.min_interval); return
        q = cmd.get("q")
        if not (isinstance(q, list) and len(q) == 6 and all(isinstance(x, (int, float)) and math.isfinite(x) for x in q)):
            self.ack(cmd, False, "bad joint list"); return
        for i, (x, (lo, hi)) in enumerate(zip(q, self.box)):
            if x < lo - 1e-6 or x > hi + 1e-6:
                self.ack(cmd, False, "joint %d outside the safe box" % (i + 1)); return
        self.last_cmd = now
        try:
            self.robot.movej(q, self.args.speed, self.args.acc)
            self.ack(cmd, True, "moving")
        except Exception as e:
            self.ack(cmd, False, "robot error: %s" % e)

    def console(self):
        print("Type a command and press Enter: arm, disarm, free [seconds], stop, home, status, quit")
        for line in sys.stdin:
            w = line.strip().lower()
            if w == "arm":
                self.armed = True; print(">>> ARMED. Students can move the robot. Stay at the emergency stop.")
            elif w == "disarm":
                self.armed = False; print(">>> disarmed, commands are rejected")
            elif w.startswith("free"):
                parts = w.split()
                try:
                    secs = float(parts[1]) if len(parts) > 1 else 20.0
                except ValueError:
                    secs = 20.0
                secs = max(3.0, min(120.0, secs))
                try:
                    self.robot.freedrive(secs)
                    self.free_until = time.time() + secs
                    print(">>> FREEDRIVE for %d s. Hold the arm and guide it by hand. Type stop to end early." % secs)
                except Exception as e:
                    print(">>> freedrive failed:", e)
            elif w == "stop":
                self.robot.stop(); self.free_until = 0.0; print(">>> stop sent")
            elif w == "home":
                self.robot.movej(self.home, self.args.speed, self.args.acc); print(">>> moving home")
            elif w == "status":
                print(">>> armed=%s q(deg)=%s" % (self.armed, [round(x / D2R, 1) for x in self.robot.get_q()]))
            elif w in ("quit", "exit"):
                os._exit(0)
            elif w:
                print("commands: arm, disarm, free [seconds], stop, home, status, quit")

    def run(self):
        threading.Thread(target=self.console, daemon=True).start()
        period = 1.0 / self.args.rate
        nxt = time.time()
        while True:
            while not self.cmds.empty():
                self.handle(self.cmds.get())
            try:
                q = self.robot.get_q()
                state = {"q": [round(x, 5) for x in q], "t": int(time.time() * 1000), "armed": self.armed,
                         "src": self.robot.src, "busy": self.robot.busy(), "free": time.time() < self.free_until,
                         "box": [[round(a, 4), round(b, 4)] for a, b in self.box]}
                self.mq.publish(self.base + "state", json.dumps(state))
            except Exception as e:
                print("[robot] read error:", e)
            nxt += period
            time.sleep(max(0.0, nxt - time.time()))


def main():
    p = argparse.ArgumentParser(description="UR twin bridge for ML2305 Lab 3")
    p.add_argument("--room", required=True, help="room code, the same as on the web page")
    p.add_argument("--broker", default="emqx", help="emqx, hivemq, mosq, shiftr or a URL like ws://host:9001/")
    p.add_argument("--robot-ip", default=os.environ.get("UR_ROBOT_IP", "192.168.56.98"))
    p.add_argument("--backend", default="auto", choices=["auto", "rtde", "socket"])
    p.add_argument("--sim", action="store_true", help="simulated robot, no hardware")
    p.add_argument("--home", default="0,-90,90,-90,-90,0", help="home pose in degrees, centre of the safe box")
    p.add_argument("--box", type=float, default=45.0, help="allowed degrees around home for every joint")
    p.add_argument("--speed", type=float, default=0.35, help="joint speed rad/s")
    p.add_argument("--acc", type=float, default=0.6, help="joint acceleration rad/s^2")
    p.add_argument("--rate", type=float, default=10.0, help="state messages per second")
    p.add_argument("--min-interval", type=float, default=1.5, help="seconds between accepted commands")
    p.add_argument("--start-armed", action="store_true", help="only for testing with --sim")
    p.add_argument("--allow", default="", help="names allowed to steer, comma separated, e.g. Yongkuk")
    a = p.parse_args()
    if a.start_armed and not a.sim:
        sys.exit("--start-armed is only allowed together with --sim")
    Bridge(a).run()


if __name__ == "__main__":
    main()
