# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name": "FakeBones",
    "author": "Aman, Corey Kinard, maylog",
    "version": (1, 0, 6),
    "blender": (4, 2, 0),
    "location": "Properties > Data > FakeBones",
    "description": "Automates the creation of fake bones for better visualization of armatures",
    "category": "Animation",
}

import bpy
from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import FloatProperty, StringProperty
import mathutils

class FakeBonesSettings(PropertyGroup):
    cone_size: FloatProperty(
        name="Cone Size",
        description="Size for cone empties (applied via Update Cone Size button)",
        default=0.004,  
        min=0.0001,
        max=1.0,
    )
    skip_bone_patterns: StringProperty(
        name="Skip Bone Patterns",
        description="Comma-separated patterns for bones to skip (e.g., IK,cor)",
        default="IK,cor",
    )


class FAKEBONES_OT_CreateFakeBones(Operator):
    bl_idname = "object.create_fake_bones"  
    bl_label = "Create Fake Bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        armature = context.active_object
        settings = context.scene.fake_bones_settings

        skip_patterns = [pattern.strip().lower() for pattern in settings.skip_bone_patterns.split(",") if pattern.strip()]

        if "FakeBones" in bpy.data.collections:
            self.report({'WARNING'}, "FakeBones collection already exists, please clear it first!")
            return {'CANCELLED'}

        armature.show_in_front = True


        fake_bones_coll = bpy.data.collections.new("FakeBones")
        context.scene.collection.children.link(fake_bones_coll)
        fake_bones_coll.hide_select = False  

        joint_empty = bpy.data.objects.new("Joint", None)
        joint_empty.empty_display_type = 'SPHERE'
        joint_empty.empty_display_size = 0.1
        fake_bones_coll.objects.link(joint_empty)  

        context.view_layer.objects.active = armature
        armature.select_set(True)
        bpy.ops.object.mode_set(mode='POSE')
        for pose_bone in armature.pose.bones:
            pose_bone.custom_shape = joint_empty
            pose_bone.use_custom_shape_bone_size = True
        bpy.ops.object.mode_set(mode='OBJECT')

        bone_empty_template = bpy.data.objects.new("Bone_Template", None)
        bone_empty_template.empty_display_type = 'CONE'
        fake_bones_coll.objects.link(bone_empty_template)  

        for bone in armature.data.bones:
            if not bone.parent:  
                continue

            bone_name_lower = bone.name.lower()
            if any(bone_name_lower.startswith(pattern) for pattern in skip_patterns):
                continue

            parent_bone = bone.parent
            if not parent_bone:
                continue

            bone_empty = bpy.data.objects.new(f"{bone.name}_Bone", None)
            bone_empty.empty_display_type = 'CONE'
            bone_empty.empty_display_size = 0.004  
            fake_bones_coll.objects.link(bone_empty)  

            loc_constraint = bone_empty.constraints.new(type='COPY_LOCATION')
            loc_constraint.target = armature
            loc_constraint.subtarget = parent_bone.name

            rot_constraint = bone_empty.constraints.new(type='COPY_ROTATION')
            rot_constraint.target = armature
            rot_constraint.subtarget = parent_bone.name

            stretch_constraint = bone_empty.constraints.new(type='STRETCH_TO')
            stretch_constraint.target = armature
            stretch_constraint.subtarget = bone.name
            stretch_constraint.rest_length = 0.004 * 2  
            stretch_constraint.volume = 'NO_VOLUME'
            stretch_constraint.keep_axis = 'SWING_Y'

        for obj in fake_bones_coll.objects:
            obj.show_in_front = True

        for obj in fake_bones_coll.objects:
            for coll in obj.users_collection:
                if coll != fake_bones_coll:
                    coll.objects.unlink(obj)

        bone_template = bpy.data.objects.get("Bone_Template")
        if bone_template:
            bone_template.empty_display_size = 0.004  
        else:
            self.report({'WARNING'}, "Bone_Template empty object not found!")

        fake_bones_coll.hide_select = True
        context.view_layer.update()  

        self.report({'INFO'}, "FakeBones created successfully!")
        return {'FINISHED'}

class FAKEBONES_OT_ClearFakeBones(Operator):
    bl_idname = "object.clear_fake_bones"  # 修改为 object 前缀
    bl_label = "Clear Fake Bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return "FakeBones" in bpy.data.collections

    def execute(self, context):
        fake_bones_coll = bpy.data.collections["FakeBones"]
        for obj in fake_bones_coll.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(fake_bones_coll)

        self.report({'INFO'}, "FakeBones cleared successfully!")
        return {'FINISHED'}

class FAKEBONES_OT_UpdateConeSize(Operator):
    bl_idname = "object.update_cone_size"
    bl_label = "Update Cone Size"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):

        return "FakeBones" in bpy.data.collections

    def execute(self, context):
        settings = context.scene.fake_bones_settings
        cone_size = settings.cone_size

        fake_bones_coll = bpy.data.collections["FakeBones"]
        updated = False
        for obj in fake_bones_coll.objects:
            if obj.name.endswith("_Bone"):  
                obj.empty_display_size = cone_size
                for constraint in obj.constraints:
                    if constraint.type == 'STRETCH_TO':
                        constraint.rest_length = cone_size * 2
                updated = True

        if updated:
            self.report({'INFO'}, "Cone size updated successfully!")
        else:
            self.report({'WARNING'}, "No cone empties found to update!")
        return {'FINISHED'}

class FAKEBONES_PT_Panel(Panel):
    bl_label = "FakeBones"
    bl_idname = "FAKEBONES_PT_Panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_category = "FakeBones"
    bl_options = {'DEFAULT_CLOSED'}  

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'ARMATURE'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.fake_bones_settings

        layout.operator("object.create_fake_bones", text="Create Fake Bones")
        layout.operator("object.clear_fake_bones", text="Clear Fake Bones")
        layout.prop(settings, "skip_bone_patterns", text="Skip Bone Patterns")
        layout.prop(settings, "cone_size", text="Cone Size")
        layout.operator("object.update_cone_size", text="Update Cone Size")

classes = (FakeBonesSettings, FAKEBONES_OT_CreateFakeBones, FAKEBONES_OT_ClearFakeBones, FAKEBONES_OT_UpdateConeSize, FAKEBONES_PT_Panel)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fake_bones_settings = bpy.props.PointerProperty(type=FakeBonesSettings)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    if hasattr(bpy.types.Scene, "fake_bones_settings"):
        del bpy.types.Scene.fake_bones_settings

if __name__ == "__main__":
    register()