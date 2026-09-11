import { useEffect, useState } from 'react';
// This bridge only changes presentation UI. It cannot start a worker or send chat.
export type AppCue = { view: string; step?: number; section?: string; chat?: boolean; chatPrompt?: string; runId?: string; reducedMotion?: boolean };
export const cueEvent = 'gridlab-presentation-cue';
let lastCue: AppCue | undefined;
export function currentCue() { return lastCue; }
export function usePresentationCue() {
  const [cue, setCue] = useState(lastCue);
  useEffect(() => {
    const listener = (event: Event) => setCue((event as CustomEvent<AppCue>).detail);
    window.addEventListener(cueEvent, listener);
    setCue(lastCue);
    return () => window.removeEventListener(cueEvent, listener);
  }, []);
  return cue;
}
export function installPresentationBridge() {
  if (window.parent === window || new URLSearchParams(location.search).get('present') !== '1') return;
  document.documentElement.classList.add('presentation-embedded');
  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.source !== window.parent || event.data?.type !== cueEvent) return;
    const cue = event.data.cue as AppCue;
    if (!cue || !['overview','experiments','network','results','strategies','benchmarks','rl'].includes(cue.view)) return;
    lastCue = cue;
    const url = new URL(location.href);
    url.searchParams.set('view', cue.view);
    if (cue.runId) url.searchParams.set('run', cue.runId); else url.searchParams.delete('run');
    history.replaceState(null, '', url);
    window.dispatchEvent(new PopStateEvent('popstate'));
    window.dispatchEvent(new CustomEvent(cueEvent, { detail: cue }));
    window.scrollTo(0, 0);
    window.parent.postMessage({ type: 'gridlab-cue-applied', view: cue.view }, location.origin);
  });
  window.addEventListener('keydown', event => {
    if ((event.target as HTMLElement).closest('input,textarea,select,[contenteditable="true"],.leaflet-container,[role="slider"],[role="tablist"]')) return;
    if (['ArrowRight','ArrowLeft','PageDown','PageUp','Escape'].includes(event.key)) {
      event.preventDefault();
      window.parent.postMessage({ type: 'gridlab-presentation-key', key: event.key }, location.origin);
    }
  });
  window.parent.postMessage({ type: 'gridlab-presentation-ready' }, location.origin);
}
