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
    "version": (1, 0, 7),
    "blender": (4, 2, 0),
    "location": "Properties > Data > FakeBones",
    "description": "Automates the creation of fake bones for better visualization of armatures",
    "category": "Animation",
}

import bpy
from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import FloatProperty, StringProperty
import mathutils

# 自定义属性组，用于存储用户设置
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

# 操作类：创建假骨骼
class FAKEBONES_OT_CreateFakeBones(Operator):
    bl_idname = "object.create_fake_bones"
    bl_label = "Create Fake Bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # 确保活动对象存在且为骨骼类型
        return context.active_object is not None and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        # 直接获取骨骼对象
        armature = context.active_object
        settings = context.scene.fake_bones_settings

        # 获取要跳过的骨骼名称模式
        skip_patterns = [pattern.strip().lower() for pattern in settings.skip_bone_patterns.split(",") if pattern.strip()]

        # 检查是否存在 FakeBones 集合，若不存在则创建
        if "FakeBones" not in bpy.data.collections:
            fake_bones_coll = bpy.data.collections.new("FakeBones")
            context.scene.collection.children.link(fake_bones_coll)
        else:
            fake_bones_coll = bpy.data.collections["FakeBones"]

        # 创建子集合，命名为 {armature.name}_FakeBones
        sub_coll_name = f"{armature.name}_FakeBones"
        if sub_coll_name not in bpy.data.collections:
            sub_coll = bpy.data.collections.new(sub_coll_name)
            fake_bones_coll.children.link(sub_coll)  # 将子集合链接到 FakeBones
        else:
            sub_coll = bpy.data.collections[sub_coll_name]

        # 临时允许选择 FakeBones 集合及其子集合中的物体
        fake_bones_coll.hide_select = False
        sub_coll.hide_select = False

        # 步骤 1：设置骨骼在前面
        armature.show_in_front = True

        # 步骤 2：创建 Joint 空物体（球形），仅在第一次创建 FakeBones 集合时执行
        if not any(obj.name == "Joint" for obj in fake_bones_coll.objects):
            joint_empty = bpy.data.objects.new("Joint", None)
            joint_empty.empty_display_type = 'SPHERE'
            joint_empty.empty_display_size = 0.1
            fake_bones_coll.objects.link(joint_empty)  # 放入 FakeBones 集合
        else:
            joint_empty = bpy.data.objects.get("Joint")

        # 步骤 3 & 4：将 Joint 空物体设为所有骨骼的自定义形状，并启用“缩放到骨骼长度”
        context.view_layer.objects.active = armature
        armature.select_set(True)
        bpy.ops.object.mode_set(mode='POSE')
        for pose_bone in armature.pose.bones:
            pose_bone.custom_shape = joint_empty
            pose_bone.use_custom_shape_bone_size = True
        bpy.ops.object.mode_set(mode='OBJECT')

        # 步骤 5：创建 Bone 空物体（锥形）模板，仅在第一次创建 FakeBones 集合时执行
        if not any(obj.name == "Bone_Template" for obj in fake_bones_coll.objects):
            bone_empty_template = bpy.data.objects.new("Bone_Template", None)
            bone_empty_template.empty_display_type = 'CONE'
            bone_empty_template.empty_display_size = 0.004
            fake_bones_coll.objects.link(bone_empty_template)  # 放入 FakeBones 集合

        # 步骤 6：为每根骨骼创建 Bone 空物体并设置约束
        for bone in armature.data.bones:
            if not bone.parent:  # 跳过根骨骼
                continue

            # 检查是否跳过当前骨骼
            bone_name_lower = bone.name.lower()
            if any(bone_name_lower.startswith(pattern) for pattern in skip_patterns):
                continue

            parent_bone = bone.parent
            if not parent_bone:
                continue

            # 固定圆锥空物体尺寸为 0.004，使用骨骼对象名称作为前缀避免冲突
            bone_empty_name = f"{armature.name}_{bone.name}_Bone"
            # 检查是否已存在同名空物体
            if bone_empty_name in bpy.data.objects:
                continue  # 跳过已存在的空物体，避免重复创建

            bone_empty = bpy.data.objects.new(bone_empty_name, None)
            bone_empty.empty_display_type = 'CONE'
            bone_empty.empty_display_size = 0.004
            sub_coll.objects.link(bone_empty)  # 放入对应子集合

            # 添加约束
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

        # 步骤 7：设置 FakeBones 集合及其子集合中所有物体的视图显示为前置
        for obj in fake_bones_coll.objects:
            obj.show_in_front = True
        for obj in sub_coll.objects:
            obj.show_in_front = True

        # 步骤 8：确保所有空物体仅属于正确的集合
        for obj in sub_coll.objects:
            for coll in obj.users_collection:
                if coll != sub_coll:
                    coll.objects.unlink(obj)
        # 确保 Joint 和 Bone_Template 仅在 FakeBones 集合中
        for obj in fake_bones_coll.objects:
            if obj.name in ["Joint", "Bone_Template"]:
                for coll in obj.users_collection:
                    if coll != fake_bones_coll:
                        coll.objects.unlink(obj)

        # 步骤 9：设置 FakeBones 集合及其子集合不可选中
        fake_bones_coll.hide_select = True
        sub_coll.hide_select = True
        context.view_layer.update()  # 更新视图层，确保设置生效

        # 步骤 10：报告成功
        self.report({'INFO'}, f"FakeBones created successfully for {armature.name} in {sub_coll_name}!")
        return {'FINISHED'}

# 操作类：清除假骨骼
class FAKEBONES_OT_ClearFakeBones(Operator):
    bl_idname = "object.clear_fake_bones"
    bl_label = "Clear Fake Bones"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # 确保活动对象存在且为骨骼类型，并且对应子集合存在
        if context.active_object is None or context.active_object.type != 'ARMATURE':
            return False
        sub_coll_name = f"{context.active_object.name}_FakeBones"
        return "FakeBones" in bpy.data.collections and sub_coll_name in bpy.data.collections

    def execute(self, context):
        armature = context.active_object
        sub_coll_name = f"{armature.name}_FakeBones"
        fake_bones_coll = bpy.data.collections["FakeBones"]
        sub_coll = bpy.data.collections[sub_coll_name]

        # 删除子集合中的所有物体
        for obj in sub_coll.objects:
            bpy.data.objects.remove(obj, do_unlink=True)

        # 删除子集合
        bpy.data.collections.remove(sub_coll)

        # 如果 FakeBones 集合中没有其他子集合，删除整个 FakeBones 集合
        if not fake_bones_coll.children:
            # 仅保留 Joint 和 Bone_Template
            remaining_objects = [obj for obj in fake_bones_coll.objects if obj.name not in ["Joint", "Bone_Template"]]
            if not remaining_objects:
                for obj in fake_bones_coll.objects:
                    bpy.data.objects.remove(obj, do_unlink=True)
                bpy.data.collections.remove(fake_bones_coll)

        self.report({'INFO'}, f"FakeBones cleared successfully for {armature.name}!")
        return {'FINISHED'}

# 操作类：更新圆锥尺寸
class FAKEBONES_OT_UpdateConeSize(Operator):
    bl_idname = "object.update_cone_size"
    bl_label = "Update Cone Size"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # 确保活动对象存在且为骨骼类型，并且对应子集合存在
        if context.active_object is None or context.active_object.type != 'ARMATURE':
            return False
        sub_coll_name = f"{context.active_object.name}_FakeBones"
        return "FakeBones" in bpy.data.collections and sub_coll_name in bpy.data.collections

    def execute(self, context):
        armature = context.active_object
        sub_coll_name = f"{armature.name}_FakeBones"
        sub_coll = bpy.data.collections[sub_coll_name]
        settings = context.scene.fake_bones_settings
        cone_size = settings.cone_size

        updated = False
        for obj in sub_coll.objects:
            if obj.name.endswith("_Bone"):  # 仅更新锥形空物体
                obj.empty_display_size = cone_size
                for constraint in obj.constraints:
                    if constraint.type == 'STRETCH_TO':
                        constraint.rest_length = cone_size * 2
                updated = True

        if updated:
            self.report({'INFO'}, f"Cone size updated successfully for {armature.name}!")
        else:
            self.report({'WARNING'}, f"No cone empties found to update for {armature.name}!")
        return {'FINISHED'}

# UI 面板类（位于属性 > 数据面板）
class FAKEBONES_PT_Panel(Panel):
    bl_label = "FakeBones"
    bl_idname = "FAKEBONES_PT_Panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_category = "FakeBones"
    bl_options = {'DEFAULT_CLOSED'}  # 默认折叠面板

    @classmethod
    def poll(cls, context):
        # 仅在选择骨骼对象时显示面板
        return context.active_object is not None and context.active_object.type == 'ARMATURE'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.fake_bones_settings

        # 添加所有 UI 控件
        layout.operator("object.create_fake_bones", text="Create Fake Bones")
        layout.operator("object.clear_fake_bones", text="Clear Fake Bones")
        layout.prop(settings, "skip_bone_patterns", text="Skip Bone Patterns")
        layout.prop(settings, "cone_size", text="Cone Size")
        layout.operator("object.update_cone_size", text="Update Cone Size")

# 注册和卸载
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