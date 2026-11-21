from pathlib import Path
import struct,numpy as np,json
root=Path(__file__).resolve().parent
dtype=np.dtype([('normal','<f4',(3,)),('vertices','<f4',(3,3)),('attr','<u2')])
out=[]
for p in (root/'brazo_compacto').glob('*_part.stl'):
    data=p.read_bytes();n=struct.unpack_from('<I',data,80)[0]
    triangles=np.frombuffer(data,dtype,count=n,offset=84)['vertices']
    vertices,ids=np.unique(np.round(triangles.reshape(-1,3),8),axis=0,return_inverse=True)
    faces=ids.reshape(-1,3)
    edges=np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1)
    _,counts=np.unique(edges,axis=0,return_counts=True)
    result={'mesh':p.name,'boundary_edges':int(sum(counts==1)),'nonmanifold_edges':int(sum(counts>2)),
        'degenerate_faces':int(sum((faces[:,0]==faces[:,1])|(faces[:,1]==faces[:,2])|(faces[:,2]==faces[:,0])))}
    out.append(result);print(result,flush=True)
(root/'urdf_mesh_topology.json').write_text(json.dumps(out,indent=2))
