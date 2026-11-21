"""Create a separate MuJoCo scene from the supplied SolidCraft URDF.
The original CAD/URDF files are left untouched. Detailed meshes are visual only;
collision shapes are simple approximations, not a clearance model.
"""
from pathlib import Path
import json,math,xml.etree.ElementTree as E
from mass_properties import build_masses
from servo_physics import load_profile,joint_parameters
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'solidcraft_import'/'brazo_compacto'
ARM_NAMES=['J1_base','J2_shoulder','J3_elbow','J4_wrist_pitch','J5_wrist_roll','J6_jaw_R']
def vals(text):return [float(x) for x in text.split()]
def fmt(x):return ' '.join(f'{v:.9g}' for v in x)
def quat(rpy):
    r,p,y=[v/2 for v in rpy];cr,sr=math.cos(r),math.sin(r);cp,sp=math.cos(p),math.sin(p);cy,sy=math.cos(y),math.sin(y)
    return [cr*cp*cy+sr*sp*sy,sr*cp*cy-cr*sp*sy,cr*sp*cy+sr*cp*sy,cr*cp*sy-sr*sp*cy]
def transform(node):
    origin=node.find('origin')
    return {} if origin is None else {'pos':origin.get('xyz','0 0 0'),'quat':fmt(quat(vals(origin.get('rpy','0 0 0'))))}
def collision(body,typ,**kwargs):
    return E.SubElement(body,'geom',{'type':typ,'group':'3','rgba':'0.2 0.6 0.3 0.25',**{k:str(v) for k,v in kwargs.items()}})
def build(profile=None,output_path=None):
    profile=load_profile() if profile is None else profile
    output_path=ROOT/'scene.xml' if output_path is None else Path(output_path)
    report_files=output_path==ROOT/'scene.xml'
    masses=build_masses(profile,write_report=report_files)
    contact=profile['contacts']
    robot=E.parse(SOURCE/'brazo_compacto.urdf').getroot();links={n.get('name'):n for n in robot.findall('link')}
    root=E.Element('mujoco',model='SolidCraft compact arm tabletop')
    E.SubElement(root,'compiler',angle='radian',autolimits='true',meshdir='../solidcraft_import/brazo_compacto',inertiafromgeom='false')
    E.SubElement(root,'option',timestep='0.002',integrator='implicitfast',gravity='0 0 -9.81',iterations='60')
    E.SubElement(root,'size',njmax='2000',nconmax='300')
    visual=E.SubElement(root,'visual');E.SubElement(visual,'global',offwidth='640',offheight='480');E.SubElement(visual,'headlight',diffuse='0.6 0.6 0.6',ambient='0.3 0.3 0.3')
    defaults=E.SubElement(root,'default');E.SubElement(defaults,'geom',friction=fmt([contact['table_slide_friction'],contact['torsional_friction_m'],contact['rolling_friction_m']]),solref=fmt([contact['time_constant_s'],contact['damping_ratio']]),solimp='0.95 0.99 0.001',condim='4')
    assets=E.SubElement(root,'asset')
    E.SubElement(assets,'texture',name='checker',type='2d',builtin='checker',rgb1='0.25 0.29 0.32',rgb2='0.30 0.34 0.37',width='256',height='256')
    E.SubElement(assets,'material',name='worktop',texture='checker',texrepeat='5 5',reflectance='0')
    world=E.SubElement(root,'worldbody');E.SubElement(world,'light',pos='0.2 -0.5 1.2',dir='0 0 -1',diffuse='0.8 0.8 0.8')
    E.SubElement(world,'geom',name='table',type='plane',size='0.6 0.6 0.02',material='worktop')
    # Fixed camera xy axes: +X camera right, camera +Y tilted upward, -Z looks down.
    E.SubElement(world,'camera',name='workspace',pos='0.16 -0.62 0.53',xyaxes='1 0 0 0 0.637 0.771',fovy='48')
    E.SubElement(world,'camera',name='overhead',pos='0.12 0 0.85',xyaxes='1 0 0 0 1 0',fovy='40')
    bodies={};base=E.SubElement(world,'body',name='base_link');bodies['base_link']=base
    metadata=[]
    def populate(name,body):
        link=links[name];inertial=link.find('inertial')
        if inertial is not None:
            estimate=masses['links'][name];i=estimate['inertia_kg_m2']
            E.SubElement(body,'inertial',pos=fmt(estimate['com_m']),mass=str(estimate['mass_kg']),fullinertia=fmt([i[0][0],i[1][1],i[2][2],i[0][1],i[0][2],i[1][2]]))
        for i,v in enumerate(link.findall('visual')):
            mesh=v.find('geometry/mesh')
            if mesh is None:continue
            meshname=name+'_mesh'+str(i);E.SubElement(assets,'mesh',name=meshname,file=mesh.get('filename'))
            color=v.find('material/color');rgba=color.get('rgba') if color is not None else '0.7 0.75 0.8 1'
            E.SubElement(body,'geom',name=name+'_visual',type='mesh',mesh=meshname,rgba=rgba,contype='0',conaffinity='0',group='2',**transform(v))
        if name=='Base_part':collision(body,'cylinder',name='base_collision',pos='0 0 0.0275',size='0.08 0.0275')
        elif name=='Shoulder_part':collision(body,'capsule',fromto='0 0 0.012 0 0 0.046',size='0.021')
        elif name=='UpperArm_part':collision(body,'capsule',fromto='-0.012 0 0 -0.078 0 0',size='0.018')
        elif name=='Forearm_part':collision(body,'capsule',fromto='-0.012 0 0 -0.073 0 0',size='0.021')
        elif name=='Wrist_part':collision(body,'capsule',fromto='-0.010 0 0 -0.051 0 0',size='0.015')
        elif name=='Gripper_part':
            collision(body,'box',pos='0 0 0.018',size='0.027 0.019 0.018')
            E.SubElement(body,'site',name='tcp',pos='0.0145 0 0.0735',size='0.004',rgba='0 1 0 0.8')
            E.SubElement(body,'site',name='tool_axis',pos='0.0145 0 0.0535',size='0.001',rgba='0 1 0 0')
        elif name in ('JawR_part','JawL_part'):
            s=1 if name=='JawR_part' else -1
            friction=fmt([contact['finger_slide_friction'],contact['torsional_friction_m'],contact['rolling_friction_m']])
            collision(body,'box',name=name+'_finger',pos='-0.0275 0 0.0025',size='0.0275 0.004 0.0025',friction=friction)
            collision(body,'box',name=name+'_pad',pos=f'-0.0465 {s*.0058} 0.0025',size='0.0085 0.0018 0.0025',friction=friction)
    populate('base_link',base)
    pending=list(robot.findall('joint'))
    while pending:
        progress=False
        for joint in pending[:]:
            parent=joint.find('parent').get('link');child=joint.find('child').get('link')
            if parent not in bodies:continue
            body=E.SubElement(bodies[parent],'body',name=child,**transform(joint));bodies[child]=body
            if joint.get('type')!='fixed':
                name=joint.get('name');lim=joint.find('limit');p=joint_parameters(profile,name)
                E.SubElement(body,'joint',name=name,type='hinge',axis=joint.find('axis').get('xyz'),range=lim.get('lower')+' '+lim.get('upper'),damping=str(p['passive_damping_Nm_s_rad']),armature=str(p['armature_kg_m2']),frictionloss=str(p['frictionloss_Nm']))
                metadata.append({'joint':name,'range_rad':[float(lim.get('lower')),float(lim.get('upper'))],
                    'assumed_peak_torque_Nm':p['stall_torque_Nm'],'parameters':p,'assumptions':'Preassembly prior; stall torque is not a continuous-duty rating.'})
            populate(child,body);pending.remove(joint);progress=True
        if not progress:raise ValueError('URDF links are not a connected tree')
    contacts=E.SubElement(root,'contact')
    E.SubElement(contacts,'exclude',body1='JawR_part',body2='JawL_part')
    equal=E.SubElement(root,'equality');E.SubElement(equal,'joint',name='jaw_gearing',joint1='J6_jaw_L',joint2='J6_jaw_R',polycoef='0 -1 0 0 0',solref='0.005 1')
    actuators=E.SubElement(root,'actuator')
    byname={j['joint']:j for j in metadata}
    for name in ARM_NAMES:
        item=byname[name];p=item['parameters'];limit=item['assumed_peak_torque_Nm']
        E.SubElement(actuators,'position',name=name+'_servo',joint=name,kp=str(p['kp_Nm_rad']),kv=str(p['kv_Nm_s_rad']),ctrlrange=fmt(item['range_rad']),forcerange=f'{-limit} {limit}')
    cube=E.SubElement(world,'body',name='block',pos='0.125 0.0145 0.008')
    E.SubElement(cube,'freejoint',name='block_free');E.SubElement(cube,'inertial',pos='0 0 0',mass='0.006',diaginertia='0.000000256 0.000000256 0.000000256')
    E.SubElement(cube,'geom',name='block_geom',type='box',size='0.008 0.008 0.008',rgba='0.9 0.18 0.08 1',friction=fmt([contact['block_slide_friction'],contact['torsional_friction_m'],contact['rolling_friction_m']]))
    E.SubElement(world,'site',name='reach_goal',pos='0.15 0.04 0.08',size='0.006',rgba='0.1 0.8 0.9 0.65')
    tray=E.SubElement(world,'body',name='tray',pos='0.145 -0.095 0')
    E.SubElement(tray,'geom',type='box',pos='0 0 0.002',size='0.030 0.030 0.002',rgba='0.1 0.35 0.7 1')
    for x,y,sx,sy in [(0,.029,.030,.001), (0,-.029,.030,.001),(.029,0,.001,.028),(-.029,0,.001,.028)]:
        E.SubElement(tray,'geom',type='box',pos=f'{x} {y} .009',size=f'{sx} {sy} .007',rgba='0.1 0.35 0.7 1')
    E.indent(root);E.ElementTree(root).write(output_path,encoding='utf-8',xml_declaration=True)
    if report_files:(ROOT/'model_assumptions.json').write_text(json.dumps({'status':profile['status'],'supply_voltage_V':profile['hardware_confirmed_by_user']['supply_voltage_V'],'source':str(SOURCE/'brazo_compacto.urdf'),
        'actuated_joints':ARM_NAMES,'joints':metadata,'tcp':'Midpoint between closed finger pads; fixed reference independent of jaw angle.',
        'contact_model':'Primitive approximations; visual meshes preserve SolidCraft geometry. Not a CAD collision certification.',
        'mass_model':masses['method'],'mass_estimate_kg':masses['total_mass_kg'],'jaw_coupling':'q_left = -q_right','controller':profile['controller'],'sources':profile['sources'],
        'limitations':['Preassembly priors only; no measured calibration of masses, COM, gains, delays, friction, backlash, thermal limits or PWM mapping.','A 5-DOF arm cannot command arbitrary 6-DOF poses.']},indent=2))
    if report_files:print('Created scene.xml with CAD-derived mass priors and six voltage-referenced servo actuators.')
if __name__=='__main__':build()
