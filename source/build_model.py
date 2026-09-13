"""北京一号外观复原。Blender 5.0；米制。所有摄影参考仅观察，不打包照片。"""
import bpy, bmesh, math, json, sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
for folder in ['models','previews','print','docs','web']:
    (ROOT/folder).mkdir(parents=True, exist_ok=True)
CFG = json.loads((ROOT/'source/dimensions.json').read_text(encoding='utf-8'))
PI = math.pi

# x：机头到机尾；y：翼展；z：上。尺寸中的局部剖面是照片复原值。
BODY = [
    (-6.20,.004,1.69,1.71),(-6.02,.20,1.52,1.88),(-5.65,.40,1.31,2.12),
    (-5.00,.62,1.13,2.40),(-4.25,.76,1.06,2.62),(-3.53,.87,1.06,3.05),
    (-2.85,.91,1.08,3.13),(-1.45,.91,1.11,3.12),(.30,.86,1.20,3.08),
    (1.80,.74,1.40,3.02),(3.25,.56,1.76,2.94),(4.55,.34,2.14,2.82),
    (5.65,.14,2.42,2.68),(6.20,.004,2.55,2.57)]


def mix(a,b,t): return a*(1-t)+b*t


def values_at(stations, x):
    if x <= stations[0][0]: return stations[0][1:]
    if x >= stations[-1][0]: return stations[-1][1:]
    for i in range(len(stations)-1):
        p,q=stations[i],stations[i+1]
        if p[0] <= x <= q[0]:
            t=(x-p[0])/(q[0]-p[0]); result=[]
            a=stations[max(0,i-1)]; b=stations[min(len(stations)-1,i+2)]
            for k in range(1,len(p)):
                m0=(q[k]-a[k])/(q[0]-a[0])*(q[0]-p[0])
                m1=(b[k]-p[k])/(b[0]-p[0])*(q[0]-p[0])
                v=(2*t**3-3*t*t+1)*p[k]+(t**3-2*t*t+t)*m0+(-2*t**3+3*t*t)*q[k]+(t**3-t*t)*m1
                result.append(min(max(v,min(p[k],q[k])),max(p[k],q[k])))
            return result


def clean_scene():
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    for col in list(bpy.data.collections):
        if col.name != 'Collection': bpy.data.collections.remove(col)
    col=bpy.data.collections.get('Collection'); col.name='Aircraft'
    return col


def material(name,color,metallic=0,roughness=.35):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Metallic'].default_value=metallic; p.inputs['Roughness'].default_value=roughness
    return m


def mesh(name,verts,faces,mat=None,smooth=True):
    me=bpy.data.meshes.new(name); me.from_pydata(verts,[],faces); me.update()
    bm=bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(me); bm.free()
    ob=bpy.data.objects.new(name,me); bpy.context.collection.objects.link(ob)
    if mat: me.materials.append(mat)
    for p in me.polygons: p.use_smooth=smooth
    return ob


def select_only(obs):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in obs: ob.select_set(True)
    bpy.context.view_layer.objects.active=obs[0]


def loft(name,stations,mat,y=0,ring=56,steps=5,power=2.1):
    xs=[]
    for a,b in zip(stations,stations[1:]):
        xs.extend(mix(a[0],b[0],j/steps) for j in range(steps))
    xs.append(stations[-1][0]); vs=[]; fs=[]
    for x in xs:
        ry,zb,zt=values_at(stations,x)
        for j in range(ring):
            th=2*PI*j/ring; s,c=math.sin(th),math.cos(th)
            vs.append((x,y+ry*math.copysign(abs(s)**(2/power),s),(zt+zb)/2+(zt-zb)/2*math.copysign(abs(c)**(2/power),c)))
    for i in range(len(xs)-1):
        for j in range(ring): fs.append((i*ring+j,i*ring+(j+1)%ring,(i+1)*ring+(j+1)%ring,(i+1)*ring+j))
    fs += [tuple(reversed(range(ring))),tuple((len(xs)-1)*ring+j for j in range(ring))]
    return mesh(name,vs,fs,mat)


def body_y(x,z,side,offset=.015):
    ry,zb,zt=values_at(BODY,max(-6.195,min(6.195,x)))
    v=min(.9999,abs((z-(zt+zb)/2)/((zt-zb)/2)))
    return side*(ry*(1-v**2.1)**(1/2.1)+offset)


def patch(name,points,side,mat,offset=.018):
    # 适于窄幅蒙皮涂装；三角扇中心也投影到曲面。
    cx=sum(p[0] for p in points)/len(points); cz=sum(p[1] for p in points)/len(points)
    vs=[(cx,body_y(cx,cz,side,offset),cz)]+[(x,body_y(x,z,side,offset),z) for x,z in points]
    ob=mesh(name,vs,[(0,j+1,(j+1)%len(points)+1) for j in range(len(points))],mat)
    bm=bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.subdivide_edges(bm,edges=list(bm.edges),cuts=3,use_grid_fill=True)
    for v in bm.verts: v.co.y=body_y(v.co.x,v.co.z,side,offset+.018)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(ob.data); bm.free()
    return ob


def band(name,stations,side,mat,offset=.018):
    vs=[]; columns=7
    for a,b in zip(stations,stations[1:]):
        for j in range(8):
            t=j/8; x=mix(a[0],b[0],t)
            for k in range(columns):
                z=mix(mix(a[1],b[1],t),mix(a[2],b[2],t),k/(columns-1)); vs.append((x,body_y(x,z,side,offset+.014),z))
    x,lo,hi=stations[-1]
    for k in range(columns):
        z=mix(lo,hi,k/(columns-1)); vs.append((x,body_y(x,z,side,offset+.014),z))
    return mesh(name,vs,[(i*columns+j,i*columns+j+1,(i+1)*columns+j+1,(i+1)*columns+j) for i in range(len(vs)//columns-1) for j in range(columns-1)],mat)


def rounded_rect(cx,cz,w,h,r):
    points=[]
    for sx,sz,start in [(1,1,0),(-1,1,90),(-1,-1,180),(1,-1,270)]:
        for j in range(7):
            th=math.radians(start+j*90/6)
            points.append((cx+sx*(w/2-r)+r*math.cos(th),cz+sz*(h/2-r)+r*math.sin(th)))
    return points


def cockpit_patch(name,x0,x1,t0,t1,side,mat):
    vs=[]; rows=5; cols=9
    for i in range(rows):
        x=mix(x0,x1,i/(rows-1)); ry,zb,zt=values_at(BODY,x)
        for j in range(cols):
            th=side*mix(t0,t1,j/(cols-1)); s,c=math.sin(th),math.cos(th)
            vs.append((x,ry*math.copysign(abs(s)**(2/2.1),s)+side*.033,(zt+zb)/2+(zt-zb)/2*c**(2/2.1)+.033))
    fs=[(i*cols+j,i*cols+j+1,(i+1)*cols+j+1,(i+1)*cols+j) for i in range(rows-1) for j in range(cols-1)]
    return mesh(name,vs,fs,mat,False)


def wing(name,stations,side,mat,vertical=False,min_thickness=.002):
    spans=[]
    for a,b in zip(stations,stations[1:]): spans.extend(mix(a[0],b[0],j/3) for j in range(3))
    spans.append(stations[-1][0]); n=28
    ts=[(1-math.cos(PI*j/n))/2 for j in range(n+1)]
    contour=[(t,1) for t in ts]+[(t,-1) for t in reversed(ts)]
    vs=[]; fs=[]; ring=len(contour)
    for s in spans:
        le,chord,height,ratio=values_at(stations,s)
        for t,sign in contour:
            yt=5*ratio*chord*(.2969*math.sqrt(t)-.1260*t-.3516*t*t+.2843*t**3-.1036*t**4)
            yt=max(min_thickness/2,yt)
            if vertical: vs.append((le+t*chord,sign*yt,s))
            else: vs.append((le+t*chord,side*s,height+sign*yt))
    for i in range(len(spans)-1):
        for j in range(ring): fs.append((i*ring+j,i*ring+(j+1)%ring,(i+1)*ring+(j+1)%ring,(i+1)*ring+j))
    fs += [tuple(reversed(range(ring))),tuple((len(spans)-1)*ring+j for j in range(ring))]
    return mesh(name,vs,fs,mat)


WING=[(.0,-2.10,3.75,1.33,.135),(1.35,-1.95,3.48,1.35,.132),(3.0,-1.65,2.96,1.42,.126),(6.70,-.99,1.71,1.66,.12),(7.95,-.72,1.20,1.75,.115),(8.15,-.56,.85,1.77,.11)]
TAIL=[(.0,3.47,2.59,2.68,.12),(.9,3.58,2.37,2.70,.12),(2.50,4.17,1.34,2.78,.105),(2.70,4.36,.97,2.79,.10)]
FIN=[(2.42,3.18,2.98,0,.12),(2.92,3.74,2.41,0,.115),(3.70,4.42,1.64,0,.11),(4.30,4.88,1.10,0,.11),(4.51,5.08,.85,0,.10),(4.60,5.29,.51,0,.08)]
NACELLE=[(-2.88,.39,1.13,1.91),(-2.76,.56,.96,2.08),(-2.32,.58,.94,2.10),(-1.6,.55,.97,2.07),(-.40,.44,1.06,1.94),(.65,.31,1.20,1.82),(1.57,.06,1.49,1.61),(1.72,.004,1.55,1.57)]


def cylinder(name,center,radius,depth,mat,axis='Z',vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=center)
    ob=bpy.context.object; ob.name=name
    if axis=='X': ob.rotation_euler[1]=PI/2
    if axis=='Y': ob.rotation_euler[0]=PI/2
    if mat: ob.data.materials.append(mat)
    for p in ob.data.polygons: p.use_smooth=len(p.vertices)==4
    return ob


def rod(name,a,b,r,mat):
    av,bv=Vector(a),Vector(b); ob=cylinder(name,(av+bv)/2,r,(bv-av).length,mat,vertices=16)
    ob.rotation_euler=(bv-av).to_track_quat('Z','Y').to_euler(); return ob


def torus(name,center,radius,tube,mat,axis='X'):
    bpy.ops.mesh.primitive_torus_add(major_segments=48,minor_segments=10,location=center,major_radius=radius,minor_radius=tube)
    ob=bpy.context.object; ob.name=name
    if axis=='X': ob.rotation_euler[1]=PI/2
    if axis=='Y': ob.rotation_euler[0]=PI/2
    ob.data.materials.append(mat)
    for p in ob.data.polygons:p.use_smooth=True
    return ob


def poly_extrude(name,polygon,thickness,mat,axis='X'):
    vs=[]
    for d in [-thickness/2,thickness/2]:
        for a,b in polygon: vs.append((d,a,b) if axis=='X' else (a,b,d))
    n=len(polygon); fs=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    for i in range(n): fs.append((i,(i+1)%n,(i+1)%n+n,i+n))
    return mesh(name,vs,fs,mat,False)


def make_prop(side,mats,thickness=.025):
    suffix='L' if side<0 else 'R'; parent=bpy.data.objects.new('Propeller_'+suffix,None)
    bpy.context.collection.objects.link(parent); parent.location=(-3.03,side*2.8,1.52)
    shape=[(.07,-.07),(.30,-.125),(.78,-.11),(1.09,-.055),(1.18,.015),(1.15,.070),(.86,.12),(.39,.115),(.13,.060)]
    for k in [0,1]:
        ob=poly_extrude('Propeller_'+suffix+'_Blade_'+str(k),shape,thickness,mats['prop'])
        ob.parent=parent; ob.rotation_euler[0]=k*PI+PI/2+.24
    hub=cylinder('Propeller_'+suffix+'_Hub',(0,0,0),.135,.21,mats['metal'],'X')
    hub.parent=parent; hub.location=(0,0,0)
    nut=cylinder('Propeller_'+suffix+'_Cap',(-.125,0,0),.065,.06,mats['metal'],'X',12)
    nut.parent=parent; nut.location=(-.125,0,0)
    parent.rotation_euler=(0,0,0); parent.keyframe_insert(data_path='rotation_euler',frame=1)
    parent.rotation_euler[0]=2*PI; parent.keyframe_insert(data_path='rotation_euler',frame=61)
    # 导出为静态节点，网页按轴旋转；源文件保留动画。
    parent.rotation_euler[0]=0
    return parent


def surface_text(text,side,mat,font,x_start,z,height):
    curve=bpy.data.curves.new('LiveryText','FONT'); curve.body=text; curve.font=font
    curve.size=height; curve.resolution_u=6
    ob=bpy.data.objects.new('Livery_Name_'+('L' if side<0 else 'R'),curve); bpy.context.collection.objects.link(ob)
    select_only([ob]); bpy.ops.object.convert(target='MESH'); ob=bpy.context.object
    for v in ob.data.vertices:
        u,w=v.co.x,v.co.y
        x=x_start+u if side<0 else x_start-u
        zz=z+w; v.co=(x,body_y(x,zz,side,.032),zz)
    ob.data.materials.append(mat)
    return ob


def star(name,x,z,side,mat):
    pts=[]
    for j in range(10):
        a=PI/2+2*PI*j/10; r=.27 if j%2==0 else .117
        pts.append((x+r*math.cos(a),side*.101,z+r*math.sin(a)))
    return mesh(name,[(x,side*.101,z)]+pts,[(0,j+1,(j+1)%10+1) for j in range(10)],mat,False)


def create_aircraft():
    clean_scene()
    mats={
        'silver': material('Satin aluminium',(.66,.70,.73),.62,.31),
        'metal': material('Brushed alloy',(.42,.48,.52),.72,.23),
        'red': material('Vermilion livery',(.58,.025,.027),.18,.32),
        'glass': material('Smoked cockpit glass',(.026,.075,.10),.35,.16),
        'black': material('Rubber',(.012,.016,.019),.02,.7),
        'prop': material('Graphite propeller',(.022,.032,.037),.33,.33),
        'line': material('Panel joint',(.16,.19,.20),.38,.46),
    }
    fus=loft('Fuselage',BODY,mats['silver'])
    fus['reference']='BUAA museum photos; approximate cross-sections'
    fus['length_m']=12.4
    for side in [-1,1]:
        suf='L' if side<0 else 'R'
        wing('Wing_'+suf,WING,side,mats['silver'])
        wing('Tailplane_'+suf,TAIL,side,mats['silver'])
        loft('Nacelle_'+suf,NACELLE,mats['silver'],y=side*2.8,ring=48,steps=4,power=2)
        # 色圈、进气口与径向结构仅作外观表达。
        cylinder('Engine_DarkFace_'+suf,(-2.91,side*2.8,1.52),.462,.045,mats['black'],'X')
        torus('Engine_RedRim_'+suf,(-2.83,side*2.8,1.52),.475,.070,mats['red'])
        red_cowl=[(-2.82,.548,.972,2.068),(-2.68,.590,.930,2.110),(-2.42,.600,.920,2.120)]
        # 前罩由独立封闭层表现，打印版使用原始短舱实体。
        loft('Engine_RedCowl_'+suf,red_cowl,mats['red'],y=side*2.8,ring=48,steps=3,power=2)
        # 前罩上的黑色圆面保持在红圈之前。
        for j in range(9):
            a=2*PI*j/9; p0=(-2.948,side*2.8+.15*math.cos(a),1.52+.15*math.sin(a)); p1=(-2.948,side*2.8+.39*math.cos(a),1.52+.39*math.sin(a))
            rod('Engine_RadialDetail_'+suf+'_'+str(j),p0,p1,.043,mats['metal'])
        make_prop(side,mats)
        # 窄鼻线与后部宽腰线，折线位置根据馆藏照片近似。
        band('Livery_Nose_'+suf,[(-6.05,1.65,1.70),(-5.5,1.65,1.70),(-4.6,1.70,1.77),(-3.7,1.77,1.84),(-2.58,1.93,2.0)],side,mats['red'])
        band('Livery_Cabin_'+suf,[(-2.50,2.20,2.60),(-1.6,2.23,2.59),(0,2.30,2.64),(1.8,2.38,2.68),(3.3,2.44,2.74),(4.7,2.53,2.75),(5.4,2.57,2.67)],side,mats['red'])
        patch('Livery_Lightning_'+suf,[(-3.25,2.29),(-2.65,2.29),(-1.92,1.98),(-2.46,1.95)],side,mats['red'],.023)
        for j,x in enumerate([-1.35,-.15,1.05,2.20]):
            z=2.445+.04*(x+1.35)
            patch('Window_Frame_'+suf+str(j),rounded_rect(x,z,.44,.43,.065),side,mats['metal'],.025)
            patch('Window_'+suf+str(j),rounded_rect(x,z,.365,.355,.047),side,mats['glass'],.032)
        cockpit_patch('Windshield_'+suf,-4.15,-3.60,.08,.80,side,mats['glass'])
        cockpit_patch('Pilot_SideWindow_'+suf,-3.53,-3.03,.69,1.35,side,mats['glass'])
        cockpit_patch('Pilot_RearWindow_'+suf,-2.95,-2.53,.70,1.36,side,mats['glass'])
        # 后舱门轮廓。窄幅四边条带避免单平面穿入曲面。
        door_x,door_z=2.72,2.12
        pts=rounded_rect(door_x,door_z,.72,1.15,.08)
        for j in range(len(pts)):
            x0,z0=pts[j]; x1,z1=pts[(j+1)%len(pts)]
            rod('Door_Seam_'+suf+str(j),(x0,body_y(x0,z0,side,.024),z0),(x1,body_y(x1,z1,side,.024),z1),.006,mats['line'])
        rod('Door_Handle_'+suf,(2.91,body_y(2.91,2.08,side,.038),2.08),(3.04,body_y(3.04,2.08,side,.038),2.08),.013,mats['metal'])
        # 前三点起落架；打印装配版采用收起姿态。
        y=side*2.8
        rod('Gear_MainStrut_'+suf,(-.34,y,1.31),(-.05,y,.32),.048,mats['metal'])
        rod('Gear_MainBrace_'+suf,(.47,y,1.31),(-.05,y,.40),.029,mats['metal'])
        cylinder('Gear_MainTyre_'+suf,(-.05,y,.30),.30,.20,mats['black'],'Y',48)
        cylinder('Gear_MainHub_'+suf,(-.05,y+side*.107,.30),.135,.025,mats['metal'],'Y',24)
        star('Livery_TailStar_'+suf,5.28,3.95,side,mats['red'])
    wing('Vertical_fin',FIN,1,mats['silver'],vertical=True)
    rod('Gear_NoseStrut',(-4.66,0,1.18),(-4.78,0,.27),.042,mats['metal'])
    rod('Gear_NoseBrace',(-4.10,0,1.19),(-4.76,0,.41),.027,mats['metal'])
    cylinder('Gear_NoseTyre',(-4.78,0,.23),.23,.16,mats['black'],'Y',40)
    cylinder('Gear_NoseHub',(-4.78,-.085,.23),.095,.023,mats['metal'],'Y',24)
    rod('Antenna',(-2.66,0,3.13),(-2.34,0,3.77),.014,mats['metal'])
    font=bpy.data.fonts.load('C:/Windows/Fonts/simkai.ttf')
    surface_text('北京一号',-1,mats['red'],font,-4.77,1.90,.37)
    surface_text('北京一号',1,mats['red'],font,-3.0,1.90,.37)
    scene=bpy.context.scene; scene.frame_set(1); scene.render.fps=30; scene.frame_end=60
    scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=1
    return mats


def setup_render():
    stage=bpy.data.collections.new('Studio'); bpy.context.scene.collection.children.link(stage)
    def move(ob):
        for col in list(ob.users_collection):col.objects.unlink(ob)
        stage.objects.link(ob)
    floor_mat=material('Studio warm grey',(.78,.77,.73),0,.9)
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.028)); move(bpy.context.object)
    bpy.context.object.name='Studio_Floor'; bpy.context.object.data.materials.append(floor_mat)
    scene=bpy.context.scene
    scene.world.use_nodes=True; scene.world.node_tree.nodes.get('Background').inputs[0].default_value=(.70,.75,.82,1)
    scene.world.node_tree.nodes.get('Background').inputs[1].default_value=.45
    for name,loc,power,size in [('Key',(-5,-8,13),2300,9),('Fill',(2,8,9),2100,8),('Rim',(7,-1,12),2700,7)]:
        bpy.ops.object.light_add(type='AREA',location=loc); ob=bpy.context.object; move(ob)
        ob.name='Studio_'+name; ob.data.energy=power; ob.data.shape='DISK'; ob.data.size=size
        ob.rotation_euler=(Vector((0,0,1.8))-ob.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add(location=(-16,-21,12)); camera=bpy.context.object; move(camera)
    camera.name='Studio_Camera'; camera.data.type='ORTHO'; camera.data.ortho_scale=21.5
    scene.camera=camera; camera.rotation_euler=(Vector((0,0,1.6))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=24; scene.cycles.use_denoising=True
    scene.render.resolution_x=1440; scene.render.resolution_y=1000; scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.view_settings.view_transform='AgX'
    return stage,camera


def render_views(camera):
    scene=bpy.context.scene
    views=[('hero',(-16,-21,12),21.5,(0,0,1.7)),('side',(0,-28,2.3),15.0,(0,0,2.3)),('top',(0,0,32),19.3,(0,0,0)),('front',(-30,0,2.3),18.6,(0,0,2.3))]
    for name,pos,scale,target in views:
        camera.location=pos; camera.data.ortho_scale=scale
        camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
        if name=='top': camera.rotation_euler=(0,0,-PI/2)
        scene.render.filepath=str(ROOT/'previews'/f'{name}.png')
        bpy.ops.render.render(write_still=True)
    camera.location=(-16,-21,12); camera.data.ortho_scale=21.5
    camera.rotation_euler=(Vector((0,0,1.7))-camera.location).to_track_quat('-Z','Y').to_euler()


def main():
    create_aircraft()
    aircraft=list(bpy.data.collections['Aircraft'].objects)
    select_only(aircraft)
    bpy.ops.export_scene.gltf(filepath=str(ROOT/'models/beijing-one.glb'),export_format='GLB',use_selection=True,export_animations=False,export_extras=True)
    tris=0
    for ob in aircraft:
        if ob.type=='MESH': ob.data.calc_loop_triangles(); tris+=len(ob.data.loop_triangles)
    metadata={'version':CFG['revision'],'length_m':12.4,'wingspan_m':16.3,'triangles':tris,'objects':len(aircraft),'glb_bytes':(ROOT/'models/beijing-one.glb').stat().st_size,'fidelity':'reference-based exterior reconstruction; no original engineering drawings','propeller_nodes':['Propeller_L','Propeller_R'],'gear_prefix':'Gear_'}
    (ROOT/'models/model-info.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    stage,camera=setup_render()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'models/beijing-one.blend'))
    render_views(camera)
    # 重新保存主视角；禁用备份避免交付多份未命名历史版本。
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'models/beijing-one.blend'))
    print('MODEL_COMPLETE',json.dumps(metadata),flush=True)


if __name__=='__main__':main()
