"""Render exported CAD, including actual latch geometry, using Blender."""
from pathlib import Path
import json, math
import bpy
from mathutils import Vector, Matrix
ROOT=Path(__file__).resolve().parent; OUT=ROOT/'renders'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True
scene.render.resolution_x=1100;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.72,.77,.84,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-1
def material(name,color,metal=0):
    m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes.get('Principled BSDF');n.inputs['Base Color'].default_value=(*color[:3],1);n.inputs['Roughness'].default_value=.4;n.inputs['Metallic'].default_value=metal;return m
objects={}
for item in json.loads((OUT/'scene.json').read_text()):
    if item['name']=='Reference_13mm_Tool':continue
    bpy.ops.wm.stl_import(filepath=str(OUT/item['mesh']));ob=bpy.context.object;ob.name=item['name'].lstrip('_');ob.scale=(.001,)*3
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    ob.data.materials.append(material(ob.name,item['color']));objects[ob.name]=ob
bpy.ops.wm.stl_import(filepath=str(OUT/'Receiver_Cutaway.stl'));cut=bpy.context.object;cut.scale=(.001,)*3;cut.data.materials.append(material('Cut receiver',(.12,.4,.55)));cut.hide_render=True
axis=Vector((0,-math.sin(math.pi/4),math.cos(math.pi/4)));center=Vector((0,.002,.085))
def cylinder(name,r,length,location,mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=r,depth=length,location=location)
    ob=bpy.context.object;ob.name=name;ob.rotation_euler=axis.to_track_quat('Z','Y').to_euler();ob.data.materials.append(mat);return ob
cylinder('13 mm cool handle reference',.0065,.04,center,material('Handle',(.12,.14,.18)))
cylinder('53 mm shaft reference',.0022,.053,center+axis*.0465,material('Metal',(.65,.68,.72),.8))
bpy.ops.mesh.primitive_plane_add(size=2,location=(0,0,-.012));bpy.context.object.data.materials.append(material('Ground',(.75,.78,.82)))
def light(pos,power,size):
    bpy.ops.object.light_add(type='AREA',location=pos);ob=bpy.context.object;ob.data.energy=power;ob.data.shape='DISK';ob.data.size=size;ob.rotation_euler=(Vector((0,0,.07))-ob.location).to_track_quat('-Z','Y').to_euler()
light((.15,-.22,.3),3,.25);light((-.2,.05,.2),2,.2)
bpy.ops.object.camera_add();camera=bpy.context.object;camera.data.type='ORTHO';scene.camera=camera
def render(name,pos,target,scale):
    camera.location=pos;camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=scale
    scene.render.filepath=str(OUT/name);bpy.ops.render.render(write_still=True)
render('assembly.png',(.19,-.28,.17),(0,-.012,.066),.18)
objects['03_Expansion_Receiver_installed'].hide_render=True;cut.hide_render=False
render('latch_open.png',(.10,-.23,.11),(0,.001,.051),.090)
for name,ob in objects.items():
    if name.startswith(('01_','02_','06_','07_')):
        side=1 if name.startswith(('01_','06_')) else -1
        pivot=Vector((side*.0106,0,0))
        ob.matrix_world=Matrix.Translation(pivot)@Matrix.Rotation(math.radians(-side*5.5),4,'Y')@Matrix.Translation(-pivot)@ob.matrix_world
render('latch_closed.png',(.10,-.23,.11),(0,.001,.051),.090)
