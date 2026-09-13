"""独立于 Blender 的交付格式、三角网格、排版和截面检查；仅使用 Python 标准库。"""
import json, struct, math, collections, zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'print'


def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def dot(a,b):return sum(x*y for x,y in zip(a,b))


def read_stl(path):
    data=path.read_bytes();count=struct.unpack_from('<I',data,80)[0]
    assert len(data)==84+count*50,(path,'length')
    triangles=[]
    for i in range(count):
        row=struct.unpack_from('<12fH',data,84+i*50);tri=tuple(tuple(row[3+3*j:6+3*j]) for j in range(3))
        assert all(math.isfinite(v) for p in tri for v in p)
        triangles.append(tri)
    return triangles


def check_triangles(tris):
    edges=collections.Counter();directed=collections.Counter();volume=0;degenerate=0
    for tri in tris:
        area=cross(sub(tri[1],tri[0]),sub(tri[2],tri[0]));degenerate+=dot(area,area)<1e-14
        volume+=dot(tri[0],cross(tri[1],tri[2]))/6
        keys=[tuple(round(v,5) for v in p) for p in tri]
        for a,b in zip(keys,keys[1:]+keys[:1]):edges[tuple(sorted((a,b)))]+=1;directed[(a,b)]+=1
    bad=sum(c!=2 for c in edges.values())
    winding=sum(directed[(a,b)]!=1 or directed[(b,a)]!=1 for a,b in edges)
    return {'triangles':len(tris),'boundary_or_nonmanifold_edges':bad,'inconsistent_winding_edges':winding,'degenerate_triangles':degenerate,'volume_mm3':round(volume,3),'passed':bad==0 and winding==0 and degenerate==0 and volume>0}


def section(tris,z):
    segments=[]
    for tri in tris:
        hits=[]
        for a,b in zip(tri,tri[1:]+tri[:1]):
            if (a[2]<z<b[2]) or (b[2]<z<a[2]):
                t=(z-a[2])/(b[2]-a[2]);hits.append((a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])))
        if len(hits)==2:segments.append(hits)
    degree=collections.Counter(tuple(round(v,4) for v in p) for segment in segments for p in segment)
    # 顶点量化恰好落在短线段上时可合并同点；奇数度才是开放截面的信号。
    return segments,sum(v%2 for v in degree.values())


def main():
    manifest=json.loads((P/'manifest.json').read_text(encoding='utf-8'))
    checks=[];svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="'+str(115+len(manifest['parts'])*155)+'" viewBox="0 0 1100 '+str(115+len(manifest['parts'])*155)+'"><rect width="100%" height="100%" fill="#f5f3ed"/><g font-family="Microsoft YaHei,sans-serif" fill="#303a3c"><text x="34" y="40" font-size="23">打印零件 · 几何截面预检</text><text x="34" y="67" font-size="12" fill="#777f78">各零件高度的 12%、50%、88% 截面。单位 mm；不是打印机切片，不包含支撑、路径或 G-code。</text></g>']
    for row,part in enumerate(manifest['parts']):
        tris=read_stl(P/(part['id']+'.stl'));result=check_triangles(tris);result['id']=part['id']
        pts=[p for t in tris for p in t];mins=[min(p[i] for p in pts) for i in range(3)];maxs=[max(p[i] for p in pts) for i in range(3)];dims=[b-a for a,b in zip(mins,maxs)]
        result['dimensions_match']=all(abs(a-b)<.015 for a,b in zip(dims,part['dimensions_mm']))
        result['bed_min_z_mm']=round(mins[2],6);result['sections']=[]
        y0=105+row*155
        svg.append(f'<text x="34" y="{y0+15}" font-family="monospace" font-size="12" fill="#a44538">{part["id"]}</text>')
        for col,f in enumerate([.12,.50,.88]):
            z=mins[2]+dims[2]*f+1e-7;segments,odd=section(tris,z)
            result['sections'].append({'height_mm':round(z,3),'segments':len(segments),'open_endpoints':odd})
            scale=min(210/max(dims[0],1),95/max(dims[1],1));ox=275+col*270;oy=y0+33
            path=' '.join(f'M{ox+(a[0]-mins[0])*scale:.3f},{oy+(a[1]-mins[1])*scale:.3f}L{ox+(b[0]-mins[0])*scale:.3f},{oy+(b[1]-mins[1])*scale:.3f}' for a,b in segments)
            svg.append(f'<text x="{ox}" y="{y0+15}" fill="#788077" font-size="10" font-family="sans-serif">z = {z:.2f} mm / {f:.0%}</text><path d="{path}" stroke="#586b6b" stroke-width="1.1" fill="none"/>')
        result['passed']=result['passed'] and result['dimensions_match'] and abs(mins[2])<.001 and all(s['open_endpoints']==0 and s['segments']>0 for s in result['sections'])
        checks.append(result)
        svg.append(f'<path d="M34 {y0+145}H1065" stroke="#d7d8cf"/>')
    svg.append('</svg>');(ROOT/'previews/section-check.svg').write_text(''.join(svg),encoding='utf-8')
    packages=[];ns={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
    for path in sorted(P.glob('*.3mf')):
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            doc=ET.fromstring(z.read('3D/3dmodel.model'));assert doc.attrib['unit']=='millimeter'
            objects=doc.findall('m:resources/m:object',ns);ids={o.attrib['id'] for o in objects}
            for o in objects:
                verts=[tuple(float(v.attrib[a]) for a in 'xyz') for v in o.findall('m:mesh/m:vertices/m:vertex',ns)]
                assert all(math.isfinite(c) for v in verts for c in v)
                for t in o.findall('m:mesh/m:triangles/m:triangle',ns):assert all(0<=int(t.attrib[f'v{i}'])<len(verts) for i in [1,2,3])
            for item in doc.findall('m:build/m:item',ns):assert item.attrib['objectid'] in ids
            packages.append({'file':path.name,'objects':len(objects),'xml_indices_units_and_zip_passed':True})
    placements=manifest['placements'];layout_ok=True
    for i,a in enumerate(placements):
        ax,ay=a['xy'];aw,ah,_=a['dimensions_mm'];layout_ok &= ax>=0 and ay>=0 and ax+aw<=210 and ay+ah<=210
        for b in placements[i+1:]:
            if a['plate']!=b['plate']:continue
            bx,by=b['xy'];bw,bh,_=b['dimensions_mm']
            assert ax+aw<=bx or bx+bw<=ax or ay+ah<=by or by+bh<=ay,'layout overlap'
    data=(ROOT/'models/beijing-one.glb').read_bytes();magic,version,length=struct.unpack_from('<4sII',data)
    assert magic==b'glTF' and version==2 and length==len(data)
    size,kind=struct.unpack_from('<II',data,12);gltf=json.loads(data[20:20+size]);names={n.get('name') for n in gltf['nodes']}
    assert {'Propeller_L','Propeller_R'}<=names
    assert not any('uri' in b for b in gltf.get('buffers',[]))
    report={'stl':checks,'three_mf':packages,'layout_no_overlap_and_within_reference_plate':bool(layout_ok),'glb':{'bytes':len(data),'version':version,'self_contained':True,'propeller_nodes_verified':True},'assembly':json.loads((P/'assembly-check.json').read_text(encoding='utf-8')),'machine_slicing_performed':False,'physical_print_tested':False}
    report['passed']=all(c['passed'] for c in checks) and bool(layout_ok) and report['assembly']['passed']
    (ROOT/'docs/asset-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'parts':len(checks),'three_mf_packages':len(packages),'stl_failures':[c for c in checks if not c['passed']]},ensure_ascii=False))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
