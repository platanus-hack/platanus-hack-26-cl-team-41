from pathlib import Path
import bpy
from mathutils import Vector
root=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.wm.stl_import(filepath=str(root/'sources/Placa_base_TT_original.stl'));obj=bpy.context.object;obj.scale=(.001,)*3
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=12;scene.cycles.use_denoising=True;scene.render.resolution_x=1000;scene.render.resolution_y=850;scene.render.resolution_percentage=100
scene.world.color=(.3,.3,.3)
for pos in ((.1,-.2,.4),(-.25,.1,.3)):
    bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.data.energy=8;o.data.size=.3
bpy.ops.object.camera_add(location=(.3,-.4,.32));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,.025))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.25;scene.camera=cam
scene.render.filepath=str(root/'base-inspection.png');bpy.ops.render.render(write_still=True)
