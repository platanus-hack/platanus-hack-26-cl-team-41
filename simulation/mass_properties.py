"""CAD-derived component mass/inertia estimates, with explicit measured-mass overrides.
Integrates closed print-STL volumes; substitutes catalog servo mass, avoiding CAD
dummy-servo material density. Original source assets are read only.
"""
from pathlib import Path
import csv,json,struct,xml.etree.ElementTree as ET
import numpy as np
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'solidcraft_import'/'brazo_compacto'
PARTS={'Base_part':['Base'],'Shoulder_part':['Turntable','Tower','TowerLid'],
 'UpperArm_part':['UpperArm'],'Forearm_part':['Forearm','ForearmLid'],
 'Wrist_part':['WristFork'],'Gripper_part':['GripperFrame'],'JawR_part':['JawR'],'JawL_part':['JawL']}
SERVOS={
 'Base_part':[('MG995 Base','MG995',[.01015,0,.0405],[.0407,.0197,.036])],
 'Shoulder_part':[('MG995 Shoulder','MG995',[0,.0026,.10185],[.0197,.036,.0407])],
 'Forearm_part':[('MG995 Elbow','MG995',[0,.0026,.21215],[.0197,.036,.0407]),('MG995 Wrist','MG995',[0,.0026,.27685],[.0197,.036,.0407])],
 'Wrist_part':[('SG90 Roll','SG90',[.0054,0,.33035],[.0228,.0122,.0227])],
 'Gripper_part':[('SG90 Grip','SG90',[.0106,-.00685,.3706],[.0122,.0227,.0228])]}
HARDWARE={
 'Base_part':(.010,[0,0,.03]),'Shoulder_part':(.008,[0,0,.09]),'UpperArm_part':(.008,[0,0,.157]),
 'Forearm_part':(.008,[0,0,.2445]),'Wrist_part':(.005,[0,0,.31]),'Gripper_part':(.004,[0,0,.37]),
 'JawR_part':(.002,[.0106,.0145,.40]),'JawL_part':(.002,[-.0106,.0145,.40])}
def offset_inertia(m,c):return m*(float(c@c)*np.eye(3)-np.outer(c,c))
def mesh_integrals(path):
    data=Path(path).read_bytes();count=struct.unpack_from('<I',data,80)[0]
    dtype=np.dtype([('normal','<f4',(3,)),('vertices','<f4',(3,3)),('attr','<u2')])
    if len(data)!=84+50*count:raise ValueError('Expected binary STL: '+str(path))
    t=np.array(np.frombuffer(data,dtype,count=count,offset=84)['vertices'],dtype=float)*.001
    anchor=(t.min(axis=(0,1))+t.max(axis=(0,1)))/2;t-=anchor
    vol=np.einsum('ij,ij->i',t[:,0],np.cross(t[:,1],t[:,2]))/6
    if vol.sum()<0:vol=-vol
    volume=vol.sum()
    if volume<=0:raise ValueError('Nonpositive signed mesh volume')
    sums=t.sum(axis=1);centre=(vol[:,None]*sums).sum(axis=0)/(4*volume)
    second=np.einsum('i,ij,ik->jk',vol,sums,sums)/20+np.einsum('i,iaj,iak->jk',vol,t,t)/20
    inertia=np.trace(second)*np.eye(3)-second-offset_inertia(volume,centre)
    if np.linalg.eigvalsh(inertia).min()<=0:raise ValueError('Nonphysical mesh inertia')
    return float(volume),centre+anchor,inertia
def rotation(rpy):
    r,p,y=rpy;cr,sr=np.cos(r),np.sin(r);cp,sp=np.cos(p),np.sin(p);cy,sy=np.cos(y),np.sin(y)
    return np.array([[cy,-sy,0],[sy,cy,0],[0,0,1]])@np.array([[cp,0,sp],[0,1,0],[-sp,0,cp]])@np.array([[1,0,0],[0,cr,-sr],[0,sr,cr]])
def source_frames():
    robot=ET.parse(SOURCE/'brazo_compacto.urdf').getroot();frames={'base_link':np.eye(4)}
    pending=list(robot.findall('joint'))
    while pending:
        for j in pending[:]:
            parent=j.find('parent').get('link');child=j.find('child').get('link')
            if parent not in frames:continue
            o=j.find('origin');T=np.eye(4);T[:3,:3]=rotation([float(x) for x in o.get('rpy','0 0 0').split()]);T[:3,3]=[float(x) for x in o.get('xyz','0 0 0').split()]
            frames[child]=frames[parent]@T;pending.remove(j)
    return frames
def build_masses(profile,write_report=True):
    measured={};path=ROOT/'calibration'/'part_masses.csv'
    if path.exists():
        for row in csv.DictReader(path.open(newline='')):
            if row['mass_g'].strip():
                value=float(row['mass_g'])/1000
                if not np.isfinite(value) or value<=0:raise ValueError('Measured mass must be positive: '+row['component'])
                measured[row['component']]=value
    frames=source_frames();report={};part_rows=[]
    for link,names in PARTS.items():
        pieces=[]
        for name in names:
            volume,centre,unit_inertia=mesh_integrals(SOURCE/'stl'/(name+'.stl'))
            density=profile['mass']['pla_density_kg_m3']*profile['mass']['printed_solid_fraction']
            mass=measured.get(name,volume*density);inertia=unit_inertia*(mass/volume)
            pieces.append((mass,centre,inertia))
            part_rows.append({'component':name,'kind':'printed','mass_kg':mass,'solid_volume_cm3':volume*1e6,
                'provenance':'measured mass + CAD distribution' if name in measured else 'CAD volume x assumed PLA density x assumed solid fraction'})
        for name,kind,centre,dimensions in SERVOS.get(link,[]):
            mass=measured.get(name,profile['mass'][kind+'_mass_kg']);x,y,z=dimensions
            inertia=np.diag([y*y+z*z,x*x+z*z,x*x+y*y])*(mass/12)
            pieces.append((mass,np.array(centre),inertia))
            part_rows.append({'component':name,'kind':kind,'mass_kg':mass,'provenance':'measured mass, box-distribution estimate' if name in measured else 'catalog mass, approximate box distribution'})
        mass,centre=HARDWARE[link];label='hardware_'+link;mass=measured.get(label,mass)
        pieces.append((mass,np.array(centre),np.eye(3)*mass*.005**2/6))
        part_rows.append({'component':label,'kind':'hardware','mass_kg':mass,'provenance':'measured mass, approximate distribution' if label in measured else 'unmeasured screw/horn/wire allowance'})
        mass=sum(x[0] for x in pieces);centre=sum(m*c for m,c,i in pieces)/mass
        inertia=sum(i+offset_inertia(m,c-centre) for m,c,i in pieces)
        R=frames[link][:3,:3];origin=frames[link][:3,3]
        local_c=R.T@(centre-origin);local_i=R.T@inertia@R
        report[link]={'mass_kg':float(mass),'com_m':local_c.tolist(),'inertia_kg_m2':local_i.tolist(),
            'source_urdf_mass_kg':float(ET.parse(SOURCE/'brazo_compacto.urdf').getroot().find(f"link[@name='{link}']/inertial/mass").get('value'))}
    unknown=set(measured)-{r['component'] for r in part_rows}
    if unknown:raise ValueError('Unknown measured components: '+', '.join(sorted(unknown)))
    result={'status':'preassembly_estimates' if not measured else 'partially_measured_mass_model',
        'method':'Integrate closed original print meshes. Catalog-mass servo boxes and hardware allowances; parallel-axis combination into actual URDF link frames.',
        'profile_mass_assumptions':profile['mass'],'measured_components':sorted(measured),'components':part_rows,'links':report,
        'total_mass_kg':sum(x['mass_kg'] for x in report.values()),
        'unmodeled':'Actual infill spatial distribution, servo internal mass distribution, measured COM and hardware distribution.'}
    if write_report:(ROOT/'mass_estimates.json').write_text(json.dumps(result,indent=2))
    return result
if __name__=='__main__':
    p=json.loads((ROOT/'physics_profile.json').read_text());r=build_masses(p)
    print(json.dumps({'total_mass_kg':r['total_mass_kg'],'links':r['links']},indent=2))
