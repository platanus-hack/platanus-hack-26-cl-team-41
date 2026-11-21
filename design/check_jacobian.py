"""Read-only FreeCAD Jacobian check. Does not save poses, run collision checks or export STL."""
from pathlib import Path
import json,math,csv
import FreeCAD as A
import numpy as np
from scipy.optimize import brentq
from arm_kinematics import model_from_document,evaluate,fk_and_jacobian,JOINT_PROPERTIES

ROOT=Path(__file__).resolve().parent
doc=A.openDocument(str(ROOT/'MG995_5DOF_Movable.FCStd'))
model=model_from_document(doc)
saved=[getattr(doc.JointControls,k).Value for k in JOINT_PROPERTIES]
tests={'saved_pose':saved,'elbow_straight':[0,55,0,20,0],
       'near_straight_1deg':[0,55,1,20,0],'near_straight_0_1deg':[0,55,.1,20,0],
       'all_zero_reference':[0,0,0,0,0]}
# The offset TCP has zero lateral roll velocity at this roll angle. Solve radial
# position x=0 for a genuine XYZ singularity within the panel's preview ranges.
q5=-math.degrees(math.atan2(15,27))
q4=brentq(lambda wrist:fk_and_jacobian(model,[0,85,30,wrist,q5])[0][0],-55,55,xtol=1e-12)
tests['XYZ_singular_in_preview_ranges']=[0,85,30,q4,q5]
results={name:evaluate(model,q) for name,q in tests.items()}

# Check the analytical spatial Jacobian against central finite differences,
# including angular velocity dR/dq * R^T in the world frame.
checks=[]
for name,q in tests.items():
    point,rot,J=fk_and_jacobian(model,q);num=np.zeros((6,5));eps=1e-6
    for i in range(5):
        plus=np.asarray(q,dtype=float).copy();minus=plus.copy()
        plus[i]+=math.degrees(eps);minus[i]-=math.degrees(eps)
        pp,rp,_=fk_and_jacobian(model,plus);pm,rm,_=fk_and_jacobian(model,minus)
        num[:3,i]=(pp-pm)/(2*eps);w=((rp-rm)/(2*eps))@rot.T
        num[3:,i]=[w[2,1],w[0,2],w[1,0]]
    lin=float(np.max(np.abs(num[:3]-J[:3])));ang=float(np.max(np.abs(num[3:]-J[3:])))
    assert lin<1e-5 and ang<1e-7,(name,lin,ang)
    # Verify this independent FK against FreeCAD's native expression-driven hierarchy.
    for key,value in zip(JOINT_PROPERTIES,q):setattr(doc.JointControls,key,float(value))
    doc.recompute()
    native=doc.Gripper_Fixed_Frame.getGlobalPlacement().multVec(A.Vector(*model['tcp_local_mm']))
    error=float(np.linalg.norm(point-np.array(list(native))))
    assert error<1e-7,(name,error)
    checks.append({'pose':name,'linear_fd_max_error_mm_per_rad':lin,
        'angular_fd_max_error':ang,'freecad_tcp_error_mm':error})

for key,value in zip(JOINT_PROPERTIES,saved):setattr(doc.JointControls,key,value)
doc.recompute() # no save; the user's on-disk pose and live session remain untouched
report={'definition':'J0 is the base/world-frame 6 x 5 geometric Jacobian, for five arm joints, excluding gripper opening.',
 'units':'Linear rows mm/rad; angular rows rad/rad. Rank/conditioning use linear rows divided by 359mm.',
 'singularity_rule':'XYZ: rank(Jv)<3. Five-joint motion: rank(J0)<5. det(J0) is undefined because it is rectangular.',
 'rank_relative_tolerance':1e-8,'model':model,'poses':results,'verification':checks,
 'coverage':'Specific singular configurations and nearby examples, not an exhaustive singularity or collision map.',
 'shoulder_mapping':'ShoulderServoCommand = 90 - 2*(ShoulderPitch - 55), so the servo-command Jacobian has its shoulder column multiplied by -0.5.'}
(ROOT/'jacobian_check.json').write_text(json.dumps(report,indent=2,allow_nan=False))
(ROOT/'kinematic_model.json').write_text(json.dumps(model,indent=2))
with (ROOT/'jacobian_positions.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['Pose',*JOINT_PROPERTIES,'TCP_X_mm','TCP_Y_mm','TCP_Z_mm','XYZ_rank','Arm_rank','XYZ_sigma_min_mm_per_rad','Arm_sigma_min_scaled'])
    for name,r in results.items():w.writerow([name,*r['angles_deg'].values(),*r['tcp_world_mm'],r['position']['rank'],r['five_joint_geometric']['rank'],r['position']['singular_values_mm_per_rad'][-1],r['five_joint_geometric']['singular_values'][-1]])
for name,r in results.items():print(name, r['angles_deg'], 'TCP',np.round(r['tcp_world_mm'],3),'ranks',r['position']['rank'],r['five_joint_geometric']['rank'],flush=True)
print('All analytic Jacobians match finite differences and FreeCAD positions.',flush=True)
