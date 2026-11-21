"""Render only the actual generated CAD meshes. Run with Blender --background --python."""
import bpy, json, math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
scene.render.engine='CYCLES'; scene.cycles.samples=48
scene.cycles.use_denoising=True
scene.render.resolution_x=1600; scene.render.resolution_y=1200; scene.render.resolution_percentage=100
scene.world.color=(0.10,0.10,0.10)
scene.view_settings.look='AgX - Medium High Contrast'
scene.view_settings.exposure=-1
scene.view_settings.view_transform='AgX'
def material(name,color,metal=0):
    color=color[:3]
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Roughness'].default_value=0.40; p.inputs['Metallic'].default_value=metal
    return m
for item in json.loads((ROOT/'renders'/'scene.json').read_text()):
    bpy.ops.wm.stl_import(filepath=item['file'])
    obj=bpy.context.object; obj.name=item['name']; obj.scale=(0.001,)*3
    obj.data.materials.append(material(item['name'],item['color'],0.55 if 'bearing' in item['name'] else 0))
    # Keep the tessellated CAD surfaces unmodified; beveling STL triangles creates artifacts.
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-0.001))
bpy.context.object.name='Render floor'; bpy.context.object.data.materials.append(material('Floor',(0.80,0.83,0.85)))
def area(name,pos,power,size,target=(0.07,0,0.15)):
    bpy.ops.object.light_add(type='AREA',location=pos); o=bpy.context.object; o.name=name
    o.data.energy=power; o.data.shape='DISK'; o.data.size=size
    o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area('Key',(0.25,-0.45,0.8),18,0.5)
area('Fill',(-0.4,0.2,0.4),10,0.45)
area('Rim',(0.4,0.4,0.65),18,0.35)
bpy.ops.object.camera_add(); cam=bpy.context.object; scene.camera=cam; cam.data.type='ORTHO'
def shoot(name,pos,target,scale):
    cam.location=pos; cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.ortho_scale=scale; scene.render.filepath=str(ROOT/'renders'/name)
    bpy.ops.render.render(write_still=True)
shoot('assembly.png',(0.60,-0.90,0.57),(0.085,0,0.17),0.52)
shoot('rear.png',(-0.25,0.8,0.46),(0.085,0,0.17),0.52)
shoot('side.png',(0.09,-1.3,0.2),(0.09,0,0.17),0.51)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'renders'/'arm_preview.blend'))
