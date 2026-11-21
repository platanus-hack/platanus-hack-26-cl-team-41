"""Validate measured CSVs and preview or explicitly apply timing/friction updates.
Blank entries are never treated as zero. No synthetic traces are fit as hardware data.
"""
from pathlib import Path
import argparse,csv,json,math,copy
from servo_physics import load_profile,NAMES
ROOT=Path(__file__).resolve().parent
def candidate():
    profile=copy.deepcopy(load_profile());used=[]
    path=ROOT/'calibration'/'servo_steps.csv'
    rows=list(csv.DictReader(path.open(newline='')))
    delays=[]
    for r in rows:
        timing=r['travel_time_s'].strip();lag=r['delay_ms'].strip()
        if not timing and not lag:continue
        name=r['joint']
        if name not in NAMES:raise ValueError('Unknown joint '+name)
        voltage=float(r['voltage_V'])
        if not math.isclose(voltage,profile['hardware_confirmed_by_user']['supply_voltage_V'],abs_tol=.15):raise ValueError('Voltage differs from the configured rail')
        changes={}
        if timing:
            seconds=float(timing);sweep=abs(float(r['end_deg'])-float(r['start_deg']))
            if not math.isfinite(seconds) or seconds<=0 or not 10<=sweep<=90:raise ValueError('Use positive timing and an unloaded 10..90 degree sweep')
            # This fits average sweep speed, not an instantaneous motor free-speed constant.
            changes['no_load_speed_rad_s']=math.radians(sweep)/seconds
            if not .1<changes['no_load_speed_rad_s']<30:raise ValueError('Implausible average sweep speed')
            profile['joint_overrides'].setdefault(name,{}).update(changes)
            used.append({'joint':name,'field':'no_load_speed_rad_s','method':'unloaded sweep average; effective response approximation','row':r})
        if lag:
            delay=float(lag)/1000
            if not math.isfinite(delay) or not 0<=delay<.5:raise ValueError('Invalid delay')
            delays.append(delay);used.append({'joint':name,'field':'command_delay_s','method':'global mean of supplied delay estimates, quantized by 50Hz simulator command frames','row':r})
    if delays:profile['controller']['command_delay_s']=sum(delays)/len(delays)
    if used:
        profile['measurements_applied']=profile.get('measurements_applied',[])+used
        profile['status']='partially_measured_not_fully_calibrated'
    return profile,used
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    p,used=candidate()
    if not used:
        print('No servo measurements entered. Profile unchanged. Part-mass overrides are read directly from calibration/part_masses.csv.');return
    print(json.dumps({'updates':used,'mode':'apply' if args.apply else 'preview'},indent=2))
    if args.apply:
        (ROOT/'physics_profile.json').write_text(json.dumps(p,indent=2));print('Profile updated. Scene rebuilds on next launch.')
if __name__=='__main__':main()
