"""Run the full Novi Sad reconstruction without the upstream GUI."""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-stage-data", action="store_true", help="resume from an existing data.pkl")
    parser.add_argument("--stages-only", action="store_true", help="skip pandapower model creation")
    args = parser.parse_args()

    if not args.keep_stage_data:
        for filename in ("data.pkl", "net0.pkl", "ppnet_novi_sad.json"):
            Path(filename).unlink(missing_ok=True)

    import stages
    import utils

    data = utils.data_un("data.pkl") or {"last_saved": 0}
    start = data["last_saved"] + 1 if args.keep_stage_data else 1
    if start <= 7:
        stages.run_stages(data, stend=(start, 7))

    if args.stages_only:
        return

    import pandapower as pandapower
    import pp

    data = utils.data_un("data.pkl")
    net, _ = pp.populate_net(data)
    target_peak_mw = utils.cf['3'].get('calibration', {}).get('target_peak_mw')
    if target_peak_mw:
        original_mw = net.load.p_mw.sum()
        net.load['p_mw'] *= target_peak_mw / original_mw
        print(f"Calibrated aggregate peak load from {original_mw:.3f} MW to {target_peak_mw:.3f} MW")
    pp.run_net(net)
    pandapower.to_json(net, "ppnet_novi_sad.json")
    print("Created ppnet_novi_sad.json")


if __name__ == "__main__":
    main()
