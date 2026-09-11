import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import type { Scene } from './slides';
import { projectCoordinate as project, buildRoadPath, sampleRoadPath } from './roadMotion';
type Geography = {points: number[][]; routes: number[][][]; roads: number[][][]; carPaths: number[][][]; stations: {name:string;lon:number;lat:number}[]};
const poses: Record<Scene, number[]> = {city:[10,10,14],stress:[7,7,12],grid:[1,18,8],district:[-5,7,11],calm:[12,12,16]};

export function City({scene, reduced, visible}:{scene:Scene; reduced:boolean; visible:boolean}) {
  const host = useRef<HTMLDivElement>(null);
  const state = useRef({scene,reduced,visible}); state.current = {scene,reduced,visible};
  const [fallback,setFallback] = useState(false);
  const [geo,setGeo] = useState<Geography>();
  useEffect(() => {
    const controller = new AbortController();
    fetch('/presentation/geography.json',{signal:controller.signal}).then(r=>{if(!r.ok)throw new Error('Missing geography');return r.json();}).then(setGeo).catch(e=>{if(e.name!=='AbortError')setFallback(true);});
    return ()=>controller.abort();
  },[]);
  useEffect(() => {
    if (!geo || !host.current) return;
    const container=host.current;
    let renderer: THREE.WebGLRenderer;
    try {renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'low-power'});} catch {setFallback(true);return;}
    renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));
    renderer.setClearColor(0x071a19,0);
    container.appendChild(renderer.domElement);
    const world=new THREE.Scene();
    world.fog=new THREE.FogExp2(0x071a19,0.014);
    const camera=new THREE.PerspectiveCamera(38,1,0.1,150);
    camera.position.set(...poses[state.current.scene] as [number,number,number]);
    world.add(new THREE.AmbientLight(0xb6ffe8,1.8));
    const key=new THREE.DirectionalLight(0xe7fff8,3);key.position.set(8,20,12);world.add(key);
    const rim=new THREE.DirectionalLight(0x40ffc3,3);rim.position.set(-15,8,-8);world.add(rim);
    const base=new THREE.Mesh(new THREE.BoxGeometry(31,0.3,28),new THREE.MeshStandardMaterial({color:0x0d2927,roughness:0.8,metalness:0.25}));
    base.position.y=-0.25; world.add(base);
    const grid=new THREE.GridHelper(32,32,0x23534c,0x163831);grid.position.y=-0.08;world.add(grid);
    const boxGeometry=new THREE.BoxGeometry(1,1,1);
    const buildings=new THREE.InstancedMesh(boxGeometry,new THREE.MeshStandardMaterial({color:0x70b4a3,roughness:0.5,metalness:0.28}),geo.points.length);
    const matrix=new THREE.Object3D();
    geo.points.forEach(([lon,lat,power],i)=>{const [x,z]=project(lon,lat);const height=0.08+Math.min(0.9,Math.sqrt(power)*0.5);matrix.position.set(x,height/2,z);matrix.scale.set(0.065,height,0.065);matrix.updateMatrix();buildings.setMatrixAt(i,matrix.matrix);buildings.setColorAt(i,new THREE.Color(i%11===0?0xb6ffd5:0x477e72));});
    world.add(buildings);
    const roadPositions:number[]=[];
    (geo.roads || []).forEach(road=>road.slice(1).forEach((point,i)=>{
      const a=project(road[i][0],road[i][1]), b=project(point[0],point[1]);
      roadPositions.push(a[0],0.055,a[1],b[0],0.055,b[1]);
    }));
    const roadGeometry=new THREE.BufferGeometry();roadGeometry.setAttribute('position',new THREE.Float32BufferAttribute(roadPositions,3));
    world.add(new THREE.LineSegments(roadGeometry,new THREE.LineBasicMaterial({color:0x8db9aa,transparent:true,opacity:0.52})));
    const positions:number[]=[];
    geo.routes.forEach(route=>route.slice(1).forEach((p,i)=>{const [x,z]=project(...route[i].slice(0,2) as [number,number]);const [xx,zz]=project(...p.slice(0,2) as [number,number]);positions.push(x,0.04,z,xx,0.04,zz);}));
    const lineGeometry=new THREE.BufferGeometry();lineGeometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
    const lineMaterial=new THREE.LineBasicMaterial({color:0x69deb3,transparent:true,opacity:0.62});
    world.add(new THREE.LineSegments(lineGeometry,lineMaterial));
    const beacons:THREE.Mesh[]=[];
    geo.stations.forEach(s=>{const [x,z]=project(s.lon,s.lat);const stem=new THREE.Mesh(new THREE.CylinderGeometry(0.035,0.035,1.2,6),new THREE.MeshBasicMaterial({color:0xe7ffc9}));stem.position.set(x,0.6,z);world.add(stem);const ring=new THREE.Mesh(new THREE.TorusGeometry(0.24,0.025,6,32),new THREE.MeshBasicMaterial({color:0xbefb83}));ring.rotation.x=-Math.PI/2;ring.position.set(x,0.16,z);world.add(ring);beacons.push(ring);});
    // Closed paths preserve the cached OSM graph's directed road connectivity.
    const paths=(geo.carPaths || []).map(buildRoadPath).filter(path=>path.length>0.1);
    const cars:THREE.Group[]=[];
    for(let i=0;i<paths.length;i++){
      const car=new THREE.Group();
      const body=new THREE.Mesh(new THREE.BoxGeometry(0.19,0.08,0.36),new THREE.MeshStandardMaterial({color:0xffef91,emissive:0xffd85c,emissiveIntensity:1.3,metalness:0.3,roughness:0.35}));body.position.y=0.09;car.add(body);
      const cabin=new THREE.Mesh(new THREE.BoxGeometry(0.145,0.07,0.17),new THREE.MeshStandardMaterial({color:0x102c3f}));cabin.position.set(0,0.16,-0.025);car.add(cabin);car.scale.setScalar(1.15);world.add(car);cars.push(car);
      const halo=new THREE.Mesh(new THREE.RingGeometry(.22,.31,32),new THREE.MeshBasicMaterial({color:0xffdf76,transparent:true,opacity:.7,side:THREE.DoubleSide}));halo.rotation.x=-Math.PI/2;halo.position.y=.015;car.add(halo);
      const charging=new THREE.Mesh(new THREE.CylinderGeometry(.04,.04,.8,8),new THREE.MeshBasicMaterial({color:0x72fff0,transparent:true,opacity:.9}));charging.position.set(.24,.4,0);charging.visible=false;car.add(charging);
      car.userData={distance:paths[i].length*((i*.618)%1),halo,charging,body};
    }
    const target=new THREE.Vector3();
    let raf=0, elapsed=0, previous=performance.now();
    const resize=()=>{const {width,height}=container.getBoundingClientRect();renderer.setSize(width,height,false);camera.aspect=width/Math.max(height,1);camera.updateProjectionMatrix();};
    const observer=new ResizeObserver(resize);observer.observe(container);resize();
    const onLost=(event:Event)=>{event.preventDefault();setFallback(true);};renderer.domElement.addEventListener('webglcontextlost',onLost);
    const animate=(now:number)=>{
      raf=requestAnimationFrame(animate);
      const dt=Math.min((now-previous)/1000,0.05);previous=now;
      if(document.hidden || !state.current.visible)return;
      const {scene:mode,reduced:still}=state.current;
      if(!still)elapsed+=dt;
      world.rotation.y=still?0:Math.sin(elapsed*0.1)*0.20;
      world.position.x=still?0:Math.sin(elapsed*.08)*.35;
      target.set(...poses[mode] as [number,number,number]);
      camera.position.lerp(target,still?1:1-Math.exp(-dt*2.8));camera.lookAt(0,0,0);
      lineMaterial.color.set(mode==='stress'?0xf1a274:0x69deb3);
      lineMaterial.opacity=mode==='grid'?0.95:0.62;
      beacons.forEach((ring,i)=>{const pulse=still?1:1+Math.sin(elapsed*1.7+i)*0.16;ring.scale.setScalar(pulse);});
      cars.forEach((car,i)=>{
        const phase=(elapsed+i*2.3)%24, charging=phase>=17;
        if(!still&&!charging)car.userData.distance+=dt*(.18+(i%5)*.018);
        const point=sampleRoadPath(paths[i],car.userData.distance);
        car.position.set(point.x,.07,point.z);car.rotation.y=point.heading;
        car.userData.charging.visible=charging;
        car.userData.halo.material.color.set(charging?0x72fff0:0xffdf76);
        car.userData.halo.scale.setScalar(charging&&!still?1.25+Math.sin(elapsed*4)*.3:1);
        car.userData.body.material.emissive.set(charging?0x39ffe0:0xffd85c);
      });
      renderer.render(world,camera);
    };raf=requestAnimationFrame(animate);
    return()=>{cancelAnimationFrame(raf);observer.disconnect();renderer.domElement.removeEventListener('webglcontextlost',onLost);world.traverse(object=>{const mesh=object as THREE.Mesh;if(mesh.geometry)mesh.geometry.dispose();if(mesh.material)(Array.isArray(mesh.material)?mesh.material:[mesh.material]).forEach(m=>m.dispose());});renderer.dispose();renderer.domElement.remove();};
  },[geo]);
  return <div className="city-host" ref={host} aria-label="Stilizovan 3D model Novog Sada; vozila prate ulice iz OSM podataka">
    {fallback && <svg className="city-fallback" viewBox="-17 -15 34 30" role="img" aria-label="Statički prikaz mape">
      {geo?.routes.filter((_,i)=>i%3===0).map((r,i)=><polyline key={i} points={r.map(p=>project(p[0],p[1]).join(',')).join(' ')} fill="none" stroke="#77dcb9" strokeWidth=".025"/>)}
      {geo?.points.map((p,i)=><circle key={i} cx={project(p[0],p[1])[0]} cy={project(p[0],p[1])[1]} r=".035" fill="#ddf99d"/>)}
      {!geo && <text x="0" y="0" textAnchor="middle" fill="#ddf99d" fontSize="1">Mapa nije dostupna</text>}
    </svg>}
  </div>;
}
