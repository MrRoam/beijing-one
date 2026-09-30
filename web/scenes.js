import * as THREE from 'three';
import { Reflector } from 'three/addons/objects/Reflector.js';

export const scenePresets = {
  night: { name:'静夜展厅', direction:[-23,10,29], background:0x0d121a, fog:[55,160],
    keyColor:0xe8efff, keyPower:2.4, keyPosition:[-8,18,5], fillColor:0x91b6e2, fillPower:.65,
    rimColor:0xc2d5ee, rimPower:2.5, ambient:.32, environment:.85, exposure:1.02 },
  hangar: { name:'晨光机库', direction:[-25,9,29], background:0x8c9294, fog:[46,135],
    keyColor:0xffd5a0, keyPower:4.2, keyPosition:[-18,19,-24], fillColor:0xc5d8ec, fillPower:.7,
    rimColor:0xffe1b4, rimPower:.8, ambient:.55, environment:.9, exposure:.88 },
  clouds: { name:'云海巡航', direction:[-24,11,30], background:0xd7e7f3, fog:[90,200],
    keyColor:0xfff4df, keyPower:2.4, keyPosition:[-14,25,8], fillColor:0xdcefff, fillPower:.45,
    rimColor:0xf5fcff, rimPower:.8, ambient:.48, environment:.6, exposure:.85 }
};

function box(group,size,position,material,shadow=true){
  const mesh=new THREE.Mesh(new THREE.BoxGeometry(...size),material);
  mesh.position.set(...position);mesh.castShadow=shadow;mesh.receiveShadow=true;group.add(mesh);return mesh;
}

function floor(group,color,reflective){
  const material=new THREE.MeshLambertMaterial({color,
    transparent:reflective,opacity:reflective?.93:1,depthWrite:true});
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(220,220),material);
  mesh.rotation.x=-Math.PI/2;mesh.position.y=-.02;mesh.receiveShadow=true;group.add(mesh);return mesh;
}

// 反射环境中的柔光板与画面内的主光方向保持一致，银色机身不再平均发亮。
function makeEnvironment(renderer,id){
  const source=new THREE.Scene();
  source.background=new THREE.Color(id==='night'?0x111820:id==='hangar'?0x555e69:0xb3d0e8);
  const panels=id==='night'?
    [[[-6,12,2],[16,5],0xe9f0ff,5],[[3,5,-12],[20,3],0xadc7ef,3],[[12,7,3],[5,8],0xdee8f6,2]]:
    id==='hangar'?[[[-15,10,-22],[24,16],0xffdfb0,6],[[0,15,0],[24,5],0xe1ecff,3],[[14,5,5],[5,8],0xb1c9e5,1.3]]:
    [[[0,18,0],[35,28],0xf1f7ff,3],[[0,-8,0],[45,30],0xffffff,2],[[20,10,8],[10,10],0xffefce,2]];
  for(const [position,size,color,power] of panels){
    const panel=new THREE.Mesh(new THREE.PlaneGeometry(...size),new THREE.MeshBasicMaterial({color:new THREE.Color(color).multiplyScalar(power),side:THREE.DoubleSide}));
    panel.position.set(...position);panel.lookAt(0,2,0);source.add(panel);
  }
  const generator=new THREE.PMREMGenerator(renderer);
  const target=generator.fromScene(source,.06,.1,120);
  source.traverse(o=>{if(o.isMesh){o.geometry.dispose();o.material.dispose();}});
  generator.dispose();return target;
}

function cloudTexture(){
  const canvas=document.createElement('canvas');canvas.width=512;canvas.height=256;
  const ctx=canvas.getContext('2d');
  // 固定种子使每次载入及手机端的云层布局一致。
  let seed=127;const random=()=>{seed=(seed*16807)%2147483647;return (seed-1)/2147483646;};
  for(let i=0;i<65;i++){
    const x=80+random()*350,y=90+random()*80,r=22+random()*53;
    const gradient=ctx.createRadialGradient(x,y,0,x,y,r);
    gradient.addColorStop(0,'rgba(255,255,255,.22)');gradient.addColorStop(.45,'rgba(247,251,255,.15)');gradient.addColorStop(1,'rgba(231,241,252,0)');
    ctx.fillStyle=gradient;ctx.fillRect(x-r,y-r,r*2,r*2);
  }
  const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;return texture;
}

export function createWorld(renderer,scene,mobile){
  const groups={night:new THREE.Group(),hangar:new THREE.Group(),clouds:new THREE.Group()};
  for(const [id,group] of Object.entries(groups)){group.name=id;group.visible=false;scene.add(group);}
  const nightFloor=floor(groups.night,0x070b12,!mobile);
  const hangarFloor=floor(groups.hangar,0x565955,!mobile);

  let reflector;
  if(!mobile){
    reflector=new Reflector(new THREE.PlaneGeometry(200,200),{textureWidth:768,textureHeight:512,color:0x667585,clipBias:.003});
    reflector.rotation.x=-Math.PI/2;reflector.position.y=-.04;scene.add(reflector);
  }

  const edge=new THREE.MeshStandardMaterial({color:0x38444f,roughness:.58,metalness:.3});

  const concrete=new THREE.MeshStandardMaterial({color:0x4a535a,roughness:.9});
  const hangar=groups.hangar;
  box(hangar,[2,21,90],[-26,10,-12],concrete);
  box(hangar,[2,21,90],[26,10,-12],concrete);
  box(hangar,[13,21,1],[-20,10,-33],concrete);
  box(hangar,[13,21,1],[20,10,-33],concrete);
  box(hangar,[28,6,1],[0,18,-33],concrete);
  box(hangar,[56,1,92],[0,21,-12],concrete);
  for(const z of [-30,-17,-4,9,22]){
    box(hangar,[.4,21,.5],[-24.5,10,z],edge);
    box(hangar,[.4,21,.5],[24.5,10,z],edge);
    box(hangar,[49,.5,.5],[0,19,z],edge);
  }
  // 窄门框和层叠横梁建立机库尺度，空间细节集中在画面边缘。
  for(const x of [-13.3,13.3])box(hangar,[.2,15,.18],[x,7.5,-32.4],edge);
  for(const y of [4,8,12]){
    box(hangar,[12,.08,.15],[-20,y,-32.4],edge,false);
    box(hangar,[12,.08,.15],[20,y,-32.4],edge,false);
  }
  const outside=new THREE.Mesh(new THREE.PlaneGeometry(180,70),new THREE.MeshBasicMaterial({color:0xf0d4ac}));
  outside.position.set(0,22,-50);hangar.add(outside);
  // 低对比地面接缝用于建立透视尺度。
  const seamMaterial=new THREE.MeshStandardMaterial({color:0x444947,roughness:1});
  for(const x of [-20,-10,0,10,20])box(hangar,[.018,.005,100],[x,-.014,-5],seamMaterial,false);
  const architecture=hangar.children.filter(object=>object!==hangarFloor).map(object=>({object,position:object.position.clone()}));

  const sky=new THREE.Mesh(new THREE.SphereGeometry(190,48,24),new THREE.ShaderMaterial({
    side:THREE.BackSide,depthWrite:false,toneMapped:false,
    uniforms:{top:{value:new THREE.Color(0x6096c2)},bottom:{value:new THREE.Color(0xd7e7f3)}},
    vertexShader:'varying vec3 vDirection; void main(){vDirection=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
    fragmentShader:'uniform vec3 top;uniform vec3 bottom;varying vec3 vDirection;void main(){float h=normalize(vDirection).y;gl_FragColor=vec4(mix(bottom,top,smoothstep(-.15,.65,h)),1.0);\n#include <tonemapping_fragment>\n#include <colorspace_fragment>\n}'
  }));
  groups.clouds.add(sky);
  const texture=cloudTexture();const cloudLayers=[];
  for(let i=0;i<(mobile?18:30);i++){
    const material=new THREE.MeshBasicMaterial({map:texture,transparent:true,opacity:.45+(i%3)*.1,depthWrite:false,side:THREE.DoubleSide,fog:true,toneMapped:false});
    const cloud=new THREE.Mesh(new THREE.PlaneGeometry(32+(i%5)*7,17+(i%4)*4),material);
    cloud.position.set(((i*37)%130)-65,-5-(i%4)*1.4,((i*29)%140)-70);
    cloud.rotation.set(-Math.PI/2+.15,0,(i%5)*.35);cloudLayers.push(cloud);groups.clouds.add(cloud);
  }
  const cloudGeometry=new THREE.PlaneGeometry(800,800,100,100);
  const vertices=cloudGeometry.attributes.position;
  for(let i=0;i<vertices.count;i++){
    const x=vertices.getX(i),y=vertices.getY(i);
    vertices.setZ(i,Math.sin(x*.09)*Math.cos(y*.085)*1.6+Math.sin(x*.17+y*.11)*.6);
  }
  cloudGeometry.computeVertexNormals();
  const cloudBed=new THREE.Mesh(cloudGeometry,new THREE.ShaderMaterial({
    toneMapped:false,
    uniforms:{haze:{value:new THREE.Color(0xd7e7f3)},time:{value:0}},
    vertexShader:`varying vec3 vWorld;void main(){vec4 world=modelMatrix*vec4(position,1.0);vWorld=world.xyz;gl_Position=projectionMatrix*viewMatrix*world;}`,
    fragmentShader:`
      varying vec3 vWorld;uniform vec3 haze;uniform float time;
      float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
      float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1.,0.)),f.x),mix(hash(i+vec2(0.,1.)),hash(i+vec2(1.,1.)),f.x),f.y);}
      float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<5;i++){v+=a*noise(p);p=p*2.03+vec2(13.1,9.7);a*=.5;}return v;}
      void main(){
        vec2 p=vWorld.xz*.12+vec2(time*.016,0.);
        float n=fbm(p),light=fbm(p+vec2(-.22,.3));
        float brightness=smoothstep(.22,.67,n);
        vec3 cloud=mix(vec3(.26,.43,.63),vec3(.91,.96,1.),brightness);
        cloud+=vec3(.1,.085,.07)*smoothstep(.03,.2,n-light);
        float distanceToCamera=length(cameraPosition-vWorld);
        cloud=mix(cloud,haze,smoothstep(70.,190.,distanceToCamera));
        gl_FragColor=vec4(cloud,1.);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`
  }));
  cloudBed.rotation.x=-Math.PI/2;cloudBed.position.y=-11;groups.clouds.add(cloudBed);

  const hemisphere=new THREE.HemisphereLight(0xcddff6,0x51545b,.3);scene.add(hemisphere);
  const key=new THREE.DirectionalLight(0xffffff,2);key.castShadow=true;
  key.shadow.mapSize.set(mobile?1024:2048,mobile?1024:2048);
  Object.assign(key.shadow.camera,{left:-18,right:18,top:18,bottom:-18,near:.5,far:95});
  key.shadow.bias=-.0003;key.shadow.normalBias=.06;scene.add(key);
  const fill=new THREE.DirectionalLight(0xa9c5e6,.5);fill.position.set(6,8,18);scene.add(fill);
  const rim=new THREE.DirectionalLight(0xb9d3ed,2);rim.position.set(7,10,-15);scene.add(rim);
  const environments=new Map();let active='night';

  // 竖屏为完整容纳机翼需要更远的机位，机库也随视口扩大，避免墙面挡住相机。
  function resize(width){
    mobile=width<700;
    const scale=mobile?new THREE.Vector3(2.5,1.7,2.5):new THREE.Vector3(1,1,1);
    for(const {object,position} of architecture){object.position.copy(position).multiply(scale);object.scale.copy(scale);}
    if(reflector)reflector.visible=!mobile&&active!=='clouds';
    for(const ground of [nightFloor,hangarFloor]){
      ground.material.transparent=!!reflector&&!mobile;ground.material.opacity=!!reflector&&!mobile?.93:1;
      ground.material.needsUpdate=true;
    }
  }
  resize(mobile?390:1440);

  function setScene(id){
    const preset=scenePresets[id];active=id;
    for(const [name,group] of Object.entries(groups))group.visible=name===id;
    if(reflector)reflector.visible=!mobile&&id!=='clouds';
    scene.background=new THREE.Color(preset.background);scene.fog=new THREE.Fog(preset.background,...preset.fog);
    key.color.set(preset.keyColor);key.intensity=preset.keyPower;key.position.set(...preset.keyPosition);
    key.castShadow=id!=='clouds';fill.color.set(preset.fillColor);fill.intensity=preset.fillPower;
    rim.color.set(preset.rimColor);rim.intensity=preset.rimPower;hemisphere.intensity=preset.ambient;
    hemisphere.groundColor.set(id==='clouds'?0xcadbe9:0x51545b);
    if(!environments.has(id))environments.set(id,makeEnvironment(renderer,id));
    scene.environment=environments.get(id).texture;scene.environmentIntensity=preset.environment;
    renderer.toneMappingExposure=preset.exposure;
  }
  function update(delta){
    if(active==='clouds'){
      cloudBed.material.uniforms.time.value+=delta;
      for(const cloud of cloudLayers){cloud.position.x+=delta*1.25;if(cloud.position.x>80)cloud.position.x=-80;}
    }
  }
  return {setScene,update,resize};
}
