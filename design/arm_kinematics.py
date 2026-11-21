"""Base-frame geometric Jacobian for the five arm joints; gripper actuation excluded.

Joint derivatives are with respect to joint-output angles in radians. All positions
and the linear Jacobian use mm. The shoulder servo's 2:1 mapping is separate.
This module needs only NumPy; model_from_document reads the actual FreeCAD hierarchy.
"""
import math
import numpy as np

JOINT_PROPERTIES = ('BaseYaw','ShoulderPitch','ElbowPitch','WristPitch','WristRoll')
JOINT_OBJECTS = ('J1_Base_Yaw','J2_Shoulder_Pitch','J3_Elbow_Pitch','J4_Wrist_Pitch','J5_Wrist_Roll')
CHAIN = ('Robot_Mechanism','J1_Base_Yaw','Shoulder_Fixed_Frame','J2_Shoulder_Pitch',
         'Elbow_Fixed_Frame','J3_Elbow_Pitch','Wrist_Fixed_Frame','J4_Wrist_Pitch',
         'Roll_Fixed_Frame','J5_Wrist_Roll','Gripper_Fixed_Frame')

def placement_matrix(placement):
    return np.asarray(placement.toMatrix().A,dtype=float).reshape(4,4)

def model_from_document(doc):
    stages=[]
    for name in CHAIN:
        obj=doc.getObject(name)
        if obj is None: raise ValueError('Missing kinematic frame: '+name)
        matrix=placement_matrix(obj.Placement)
        index=JOINT_OBJECTS.index(name) if name in JOINT_OBJECTS else None
        if index is not None:
            # Each joint rotates about its local +Z; leave its translation intact.
            matrix[:3,:3]=np.eye(3)
        stages.append({'name':name,'joint':index,'matrix':matrix.tolist()})
    marker=doc.getObject('Ref_Tool_reference')
    centre=marker.Shape.BoundBox.Center
    tcp=[centre.x,centre.y,centre.z]
    return {'stages':stages,'tcp_local_mm':tcp,'characteristic_length_mm':359.0,
            'joint_properties':list(JOINT_PROPERTIES),
            'tcp_definition':'Fixed nominal grip-centre reference, between closed fingertips; independent of jaw opening.'}

def fk_and_jacobian(model,angles_deg):
    q=np.radians(np.asarray(angles_deg,dtype=float));T=np.eye(4);origins=[];axes=[]
    for stage in model['stages']:
        T=T@np.asarray(stage['matrix'])
        j=stage['joint']
        if j is not None:
            origins.append(T[:3,3].copy());axes.append(T[:3,2].copy())
            c,s=np.cos(q[j]),np.sin(q[j]);rot=np.eye(4);rot[:2,:2]=[[c,-s],[s,c]]
            T=T@rot
    point=(T@np.r_[model['tcp_local_mm'],1.0])[:3]
    linear=np.column_stack([np.cross(axis,point-origin) for axis,origin in zip(axes,origins)])
    angular=np.column_stack(axes)
    return point,T[:3,:3],np.vstack((linear,angular))

def spectrum(matrix):
    singular=np.linalg.svd(matrix,compute_uv=False)
    tol=max(matrix.shape)*np.finfo(float).eps*singular[0]
    # Engineering rank tolerance, separate from the near-singular display threshold.
    rank=int(np.count_nonzero(singular>max(tol,singular[0]*1e-8)))
    return {'rank':rank,'singular_values':singular.tolist(),
            'condition_number':float(singular[0]/singular[-1]) if rank==min(matrix.shape) else None}

def evaluate(model,angles_deg):
    position,rotation,jac=fk_and_jacobian(model,angles_deg)
    length=model['characteristic_length_mm']
    pos=spectrum(jac[:3]/length)
    full=spectrum(np.vstack((jac[:3]/length,jac[3:])))
    pos['singular_values_mm_per_rad']=(np.asarray(pos['singular_values'])*length).tolist()
    # Scale angular derivatives for shoulder SERVO command degrees: dq2/dservo=-1/2.
    servo_jac=jac@np.diag([1,-.5,1,1,1])
    return {'angles_deg':dict(zip(JOINT_PROPERTIES,map(float,angles_deg))),
            'tcp_world_mm':position.tolist(),'J0_rows_vx_vy_vz_wx_wy_wz':jac.tolist(),
            'servo_command_J0':servo_jac.tolist(),
            'position':pos,'five_joint_geometric':full,
            'position_gram_determinant_normalized':float(np.linalg.det((jac[:3]/length)@(jac[:3]/length).T)),
            'full_gram_determinant_normalized':float(np.linalg.det((np.vstack((jac[:3]/length,jac[3:]))).T@np.vstack((jac[:3]/length,jac[3:]))))}

def status_text(result):
    a=result['position'];b=result['five_joint_geometric']
    return 'XYZ rank %d/3 | arm rank %d/5'%(a['rank'],b['rank'])
