"""Create self-contained A2L Bambu Studio projects; source meshes stay unchanged."""
from pathlib import Path
import os,json,zipfile,hashlib,math,uuid,xml.etree.ElementTree as E
import FreeCAD as A,Mesh,MeshPart,Part,numpy as np
ROOT=Path(__file__).resolve().parent;WORK=ROOT.parent.parent
PROFILES=Path(os.environ['APPDATA'])/'BambuStudio/system/BBL'
NS='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
PNS='http://schemas.microsoft.com/3dmanufacturing/production/2015/06'
E.register_namespace('',NS)
E.register_namespace('p',PNS)
for p in ('profiles','sources','cli_slices'):(ROOT/p).mkdir(exist_ok=True)
META={'type','name','inherits','from','instantiation','setting_id','description','include','compatible_printers','compatible_printers_condition','compatible_prints','compatible_prints_condition'}
def resolved(kind,name):
    data=json.loads((PROFILES/kind/(name+'.json')).read_text(encoding='utf-8-sig'))
    result=resolved(kind,data['inherits']) if data.get('inherits') else {}
    for inc in data.get('include',[]):result.update(resolved(kind,inc))
    result.update({k:v for k,v in data.items() if k not in META})
    return result
machine=resolved('machine','Bambu Lab A2L 0.4 nozzle')
process=resolved('process','0.20mm Standard @BBL A2L')
filament=resolved('filament','Generic PLA @BBL A2L')
machine.update(printer_settings_id='Bambu Lab A2L 0.4 nozzle')
filament.update(filament_settings_id=['Generic PLA @BBL A2L'],filament_max_volumetric_speed=['12'])
common=dict(wall_loops='5',sparse_infill_density='35%',sparse_infill_pattern='gyroid',top_shell_layers='6',bottom_shell_layers='6',
    top_shell_thickness='1',bottom_shell_thickness='1',outer_wall_speed=['50'],inner_wall_speed=['100'],
    top_surface_speed=['50'],initial_layer_speed=['25'],initial_layer_infill_speed=['40'],default_acceleration=['3000'],
    enable_support='1',support_type='normal(auto)',support_style='snug',support_threshold_angle='45',
    support_on_build_plate_only='0',support_top_z_distance='0.2',support_bottom_z_distance='0.2',
    support_interface_top_layers='3',support_interface_bottom_layers='2',support_interface_spacing='0.3',
    support_object_xy_distance='0.35',support_remove_small_overhang='1',brim_type='outer_only',brim_width='5',brim_object_gap='0.1',
    xy_hole_compensation='0',xy_contour_compensation='0',elefant_foot_compensation='0.15',
    enable_prime_tower='0',print_sequence='by layer',curr_bed_type='Textured PEI Plate',
    filament_colour=['#39A5A1'],default_filament_colour=['#39A5A1'],filament_map=['1'],filament_is_support=['0'],
    filament_ids=['GFL99'],filament_self_index=['1'],filament_map_mode='Auto For Flush',version='02.09.01.70')

def rx(d):
    a=math.radians(d);c,s=math.cos(a),math.sin(a);return np.array([[1,0,0],[0,c,-s],[0,s,c]])

# One optional calibration coupon: through bores 3.1/3.2/3.3/3.4 mm and
# nut pockets 5.6/5.7/5.8 mm AF. Edge notches identify their column number.
V=A.Vector
coupon=Part.makeBox(64,38,4)
for i,diam in enumerate((3.1,3.2,3.3,3.4)):
    x=8+i*16;coupon=coupon.cut(Part.makeCylinder(diam/2,6,V(x,10,-1)))
    for k in range(i+1):coupon=coupon.cut(Part.makeBox(.8,2,2,V(x-3+k*1.7,0,3)))
for i,af in enumerate((5.6,5.7,5.8)):
    x=8+i*16;y=28;r=af/math.sqrt(3)
    pts=[V(x+r*math.cos(math.radians(30+60*k)),y+r*math.sin(math.radians(30+60*k)),1.4) for k in range(6)];pts.append(pts[0])
    cut=Part.Face(Part.makePolygon(pts)).extrude(V(0,0,3))
    coupon=coupon.cut(cut).cut(Part.makeCylinder(1.65,6,V(x,y,-1)))
    for k in range(i+1):coupon=coupon.cut(Part.makeBox(.8,2,2,V(x-3+k*1.7,36,3)))
coupon=coupon.removeSplitter();assert coupon.isValid() and len(coupon.Solids)==1
MeshPart.meshFromShape(Shape=coupon,LinearDeflection=.04,AngularDeflection=.10,Relative=False).write(str(ROOT/'sources/M3_Fit_Coupon.stl'))
base_source=ROOT/'sources/Placa_base_TT_original.stl'
if not base_source.is_file():raise FileNotFoundError('Missing bundled base STL: '+str(base_source))
TOOL=WORK/'toolhead_13mm/stl'
I=np.eye(3)
def item(name,path,center,rotation=I,support=False,note=''):
    return dict(name=name,path=Path(path),center=center,rotation=rotation,support=support,note=note)
handle=item('Handle_fit_13.0_13.2_13.4mm',TOOL/'08_Handle_Fit_Coupon.stl',(90,245),note='1/2/3 notches identify 13.0/13.2/13.4 mm bores.')
m3=item('M3_fit_clearance_3.1_3.2_3.3_3.4_nuts_AF5.6_5.7_5.8',ROOT/'sources/M3_Fit_Coupon.stl',(220,245),note='Through-hole row has 1/2/3/4 notches; nut row 1/2/3.')
jobs=[
 ('A2L_Base_TT_PLA_0.20mm',[item('Base_TT_M3_pilot_bosses',ROOT/'sources/Placa_base_TT_original.stl',(165,160),rx(180),True,'Broad plate face down, bosses and TT mounts up. Four 2.6 mm blind M3 pilot bores are retained; tap for M3 machine screws.')],.20),
 ('A2L_Toolhead_M3_PLA_0.16mm',[
    item('Right_M3_retention_shoe',TOOL/'01_Right_Retention_Shoe.stl',(65,145),rx(180),note='Broad flat flange down, nut boss up; M3 bore vertical.'),
    item('Left_M3_retention_shoe',TOOL/'02_Left_Retention_Shoe.stl',(105,145),rx(180),note='Broad flat flange down, nut boss up; M3 bore vertical.'),
    item('Expansion_receiver',TOOL/'03_Expansion_Receiver.stl',(85,80),rx(180),True,'Rear flange down; mouth up. Remove internal supports through the mouth.'),
    item('Angled_handle_saddle',TOOL/'04_Angled_Handle_Saddle.stl',(180,80),I,True,'Mounting plate down; automatic supports under angled saddle.'),
    item('Handle_clamp_cap',TOOL/'05_Handle_Clamp_Cap.stl',(260,80),note='Collar end down; 5 mm brim stabilizes 30 mm height. Small M3 holes bridge.'),
    item('Right_replacement_jaw_M3',TOOL/'06_JawR_M3.stl',(170,170),note='Flat side down, teeth in bed plane, M3 attachment hole vertical.'),
    item('Left_replacement_jaw_M3',TOOL/'07_JawL_M3.stl',(220,170),note='Flat side down, teeth in bed plane, M3 attachment hole vertical.'),handle,m3],.16),
 ('A2L_M3_and_Handle_Fit_Test_0.16mm',[
    item(handle['name'],handle['path'],(115,160),note=handle['note']),
    item(m3['name'],m3['path'],(215,160),note=m3['note'])],.16)
]

def metadata(parent,key,value):E.SubElement(parent,'metadata',key=key,value=str(value))
def uid(label):return str(uuid.uuid5(uuid.NAMESPACE_URL,'local-a2l-toolhead/'+label))
def project(name,items,layer):
    config={**machine,**process,**filament,**common}
    config.update(layer_height=str(layer),initial_layer_print_height='0.2',print_settings_id=('0.20mm Standard @BBL A2L' if layer==.20 else '0.16mm Standard @BBL A2L'),
        print_compatible_printers=['Bambu Lab A2L 0.4 nozzle'],printer_model='Bambu Lab A2L',printer_variant='0.4')
    if 'Base_TT' in name:config.update(wall_loops='6',sparse_infill_density='40%',brim_width='8')
    model=E.Element('{%s}model'%NS,{'unit':'millimeter','xml:lang':'en-US','xmlns:BambuStudio':'http://schemas.bambulab.com/package/2021','requiredextensions':'p'})
    for key,value in [('Application','BambuStudio-02.09.01.70'),('BambuStudio:3mfVersion','1'),('Title',name),('Description','A2L 0.4 mm, Generic PLA, M3 mechanical prototype')]:E.SubElement(model,'{%s}metadata'%NS,name=key).text=value
    resources=E.SubElement(model,'{%s}resources'%NS);build=E.SubElement(model,'{%s}build'%NS,{'{%s}UUID'%PNS:uid(name+'/build')})
    settings=E.Element('config');manifest=[];submodels={};rels=E.Element('Relationships',xmlns='http://schemas.openxmlformats.org/package/2006/relationships')
    assemble=E.Element('assemble')
    plate=E.Element('plate');metadata(plate,'plater_id',1);metadata(plate,'plater_name',name);metadata(plate,'locked','false')
    for index,part in enumerate(items,1):
        mesh=Mesh.Mesh(str(part['path']));assert mesh.isSolid(),('Open source mesh',part['name'])
        points,triangles=mesh.Topology;v=np.array([[p.x,p.y,p.z] for p in points])@part['rotation'].T
        lo=v.min(0);hi=v.max(0);v+=np.r_[np.array(part['center'])-(lo[:2]+hi[:2])/2,-lo[2]]
        lo=v.min(0);hi=v.max(0);brim=8 if 'Base_TT' in name else 5
        assert np.all(lo[:2]>=brim+5) and np.all(hi[:2]<=np.array([330,320])-brim-5)
        origin=(lo+hi)/2
        local_vertices=v-origin
        placement='1 0 0 0 1 0 0 0 1 '+' '.join(f'{t:.7f}' for t in origin)
        root_id=index+1
        component_path=f'/3D/Objects/part_{index}.model'
        root_obj=E.SubElement(resources,'{%s}object'%NS,{'id':str(root_id),'type':'model','{%s}UUID'%PNS:uid(name+part['name']+'/root')})
        components=E.SubElement(root_obj,'{%s}components'%NS)
        E.SubElement(components,'{%s}component'%NS,{'{%s}path'%PNS:component_path,'{%s}UUID'%PNS:uid(name+part['name']+'/component'),'objectid':'1','transform':'1 0 0 0 1 0 0 0 1 0 0 0'})
        E.SubElement(rels,'Relationship',Target=component_path,Id=f'rel-{index}',Type='http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel')
        leaf_model=E.Element('{%s}model'%NS,{'unit':'millimeter','xml:lang':'en-US','xmlns:BambuStudio':'http://schemas.bambulab.com/package/2021','requiredextensions':'p'})
        E.SubElement(leaf_model,'{%s}metadata'%NS,name='BambuStudio:3mfVersion').text='1'
        leaf_resources=E.SubElement(leaf_model,'{%s}resources'%NS)
        o=E.SubElement(leaf_resources,'{%s}object'%NS,{'id':'1','type':'model','name':part['name'],'{%s}UUID'%PNS:uid(name+part['name']+'/mesh')})
        m=E.SubElement(o,'{%s}mesh'%NS);verts=E.SubElement(m,'{%s}vertices'%NS)
        for x,y,z in local_vertices:E.SubElement(verts,'{%s}vertex'%NS,x=f'{x:.7f}',y=f'{y:.7f}',z=f'{z:.7f}')
        ts=E.SubElement(m,'{%s}triangles'%NS)
        for a,b,c in triangles:E.SubElement(ts,'{%s}triangle'%NS,v1=str(a),v2=str(b),v3=str(c))
        submodels[component_path.lstrip('/')]=E.tostring(leaf_model,encoding='utf-8',xml_declaration=True)
        E.SubElement(build,'{%s}item'%NS,{'objectid':str(root_id),'printable':'1','transform':placement,'{%s}UUID'%PNS:uid(name+part['name']+'/instance')})
        obj=E.SubElement(settings,'object',id=str(root_id));metadata(obj,'name',part['name']);metadata(obj,'extruder',1);E.SubElement(obj,'metadata',face_count=str(len(triangles)))
        metadata(obj,'enable_support','1' if part['support'] else '0')
        if not part['support']:metadata(obj,'brim_width','5' if 'cap' in part['name'] or 'shoe' in part['name'] else '3')
        volume=E.SubElement(obj,'part',id='1',subtype='normal_part');metadata(volume,'name',part['name']);metadata(volume,'extruder',1)
        metadata(volume,'matrix','1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1')
        E.SubElement(volume,'mesh_stat',face_count=str(len(triangles)),edges_fixed='0',degenerate_facets='0',facets_removed='0',facets_reversed='0',backwards_edges='0')
        inst=E.SubElement(plate,'model_instance');metadata(inst,'object_id',root_id);metadata(inst,'instance_id',0);metadata(inst,'identify_id',index)
        E.SubElement(assemble,'assemble_item',object_id=str(root_id),instance_id='0',transform=placement,offset='0 0 0')
        manifest.append({'name':part['name'],'source':str(part['path'].relative_to(WORK)),'source_sha256':hashlib.sha256(part['path'].read_bytes()).hexdigest(),
            'bounds_mm':[lo.tolist(),hi.tolist()],'rotation':part['rotation'].tolist(),'support':part['support'],'note':part['note'],'closed_mesh':True,'triangles':len(triangles)})
    settings.append(plate)
    settings.append(assemble)
    for i,a in enumerate(manifest):
        for b in manifest[i+1:]:
            al,ah=np.array(a['bounds_mm']);bl,bh=np.array(b['bounds_mm'])
            assert not np.all(np.minimum(ah[:2]+brim,bh[:2]+brim)>np.maximum(al[:2]-brim,bl[:2]-brim)),('Brim overlap',a['name'],b['name'])
    path=ROOT/(name+'.3mf')
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/><Default Extension="config" ContentType="application/octet-stream"/></Types>')
        z.writestr('_rels/.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr('3D/3dmodel.model',E.tostring(model,encoding='utf-8',xml_declaration=True))
        z.writestr('3D/_rels/3dmodel.model.rels',E.tostring(rels,encoding='utf-8',xml_declaration=True))
        for subpath,data in submodels.items():z.writestr(subpath,data)
        z.writestr('Metadata/project_settings.config',json.dumps(config,indent=2))
        z.writestr('Metadata/model_settings.config',E.tostring(settings,encoding='utf-8',xml_declaration=True))
    (ROOT/'profiles'/(name+'.json')).write_text(json.dumps({'type':'process','name':name,'from':'user','instantiation':'true',**process,**common,'layer_height':str(layer),'initial_layer_print_height':'0.2','print_settings_id':name,**({'wall_loops':'6','sparse_infill_density':'40%','brim_width':'8'} if 'Base_TT' in name else {})},indent=2))
    return {'project':path.name,'printer':'Bambu Lab A2L 0.4 nozzle','filament':'Generic PLA @BBL A2L','layer_height_mm':layer,'parts':manifest,'settings':{k:config[k] for k in ['wall_loops','sparse_infill_density','sparse_infill_pattern','xy_hole_compensation','elefant_foot_compensation','curr_bed_type']},'status':'configured, arranged project; not sliced'}

reports=[project(*job) for job in jobs]
for name,data,typ in [('A2L_0.4_machine',machine,'machine'),('Generic_PLA_A2L',filament,'filament')]:
    (ROOT/'profiles'/(name+'.json')).write_text(json.dumps({'type':typ,'name':'Bambu Lab A2L 0.4 nozzle' if typ=='machine' else 'Generic PLA @BBL A2L','from':'system','instantiation':'true',**data},indent=2))
(ROOT/'job_manifest.json').write_text(json.dumps({'jobs':reports,'base_input_sha256':hashlib.sha256(base_source.read_bytes()).hexdigest(),'source_geometry_unchanged':True,'bed_mm':[330,320],'notes':['Base broad plate face down, source Z reversed.','Base 4 blind 2.6 mm pilots are for M3 tapping, not M3 through clearance.','Toolhead retains 3.2–3.3 mm screw clearance and 5.7 mm AF nuts.','Fit coupon is optional; print fit test before the full toolhead.','PLA toolhead is a cold-fit prototype.']},indent=2))
print(json.dumps([{'file':r['project'],'objects':len(r['parts'])} for r in reports],indent=2))
