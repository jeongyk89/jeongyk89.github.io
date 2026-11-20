# ML2305 Lab 3 run sheet

## Before class, about 20 minutes

1. The apps live in the `ml2305` folder on the main branch of the `jeongyk89.github.io` repository. The links are `jeongyk89.github.io/ml2305/market`, `/connect`, `/ur/many.html?room=teacher` and `/fleet`. The overview page is `jeongyk89.github.io/ml2305/lab3.html`.
2. Open the supermarket board `ml2305/market/?board=1` once. The layout of our four racks is already in it, with the real labels such as 01-02-A AIR, and position A nearest the start. If the picker starts at the other end of the aisle, tap Start at the other end. Tap Send layout to every phone.
3. Write the codes on the board. Class code `lab3` for the supermarket and the fleet twin. Team codes `t1`, `t2` and so on for the supermarket, `c1`, `c2` for Connect, `f1`, `f2` for the fleet twin. Server A is the default. If it does not connect on eduroam, use Server D on port 443.
4. For the robot twin, on the laptop that reaches the robot, stop the UR driver of the docker stack, then run the bridge.

```
python3 ur_bridge.py --room teacher --robot-ip 192.168.56.98 --allow Yongkuk
```

   The bridge starts disarmed. Type `home` to move the robot to its home pose, and `arm` only when you stand at the emergency stop. `free 20` lets you guide the arm by hand for 20 seconds while every copy follows, and `stop` ends it early.

## Session A, supermarket, 45 minutes per half

| Time | What happens |
|---|---|
| 0 to 5 | Teams of three join `market` with class `lab3` and their team code. Each person picks one role and keeps it |
| 5 to 40 | Four rounds. Plan and promise away from the rack, then queue. A run takes about a minute |
| 40 to 45 | Board on the projector, error chart and leaderboard, closing questions |

The planner compares four sequences with the model and promises a time. The picker sees one item at a time and never sees predictions. The recorder taps Start, Picked for every item and Back at the start. Round 1 runs on guesses, so the error is large. Every round adds about seven data points and the range shrinks. The board shows who is at the rack and who is next, so several teams can share it.

## Session B, digital twins, 45 minutes per half

| Time | What happens |
|---|---|
| 0 to 45 | Three teams rotate through Connect, Robot twin and Fleet twin, about 15 minutes each |

Model, shadow, twin, the two lab videos and the effort per level belong in the common intro, so the half can go straight to the stations.

Connect. One laptop joins as integrator, everyone else is a supplier with one device. Suppliers press Cause a problem whenever they like. Round 1, own format, the integrator translates field and unit for every device. Round 2, suppliers describe their own data. Round 3, standard. Compare the three rows of the score table, caught in 10 seconds, false alarms, translations.

Robot twin. Students open `ur/many.html?room=teacher` and test plans on their own copy. The board `ur/many.html?board=1` with your name `Yongkuk` collects every test. At the end, type `home` and `arm`, tap Run best plan twice and stand at the emergency stop. The real run teaches every copy, then run the new best plan. Tap Clear class results before the next group. The plans stay in front of the robot, 22 to 52 cm above the base with the 12 cm tool of the model. The red block is virtual.

Fleet twin. Students open `fleet` with class `lab3` and their team code. Every phone adds a robot. They claim the eight missions, fix the collisions the twin shows with waits, order or a via cell, and then run on the floor, five runs per team. The board `fleet/?board=1` keeps the leaderboard and replays every floor run.

## Discussion, 10 minutes after each half and 20 minutes at the end

Use the closing question slides. End with which twin service each group would build first in our lab, now that they have seen a model learn, a plant view connect, and twins plan for one robot and for a fleet.

## If something fails

* No server reachable. Switch every phone to Server D. The supermarket board and the fleet board also work on a laptop with a local broker.
* The robot is not reachable. Run the bridge with `--sim` instead of the robot IP. The robot twin station then works with a simulated robot.
