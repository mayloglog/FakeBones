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
    "name": "FakeBones Addon",
    "author": "dfelinto , maylog",
    "version": (1, 0, 5),
    "blender": (4, 2, 0),
    "location": "Properties > Data > FakeBones",
    "description": "Automates the creation of fake bones for better visualization of armatures",
    "category": "Animation",
}

import bpy
from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import FloatProperty, StringProperty

# 自定义属性组，用于存储用户设置
class FakeBonesSettings(PropertyGroup):
    cone_size: FloatProperty(
        name="Cone Size",
        description="Size for cone empties (applied via Update Cone Size button)",
        default=0.001,
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
    bl_idname = "fakebones.create_fake_bones"
    bl_label = "Create Fake Bones"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # 直接获取骨骼对象（按钮在骨骼面板，用户已选择骨骼）
        armature = context.active_object
        settings = context.scene.fake_bones_settings

        # 获取要跳过的骨骼名称模式
        skip_patterns = [pattern.strip().lower() for pattern in settings.skip_bone_patterns.split(",") if pattern.strip()]

        # 检查是否已存在 FakeBones 集合
        if "FakeBones" in bpy.data.collections:
            self.report({'WARNING'}, "FakeBones 集合已存在，请先清除！")
            return {'CANCELLED'}

        # 步骤 1：设置骨骼在前面
        armature.show_in_front = True

        # 步骤 2：获取骨骼长度
        bone_lengths = {}
        context.view_layer.objects.active = armature
        armature.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        for bone in armature.data.edit_bones:
            length = max((bone.tail - bone.head).length, 0.0001)  # 确保长度不为零
            bone_lengths[bone.name] = length
        bpy.ops.object.mode_set(mode='OBJECT')

        # 步骤 3：创建 FakeBones 集合
        fake_bones_coll = bpy.data.collections.new("FakeBones")
        context.scene.collection.children.link(fake_bones_coll)
        fake_bones_coll.hide_select = False  # 暂时保持可选中，直到最后设置

        # 步骤 4：创建 Joint 空物体（球形）
        joint_empty = bpy.data.objects.new("Joint", None)
        joint_empty.empty_display_type = 'SPHERE'
        joint_empty.empty_display_size = 0.1
        fake_bones_coll.objects.link(joint_empty)  # 仅添加到 FakeBones 集合

        # 步骤 5 & 6：将 Joint 空物体设为所有骨骼的自定义形状，并启用“缩放到骨骼长度”
        context.view_layer.objects.active = armature
        armature.select_set(True)
        bpy.ops.object.mode_set(mode='POSE')
        for pose_bone in armature.pose.bones:
            pose_bone.custom_shape = joint_empty
            pose_bone.use_custom_shape_bone_size = True
        bpy.ops.object.mode_set(mode='OBJECT')

        # 步骤 7：创建 Bone 空物体（锥形）模板
        bone_empty_template = bpy.data.objects.new("Bone_Template", None)
        bone_empty_template.empty_display_type = 'CONE'
        fake_bones_coll.objects.link(bone_empty_template)  # 仅添加到 FakeBones 集合

        # 步骤 8：为每根骨骼创建 Bone 空物体并设置约束
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

            # 计算锥体空物体的尺寸（骨骼长度除以 1000）
            bone_length = bone_lengths.get(bone.name, 0.1)
            bone_empty_size = bone_length / 1000

            # 复制 Bone 空物体
            bone_empty = bpy.data.objects.new(f"{bone.name}_Bone", None)
            bone_empty.empty_display_type = 'CONE'
            bone_empty.empty_display_size = bone_empty_size
            fake_bones_coll.objects.link(bone_empty)  # 仅添加到 FakeBones 集合

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
            stretch_constraint.rest_length = bone_empty_size * 2
            stretch_constraint.volume = 'NO_VOLUME'
            stretch_constraint.keep_axis = 'SWING_Y'

        # 步骤 9：设置 FakeBones 集合中所有物体的视图显示为前置
        for obj in fake_bones_coll.objects:
            obj.show_in_front = True

        # 步骤 10：确保所有空物体仅属于 FakeBones 集合
        for obj in fake_bones_coll.objects:
            for coll in obj.users_collection:
                if coll != fake_bones_coll:
                    coll.objects.unlink(obj)

        # 步骤 11：调整 Bone_Template 的尺寸
        bone_template = bpy.data.objects.get("Bone_Template")
        if bone_template:
            bone_template.empty_display_size = 0.1
        else:
            self.report({'WARNING'}, "未找到 Bone_Template 空物体！")

        # 步骤 12：设置 FakeBones 集合不可选中
        fake_bones_coll.hide_select = True
        context.view_layer.update()  # 更新视图层，确保设置生效

        # 步骤 13：报告成功
        self.report({'INFO'}, "FakeBones 创建成功！")
        return {'FINISHED'}

# 操作类：清除假骨骼
class FAKEBONES_OT_ClearFakeBones(Operator):
    bl_idname = "fakebones.clear_fake_bones"
    bl_label = "Clear Fake Bones"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if "FakeBones" not in bpy.data.collections:
            self.report({'WARNING'}, "没有找到 FakeBones 集合！")
            return {'CANCELLED'}

        fake_bones_coll = bpy.data.collections["FakeBones"]
        # 删除 FakeBones 集合及其所有物体
        for obj in fake_bones_coll.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(fake_bones_coll)

        self.report({'INFO'}, "FakeBones 已清除！")
        return {'FINISHED'}

# 操作类：更新圆锥尺寸
class FAKEBONES_OT_UpdateConeSize(Operator):
    bl_idname = "fakebones.update_cone_size"
    bl_label = "Update Cone Size"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.fake_bones_settings
        cone_size = settings.cone_size

        if "FakeBones" not in bpy.data.collections:
            self.report({'WARNING'}, "没有找到 FakeBones 集合！")
            return {'CANCELLED'}

        fake_bones_coll = bpy.data.collections["FakeBones"]
        updated = False
        for obj in fake_bones_coll.objects:
            if obj.name.endswith("_Bone"):  # 仅更新锥形空物体
                obj.empty_display_size = cone_size
                for constraint in obj.constraints:
                    if constraint.type == 'STRETCH_TO':
                        constraint.rest_length = cone_size * 2
                updated = True

        if updated:
            self.report({'INFO'}, "圆锥尺寸更新成功！")
        else:
            self.report({'WARNING'}, "没有找到锥形空物体！")
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
        return context.active_object and context.active_object.type == 'ARMATURE'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.fake_bones_settings

        # 添加所有 UI 控件
        layout.operator("fakebones.create_fake_bones", text="Create Fake Bones")
        layout.operator("fakebones.clear_fake_bones", text="Clear Fake Bones")
        layout.prop(settings, "skip_bone_patterns", text="Skip Bone Patterns")
        layout.prop(settings, "cone_size", text="Cone Size")
        layout.operator("fakebones.update_cone_size", text="Update Cone Size")

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