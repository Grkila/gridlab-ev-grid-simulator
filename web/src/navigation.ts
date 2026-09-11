import { useEffect, useState } from 'react';

export const pageLabels: Record<string, string> = {
  overview: 'Overview', experiments: 'Experiments', results: 'Results', network: 'Network',
  strategies: 'Strategies', benchmarks: 'Benchmarks', rl: 'Training',
};

export function readLocation() {
  const params = new URLSearchParams(window.location.search);
  const page = params.get('view') || 'overview';
  return { view: Object.hasOwn(pageLabels, page) ? page : 'overview', runId: params.get('run') || undefined };
}

export function pageHref(view: string, runId?: string) {
  const url = new URL(window.location.href);
  url.searchParams.set('view', view);
  if (runId) url.searchParams.set('run', runId);
  else url.searchParams.delete('run');
  url.hash = '';
  return `${url.pathname}${url.search}`;
}

export function useNavigation() {
  const [location, setLocation] = useState(readLocation);
  useEffect(() => {
    const restore = () => setLocation(readLocation());
    window.addEventListener('popstate', restore);
    restore(); // A presentation cue can arrive between first render and subscription.
    return () => window.removeEventListener('popstate', restore);
  }, []);
  const navigate = (view: string, runId?: string) => {
    const href = pageHref(view, runId);
    if (href !== `${window.location.pathname}${window.location.search}`) window.history.pushState(null, '', href);
    setLocation({ view, runId });
    window.scrollTo(0, 0);
  };
  return { ...location, navigate };
}
