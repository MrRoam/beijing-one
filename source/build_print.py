"""由同一外形生成 1:72 打印套件。输出 STL、通用 3MF 与几何检查结果。"""
import sys, math, json, zipfile, copy
from pathlib import Path
import xml.etree.ElementTree as ET
import bpy, bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).parent))
import build_model as M
ROOT=M.ROOT; OUT=ROOT/'print'; S=1000/72
PARTS=[]; RESULTS=[]


def mm(ob):
    bpy.context.view_layer.update()
    matrix=ob.matrix_world.copy()
    ob.parent=None; ob.matrix_world=Matrix.Identity(4)
    for v in ob.data.vertices:v.co=matrix@v.co*S
    ob.data.update(); return ob


def boolean(a,b,operation='UNION',remove=True):
    M.select_only([a]); mod=a.modifiers.new('Solid_'+operation,'BOOLEAN'); mod.operation=operation
    mod.solver='EXACT'; mod.object=b
    bpy.ops.object.modifier_apply(modifier=mod.name)
    if remove:bpy.data.objects.remove(b,do_unlink=True)
    return a


def clone(ob,name):
    n=ob.copy(); n.data=ob.data.copy(); n.name=name; bpy.context.collection.objects.link(n); return n


def cyl(name,center,r,depth,axis):
    ob=M.cylinder(name,center,r,depth,None,axis,32)
    M.select_only([ob]); bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    return ob


def cube(name,center,dims):
    bpy.ops.mesh.primitive_cube_add(size=1,location=center); ob=bpy.context.object; ob.name=name; ob.dimensions=dims
    M.select_only([ob]); bpy.ops.object.transform_apply(location=True,rotation=True,scale=True); return ob


def part(ob,name,description,rotation=(0,0,0),quantity=1):
    ob.name=name
    # 清理布尔运算后的微小数值重合，保留实质形状。
    bm=bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-5)
    # 布尔产生的凹多边形先显式三角化；默认导出细分曾在后机身
    # 生成一条被四个三角面共享的对角线，原多边形检查无法发现。
    bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(ob.data); bm.free(); ob.data.update()
    PARTS.append({'object':ob,'name':name,'description':description,'rotation':rotation,'quantity':quantity})
    return ob


def trimmed(stations,start):return [(start,*M.values_at(stations,start))]+[p for p in stations if p[0]>start]


def make_parts():
    M.clean_scene(); white=M.material('Print ivory',(.80,.79,.74),.05,.5)
    body=mm(M.loft('PrintFuselage',M.BODY,white))
    fin=mm(M.wing('PrintFin',M.FIN,1,white,vertical=True,min_thickness=.0792))
    boolean(body,fin)
    for side in [-1,1]:
        suf='L' if side<0 else 'R'
        wing=mm(M.wing('Wing_'+suf,trimmed(M.WING,.62),side,white,min_thickness=.0792))
        nac=mm(M.loft('Nacelle_'+suf,M.NACELLE,white,y=side*2.8,ring=48,steps=4,power=2))
        boolean(wing,nac)
        # 翼根本体的凹槽由实际翼型减去，避免装配时翼根穿入机身实体。
        boolean(body,clone(wing,'Wing_socket_'+suf),'DIFFERENCE')
        for x in [-.80,.10]:
            root=.62*S; z=1.34*S
            boolean(wing,cyl('Wing_integral_pin',(x*S,side*(root-2),z),1.5,6,'Y'))
            boolean(body,cyl('Wing_pin_socket',(x*S,side*(root-2.1),z),1.65,6.3,'Y'),'DIFFERENCE')
        # 固定式螺旋桨轴，预留 0.2 mm 直径间隙。
        boolean(wing,cyl('Prop_axis',(-2.88*S-.8,side*2.8*S,1.52*S),1.0,2.6,'X'))
        part(wing,'03_wing_left' if side<0 else '04_wing_right','机翼与短舱；翼根双定位销；平放，短舱及销下方需要支撑')
        tail=mm(M.wing('Tail_'+suf,trimmed(M.TAIL,.30),side,white,min_thickness=.0792))
        boolean(body,clone(tail,'Tail_socket_'+suf),'DIFFERENCE')
        root=.30*S; x=4.35*S; z=2.705*S
        boolean(tail,cyl('Tail_integral_pin',(x,side*(root-.8),z),.85,3.0,'Y'))
        boolean(body,cyl('Tail_pin_socket',(x,side*(root-.85),z),1.0,3.3,'Y'),'DIFFERENCE')
        part(tail,'05_tail_left' if side<0 else '06_tail_right','平尾；一体定位销；平放并按需支撑')
        # 桨叶厚 1.2 mm、轮毂厚 2 mm；不复用展示版的薄桨叶和小螺帽。
        shape=[(.07,-.07),(.30,-.125),(.78,-.11),(1.09,-.055),(1.18,.015),(1.15,.070),(.86,.12),(.39,.115),(.13,.060)]
        hub=cyl('Print_prop_hub',(-2.88*S-1.15,side*2.8*S,1.52*S),2.7,2.0,'X')
        for k in [0,1]:
            leaf=M.poly_extrude('Print_prop_blade',[(a*S,b*S) for a,b in shape],1.2,white)
            leaf.rotation_euler[0]=k*math.pi+math.pi/2+.24
            leaf.location=(-2.88*S-1.15+.4,side*2.8*S,1.52*S)
            M.select_only([leaf]); bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
            boolean(hub,leaf)
        boolean(hub,cyl('Prop_hole',(-2.88*S-1.15,side*2.8*S,1.52*S),1.1,4,'X'),'DIFFERENCE')
        part(hub,'07_propeller_left' if side<0 else '08_propeller_right','加厚双叶桨；中心孔 2.2 mm；平面朝平台',(0,math.pi/2,0))
    # 底座定位孔位于机腹，用于静态摆件。
    boolean(body,cyl('Stand_socket',(0,0,17.8),2.2,5.5,'Z'),'DIFFERENCE')
    split=.60*S
    fore=clone(body,'Front'); aft=clone(body,'Rear')
    boolean(fore,cube('Fore_half',(split-250,0,0),(500,500,500)),'INTERSECT')
    boolean(aft,cube('Aft_half',(split+250,0,0),(500,500,500)),'INTERSECT')
    bpy.data.objects.remove(body,do_unlink=True)
    for y in [-4.8,4.8]:
        boolean(fore,cyl('Join_socket',(split-2.25,y,2.2*S),1.65,5.0,'X'),'DIFFERENCE')
        boolean(aft,cyl('Join_socket',(split+2.25,y,2.2*S),1.65,5.0,'X'),'DIFFERENCE')
    part(fore,'01_fuselage_front','前机身；分割平面朝平台；两孔为 3.3 mm',(0,math.pi/2,0))
    part(aft,'02_fuselage_rear','后机身与垂尾；分割平面朝平台；机翼和平尾插槽已经预留',(0,-math.pi/2,0))
    pin=cyl('Join_pin',(0,0,4.5),1.5,9,'Z')
    part(pin,'09_join_pin','直径 3 mm、长度 9 mm；打印两根；先用配合试片确认',quantity=2)
    # 整体底座，机身在摆放时比原始装配坐标升高 20 mm。
    base=cyl('Stand_base',(0,0,2),1,4,'Z')
    for v in base.data.vertices:v.co.x*=35; v.co.y*=22.5
    boolean(base,cyl('Stand_column',(0,0,20),4.5,32.6,'Z'))
    boolean(base,cyl('Stand_locator',(0,0,38),2.0,4.2,'Z'))
    saddle=clone(fore,'Stand_saddle_clearance')
    for v in saddle.data.vertices:v.co.z+=19.9
    saddle.data.update();boolean(base,saddle,'DIFFERENCE')
    part(base,'10_display_stand','70 × 45 mm 底座；整体竖直打印；顶部定位销 4 mm')
    # 通用间隙试片：与机身相同 3 mm 销，试验不同孔径。
    coupon=cube('Fit_coupon',(0,0,2),(38,12,4))
    boolean(coupon,cyl('Coupon_orientation_notch',(-19,-6,2),2.0,6,'Z'),'DIFFERENCE')
    for i,diam in enumerate([3.10,3.20,3.30,3.40]):
        boolean(coupon,cyl('Coupon_hole',(-13.5+i*9,0,2),diam/2,6,'Z'),'DIFFERENCE')
    part(coupon,'11_fit_coupon','从缺口端起孔径 3.10 / 3.20 / 3.30 / 3.40 mm；用 09 号销测试')
    PARTS.sort(key=lambda p:p['name'])
    for p in PARTS:
        if not p['object'].data.materials:p['object'].data.materials.append(white)


def validate(ob):
    bm=bmesh.new(); bm.from_mesh(ob.data)
    nonmanifold=sum(not e.is_manifold for e in bm.edges)
    volume=bm.calc_volume(signed=True)
    unseen=set(bm.verts); count=0
    while unseen:
        count+=1; queue=[unseen.pop()]
        while queue:
            v=queue.pop()
            for e in v.link_edges:
                w=e.other_vert(v)
                if w in unseen:unseen.remove(w); queue.append(w)
    bm.free()
    ob.data.calc_loop_triangles()
    verts=[v.co.copy() for v in ob.data.vertices]; faces=[tuple(t.vertices) for t in ob.data.loop_triangles]
    tree=BVHTree.FromPolygons(verts,faces,all_triangles=True,epsilon=1e-7)
    overlap=set()
    for a,b in tree.overlap(tree):
        if a<b and not (set(faces[a])&set(faces[b])):overlap.add((a,b))
    return {'non_manifold_edges':nonmanifold,'connected_components':count,'volume_mm3':round(volume,3),'triangles':len(faces),'possible_self_intersections':len(overlap),'passed':nonmanifold==0 and count==1 and volume>0 and not overlap}


def geometry(ob,rotation=(0,0,0),bed=False):
    from mathutils import Euler
    rot=Euler(rotation).to_matrix()
    vs=[rot@v.co for v in ob.data.vertices]
    if bed:
        mins=Vector(tuple(min(v[i] for v in vs) for i in range(3)))
        vs=[v-mins for v in vs]
    ob.data.calc_loop_triangles(); fs=[tuple(t.vertices) for t in ob.data.loop_triangles]
    return [tuple(v) for v in vs],fs


def write_3mf(path,entries):
    ns='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
    ET.register_namespace('',ns); model=ET.Element('{'+ns+'}model',{'unit':'millimeter','{http://www.w3.org/XML/1998/namespace}lang':'zh-CN'})
    ET.SubElement(model,'{'+ns+'}metadata',{'name':'Title'}).text='Beijing No.1 — generic geometry, no printer profile'
    resources=ET.SubElement(model,'{'+ns+'}resources'); build=ET.SubElement(model,'{'+ns+'}build')
    for i,(name,vs,fs,translation) in enumerate(entries,1):
        obj=ET.SubElement(resources,'{'+ns+'}object',{'id':str(i),'type':'model','name':name})
        me=ET.SubElement(obj,'{'+ns+'}mesh'); vertices=ET.SubElement(me,'{'+ns+'}vertices'); triangles=ET.SubElement(me,'{'+ns+'}triangles')
        for v in vs:ET.SubElement(vertices,'{'+ns+'}vertex',{a:f'{v[j]:.6f}' for j,a in enumerate('xyz')})
        for f in fs:ET.SubElement(triangles,'{'+ns+'}triangle',{f'v{j+1}':str(f[j]) for j in range(3)})
        tx,ty,tz=translation
        ET.SubElement(build,'{'+ns+'}item',{'objectid':str(i),'transform':f'1 0 0 0 1 0 0 0 1 {tx:.6f} {ty:.6f} {tz:.6f}'})
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr('_rels/.rels','<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr('3D/3dmodel.model',ET.tostring(model,encoding='utf-8',xml_declaration=True))


def check_assembly():
    objects=[]
    for p in PARTS:
        if p['name'].startswith(('09','11')):continue
        ob=clone(p['object'],'Check_'+p['name'])
        if not p['name'].startswith('10'):
            for v in ob.data.vertices:v.co.z+=20
        objects.append(ob)
    for y in [-4.8,4.8]:objects.append(cyl('Check_dowel',(.60*S,y,2.2*S+20),1.5,9,'X'))
    bounds={ob.name:([min(v.co[i] for v in ob.data.vertices) for i in range(3)],[max(v.co[i] for v in ob.data.vertices) for i in range(3)]) for ob in objects}
    collisions=[]; tested=0
    for i,a in enumerate(objects):
        for b in objects[i+1:]:
            amin,amax=bounds[a.name];bmin,bmax=bounds[b.name]
            if any(amax[k]<bmin[k] or bmax[k]<amin[k] for k in range(3)):continue
            probe=clone(a,'Intersection_probe');boolean(probe,b,'INTERSECT',False)
            bm=bmesh.new();bm.from_mesh(probe.data);volume=abs(bm.calc_volume(signed=True));bm.free();tested+=1
            if volume>.01:collisions.append({'a':a.name,'b':b.name,'overlap_mm3':round(volume,6)})
            bpy.data.objects.remove(probe,do_unlink=True)
    for ob in objects:bpy.data.objects.remove(ob,do_unlink=True)
    result={'candidate_pairs_tested':tested,'collision_tolerance_mm3':.01,'collisions':collisions,'passed':not collisions,'method':'Exact boolean intersections of assembled parts, including alignment dowels and stand'}
    (OUT/'assembly-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('ASSEMBLY_CHECK',json.dumps(result),flush=True)
    return result


def export_parts():
    placements=[]; plate=1; px=5; py=5; rowheight=0; entries=[]; assembly=[]
    for p in PARTS:
        ob=p['object']; checks=validate(ob)
        vs,fs=geometry(ob,p['rotation'],True)
        dims=[max(v[i] for v in vs)-min(v[i] for v in vs) for i in range(3)]
        export=M.mesh('Export_'+p['name'],vs,fs)
        M.select_only([export]); bpy.ops.wm.stl_export(filepath=str(OUT/(p['name']+'.stl')),export_selected_objects=True,global_scale=1.0)
        bpy.data.objects.remove(export,do_unlink=True)
        RESULTS.append({'id':p['name'],'description':p['description'],'quantity':p['quantity'],'dimensions_mm':[round(v,2) for v in dims],**checks})
        print('PRINT_CHECK',p['name'],json.dumps(checks),flush=True)
        for k in range(p['quantity']):
            if px+dims[0]>205:px=5; py+=rowheight+8; rowheight=0
            if py+dims[1]>205:
                write_3mf(OUT/f'layout-{plate:02d}.3mf',entries); entries=[]; plate+=1; px=5; py=5; rowheight=0
            entries.append((p['name']+'_'+str(k+1),vs,fs,(px,py,0)))
            placements.append({'id':p['name'],'instance':k+1,'plate':plate,'xy':[px,py],'dimensions_mm':dims})
            px+=dims[0]+8; rowheight=max(rowheight,dims[1])
        # 装配参考包包含飞机和底座；配合试片与自由销不混入装配形态。
        if not p['name'].startswith(('09','11')):
            av,af=geometry(ob)
            assembly.append((p['name'],av,af,(90,120,0 if p['name'].startswith('10') else 20)))
    if entries:write_3mf(OUT/f'layout-{plate:02d}.3mf',entries)
    for y in [-4.8,4.8]:
        pin=cyl('Assembled_pin',(.60*S,y,2.2*S),1.5,9,'X'); vs,fs=geometry(pin)
        assembly.append(('09_join_pin',vs,fs,(90,120,20))); bpy.data.objects.remove(pin,do_unlink=True)
    write_3mf(OUT/'assembly-reference.3mf',assembly)
    manifest={'scale':'1:72','units':'millimetres','printer':'not selected','material':'not selected','layout_reference_bed_mm':[210,210],'layout_is_printer_profile':False,'body_length_mm':round(12.4*S,3),'wingspan_mm':round(16.3*S,3),'wing_tail_min_edge_mm':1.1,'propeller_thickness_mm':1.2,'wing_joint_pin_diameter_mm':3.0,'wing_joint_hole_diameter_mm':3.3,'parts':RESULTS,'placements':placements,'geometry_passed':all(p['passed'] for p in RESULTS),'physical_fit_tested':False,'machine_sliced':False}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    # 留下可编辑的毫米制打印工程。
    bpy.context.scene.unit_settings.system='METRIC'; bpy.context.scene.unit_settings.scale_length=.001
    bpy.context.preferences.filepaths.save_version=0
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_distance=300
                area.spaces.active.region_3d.view_location=(0,0,25)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'beijing-one-print.blend'))
    if not manifest['geometry_passed']:raise RuntimeError('打印几何检查发现问题，请查看 manifest.json')


def main():
    make_parts(); assembly=check_assembly(); export_parts()
    if not assembly['passed']:raise RuntimeError('装配实体干涉检查未通过')
    print('PRINT_KIT_COMPLETE',flush=True)


if __name__=='__main__':main()
