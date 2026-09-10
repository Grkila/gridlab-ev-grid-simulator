# Public-source audit of Novi Sad transformer data

## Conclusion

The public record is strong enough to support the nominal voltage paths and
installed transformer capacities used for several named Novi Sad stations. It
does **not** support describing the model's transformer-loading threshold as an
exact asset failure limit. The playground's default 100% loading limit is a
scenario threshold based on adopted installed MVA. Lower 86% and 90% margins
used elsewhere in the reference-model workflow are project engineering choices,
not the current playground's default or verified EDS trip limits.

This audit uses public documents issued by Elektrodistribucija Srbije (EDS), the
distribution-system operator. The main source is the *Plan razvoja
distributivnog sistema 2025–2034*. Its Novi Sad inventory has base year 2024,
and its aggregate table is explicitly dated 31 December 2024. Page references
below are PDF page numbers shown by the document viewer. The source was checked
on 10 September 2026.

## What the operator documents

The EDS inventory identifies the following assets in the **ED Novi Sad branch**
of the wider DP Novi Sad distribution area:

| Station | Publicly documented 2024 voltage ratio | Publicly documented installed transformer capacity, `Sins` | Audit result |
|---|---:|---:|---|
| Novi Sad 2 | 110/35 kV | 31.5 + 20 MVA | Supports the model's 110-to-35-kV path and aggregate installed capacity. |
| Novi Sad 4 | 110/35 kV | 2 × 63 MVA | Supports the existing 110-to-35-kV path. A separate 31.5-MVA 110/20-kV unit is a planned addition for completion in 2029, not part of the 2024 installed inventory. |
| Novi Sad 5 | 110/20/10 kV | 2 × 31.5 MVA | Supports a mixed 20/10-kV secondary designation and 63 MVA installed capacity. It does not establish how that capacity is divided between the 20- and 10-kV buses. A third 31.5-MVA 110/20-kV unit is planned for 2021–2028 and must not be counted as installed in the 2024 base year. |
| Novi Sad 7 | 110/20 kV plus a separately listed 110/35-kV unit | 2 × 31.5 MVA at 110/20 kV; 20 MVA at 110/35 kV | Supports both voltage paths. The project should state which documented units it retains rather than treating all station capacity as interchangeable. |
| Novi Sad 9 | 110/20/10 kV | 2 × 31.5 MVA | Supports a mixed 20/10-kV secondary designation and 63 MVA installed capacity. A third 31.5-MVA 110/20-kV unit is only a 2028–2029 development project. |
| Rimski Šančevi | 110/20 kV | 2 × 31.5 MVA | Supports the model's nominal voltage path and aggregate installed capacity. |

These entries appear in EDS table 2.5.1.1.1 on PDF page 162. EDS defines
`Sins` as the installed transformer capacity in the station, distinguishes the
registered maximum load in the base year from maximum individual load in normal
switching configuration, and reports a separate `Smax/Sins` utilization ratio
on PDF page 164. [EDS development plan, pp. 162–164](https://elektrodistribucija.rs/regulativa/propisi/dokumenta/Plan_razvoja_2025_2034.pdf#page=162)

The six legacy delivery stations are also explicitly listed in the same EDS
inventory:

| Delivery station | Publicly documented 2024 voltage ratio | Publicly documented `Sins` |
|---|---:|---:|
| Novi Sad–Liman | 35/10 kV | 4 × 8 MVA |
| Novi Sad–Centar | 35/10 kV | 4 × 8 MVA |
| Novi Sad–Podbara | 35/10 kV | 4 × 8 MVA |
| Novi Sad–Sever | 35/10 kV | 2 × 8 MVA |
| Novi Sad–Industrijska | 35/10 kV | 4 × 8 MVA |
| Novi Sad–Telep | 35/10 kV | 2 × 8 MVA |

This is evidence for 35/10-kV delivery, not 35/20-kV delivery. The same plan
documents 35-kV cable projects from Novi Sad 2 to Centar and from Novi Sad 4 to
Liman, which supports those two upstream associations. It does not document the
project's other station-to-delivery assignments. [EDS development plan, pp.
164 and 178](https://elektrodistribucija.rs/regulativa/propisi/dokumenta/Plan_razvoja_2025_2034.pdf#page=164)

The mixed designations matter. Calling Novi Sad 5 and Novi Sad 9 simply
“110/20 kV” omits the operator's `/10` designation. Calling Liman or
Industrijska “20/LV” contradicts the published 35/10-kV inventory. If the model
converts these paths to a common 20-kV study layer, that conversion is an
engineering abstraction and must remain labelled as such.

For lower-voltage distribution transformers, EDS publishes only an aggregate
for the entire DP Novi Sad area, not a Novi Sad city asset register. At 31
December 2024 it reports 11,373 stations, 12,308 transformer units, and 5,718.08
MVA in the 20/0.4-kV class when EDS-owned and third-party assets are combined.
Those totals confirm that 20/0.4 kV is a real distribution class, but they do
not identify any modeled block transformer or its nameplate. [EDS development
plan, p. 167](https://elektrodistribucija.rs/regulativa/propisi/dokumenta/Plan_razvoja_2025_2034.pdf#page=167)

## Installed capacity is not a failure limit

The station table reports installed MVA and observed loading. It does not give
asset serial numbers, cooling modes, winding-specific continuous ratings,
seasonal or emergency ratings, protection settings, thermal histories, ambient
conditions, or trip curves. It also reports capacity at station or voltage-path
level, sometimes as multiple units. Consequently:

- a published `2 × 31.5 MVA` is evidence of two installed nameplate units in the
  2024 inventory; it is not evidence that 63 MVA is continuously deliverable
  under every topology or an N-1 condition;
- `Smax/Sins` is an observed utilization calculation, not a published failure
  threshold;
- a modeled 100% loading threshold is a reproducible scenario boundary, not the
  physical failure point or operator trip setting of the real asset;
- 86% allocation and 90% solved-case limits are project-selected planning
  margins. No reviewed public source attributes those limits to EDS;
- a modeled 20/0.4-kV transformer rating remains assumed unless an asset-level
  source supplies that exact unit's nameplate.

This distinction also follows the scope of IEC 60076-7, which treats transformer
loading in terms of temperature and thermal ageing, including operation above
nameplate rating, rather than defining 100% nameplate loading as an exact
failure point. [IEC 60076-7:2018 publication page](https://webstore.iec.ch/en/publication/34351)

## Planning projects cannot be backfilled into the 2024 inventory

EDS separately labels future construction and reconstruction. Examples include
a 31.5-MVA 110/20-kV addition at Novi Sad 4, a third 31.5-MVA unit at Novi Sad 5,
and a third 31.5-MVA unit at Novi Sad 9. The plan gives project windows extending
to 2028 or 2029. These rows prove planned equipment size and voltage ratio, but
not that the equipment was installed or available in the 2024 base year. [EDS
development plan, pp. 174–177](https://elektrodistribucija.rs/regulativa/propisi/dokumenta/Plan_razvoja_2025_2034.pdf#page=174)

The plan's narrative is especially clear for Novi Sad 4: the existing station
entered service with two 63-MVA 110/35-kV transformers, while the 31.5-MVA
110/20-kV transformer is described as a planned addition with completion in
2029. [EDS development plan, pp. 266–267](https://elektrodistribucija.rs/regulativa/propisi/dokumenta/Plan_razvoja_2025_2034.pdf#page=266)

## Claims the project can make

The public evidence supports saying that the named voltage ratios and aggregate
installed capacities above are transcribed from an EDS 2024 inventory. It also
supports comparing modeled loading with the operator's reported 2024 utilization
as a reasonableness check, provided the different demand and topology scope is
stated.

The project should continue to describe the network as a synthetic planning
proxy. Exact feeder routes, most upstream associations, block-level 20/0.4-kV
ratings, asset-specific protection behavior, and all failure thresholds remain
unverified. A result such as “transformer loading exceeded 100%” means “the
scenario crossed the configured nameplate-based model boundary”; it must not be
reported as a prediction that a real Novi Sad transformer would fail.

## Source scope and freshness

The principal inventory is the EDS *Plan razvoja distributivnog sistema
2025–2034*, whose station tables use base year 2024. The document covers the
large DP Novi Sad distribution area, while its station rows separately identify
the ED Novi Sad branch. Regional totals must not be presented as city totals.
The accompanying EDS *Plan investicija 2025–2027* is useful as a cross-check for
planned works, but investment rows remain planned-project evidence rather than
as-built commissioning records. [EDS investment plan
2025–2027](https://www.elektrodistribucija.rs/regulativa/propisi/dokumenta/Plan_investicija_2025_2027.pdf)

No newer authoritative, public, asset-level inventory or protection/operating
limit register was located in this audit. Absence from the public search is not
evidence that EDS lacks such records; it means the project cannot use them as
public validation without obtaining and recording an authoritative release.
