/** Retired controllers stay in immutable files but are excluded from app views. */
export function visibleControllers(value: any): any {
  if (Array.isArray(value)) return value
    .filter(x => x !== 'mpc' && !(x && typeof x === 'object' && (x.strategy === 'mpc' || x.id === 'mpc')))
    .map(visibleControllers)
    .filter(x => !(x && typeof x === 'object' && Array.isArray(x.strategies) && x.strategies.length === 0));
  if (!value || typeof value !== 'object') return value;
  const result: any = Object.fromEntries(Object.entries(value).map(([k, v]) => [k, visibleControllers(v)]));
  if (result.job && Array.isArray(result.rows) && Array.isArray(result.job.strategies)) {
    result.job.total_rows = result.job.strategies.length * 10;
    result.job.completed_rows = result.rows.length;
    if (result.job.current_strategy === 'mpc') result.job.current_strategy = '';
  }
  return result;
}
