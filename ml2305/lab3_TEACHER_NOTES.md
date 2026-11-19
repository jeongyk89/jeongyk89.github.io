# ML2305 Lab 3 run sheet

## Before class, about 20 minutes

1. The apps live in `labs/ml2305` of the `jeongyk89.github.io` repository. After a push the links are `jeongyk89.github.io/labs/ml2305/market`, `/connect`, `/ur` and `/service`, which are the links and QR codes in the slides. The overview page is `jeongyk89.github.io/labs/ml2305/lab3.html`.
2. Label the supermarket. Put L and R on the two racks, number the sections from the start, and the levels from the floor. Sticky notes are enough. Park the cart at the start. The apps assume heavy items sit on level 1.
3. Write team and pair codes on the board, for example `b1`, `b2`, `b3` for Connect and Twin service, and `r1`, `r2` and so on for the robot twin pairs. Everyone in a team or pair uses the same code and the same server. Server A is the default. If it does not connect on eduroam, switch to Server D, which runs on port 443.
4. Only for your own real robot demo. On the laptop that reaches the robot, stop the UR driver of the docker stack, then run the bridge.

```
pip3 install paho-mqtt
python3 ur_bridge.py --room teacher --sim                          # test with a simulated robot
python3 ur_bridge.py --room teacher --robot-ip 192.168.56.98       # the real robot
```

   Open `jeongyk89.github.io/labs/ml2305/ur/?teacher=1`, choose Real UR robot and use the code `teacher`. The bridge starts disarmed. Type `arm` only when you stand at the emergency stop and `disarm` afterwards. Students never see the real robot option.

## Session A, supermarket, 70 minutes

| Time | What happens |
|---|---|
| 0 to 10 | Teams of three open `market`, type their names, build the digital supermarket in tab 2 |
| 10 to 26 | Round 1 just pick, round 2 plan by a rule |
| 26 to 50 | Round 3 model first, round 4 AI plans |
| 50 to 70 | Round 5 improve, Results tab, closing questions |

Several teams can share the supermarket. Waiting teams work in the Model or AI tab. In run mode the recorder only taps Picked for every line. Every team can copy a summary and download a CSV for the report.

## Session B, digital twin, 70 minutes

| Time | What happens |
|---|---|
| 0 to 15 | Model, shadow, twin, the two lab videos, effort per level |
| 15 to 70 | Three teams rotate through Connect, Robot twin and Twin service, about 18 minutes each, then the closing questions |

Connect. Every student picks an asset card and sends data. One integrator opens tab 2 on a laptop. Round 1 free, round 2 describe, round 3 standard, then the Time tab. `Add practice suppliers` fills the view if the team is small.

Robot twin. Students work in pairs with the same pair code. One chooses Physical robot and jogs the robot, the other chooses Digital twin. First shadow, where the twin only watches the box being picked, then twin, where the twin sends moves and the physical side accepts or rejects each one. Then they swap.

Twin service. Teams fill the canvas and share it to the class board. Open the board on the projector for the joint discussion.

## If something fails

* No server reachable. Connect has an offline practice mode with practice suppliers on one laptop. The robot twin works in Model mode on one screen. The service canvas still works and can be copied as text.
* The supermarket app keeps its data in the browser of each phone. Do not clear the browser before the summary is copied.
