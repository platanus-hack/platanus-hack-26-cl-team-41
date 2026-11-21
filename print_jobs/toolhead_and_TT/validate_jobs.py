"""Validate native 3MF structure and attempt Bambu CLI slicing without uploading."""
from pathlib import Path
import json,zipfile,xml.etree.ElementTree as E,subprocess,time,hashlib,re,sys
ROOT=Path(__file__).resolve().parent
NS={'c':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02','p':'http://schemas.microsoft.com/3dmanufacturing/production/2015/06'}
jobs=json.loads((ROOT/'job_manifest.json').read_text())['jobs'];reports=[]
for job in sorted(jobs,key=lambda j:('Fit_Test' not in j['project'],'Base_TT' in j['project'])):
    path=ROOT/job['project']
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        cfg=json.loads(z.read('Metadata/project_settings.config'));settings=E.fromstring(z.read('Metadata/model_settings.config'));model=E.fromstring(z.read('3D/3dmodel.model'))
        assert cfg['printer_model']=='Bambu Lab A2L' and cfg['nozzle_diameter']==['0.4'] and cfg['filament_type']==['PLA']
        assert len(settings.findall('object'))==len(job['parts'])
        assert len(model.findall('c:build/c:item',NS))==len(job['parts'])
        for o,item,part in zip(model.findall('c:resources/c:object',NS),model.findall('c:build/c:item',NS),job['parts']):
            component=o.find('c:components/c:component',NS);sub=E.fromstring(z.read(component.get('{'+NS['p']+'}path').lstrip('/')))
            import numpy as np
            vertices=np.array([[float(v.get(a)) for a in ['x','y','z']] for v in sub.findall('.//c:vertex',NS)])
            transform=np.array([float(x) for x in item.get('transform').split()]);vertices=vertices@transform[:9].reshape(3,3)+transform[9:]
            assert np.max(np.abs(np.array([vertices.min(0),vertices.max(0)])-part['bounds_mm']))<1e-5
    out=ROOT/'cli_slices'/path.stem;out.mkdir(exist_ok=True)
    if '--structure-only' in sys.argv:
        reports.append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'zip_and_native_structure_valid':True,'bed_bounds_and_placements_match':True,'embedded_A2L_PLA_profile_verified':True,'quantity':len(job['parts']),'sliced':False})
        (ROOT/'validation_report.json').write_text(json.dumps({'delivery':'editable arranged A2L projects; user will slice','projects':reports},indent=2))
        print(path.name,'structure, A2L/PLA settings and bed placement checked',flush=True);continue
    start=time.time()
    try:
        r=subprocess.run(['C:/Program Files/Bambu Studio/bambu-studio.exe','--debug','3','--slice','0','--outputdir',str(out),str(path)],capture_output=True,timeout=240)
        (out/'cli.log').write_bytes(r.stdout+r.stderr);code=r.returncode
    except subprocess.TimeoutExpired:code='timeout'
    result=json.loads((out/'result.json').read_text()) if (out/'result.json').exists() else {}
    gcode=out/'plate_1.gcode'
    row={'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'zip_and_native_structure_valid':True,'bed_bounds_and_placements_match':True,'embedded_A2L_PLA_profile_verified':True,'cli_exit':code,'elapsed_s':round(time.time()-start,2),'cli_result':result,'sliced_gcode_present':gcode.exists()}
    if gcode.exists():
        s=gcode.read_text(errors='replace');row['gcode_header']=s.split('; HEADER_BLOCK_END')[0]
        for key in ['printer_model','printer_settings_id','nozzle_temperature','filament_density','layer_height','wall_loops','curr_bed_type']:
            m=re.search(r'^; '+re.escape(key)+r' = (.*)$',s,re.M);row[key]=m.group(1) if m else None
    reports.append(row);(ROOT/'validation_report.json').write_text(json.dumps({'projects':reports},indent=2));print(json.dumps({k:v for k,v in row.items() if k not in ['gcode_header','cli_result']}),flush=True)
    if code!=0 and not gcode.exists():print(json.dumps(result),flush=True);break
