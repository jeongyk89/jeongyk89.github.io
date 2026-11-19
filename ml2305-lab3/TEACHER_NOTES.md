# ML2305 Lab 3 run sheet

## Before class, about 20 minutes

1. Upload the folders `market`, `connect`, `ur`, `service` and the file `lab3.html` to the root of the `ml2305` repository. The links become `jeongyk89.github.io/ml2305/market` and so on, which are the links and QR codes in the slides.
2. Label the supermarket. Put L and R on the two racks, number the sections from the start, and the levels from the floor. Sticky notes are enough. Park the cart at the start.
3. Choose room codes for Session B, one per team, for example `b1`, `b2`, `b3`. Students type the code at the top of Connect, UR twin and Twin service. Everyone in a team uses the same server. Server A is the default. If it does not connect on eduroam, switch the whole team to Server D, which runs on port 443.
4. Prepare the UR station on the lab laptop that reaches the robot.

```
pip install paho-mqtt            # ur_rtde is optional, the bridge falls back to sockets
python ur/ur_bridge.py --room ur --sim                         # test with a simulated robot
python ur/ur_bridge.py --room ur --robot-ip 192.168.1.100      # the real robot
```

   * Stop the UR driver of the docker stack first, so that only one program controls the robot.
   * The bridge starts disarmed. Students can use Model and Shadow at once. Type `arm` only when you stand at the emergency stop, and `disarm` when the team leaves. Other commands are `stop`, `home`, `status` and `quit`.
   * Commands outside a box of ±45° around home are rejected, and only one command is accepted every 1.5 s. Change this with `--home` and `--box` if your cell needs it.
   * On e-Series robots the socket fallback needs remote control mode.

## Session A, supermarket, 70 minutes

| Time | What happens |
|---|---|
| 0 to 10 | Teams of three open `market`, type their names, build the digital supermarket in tab 2 |
| 10 to 26 | Round 1 just pick, round 2 plan by a rule |
| 26 to 56 | Round 3 model first, round 4 surprise, round 5 AI on the spot |
| 56 to 70 | Round 6 improve, Results tab, four closing questions |

Several teams can share the supermarket. Waiting teams work in the Model or AI tab. Every team can copy a summary and download a CSV for the report.

## Session B, digital twin, 70 minutes

| Time | What happens |
|---|---|
| 0 to 15 | Model, shadow, twin, the two lab videos, effort per level |
| 15 to 70 | Three teams rotate through Connect, UR twin and Twin service, about 18 minutes each, then the four closing questions |

Connect. Every student picks an asset card and sends data. One integrator opens tab 2 on a laptop. Round 1 free, round 2 describe, round 3 standard, then the Time tab. `Add practice suppliers` fills the view if the team is small.

UR twin. Model mode works without anything. Shadow and Twin need the bridge running with the same room code.

Twin service. Teams fill the canvas and share it to the class board. Open the board on the projector for the joint discussion.

## If something fails

* No server reachable. Connect has an offline practice mode with practice suppliers on one laptop. The UR page works in Model mode. The service canvas still works and can be copied as text.
* Robot not reachable. Run the bridge with `--sim`. Shadow and Twin then show a simulated robot, which still shows the data flow.
* The supermarket app keeps its data in the browser of each phone. Do not clear the browser before the summary is copied.
