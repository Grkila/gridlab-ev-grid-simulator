const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
(async () => {
  const root = path.resolve(__dirname, '..');
  const {buildRoadPath,sampleRoadPath} = await import(pathToFileURL(path.join(root,'web/src/presentation/roadMotion.ts')).href);
  const geography = JSON.parse(fs.readFileSync(path.join(root,'web/public/presentation/geography.json'),'utf8'));
  const segmentKey = (a,b) => [a.join(','),b.join(',')].sort().join('|');
  const roadSegments = new Set();
  for (const road of geography.roads) for (let i=1;i<road.length;i++) roadSegments.add(segmentKey(road[i-1],road[i]));
  assert.equal(geography.carPaths.length,36);
  let samples=0;
  for (const coordinates of geography.carPaths) {
    assert.deepEqual(coordinates[0],coordinates.at(-1),'A closed route must not teleport at its loop boundary');
    for(let i=1;i<coordinates.length;i++) assert(roadSegments.has(segmentKey(coordinates[i-1],coordinates[i])),'Every vehicle segment must be an exported street segment');
    const road=buildRoadPath(coordinates);
    for(let i=0;i<180;i++){
      const p=sampleRoadPath(road,road.length*i/180);
      const nearest=Math.min(...road.points.slice(1).map((b,index)=>{
        const a=road.points[index],dx=b[0]-a[0],dz=b[1]-a[1];
        const t=Math.max(0,Math.min(1,((p.x-a[0])*dx+(p.z-a[1])*dz)/(dx*dx+dz*dz)));
        return Math.hypot(p.x-a[0]-t*dx,p.z-a[1]-t*dz);
      }));
      assert(nearest<1e-8,'Interpolation left the road');
      assert(Number.isFinite(p.heading));samples++;
    }
    const before=sampleRoadPath(road,road.length-1e-7), after=sampleRoadPath(road,road.length+1e-7);
    assert(Math.hypot(before.x-after.x,before.z-after.z)<3e-7,'Loop seam is discontinuous');
  }
  const report={roads:geography.roads.length,closedPaths:36,samples,sourceSnapshot:geography.roadSnapshotSha256,verdict:'passed'};
  fs.writeFileSync(path.join(root,'artifacts/playground/evidence/presentation/roads-verification.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
})().catch(error=>{console.error(error);process.exitCode=1;});
