import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { createWorld, scenePresets } from './scenes.js';

const $=selector=>document.querySelector(selector);
const host=$('#canvas-host'),loading=$('#loading'),fallback=$('#fallback');
const readyButtons=[...document.querySelectorAll('#controls button,.scene-buttons button,#play,#open-controls')];
const motionPreference=matchMedia('(prefers-reduced-motion: reduce)');
let renderer,scene,camera,controls,aircraft,world,center;
let currentScene='night',currentView='perspective',playing=!motionPreference.matches,spinning=false;
let lastTime=0,elapsed=0,cameraTransition=null,homeFrame=null,switchTimer=null,switching=false,failed=false;
const fitPoints=[],propellers=[],gear=[];

function fail(error){
  failed=true;console.error('三维展示载入失败',error);
  if(renderer)renderer.setAnimationLoop(null);
  loading.textContent='三维展示暂不可用，可查看预览图或下载模型。';
  loading.hidden=false;fallback.classList.remove('loaded');$('#retry').hidden=false;
  readyButtons.forEach(button=>button.disabled=true);
}
$('#retry').addEventListener('click',()=>location.reload());

// 资料与控制面板使用原生 dialog，支持 Escape、焦点约束和关闭后焦点恢复。
for(const [buttonId,dialogId] of [['#open-info','#info-dialog'],['#open-controls','#controls-dialog']]){
  const button=$(buttonId),dialog=$(dialogId);
  button.addEventListener('click',()=>dialog.showModal());
  dialog.querySelector('[data-close]').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('click',event=>{
    if(event.target!==dialog)return;
    const rect=dialog.getBoundingClientRect();
    if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)dialog.close();
  });
}
const fullscreenButton=$('#fullscreen');
if(!document.fullscreenEnabled)fullscreenButton.hidden=true;
fullscreenButton.addEventListener('click',async()=>{
  try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}
  catch(error){console.warn('全屏未开启',error);}
});
document.addEventListener('fullscreenchange',()=>fullscreenButton.setAttribute('aria-label',document.fullscreenElement?'退出全屏':'进入全屏'));

function syncPlayback(){
  $('#play').setAttribute('aria-pressed',String(playing));
  $('#play').setAttribute('aria-label',playing?'暂停场景动画':'播放场景动画');
  $('#play-symbol').innerHTML=playing?'<path d="M9 6v12M15 6v12"/>':'<path d="m9 5 10 7-10 7Z"/>';
  if(controls)controls.autoRotate=playing&&currentView==='perspective'&&currentScene==='night';
}
function syncSpin(){
  $('#spin').setAttribute('aria-pressed',String(spinning));
  $('#spin').textContent=spinning?'暂停螺旋桨':'播放螺旋桨';
}
function setPlaying(value){playing=value;if(!value){spinning=false;syncSpin();}syncPlayback();}
syncPlayback();
motionPreference.addEventListener('change',event=>{
  if(event.matches){setPlaying(false);spinning=false;syncSpin();}
  if(controls){controls.enableDamping=!event.matches;controls.update();}
});

function frameFor(view){
  const directions={perspective:new THREE.Vector3(...scenePresets[currentScene].direction),side:new THREE.Vector3(0,.08,1),top:new THREE.Vector3(0,1,0),front:new THREE.Vector3(-1,.045,0)};
  const direction=directions[view].normalize();
  const cameraUp=view==='top'?new THREE.Vector3(0,0,-1):new THREE.Vector3(0,1,0);
  const right=new THREE.Vector3().crossVectors(cameraUp,direction).normalize();
  const up=new THREE.Vector3().crossVectors(direction,right).normalize();
  const aspect=host.clientWidth/Math.max(host.clientHeight,1),mobile=host.clientWidth<700;
  const tangent=Math.tan(THREE.MathUtils.degToRad(camera.fov/2));
  let distance=12;
  for(const point of fitPoints){
    const relative=point.clone().sub(center),depth=relative.dot(direction);
    distance=Math.max(distance,depth+Math.abs(relative.dot(right))/(tangent*aspect*(mobile?.85:.80)),depth+Math.abs(relative.dot(up))/(tangent*(mobile?.46:.65)));
  }
  const target=center.clone().addScaledVector(up,-distance*tangent*(mobile?.12:.035));
  if(!mobile)target.addScaledVector(right,-distance*tangent*aspect*.025);
  return {position:target.clone().addScaledVector(direction,distance),target,up:cameraUp};
}

function fitView(view=currentView,smooth=false){
  if(!center)return;
  currentView=view;
  const frame=frameFor(view);
  homeFrame=frame;
  camera.aspect=host.clientWidth/Math.max(host.clientHeight,1);camera.updateProjectionMatrix();
  // 正俯视时更换相机 up，避免过渡穿过极点造成翻转。
  const canAnimate=smooth&&!motionPreference.matches&&view!=='top'&&camera.up.y>.5;
  camera.up.copy(frame.up);
  if(canAnimate){
    cameraTransition={start:performance.now(),from:camera.position.clone(),fromTarget:controls.target.clone(),to:frame.position,target:frame.target};
  }else{
    cameraTransition=null;camera.position.copy(frame.position);controls.target.copy(frame.target);camera.lookAt(frame.target);controls.update();
  }
  document.querySelectorAll('[data-view]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.view===view)));
  syncPlayback();
}
function resize(){
  if(!renderer||failed)return;
  renderer.setPixelRatio(Math.min(devicePixelRatio,host.clientWidth<700?1.5:2));
  renderer.setSize(host.clientWidth,host.clientHeight,false);world?.resize(host.clientWidth);fitView(currentView);
}

function applyScene(id,initial=false){
  currentScene=id;elapsed=0;world.setScene(id);aircraft.position.set(0,0,0);aircraft.rotation.set(0,0,0);
  document.body.dataset.scene=id;$('#scene-name').textContent=scenePresets[id].name;
  document.querySelectorAll('.scene-buttons button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.scene===id)));
  spinning=playing&&id==='clouds';syncSpin();controls.autoRotateSpeed=id==='night'?.22:.13;
  fitView('perspective',!initial);
  renderer.render(scene,camera);
}
function selectScene(id){
  if(!scenePresets[id]||id===currentScene&&!switching)return;
  clearTimeout(switchTimer);
  switching=true;const transition=$('#scene-transition');transition.classList.add('active');
  switchTimer=setTimeout(()=>{
    try{applyScene(id);}catch(error){transition.classList.remove('active');switching=false;fail(error);return;}
    requestAnimationFrame(()=>requestAnimationFrame(()=>{transition.classList.remove('active');switching=false;}));
  },motionPreference.matches?0:380);
}

function animate(time){
  const delta=Math.min(Math.max((time-lastTime)/1000,0),.05);lastTime=time;
  if(playing){elapsed+=delta;world.update(delta);}
  if(spinning)for(const propeller of propellers)propeller.rotation.x=(propeller.rotation.x+delta*Math.PI*7)%(Math.PI*2);
  if(currentScene==='clouds'&&playing){aircraft.position.y=Math.sin(elapsed*.5)*.12;aircraft.rotation.x=Math.sin(elapsed*.28)*.018;}
  if(cameraTransition){
    const progress=Math.min((time-cameraTransition.start)/1100,1),ease=1-Math.pow(1-progress,4);
    camera.position.lerpVectors(cameraTransition.from,cameraTransition.to,ease);
    controls.target.lerpVectors(cameraTransition.fromTarget,cameraTransition.target,ease);
    if(progress===1)cameraTransition=null;
  }
  // 机库内只作小角度往返运镜，避免自动环绕穿过侧墙。
  if(currentScene==='hangar'&&playing&&currentView==='perspective'&&!cameraTransition&&homeFrame){
    const offset=homeFrame.position.clone().sub(homeFrame.target).applyAxisAngle(new THREE.Vector3(0,1,0),Math.sin(elapsed*.1)*.12);
    camera.position.copy(homeFrame.target).add(offset);
  }
  const autoRotate=controls.autoRotate;
  if(cameraTransition)controls.autoRotate=false;
  controls.update(delta);controls.autoRotate=autoRotate;renderer.render(scene,camera);
}

try{
  const mobile=host.clientWidth<700;
  renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'high-performance'});
  renderer.setPixelRatio(Math.min(devicePixelRatio,mobile?1.5:2));renderer.setSize(host.clientWidth,host.clientHeight,false);
  renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.AgXToneMapping;
  renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFShadowMap;
  renderer.domElement.tabIndex=0;renderer.domElement.setAttribute('aria-label','北京一号三维模型，拖动旋转，滚轮或双指缩放。');host.append(renderer.domElement);
  renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();fail(new Error('WebGL context lost'));});
  scene=new THREE.Scene();camera=new THREE.PerspectiveCamera(34,host.clientWidth/host.clientHeight,.2,500);
  camera.position.set(-24,12,30);
  controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=!motionPreference.matches;controls.dampingFactor=.08;
  controls.enablePan=false;controls.minDistance=7;controls.maxDistance=125;controls.maxPolarAngle=Math.PI*.72;
  controls.addEventListener('start',()=>{cameraTransition=null;setPlaying(false);});
  world=createWorld(renderer,scene,mobile);
  const gltf=await new GLTFLoader().loadAsync('../models/beijing-one.glb',progress=>{
    if(progress.total)loading.textContent=`正在载入模型… ${Math.round(progress.loaded/progress.total*100)}%`;
  });
  if(failed)throw new Error('WebGL unavailable during model loading');
  aircraft=gltf.scene;scene.add(aircraft);aircraft.updateMatrixWorld(true);
  aircraft.traverse(object=>{
    if(object.isMesh){
      object.castShadow=true;object.receiveShadow=true;
      for(const material of Array.isArray(object.material)?object.material:[object.material])material.fog=false;
      const positions=object.geometry.attributes.position;
      for(let i=0;i<positions.count;i++)fitPoints.push(new THREE.Vector3().fromBufferAttribute(positions,i).applyMatrix4(object.matrixWorld));
    }
    if(object.name==='Propeller_L'||object.name==='Propeller_R')propellers.push(object);
    if(object.name.startsWith('Gear_'))gear.push(object);
  });
  if(propellers.length!==2)throw new Error('Missing propeller nodes');
  center=new THREE.Box3().setFromObject(aircraft).getCenter(new THREE.Vector3());
  applyScene('night',true);fallback.classList.add('loaded');loading.hidden=true;
  readyButtons.forEach(button=>button.disabled=false);$('#viewer').setAttribute('aria-label','北京一号三维模型已载入');
  new ResizeObserver(resize).observe(host);
  renderer.setAnimationLoop(animate);
  document.querySelectorAll('.scene-buttons button').forEach(button=>button.addEventListener('click',()=>selectScene(button.dataset.scene)));
  document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>{setPlaying(false);fitView(button.dataset.view,true);}));
  $('#play').addEventListener('click',()=>{
    if(!playing&&currentView!=='perspective')fitView('perspective',true);
    setPlaying(!playing);
    if(currentScene==='clouds'){spinning=playing;syncSpin();}
  });
  $('#spin').addEventListener('click',()=>{spinning=!spinning;syncSpin();});
  $('#gear').addEventListener('click',()=>{
    const visible=$('#gear').getAttribute('aria-pressed')!=='true';
    gear.forEach(object=>object.visible=visible);$('#gear').setAttribute('aria-pressed',String(visible));
  });
  function zoom(factor){
    setPlaying(false);cameraTransition=null;
    const direction=camera.position.clone().sub(controls.target),distance=THREE.MathUtils.clamp(direction.length()*factor,controls.minDistance,controls.maxDistance);
    camera.position.copy(controls.target).add(direction.setLength(distance));controls.update();
  }
  $('#zoom-in').addEventListener('click',()=>zoom(1/1.2));$('#zoom-out').addEventListener('click',()=>zoom(1.2));
  $('#reset').addEventListener('click',()=>{setPlaying(false);fitView('perspective',true);});
  document.addEventListener('visibilitychange',()=>{
    if(failed)return;
    if(document.hidden)renderer.setAnimationLoop(null);
    else{lastTime=performance.now();renderer.setAnimationLoop(animate);}
  });
}catch(error){fail(error);}
