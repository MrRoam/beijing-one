import * as THREE from 'three';
import { Reflector } from 'three/addons/objects/Reflector.js';

export const scenePresets = {
  night: { name:'静夜展厅', direction:[-23,10,29], portrait:[-9,23,32], background:0x0b1017, fog:[45,120],
    keyColor:0xe5edfa, keyPower:1.6, keyPosition:[-8,18,5], fillColor:0x98b9df, fillPower:.32,
    rimColor:0xd5e2f2, rimPower:2.1, ambient:.22, environment:.8, exposure:1.0 },
  hangar: { name:'晨光机库', direction:[-23,8,32], portrait:[-18,17,34], background:0x354553, fog:[65,160],
    keyColor:0xffd8a9, keyPower:3.7, keyPosition:[18,20,-32], fillColor:0xbdd7ee, fillPower:.42,
    rimColor:0xffe2b9, rimPower:1.1, ambient:.3, environment:.7, exposure:.95 },
  clouds: { name:'云海巡航', direction:[-24,8,30], portrait:[-10,23,32], background:0xc7daea, fog:[100,230],
    keyColor:0xfff1dc, keyPower:2.8, keyPosition:[-16,25,-8], fillColor:0xa8cbe8, fillPower:.2,
    rimColor:0xe1edfc, rimPower:.8, ambient:.24, environment:.65, exposure:.96 }
};

function box(group,size,position,material,shadow=true){
  const mesh=new THREE.Mesh(new THREE.BoxGeometry(...size),material);
  mesh.position.set(...position);mesh.castShadow=shadow;mesh.receiveShadow=true;group.add(mesh);return mesh;
}
function beam(group,start,end,width,material){
  const a=new THREE.Vector3(...start),b=new THREE.Vector3(...end),direction=b.clone().sub(a);
  const mesh=box(group,[width,direction.length(),width],a.add(b).multiplyScalar(.5).toArray(),material);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),direction.normalize());return mesh;
}
function floor(group,color){
  const material=new THREE.MeshLambertMaterial({color});
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(260,260),material);
  mesh.rotation.x=-Math.PI/2;mesh.position.y=-.02;mesh.receiveShadow=true;group.add(mesh);return mesh;
}

// 柔光板只参与环境反射，控制银色机身上连续的亮带和暗部。
function makeEnvironment(renderer,id){
  const source=new THREE.Scene();
  source.background=new THREE.Color(id==='night'?0x0b111a:id==='hangar'?0x253644:0x68829a);
  const panels=id==='night'?
    [[[-6,12,2],[16,4],0xe9f0ff,3.7],[[3,5,-12],[20,2],0xbacfeb,3.5],[[12,7,3],[4,8],0xdce5f2,1.7]]:
    id==='hangar'?[[[12,9,-24],[22,12],0xffe4bf,4.6],[[-6,15,3],[20,3],0xe1ecff,2.1],[[14,5,9],[4,8],0xb1c9e5,.8]]:
    [[[-10,18,-4],[24,16],0xfff5e7,2.4],[[0,-9,0],[40,26],0xc7d9e9,.75],[[18,8,10],[12,8],0xaecbe5,.8]];
  for(const [position,size,color,power] of panels){
    const panel=new THREE.Mesh(new THREE.PlaneGeometry(...size),new THREE.MeshBasicMaterial({color:new THREE.Color(color).multiplyScalar(power),side:THREE.DoubleSide}));
    panel.position.set(...position);panel.lookAt(0,2,0);source.add(panel);
  }
  const generator=new THREE.PMREMGenerator(renderer),target=generator.fromScene(source,.065,.1,120);
  source.traverse(object=>{if(object.isMesh){object.geometry.dispose();object.material.dispose();}});
  generator.dispose();return target;
}

function createHangar(group){
  const wall=new THREE.MeshStandardMaterial({color:0x29343e,roughness:.94});
  const steel=new THREE.MeshStandardMaterial({color:0x1c2934,roughness:.62,metalness:.38});
  const trim=new THREE.MeshStandardMaterial({color:0x556572,roughness:.5,metalness:.5});
  // 开放的摄影布景：门厅和桁架位于飞机后方，竖屏相机拉远也不会穿进侧墙。
  box(group,[43,21,1],[-26.5,10.5,-27],wall);
  box(group,[33,21,1],[35.5,10.5,-27],wall);
  box(group,[100,6,1],[2,18,-27],wall);
  box(group,[100,.5,21],[2,21,-17],wall);
  for(const x of [-5,19]){
    box(group,[.45,15.5,1.2],[x,7.75,-26.5],steel);
    box(group,[.08,15.5,.08],[x+.28,7.75,-25.85],trim,false);
  }
  box(group,[24.6,.45,1.2],[7,15.4,-26.5],steel);
  const ribPositions=[];
  for(let x=-46;x<51;x+=2)if(x<-5||x>19)ribPositions.push(x);
  const ribs=new THREE.InstancedMesh(new THREE.BoxGeometry(.065,19,.14),steel,ribPositions.length);
  const matrix=new THREE.Matrix4();
  ribPositions.forEach((x,i)=>ribs.setMatrixAt(i,matrix.makeTranslation(x,9.5,-26.43)));
  ribs.receiveShadow=true;group.add(ribs);
  for(const z of [-26,-15]){
    box(group,[100,.24,.3],[2,18,z],steel);
    box(group,[100,.24,.3],[2,20.4,z],steel);
    for(let x=-46;x<49;x+=6){
      beam(group,[x,18,z],[x+3,20.4,z],.1,steel);
      beam(group,[x+3,20.4,z],[x+6,18,z],.1,steel);
    }
  }
  // 门外天空带冷色，晨光只落在门框、机翼边缘和地面，保留室内的暗部。
  const outdoors=new THREE.Mesh(new THREE.PlaneGeometry(180,80),new THREE.ShaderMaterial({
    toneMapped:false,
    vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
    fragmentShader:`varying vec2 vUv;void main(){vec3 c=mix(vec3(.64,.69,.68),vec3(.42,.62,.79),smoothstep(.1,.95,vUv.y));c+=vec3(.17,.12,.06)*(1.-smoothstep(.25,.8,vUv.y));gl_FragColor=vec4(c,1.);\n#include <colorspace_fragment>\n}`
  }));
  outdoors.position.set(7,22,-66);group.add(outdoors);
  const seam=new THREE.MeshBasicMaterial({color:0x242d33});
  for(const x of [-18,-6,6,18,30])box(group,[.018,.005,100],[x,-.013,-5],seam,false);
  for(const z of [-18,-6,6,18])box(group,[100,.005,.018],[0,-.013,z],seam,false);
  const shaftGeometry=new THREE.BufferGeometry();
  shaftGeometry.setAttribute('position',new THREE.Float32BufferAttribute([7,14,-26,16,14,-26,-4,.05,17,-18,.05,17],3));
  shaftGeometry.setAttribute('uv',new THREE.Float32BufferAttribute([0,1,1,1,1,0,0,0],2));
  shaftGeometry.setIndex([0,1,2,0,2,3]);
  const shaft=new THREE.Mesh(shaftGeometry,new THREE.ShaderMaterial({
    transparent:true,depthWrite:false,side:THREE.DoubleSide,toneMapped:false,
    vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
    fragmentShader:'varying vec2 vUv;void main(){float edge=smoothstep(0.,.3,vUv.x)*(1.-smoothstep(.7,1.,vUv.x));float fade=smoothstep(0.,.25,vUv.y)*(1.-smoothstep(.85,1.,vUv.y));gl_FragColor=vec4(1.,.86,.66,edge*fade*.035);}'
  }));
  group.add(shaft);
}

function createClouds(group,mobile){
  const horizon=new THREE.Color(0xc7daea);
  const sky=new THREE.Mesh(new THREE.SphereGeometry(240,48,24),new THREE.ShaderMaterial({
    side:THREE.BackSide,depthWrite:false,toneMapped:false,
    uniforms:{top:{value:new THREE.Color(0x417da7)},bottom:{value:horizon}},
    vertexShader:'varying vec3 vDirection;void main(){vDirection=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
    fragmentShader:'uniform vec3 top;uniform vec3 bottom;varying vec3 vDirection;void main(){float h=normalize(vDirection).y;gl_FragColor=vec4(mix(bottom,top,smoothstep(-.08,.6,h)),1.);\n#include <colorspace_fragment>\n}'
  }));
  group.add(sky);
  // 在平面后的云层中积分透明度，避免把云海做成起伏的实体地形。
  const cloudMaterial=new THREE.ShaderMaterial({
    toneMapped:false,
    uniforms:{haze:{value:horizon},time:{value:0},steps:{value:mobile?12:32}},
    vertexShader:'varying vec3 vWorld;void main(){vec4 world=modelMatrix*vec4(position,1.);vWorld=world.xyz;gl_Position=projectionMatrix*viewMatrix*world;}',
    fragmentShader:`
      varying vec3 vWorld;uniform vec3 haze;uniform float time;uniform int steps;
      float hash(vec2 p){vec3 q=fract(vec3(p.xyx)*.1031);q+=dot(q,q.yzx+33.33);return fract((q.x+q.y)*q.z);}
      float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}
      float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<4;i++){v+=a*noise(p);p=p*2.02+vec2(7.3,13.9);a*=.5;}return v;}
      float density(vec3 p){
        float altitude=(p.y+18.)/12.;
        vec2 drift=vec2(time*.015,0.);
        float n=fbm(p.xz*.065+vec2(p.y*.085,0.)+drift)+noise(p.xy*.13+drift)*.22;
        return smoothstep(.56,.83,n)*1.5*smoothstep(0.,.14,altitude)*(1.-smoothstep(.78,1.,altitude));
      }
      void main(){
        vec3 ray=normalize(vWorld-cameraPosition);
        float stride=min(5.,12./max(.12,-ray.y)/float(steps));
        // 固定的像素抖动打散低角度采样条带，暂停时不会产生噪点闪动。
        vec3 p=vWorld+ray*stride*(.25+.5*hash(gl_FragCoord.xy)),accum=vec3(0.);
        float transmittance=1.;
        for(int i=0;i<32;i++){
          if(i>=steps||transmittance<.025)break;
          float d=density(p);
          float light=exp(-density(p+vec3(-2.5,2.2,-1.8))*4.5);
          vec3 color=mix(vec3(.25,.42,.6),vec3(.95,.98,1.),light);
          float opacity=1.-exp(-d*stride*.85);
          accum+=color*opacity*transmittance;
          transmittance*=1.-opacity;p+=ray*stride;
        }
        vec3 cloud=accum+haze*transmittance;
        cloud=mix(cloud,haze,smoothstep(65.,165.,length(cameraPosition-vWorld)));
        gl_FragColor=vec4(cloud,1.);
        #include <colorspace_fragment>
      }`
  });
  const bed=new THREE.Mesh(new THREE.PlaneGeometry(1400,1400),cloudMaterial);
  bed.rotation.x=-Math.PI/2;bed.position.y=-6;group.add(bed);
  return cloudMaterial;
}

export function createWorld(renderer,scene,mobile){
  const groups={night:new THREE.Group(),hangar:new THREE.Group(),clouds:new THREE.Group()};
  for(const [id,group] of Object.entries(groups)){group.name=id;group.visible=false;scene.add(group);}
  const nightFloor=floor(groups.night,0x111822),hangarFloor=floor(groups.hangar,0x343c43);
  createHangar(groups.hangar);
  const cloudMaterial=createClouds(groups.clouds,mobile);
  const hemisphere=new THREE.HemisphereLight(0xcddff6,0x353d49,.3);scene.add(hemisphere);
  const key=new THREE.DirectionalLight(0xffffff,2);key.castShadow=true;
  key.shadow.mapSize.set(mobile?1024:2048,mobile?1024:2048);
  Object.assign(key.shadow.camera,{left:-18,right:18,top:18,bottom:-18,near:.5,far:105});
  key.shadow.bias=-.0003;key.shadow.normalBias=.06;key.shadow.radius=2;scene.add(key);
  const fill=new THREE.DirectionalLight(0xa9c5e6,.5);fill.position.set(6,8,18);scene.add(fill);
  const rim=new THREE.DirectionalLight(0xb9d3ed,2);rim.position.set(7,10,-15);scene.add(rim);
  const stageLight=new THREE.SpotLight(0xc7d9f5,180,45,.72,.9,2);
  stageLight.position.set(0,14,3);stageLight.target.position.set(0,0,0);groups.night.add(stageLight,stageLight.target);
  const environments=new Map();let active='night',reflector;

  function resize(width){
    mobile=width<700;
    if(!mobile&&!reflector){
      reflector=new Reflector(new THREE.PlaneGeometry(220,220),{textureWidth:640,textureHeight:400,color:0x667585,clipBias:.003});
      reflector.rotation.x=-Math.PI/2;reflector.position.y=-.04;scene.add(reflector);
    }
    if(reflector)reflector.visible=!mobile&&active!=='clouds';
    cloudMaterial.uniforms.steps.value=mobile?12:32;
    for(const ground of [nightFloor,hangarFloor]){
      const reflect=!!reflector&&!mobile;
      if(ground.material.transparent!==reflect){ground.material.transparent=reflect;ground.material.needsUpdate=true;}
      ground.material.opacity=reflect?.94:1;
    }
  }
  resize(mobile?390:1440);

  function setScene(id){
    const preset=scenePresets[id];active=id;
    for(const [name,group] of Object.entries(groups))group.visible=name===id;
    if(reflector)reflector.visible=!mobile&&id!=='clouds';
    scene.background=new THREE.Color(preset.background);scene.fog=new THREE.Fog(preset.background,...preset.fog);
    key.color.set(preset.keyColor);key.intensity=preset.keyPower;key.position.set(...preset.keyPosition);
    fill.color.set(preset.fillColor);fill.intensity=preset.fillPower;
    rim.color.set(preset.rimColor);rim.intensity=preset.rimPower;hemisphere.intensity=preset.ambient;
    hemisphere.groundColor.set(id==='clouds'?0x8ba2b8:0x353d49);
    if(!environments.has(id))environments.set(id,makeEnvironment(renderer,id));
    scene.environment=environments.get(id).texture;scene.environmentIntensity=preset.environment;
    renderer.toneMappingExposure=preset.exposure;
  }
  function update(delta){if(active==='clouds')cloudMaterial.uniforms.time.value+=delta;}
  return {setScene,update,resize};
}
