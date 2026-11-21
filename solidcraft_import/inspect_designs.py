"""Read-only audit of the supplied SolidCraft archive; does not run its generators."""
from pathlib import Path
import json,zipfile,xml.etree.ElementTree as ET
import FreeCAD as A,Part,Mesh,numpy as np
ROOT=Path(__file__).resolve().parent
report={'native':{},'step':{},'meshes':[]}
for p in ROOT.glob('*/*.sc'):
    with zipfile.ZipFile(p) as z:d=json.loads(z.read('document.json'))
    report['native'][p.parent.name]={'format':d['format'],'params':d['params'],
        'components':d.get('components',[]),'assembly':d.get('assembly',{}),
        'feature_count':len(d['features']),'reference_body_names':[n for n in d.get('appearances',{}).get('bodies',{}) if 'MG995' in n or 'SG90' in n]}
for p in ROOT.glob('*/*.step'):
    s=Part.read(str(p));bb=s.BoundBox
    report['step'][p.parent.name]={'valid':s.isValid(),'solids':len(s.Solids),
        'bbox_mm':[bb.XMin,bb.YMin,bb.ZMin,bb.XMax,bb.YMax,bb.ZMax],
        'invalid_solids':sum(not t.isValid() for t in s.Solids)}
    print('STEP',p.parent.name,report['step'][p.parent.name],flush=True)
for p in ROOT.rglob('*.stl'):
    mesh=Mesh.Mesh(str(p));bb=mesh.BoundBox
    report['meshes'].append({'path':str(p.relative_to(ROOT)),'closed':mesh.isSolid(),
        'triangles':mesh.CountFacets,'bbox':[bb.XMin,bb.YMin,bb.ZMin,bb.XMax,bb.YMax,bb.ZMax]})
tree=ET.parse(ROOT/'brazo_compacto'/'brazo_compacto.urdf');robot=tree.getroot()
report['urdf']={'joints':[{'name':j.get('name'),'type':j.get('type'),
    'axis':j.find('axis').get('xyz') if j.find('axis') is not None else None,
    'limits':j.find('limit').attrib if j.find('limit') is not None else None,
    'mimic':j.find('mimic').attrib if j.find('mimic') is not None else None} for j in robot.findall('joint')],
    'total_exported_mass_kg':sum(float(m.get('value')) for m in robot.findall('link/inertial/mass'))}
# Native assembly home axes are explicit, independent of URDF mesh conventions.
joints=report['native']['brazo_compacto']['assembly']['joints'][:5]
p=np.array([0,14.5,422.5]) # midpoint between the two pad centres at zero jaw angle
origins=[np.array(j['a']['snap']['origin']) for j in joints]
axes=[np.array(j['a']['snap']['z']) for j in joints]
J=np.vstack((np.column_stack([np.cross(a,p-o) for a,o in zip(axes,origins)]),np.column_stack(axes)))
report['compact_home_jacobian']={'angles_deg':[0,0,0,0,0],'tcp_pad_midpoint_mm':p.tolist(),
 'J0':J.tolist(),'XYZ_rank':int(np.linalg.matrix_rank(J[:3])),
 'arm_rank':int(np.linalg.matrix_rank(np.vstack((J[:3]/320,J[3:]))))}
(ROOT/'inspection.json').write_text(json.dumps(report,indent=2))
print('NON-CLOSED MESHES',[r['path'] for r in report['meshes'] if not r['closed']],flush=True)
print('COMPACT HOME JACOBIAN',report['compact_home_jacobian'],flush=True)
print('URDF',report['urdf'],flush=True)
print('REPRESENTATIVE MESH BOUNDS',[(r['path'],r['bbox']) for r in report['meshes'] if 'Base_part' in r['path'] or r['path'].endswith('stl\\Base.stl')],flush=True)
