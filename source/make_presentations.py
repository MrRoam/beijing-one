"""整理源工程初始视角、比例草模、正交轮廓及打印装配预览。"""
import bpy, sys, math, json
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).parent))
import build_model as M
ROOT=M.ROOT


def frame_view(distance=28,location=(0,0,2)):
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active;space.region_3d.view_distance=distance;space.region_3d.view_location=location
                space.region_3d.view_rotation=(Vector((-16,-21,12))-Vector(location)).to_track_quat('Z','Y')
                space.shading.type='SOLID';space.shading.color_type='MATERIAL'


def outline_svg(objects):
    views=[('俯视 / TOP',Vector((0,0,1)),(1,0),(0,1),310,350,26),('侧视 / SIDE',Vector((0,-1,0)),(0,2),(1,-1),865,380,37),('正视 / FRONT',Vector((-1,0,0)),(1,2),(1,-1),620,840,50)]
    pieces=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1240 1000"><rect width="1240" height="1000" fill="#f6f4ed"/><g fill="#323b3b" font-family="Microsoft YaHei, sans-serif"><text x="50" y="52" font-size="24">北京一号 · 比例研究</text><text x="50" y="80" font-size="12" fill="#7c817b">模型正交轮廓 · 总体尺度约束 / 局部形状推定 · 非原始工程三视图</text></g>']
    for title,direction,axes,signs,cx,cy,scale in views:
        # 第一项俯视将机头朝左，采用 x/y 平面，并保持翼展纵向。
        if title.startswith('俯视'):axes=(0,1);signs=(1,1)
        paths=[]
        for ob in objects:
            if ob.type!='MESH':continue
            me=ob.data;edge_faces={}
            for f in me.polygons:
                facing=f.normal.dot(direction)>=0
                for edge in f.edge_keys:edge_faces.setdefault(tuple(sorted(edge)),[]).append(facing)
            for (a,b),flags in edge_faces.items():
                if len(flags)!=2 or flags[0]!=flags[1]:
                    p,q=ob.matrix_world@me.vertices[a].co,ob.matrix_world@me.vertices[b].co
                    paths.append(f'M{cx+p[axes[0]]*scale*signs[0]:.2f},{cy+p[axes[1]]*scale*signs[1]:.2f}L{cx+q[axes[0]]*scale*signs[0]:.2f},{cy+q[axes[1]]*scale*signs[1]:.2f}')
        pieces.append(f'<path d="{" ".join(paths)}" fill="none" stroke="#536265" stroke-width=".85"/>')
        lx=50 if title.startswith('俯视') else (620 if title.startswith('侧视') else 50)
        ly=595 if title.startswith('俯视') else (480 if title.startswith('侧视') else 900)
        pieces.append(f'<text x="{lx}" y="{ly}" fill="#323b3b" font-size="14" font-family="Microsoft YaHei,sans-serif">{title}</text>')
    pieces.append('<g stroke="#ae483a" stroke-width="1" fill="none"><path d="M148.8 575H471.2M148.8 569V581M471.2 569V581"/><path d="M212.5 870H1027.5M212.5 864V876M1027.5 864V876"/></g><g fill="#ae483a" font-size="12" font-family="Microsoft YaHei,sans-serif"><text x="260" y="597">机长 12.4 m</text><text x="567" y="895">翼展 16.3 m</text></g><text x="50" y="960" fill="#7c817b" font-family="Microsoft YaHei,sans-serif" font-size="12">尺寸来源：北航刊物 PDF 第31页（印刷页29）。另有翼展16.4m记载，差异见资料说明。</text></svg>')
    (ROOT/'previews/proportion-study.svg').write_text(''.join(pieces),encoding='utf-8')


def main():
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'models/beijing-one.blend'))
    bpy.context.preferences.filepaths.save_version=0
    frame_view()
    studio=bpy.data.collections.get('Studio')
    if studio:studio.hide_viewport=True
    M.select_only([bpy.data.objects['Fuselage']])
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'models/beijing-one.blend'))
    names={'Fuselage','Wing_L','Wing_R','Tailplane_L','Tailplane_R','Vertical_fin','Nacelle_L','Nacelle_R'}
    for ob in list(bpy.data.collections['Aircraft'].objects):
        if ob.name not in names:bpy.data.objects.remove(ob,do_unlink=True)
    base=M.material('Blockout neutral',(.49,.55,.58),0,.65)
    for ob in bpy.data.collections['Aircraft'].objects:
        ob.data.materials.clear();ob.data.materials.append(base)
    outline_svg(list(bpy.data.collections['Aircraft'].objects))
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'models/beijing-one-blockout.blend'))

    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'print/beijing-one-print.blend'))
    for ob in list(bpy.context.scene.objects):
        if ob.name.startswith(('09','11')):bpy.data.objects.remove(ob,do_unlink=True)
    objs=list(bpy.context.scene.objects)
    for ob in objs:
        for v in ob.data.vertices:
            if not ob.name.startswith('10'):v.co.z+=20
            v.co/=1000/72
        ob.data.update()
    bpy.context.scene.unit_settings.scale_length=1
    stage,camera=M.setup_render()
    # 展示底座上方的打印版。
    camera.location=(-17,-22,14);camera.data.ortho_scale=22
    camera.rotation_euler=(Vector((0,0,2.6))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene=bpy.context.scene;scene.render.filepath=str(ROOT/'previews/print-assembled.png');bpy.ops.render.render(write_still=True)
    offsets={'01':(-1.15,0,.4),'02':(1.15,0,.4),'03':(0,-1.65,.4),'04':(0,1.65,.4),'05':(1.15,-1.35,.9),'06':(1.15,1.35,.9),'07':(-1.0,-1.65,.4),'08':(-1.0,1.65,.4),'10':(0,0,0)}
    ink=M.material('Labels',(.11,.14,.15),0,.9)
    camera.location=(-19,-25,16);camera.data.ortho_scale=28
    camera.rotation_euler=(Vector((0,0,2.8))-camera.location).to_track_quat('-Z','Y').to_euler()
    for ob in objs:
        ob.location=offsets.get(ob.name[:2],(0,0,0))
        coords=[v.co+ob.location for v in ob.data.vertices]
        center=sum(coords,Vector())/len(coords)
        center.z=max(v.z for v in coords)+.30
        if ob.name.startswith('01'):center.x-=1.2
        if ob.name.startswith('02'):center.x+=1.0
        curve=bpy.data.curves.new('Part_number','FONT');curve.body=ob.name[:2];curve.size=.28;curve.align_x='CENTER'
        label=bpy.data.objects.new('Label_'+ob.name,curve);bpy.context.collection.objects.link(label)
        label.location=center;label.rotation_euler=camera.rotation_euler;label.data.materials.append(ink)
    scene.render.filepath=str(ROOT/'previews/print-exploded.png');bpy.ops.render.render(write_still=True)
    print('PRESENTATIONS_COMPLETE',flush=True)


if __name__=='__main__':main()
