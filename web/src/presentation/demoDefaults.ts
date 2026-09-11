// Real saved evidence. Missing records fall back to another completed run.
export const presentationRunId='run-3484553ec8bb4a5f';
export function preferredDemoRun<T extends {run_id:string;status:string}>(runs:T[]) {
  return runs.find(run=>run.run_id===presentationRunId&&run.status==='completed') || runs.find(run=>run.status==='completed');
}

