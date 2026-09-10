# Baseline charging contracts

These four baselines do not claim reproduction of a particular research paper.
They share half-open connection windows `[arrival_step, departure_step)`, a
constant charger-power bound, and battery energy `grid kW * hours * efficiency`.
The last interval is capped to the remaining battery energy. Direct simulator
inputs require finite positive timestep, finite energy/power/efficiency and
finite integral session indices.

## Immediate

Charge immediately at the available charger rate until the requested energy is
met or the session departs. No capacity admission or AC curtailment is applied.
Violations remain visible. This is an uncontrolled demand baseline.

## Fixed delay

The configured integer hour (0 through 23) is a release threshold on the
**arrival's calendar day**. Charging starts at the later of arrival and that
threshold and may continue overnight. This is not a recurring tariff window.
An 18:00 arrival with start 00:00 charges immediately; it does not wait for the
next midnight. A 00:30 arrival with start 23:00 waits until 23:00 that day.
There is no deadline rescue: departure before release means no charging.
The same rule applies to residential, workplace and public sessions, so the
23:00 default commonly prevents daytime workplace/public charging.

## Randomized delay

Add one seeded discrete jitter to the fixed release threshold. At the standard
15-minute timestep it is uniform over 0, 0.25, ..., 3.75 hours (four hours is
excluded). A 23:00 threshold can therefore release as late as 02:45 the next
day. Arrivals after their assigned release charge immediately. The delay is
not added to arrival time. Sessions are assigned draws in sorted ID order,
so input reordering preserves draws; inserting another ID can shift subsequent
draws. Identical sessions and seeds replay identically. At nonstandard timesteps
the discrete support is `range(max(1, int(4/dt))) * dt`.

## Capacity aware

Earliest departure first (ID breaks ties) consumes current block, source,
district and weighted aggregate-stage headroom. It then applies an AC safety
wrapper: all EV powers are halved together for up to seven retries, followed by
removing all EV power on the eighth. External requests retain both protections.
Unresolved baseline violations remain visible even after all EV load is removed.
This is not an optimal dispatch: it does not account for laxity, guarantee all
feasible deadlines, or selectively curtail only the congested feeder. Global
halving can leave substantial feasible capacity unused.

## Comparison and physical boundaries

The configured daily kWh limit is monitored after dispatch for these baselines;
only the RL controller has dedicated energy-budget enforcement. Instantaneous
kW capacity control is a different constraint. Comparisons must state this
difference and distinguish scheduling from the additional AC shield used by
managed controllers.

When AC load flow fails, the simulator still counts requested consumption in
its delivered-energy accounting. This is a demand-accounting convention, not
evidence that electrical delivery succeeded. Nonconverged cases remain failed
electrical evidence. No protection-trip or outage model is implied.

The synthetic balanced MV blocks and aggregate downstream capacity estimates
do not reproduce household LV circuits, phase imbalance, battery taper,
transformer thermal ageing, or a published travel-demand data set. These are
model boundaries, not validation of field performance.
