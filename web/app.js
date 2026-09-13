import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const host=document.querySelector('#canvas-host');
const loading=document.querySelector('#loading');
const fallback=document.querySelector('#fallback');
const buttons=[...document.querySelectorAll('#controls button')];
const spinButton=document.querySelector('#spin');
const gearButton=document.querySelector('#gear');
let renderer,scene,camera,controls,aircraft,box,center,spinning=false,currentView='perspective',lastTime=0;
let propellers=[],gear=[],fitPoints=[];

function fail(error){
  console.error('模型载入失败',error);
  loading.textContent='三维展示暂不可用，可查看预览图或下载模型。';
  loading.hidden=false;fallback.classList.remove('loaded');
  document.querySelector('#retry').hidden=false;
  buttons.forEach(b=>b.disabled=true);
}
document.querySelector('#retry').addEventListener('click',()=>location.reload());

function fitView(view=currentView){
  if(!box)return;
  currentView=view;
  const directions={perspective:new THREE.Vector3(-16,10,21),side:new THREE.Vector3(0,0,1),top:new THREE.Vector3(0,1,0),front:new THREE.Vector3(-1,0,0)};
  const d=directions[view].normalize();
  camera.up.set(0,1,0);
  if(view==='top')camera.up.set(0,0,-1);
  const right=new THREE.Vector3().crossVectors(camera.up,d).normalize();
  const up=new THREE.Vector3().crossVectors(d,right).normalize();
  let xmin=Infinity,xmax=-Infinity,ymin=Infinity,ymax=-Infinity;
  for(const p of fitPoints){const x=p.dot(right),y=p.dot(up);xmin=Math.min(xmin,x);xmax=Math.max(xmax,x);ymin=Math.min(ymin,y);ymax=Math.max(ymax,y);}
  const width=xmax-xmin,height=ymax-ymin;
  const target=center.clone().addScaledVector(right,(xmin+xmax)/2-center.dot(right)).addScaledVector(up,(ymin+ymax)/2-center.dot(up));
  const aspect=host.clientWidth/Math.max(host.clientHeight,1);
  const viewHeight=Math.max(height,width/aspect)*1.23;
  camera.left=-viewHeight*aspect/2;camera.right=viewHeight*aspect/2;
  camera.top=viewHeight/2;camera.bottom=-viewHeight/2;
  camera.zoom=1;camera.position.copy(target).addScaledVector(d,40);
  camera.lookAt(target);camera.updateProjectionMatrix();controls.target.copy(target);controls.update();controls.saveState();
  document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===view)));
}

function resize(){
  if(!renderer)return;
  renderer.setSize(host.clientWidth,host.clientHeight,false);
  fitView(currentView);
}

function animate(time){
  const delta=Math.min((time-lastTime)/1000,.05);lastTime=time;
  if(spinning)propellers.forEach(p=>p.rotation.x=(p.rotation.x+delta*Math.PI*5)%(Math.PI*2));
  controls.update();renderer.render(scene,camera);
}

try{
  renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'high-performance'});
  renderer.setPixelRatio(Math.min(devicePixelRatio,2));
  renderer.setSize(host.clientWidth,host.clientHeight,false);
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.AgXToneMapping;renderer.toneMappingExposure=.9;
  renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFShadowMap;
  renderer.domElement.tabIndex=0;renderer.domElement.setAttribute('aria-label','北京一号三维模型。拖动旋转；也可使用下方视角、缩放与复位按钮。');
  host.append(renderer.domElement);
  renderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();renderer.setAnimationLoop(null);fail(new Error('WebGL context lost'));});
  scene=new THREE.Scene();camera=new THREE.OrthographicCamera(-12,12,8,-8,.1,180);
  controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.dampingFactor=.08;
  controls.enablePan=false;controls.minZoom=.55;controls.maxZoom=4;
  controls.maxPolarAngle=Math.PI*.94;
  const pmrem=new THREE.PMREMGenerator(renderer);const room=new RoomEnvironment();
  const environment=pmrem.fromScene(room,.04);scene.environment=environment.texture;room.dispose();pmrem.dispose();
  scene.add(new THREE.HemisphereLight(0xf1f3ff,0xb7aea0,.7));
  const key=new THREE.DirectionalLight(0xfff8ed,1.3);key.position.set(-3,18,4);key.castShadow=true;
  key.shadow.mapSize.set(2048,2048);Object.assign(key.shadow.camera,{left:-14,right:14,top:14,bottom:-14,near:.5,far:60});
  key.shadow.bias=-.0002;key.shadow.normalBias=.03;key.shadow.radius=4;scene.add(key);
  const fill=new THREE.DirectionalLight(0xe7efff,.6);fill.position.set(4,6,-10);scene.add(fill);
  const ground=new THREE.Mesh(new THREE.PlaneGeometry(100,100),new THREE.ShadowMaterial({color:0x6c685f,opacity:.08}));
  ground.rotation.x=-Math.PI/2;ground.position.y=-.02;ground.receiveShadow=true;scene.add(ground);
  new ResizeObserver(resize).observe(host);
  const gltf=await new GLTFLoader().loadAsync('../models/beijing-one.glb',progress=>{
    if(progress.total)loading.textContent=`正在载入三维模型… ${Math.round(progress.loaded/progress.total*100)}%`;
  });
  aircraft=gltf.scene;scene.add(aircraft);aircraft.updateMatrixWorld(true);
  aircraft.traverse(o=>{
    if(o.isMesh){o.castShadow=true;o.receiveShadow=true;const positions=o.geometry.attributes.position;for(let i=0;i<positions.count;i++)fitPoints.push(new THREE.Vector3().fromBufferAttribute(positions,i).applyMatrix4(o.matrixWorld));}
    if(o.name==='Propeller_L'||o.name==='Propeller_R')propellers.push(o);
    if(o.name.startsWith('Gear_'))gear.push(o);
  });
  if(propellers.length!==2)throw new Error('Missing propeller nodes');
  box=new THREE.Box3().setFromObject(aircraft);center=box.getCenter(new THREE.Vector3());
  fitView();renderer.render(scene,camera);
  fallback.classList.add('loaded');loading.hidden=true;buttons.forEach(b=>b.disabled=false);
  document.querySelector('#viewer').setAttribute('aria-label','北京一号三维模型已载入');
  renderer.setAnimationLoop(animate);
  document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>fitView(b.dataset.view)));
  spinButton.addEventListener('click',()=>{spinning=!spinning;spinButton.setAttribute('aria-pressed',String(spinning));document.querySelector('#spin-label').textContent=spinning?'暂停螺旋桨':'播放螺旋桨';spinButton.querySelector('.play-icon').textContent=spinning?'Ⅱ':'▷';});
  gearButton.addEventListener('click',()=>{const visible=gearButton.getAttribute('aria-pressed')!=='true';gear.forEach(o=>o.visible=visible);gearButton.setAttribute('aria-pressed',String(visible));});
  document.querySelector('#zoom-in').addEventListener('click',()=>{camera.zoom=Math.min(controls.maxZoom,camera.zoom*1.2);camera.updateProjectionMatrix();});
  document.querySelector('#zoom-out').addEventListener('click',()=>{camera.zoom=Math.max(controls.minZoom,camera.zoom/1.2);camera.updateProjectionMatrix();});
  document.querySelector('#reset').addEventListener('click',()=>fitView('perspective'));
  document.addEventListener('visibilitychange',()=>{if(document.hidden){renderer.setAnimationLoop(null);}else{lastTime=performance.now();renderer.setAnimationLoop(animate);}});
}catch(error){fail(error);}
