# Prvo pitanje: dnevna dopuna i cela baterija

Reprodukcija: `python scripts/presentation_daily_energy.py`.
Izvor je zamrznuti profil `artifacts/challenge-study-v2/fixtures/2025-06-1-as_supplied-normal.json`.
JSON sa SHA-256 izvora i proračunom: `artifacts/playground/evidence/presentation/daily-energy.json`.

## Energetska gornja granica za 24 sata

Jun 2025, reprezentativan dan: osnovna energija grada sa gubicima je 2.565,5 MWh.
Posle razdvajanja osnovnih gubitaka, neto potrošnja je 2.537,072 MWh.
Zamrznuta pretpostavka dopušta ukupno 120 MW na zbirnom NN nivou, gde se računa
50% osnovnog neto opterećenja i 100% EV punjenja.

E_EV = zbir(120.000 kW − 0,5 × P_osnovno_neto(t)) × 0,25 h
= 1.611.464,059 kWh za punjače kroz 96 koraka.
Preostala snaga je pozitivna u svakom koraku. Uz efikasnost punjenja 90%,
u baterije može da se prenese najviše 1.450.317,653 kWh prema ovom izdvojenom ograničenju.

| Cela baterija | Energija iz punjača po vozilu | Najviše celih baterija | Vreme na 7,4 kW |
| --- | --- | --- | --- |
| 40 kWh | 44,444 kWh | 36.257 | 6,006 h |
| 60 kWh | 66,667 kWh | 24.171 | 9,009 h |
| 80 kWh | 88,889 kWh | 18.128 | 12,012 h |

Ovo je idealna energetska gornja granica, ne simulaciono potvrđen broj vozila.
Pretpostavlja se mogućnost korišćenja prostora tokom svih 24 sata. Zanemareni su
raspoloživost vozila, lokalna ograničenja, dodatni mrežni gubici i AC uslovi.
Model koristi konstantnu snagu/efikasnost; nema usporavanja punjenja pri visokom SoC.
Zato prikazano vreme predstavlja idealni minimum u modelu.
Javni boravak od 3–4 sata u postojećem whole_day profilu ne može ispuniti zahtev
od 60 kWh uz 7,4 kW i 90% efikasnosti. Promena tog profila zahteva zasebnu simulaciju.

## Zašto postoje i brojevi 48.000 i 65.544?

48.000 dnevnih učesnika u završenoj studiji traži po **14 kWh**, ukupno 672 MWh
u baterijama i 746,667 MWh iz punjača. Završni horizont je 33 sata da obuhvati
odlaske sledećeg jutra; to nije 33 sata neprekidne dostupnosti svakog vozila.
Agregacija zadržava 48.000 vozila i njihovu energiju, a predstavlja ih kroz grupe
sa istim čvorom, vremenima i parametrima:

| Seme | Grupe | Sačuvani rezultat |
| --- | --- | --- |
| 61001 | 637 | ac36975e1151a5dfa832 |
| 61002 | 633 | 11eac23f4686861c8449 |
| 61003 | 623 | 23de8f88e1540a3def29 |

Istorijski benchmark `bench-c0c965da89ab4b2d`, red `city_max/least_laxity_first`,
beleži 65.544 pri 14 kWh: 917,616 MWh, energetski ekvivalent 15.293,6 baterija
od 60 kWh. To nije dokaz da isti raspored može da napuni toliko celih baterija.
Benchmark koristi druge uslove od završene direktne studije i završio je sa
statusom `failed`: `Implementation changed during benchmark; start a fresh run.`
Njegovi redovi ostaju privremena evidencija. Prekinuti whole_day benchmark
`bench-1682223431ba4678` ima 42/70 redova, bez završenog kapacitetskog pretraživanja.
Ni jedan nije ponovo pokrenut radi ove izmene slajda.
