"""Orient existing individual print STLs and create arranged core-3MF plates.
No CAD geometry is altered. Output uses the original millimetre meshes, one of each part.
"""
from pathlib import Path
import json,zipfile,xml.etree.ElementTree as ET
import FreeCAD,Mesh,numpy as np
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'bambu_print';OUT.mkdir(exist_ok=True)
SRC=ROOT/'brazo_compacto'/'stl'
NS='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
ET.register_namespace('',NS)
def rx(d):
    a=np.radians(d);c,s=np.cos(a),np.sin(a)
    return np.array([[1,0,0],[0,c,-s],[0,s,c]])
def rz(d):
    a=np.radians(d);c,s=np.cos(a),np.sin(a)
    return np.array([[c,-s,0],[s,c,0],[0,0,1]])
plates={
 'A2L_structural':[
    ('Base',np.eye(3),(90,90),'Flange down; internal tree support'),
    ('Turntable',rx(180),(255,70),'Flat cap face down; skirt up'),
    ('UpperArm',rz(90)@rx(-90),(85,235),'Broad outer cheek down; tree support for upper cheek'),
    ('WristFork',rz(90)@rx(-90),(220,230),'Broad outer cheek down; tree support for upper cheek'),
    ('GripperFrame',np.eye(3),(285,160),'Palm down; tree support at horizontal bosses')],
 'A1mini_links_and_jaws':[
    ('Forearm',rx(-90),(29,71.5),'Closed back down; cavity opens upward'),
    ('ForearmLid',rx(90),(83,71.5),'Flat outer lid face down; bosses up'),
    ('Tower',rx(-90),(137,37.5),'Closed back down; cavity opens upward'),
    ('TowerLid',rx(90),(137,108.5),'Flat outer lid face down; bosses up'),
    ('JawL',rz(90)@rx(-90),(38.5,159),'Broad flat face down; gear teeth in bed plane'),
    ('JawR',rz(90)@rx(-90),(113.5,159),'Broad flat face down; horn recess upward')]
}
def make_plate(name,items):
    model=ET.Element('{%s}model'%NS,{'unit':'millimeter','xml:lang':'en-US'})
    ET.SubElement(model,'{%s}metadata'%NS,{'name':'Application'}).text='BambuStudio'
    resources=ET.SubElement(model,'{%s}resources'%NS);build=ET.SubElement(model,'{%s}build'%NS)
    manifest=[]
    for number,(part,rotation,centre,note) in enumerate(items,1):
        mesh=Mesh.Mesh(str(SRC/(part+'.stl')));points,triangles=mesh.Topology
        vertices=np.array([[v.x,v.y,v.z] for v in points])@rotation.T
        low=vertices.min(axis=0);high=vertices.max(axis=0)
        vertices+=np.array([centre[0]-(low[0]+high[0])/2,centre[1]-(low[1]+high[1])/2,-low[2]])
        low=vertices.min(axis=0);high=vertices.max(axis=0)
        bed=(330,320) if name.startswith('A2L') else (180,180)
        assert low[0]>=3 and low[1]>=3 and high[0]<=bed[0]-3 and high[1]<=bed[1]-3,(part,low,high)
        obj=ET.SubElement(resources,'{%s}object'%NS,{'id':str(number),'type':'model','name':part})
        node=ET.SubElement(obj,'{%s}mesh'%NS);vs=ET.SubElement(node,'{%s}vertices'%NS)
        for x,y,z in vertices:ET.SubElement(vs,'{%s}vertex'%NS,{'x':f'{x:.7f}','y':f'{y:.7f}','z':f'{z:.7f}'})
        ts=ET.SubElement(node,'{%s}triangles'%NS)
        for a,b,c in triangles:ET.SubElement(ts,'{%s}triangle'%NS,{'v1':str(a),'v2':str(b),'v3':str(c)})
        ET.SubElement(build,'{%s}item'%NS,{'objectid':str(number)})
        manifest.append({'part':part,'source':str(SRC/(part+'.stl')),'quantity':1,
           'bed_bounds_mm':[low.tolist(),high.tolist()],'orientation':note,'rotation':rotation.tolist()})
    for i,a in enumerate(manifest):
        for b in manifest[i+1:]:
            al,ah=np.array(a['bed_bounds_mm']);bl,bh=np.array(b['bed_bounds_mm'])
            assert not np.all(np.minimum(ah[:2],bh[:2])-np.maximum(al[:2],bl[:2])>0),(a['part'],b['part'],'overlap')
    with zipfile.ZipFile(OUT/(name+'.3mf'),'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr('_rels/.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr('3D/3dmodel.model',ET.tostring(model,encoding='utf-8',xml_declaration=True))
    return manifest
result={name:make_plate(name,items) for name,items in plates.items()}
(OUT/'batch_manifest.json').write_text(json.dumps(result,indent=2))
# Single part to obtain a Bambu Studio-native project settings template, if needed.
make_plate('template',[('JawL',rz(90)@rx(-90),(90,90),'Template only; not an additional print')])
print(json.dumps({k:[x['part'] for x in v] for k,v in result.items()},indent=2))
