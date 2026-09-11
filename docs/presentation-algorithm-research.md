# Algoritmi, istraživanja i industrijska paralela

Provereno 11. septembra 2026. Implementacije su planerske adaptacije; rezultat rada iz literature nije automatski rezultat naše platforme.

| Algoritam | Mehanizam i poreklo | Status u projektu |
| --- | --- | --- |
| Immediate | Punjenje odmah po dolasku; inženjerska referenca. | Izvršen u stvarnom demou i studijama. |
| Fixed delay | Zajednički zadati početak; inženjerska referenca. | Izvršen; može stvoriti novi vrh. |
| Randomized delay | Počeci raspoređeni pomoću fiksiranog semena; inženjerska referenca. | Izvršen; niži vrh u navedenom kućnom scenariju. |
| Capacity-aware | Naša heuristika: rokovi odlaska, raspoloživi budžeti i AC provera. | Izvršen; prednost u navedenom poređenju dnevnog broja vozila. |
| Smoothed LLF | Prioritet vozilima sa manje vremenske rezerve; [Chen et al. (2021), Smoothed Least-Laxity-First Algorithm for EV Charging](https://arxiv.org/abs/2102.08610). | Dodati mrežni budžeti, AC provera i LLF rezervni postupak. Teorijske garancije rada nisu dokazane za naš model. |
| Valley filling / ODC | Iterativno usaglašavanje rasporeda radi ravnomernijeg opterećenja; [Gan, Topcu & Low, Optimal Decentralized Protocol for Electric Vehicle Charging](https://smart.caltech.edu/papers/ContinuousEVCharging.pdf). | Ograničene simultane proksimalne iteracije, kauzalna prognoza, samo povezana vozila i kapacitetska projekcija. |
| Voltage-responsive | Lokalni napon kao signal; [Cardona Ruiz, López & Rider (2018), Decentralized electric vehicles charging coordination using only local voltage magnitude measurements](https://doi.org/10.1016/j.epsr.2018.04.003). | Naša droop heuristika sa prethodnim naponom i centralnom zaštitom; nije reprodukcija trofaznog postupka. |
| MPC | Prediktivno ponovno planiranje; [Lee et al., Adaptive Charging Networks: A Framework for Smart Electric Vehicle Charging](https://arxiv.org/abs/2012.02636). | Raniji LP prototip sa LLF rezervnim postupkom; povučen iz aktivnog poređenja. |
| Binary REINFORCE | Gradijent očekivane nagrade; [Williams (1992), Simple statistical gradient-following algorithms for connectionist reinforcement learning](https://link.springer.com/article/10.1007/BF00992696). | Sopstveni on/off prototip i sačuvani trening; zahteva izdvojenu evaluaciju. |
| Continuous PPO | Policy-gradient porodica; [Schulman et al. (2017), Proximal Policy Optimization Algorithms](https://arxiv.org/abs/1707.06347). | Snaga po čvoru, kampanje i provere. Animirani prikaz koristi ilustrativne podatke; nema dokaza ukupne nadmoći. |

Sačuvani benchmark sa sedam ne-MPC strategija ima neuspešnu završnu proveru identiteta implementacije. Njegove ćelije ostaju istorijska evidencija, bez konačnog ukupnog ranga. Stvarni pripremljeni demo sadrži četiri početne politike. Detalji implementacija: `src/mvgrid/novi_sad/playground/strategies.py`, `valley_odc.py`, `smoothed_llf.py`, `rl.py` i `continuous_ppo.py`.

## Schneider Electric: korisna paralela

[Zvanični vodič za EcoStruxure EV Charging Expert](https://productinfo.se.com/emobility-infrastructure-commissioning/evsolcg001-emobility-infrastructure-commissioning-guide/English/BM_EVSOLCG001EN_eMobility_Infrastructure_Commissioning_Guide_DD01016549.xml/$/EVSOLCG001EN_EV_OffersCommissioningTools_DD01022596) opisuje raspodelu raspoložive snage punjačima, statičku/dinamičku alokaciju i upravljanje prema vremenskim tarifama. [Stranica proizvoda](https://www.se.com/ie/en/product-range/62159-ecostruxure-ev-charging-expert/) opisuje upravljanje opterećenjem infrastrukture punjenja.

Naša konceptualna paralela: oba pristupa prilagođavaju punjenje energetskim ograničenjima. Valley filling planira raspored preko vremenskog horizonta; dinamička alokacija na lokaciji prilagođava raspoloživu snagu punjačima i srodna je i capacity-aware pristupu. Javna dokumentacija ne potvrđuje da Schneider koristi ODC ili našu implementaciju. Proizvod nismo implementirali niti benchmarkovali.
