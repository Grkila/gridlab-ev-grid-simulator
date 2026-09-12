# Configuration reference

This reference lists accepted experiment and benchmark fields from the current Python schema.
Use the [user guide](USER_GUIDE.md) for procedures and interpretation.
Saved definitions and GUI presets can override schema defaults.
A dash means the schema provides no literal default.

Generated with `python scripts/export_configuration_reference.py`.

## Experiment

| Field | Type or choices | Default | Constraints |
| --- | --- | --- | --- |
| `operating_mode` | as_supplied / regulated | `"as_supplied"` |  |
| `schema_version` | integer | `1` |  |
| `name` | string | `—` | minLength: 1, required |
| `hypothesis` | string | `—` | minLength: 1, required |
| `metric_boundary` | city_total / grid_asset / departure | `"city_total"` |  |
| `observation_contract` | string | `"current_state"` |  |
| `case_origin` | manual / llm / random / ga | `"manual"` |  |
| `assumptions` | list of string | `—` |  |
| `demand` | DemandConfig | `—` |  |
| `fleet` | FleetConfig | `—` |  |
| `district_capacity` | DistrictCapacity | `—` |  |
| `network_capacity` | NetworkCapacity | `—` |  |
| `rl` | RLControl or null | `null` |  |
| `strategy_options` | StrategyOptions | `—` |  |
| `strategies` | list of immediate / fixed_delay / randomized_delay / capacity_aware / rl / least_laxity_first / valley_filling / mpc / voltage_responsive | `—` |  |
| `seeds` | list of integer | `—` |  |
| `fleet_sizes` | list of integer or null | `null` |  |
| `limits` | Limits | `—` |  |
| `assertions` | list of HardAssertion or PairedAssertion | `—` |  |
| `max_cases` | integer | `100` | minimum: 1, maximum: 10000 |
| `max_runtime_seconds` | number | `600.0` | maximum: 86400, exclusiveMinimum: 0 |
| `stress_first` | boolean | `true` |  |
| `stop_on_violation` | boolean | `true` |  |
| `fixed_start_hour` | integer | `23` | minimum: 0, maximum: 23 |

## CompositionConfig

| Field | Type or choices | Default | Constraints |
| --- | --- | --- | --- |
| `mode` | preserve_city / preserve_energy | `"preserve_city"` |  |
| `residential` | number or null | `null` |  |
| `commercial` | number or null | `null` |  |
| `industrial` | number or null | `null` |  |

## DemandConfig

| Field | Type or choices | Default | Constraints |
| --- | --- | --- | --- |
| `scope` | city_total / active_sources | `"city_total"` |  |
| `measurement` | load / supply_including_losses | `"supply_including_losses"` |  |
| `monthly_energy` | number | `95636.0` | exclusiveMinimum: 0 |
| `unit` | kWh / MWh | `"MWh"` |  |
| `month` | integer | `1` | minimum: 1, maximum: 12 |
| `days_per_month` | integer | `30` | minimum: 1, maximum: 31 |
| `days` | integer | `1` | minimum: 1, maximum: 31 |
| `annual_growth_rate` | number | `0.03` | minimum: 0, maximum: 1 |
| `years_ahead` | integer | `0` | minimum: 0, maximum: 100 |
| `scenario` | base / worst_case | `"base"` |  |
| `variation` | base / lower / upper | `"base"` |  |
| `composition` | CompositionConfig | `—` |  |
| `randomize` | boolean | `false` |  |
| `daily_scale_min` | number | `0.8` | maximum: 3, exclusiveMinimum: 0 |
| `daily_scale_max` | number | `1.2` | maximum: 3, exclusiveMinimum: 0 |
| `shape_noise` | number | `0.1` | minimum: 0, maximum: 0.5 |

## DistrictCapacity

| Field | Type or choices | Default | Constraints |
| --- | --- | --- | --- |
| `scenario` | low / central / high | `"central"` |  |
| `overrides` | map to DistrictOverride | `—` |  |

## DistrictOverride

| Field | Type or choices | Default | Constraints |
| --- | --- | --- | --- |
| `capacity_kw` | number | `—` | exclusiveMinimum: 0, required |
| `provenance` | string | `—` | minLength: 1, required |

## FleetConfig

| Field | Type or choices | Default | Constraints |
| --- | --- | --- | --- |
| `charging_profile` | legacy_mix / home_only / whole_day | `"legacy_mix"` |  |
| `fleet_size` | integer | `100` | minimum: 0, maximum: 1000000 |
| `charger_kw` | number | `7.4` | exclusiveMinimum: 0 |
| `energy_kwh` | number | `14.0` | exclusiveMinimum: 0 |
| `efficiency` | number | `0.9` | maximum: 1, exclusiveMinimum: 0 |
| `location_mix` | LocationMix | `—` |  |
| `district_mix` | map to number or null | `null` |  |

## HardAssertion

| Field | Type or choices | Default | Constraints |
| --- | --- | --- | --- |
| `type` | string | `"hard"` |  |
| `metric` | min_voltage_pu / max_line_loading_percent / max_transformer_loading_percent / unmet_energy_kwh / nonconverged_steps / overload_steps / max_district_loading_percent / district_overload_steps / max_network_capacity_loading_percent / network_capacity_overload_steps / energy_excess_kwh / energy_limit_exceeded_steps | `—` | required |
| `operator` | le / ge | `—` | required |
| `value` | number | `—` | required |

## Limits

| Field | Type or choices | Default | Constraints |
| --- | --- | --- | --- |
| `min_voltage_pu` | number | `0.95` | maximum: 2, exclusiveMinimum: 0 |
| `max_voltage_pu` | number | `1.05` | maximum: 2, exclusiveMinimum: 0 |
| `max_loading_percent` | number | `100.0` | exclusiveMinimum: 0 |

## LocationMix

| Field | Type or choices | Default | Constraints |
| --- | --- | --- | --- |
| `residential` | number | `0.7` | minimum: 0, maximum: 1 |
| `workplace` | number | `0.2` | minimum: 0, maximum: 1 |
| `public` | number | `0.1` | minimum: 0, maximum: 1 |

## NetworkCapacity

| Field | Type or choices | Default | Constraints |
| --- | --- | --- | --- |
| `lv_baseline_fraction` | number | `0.5` | minimum: 0, maximum: 1 |
| `lv_ev_fraction` | number | `1.0` | minimum: 0, maximum: 1 |

## PairedAssertion

| Field | Type or choices | Default | Constraints |
| --- | --- | --- | --- |
| `type` | string | `"paired"` |  |
| `metric` | string | `—` | required |
| `reduction_fraction` | number | `—` | minimum: 0, maximum: 1, required |
| `control` | string | `—` | minLength: 1, required |
| `candidate` | string | `—` | minLength: 1, required |

## RLControl

| Field | Type or choices | Default | Constraints |
| --- | --- | --- | --- |
| `model_id` | string | `—` | required |
| `reward` | RewardWeights | `—` |  |
| `safety_shield` | boolean | `true` |  |
| `daily_energy_limit_kwh` | number or null | `null` |  |

## RewardWeights

| Field | Type or choices | Default | Constraints |
| --- | --- | --- | --- |
| `delivery` | number | `1.0` | minimum: 0, maximum: 1000000.0 |
| `shortfall` | number | `10.0` | minimum: 0, maximum: 1000000.0 |
| `capacity` | number | `1000.0` | maximum: 1000000.0, exclusiveMinimum: 0 |
| `energy` | number | `1000.0` | maximum: 1000000.0, exclusiveMinimum: 0 |
| `switching` | number | `0.05` | minimum: 0, maximum: 1000000.0 |
| `peak` | number | `0.1` | minimum: 0, maximum: 1000000.0 |
| `intervention` | number | `10.0` | minimum: 0, maximum: 1000000.0 |

## StrategyOptions

| Field | Type or choices | Default | Constraints |
| --- | --- | --- | --- |
| `horizon_steps` | integer | `96` | minimum: 1, maximum: 192 |
| `forecast` | persistence / previous_day | `"persistence"` |  |
| `valley_iterations` | integer | `8` | minimum: 1, maximum: 50 |
| `max_variables` | integer | `30000` | minimum: 100, maximum: 100000 |
| `solver_seconds` | number | `3.0` | maximum: 30, exclusiveMinimum: 0 |
| `voltage_stop_pu` | number | `0.95` | maximum: 1.1, exclusiveMinimum: 0 |
| `voltage_full_pu` | number | `0.99` | maximum: 1.2, exclusiveMinimum: 0 |
| `recovery_fraction` | number | `0.25` | maximum: 1, exclusiveMinimum: 0 |

## BenchmarkConfig

| Field | Type or choices | Default | Constraints |
| --- | --- | --- | --- |
| `name` | string | `"Novi Sad · standard 10"` | minLength: 1, maxLength: 100 |
| `standard_fleet` | integer | `100` | minimum: 1, maximum: 50000 |
| `max_fleet` | integer | `10000` | minimum: 1, maximum: 50000 |
| `seeds` | list of integer | `—` | minItems: 1, maxItems: 5 |
| `district` | string or null | `null` |  |
| `operating_mode` | as_supplied / regulated | `"as_supplied"` |  |
| `search_mode` | refined / doubling | `"refined"` |  |
| `until_failure` | boolean | `false` |  |
| `aggregate_ev_nodes` | boolean | `false` |  |
| `charging_profile` | home_only / whole_day | `"home_only"` |  |

## BenchmarkRunConfig

| Field | Type or choices | Default | Constraints |
| --- | --- | --- | --- |
| `strategies` | list of string | `—` | minItems: 1, maxItems: 100, required |
| `model_id` | string or null | `null` |  |
| `strategy_options` | StrategyOptions | `—` |  |
| `max_runtime_seconds` | number | `3600` | minimum: 1, maximum: 43200 |
| `case_runtime_seconds` | number | `120` | minimum: 1, maximum: 3600 |
