export const chargingKinds = ['residential', 'workplace', 'public'] as const;
export type ChargingKind = typeof chargingKinds[number];
export type ChargingMix = Record<ChargingKind, number>;

export function mixPercentages(mix: ChargingMix): ChargingMix {
  const values = chargingKinds.map(k => Number.isFinite(mix?.[k]) ? Math.max(0, mix[k]) : 0);
  const total = values.reduce((a,b) => a+b,0);
  if (!total) return { residential: 70, workplace: 20, public: 10 };
  const exact = values.map(v => 100*v/total);
  const rounded = exact.map(Math.floor);
  const order = [0,1,2].sort((a,b) => (exact[b]-rounded[b])-(exact[a]-rounded[a]));
  for (let left=100-rounded.reduce((a,b)=>a+b,0),i=0; left>0; left--,i++) rounded[order[i%3]]++;
  return Object.fromEntries(chargingKinds.map((k,i)=>[k,rounded[i]])) as ChargingMix;
}

export function redistributeMix(mix: ChargingMix, changed: ChargingKind, percentage: number): ChargingMix {
  const current = mixPercentages(mix);
  const value = Math.max(0,Math.min(100,Math.round(Number.isFinite(percentage) ? percentage : current[changed])));
  const others = chargingKinds.filter(k=>k!==changed);
  const remaining = 100-value;
  const otherTotal = current[others[0]]+current[others[1]];
  const first = Math.round(remaining*(otherTotal ? current[others[0]]/otherTotal : .5));
  return { ...mix, [changed]: value/100, [others[0]]: first/100, [others[1]]: (remaining-first)/100 };
}
