"""Preview the supplied URDF meshes at their exported zero-angle pose, without modifying CAD."""
from pathlib import Path
import bpy,xml.etree.ElementTree as ET
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=20;scene.cycles.use_denoising=True
scene.render.resolution_x=1100;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.world.use_nodes=True;bg=scene.world.node_tree.nodes.get('Background');bg.inputs['Color'].default_value=(.7,.75,.8,1);bg.inputs['Strength'].default_value=.2
scene.view_settings.view_transform='AgX'
def mat(name,color):
    m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes.get('Principled BSDF');n.inputs['Base Color'].default_value=(*color,1);n.inputs['Roughness'].default_value=.5;return m
robot=ET.parse(ROOT/'brazo_compacto'/'brazo_compacto.urdf').getroot()
for link in robot.findall('link'):
    mesh=link.find('visual/geometry/mesh')
    if mesh is None:continue
    # These exports already contain the home assembly coordinates in metres.
    bpy.ops.wm.stl_import(filepath=str(ROOT/'brazo_compacto'/mesh.get('filename')))
    ob=bpy.context.object;ob.name=link.get('name')
    color=(.64,.68,.72) if 'Jaw' not in ob.name else (.8,.14,.1)
    ob.data.materials.append(mat(ob.name,color))
bpy.ops.mesh.primitive_plane_add(size=5,location=(0,0,-.001));bpy.context.object.data.materials.append(mat('Floor',(.65,.69,.73)))
def light(pos,power,size):
    bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(Vector((0,0,.2))-o.location).to_track_quat('-Z','Y').to_euler()
light((.4,-.5,.8),30,.5);light((-.4,.1,.5),18,.45)
bpy.ops.object.camera_add(location=(.55,-.85,.47));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,.215))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.51;scene.camera=cam
scene.render.filepath=str(ROOT/'compact_review.png');bpy.ops.render.render(write_still=True)
