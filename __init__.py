bl_info = {
    "name": "FakeBones",
    "author": "maylog",
    "version": (1, 0, 3),
    "blender": (3, 0, 0),
    "location": "Properties > Data > FakeBones",
    "description": "Automates the creation of fake bones for better visualization of armatures",
    "category": "Animation",
}

import bpy
from bpy.types import Operator, Panel

# 操作类：创建假骨骼
class FAKEBONES_OT_CreateFakeBones(Operator):
    bl_idname = "fakebones.create_fake_bones"
    bl_label = "Create Fake Bones"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # 直接获取骨骼对象（按钮在骨骼面板，用户已选择骨骼）
        armature = context.active_object

        # 步骤 1：设置骨骼在前面
        armature.show_in_front = True

        # 步骤 2：获取骨骼长度
        bone_lengths = {}
        context.view_layer.objects.active = armature
        armature.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        for bone in armature.data.edit_bones:
            # 计算骨骼的实际长度（头到尾的距离）
            length = (bone.tail - bone.head).length
            bone_lengths[bone.name] = length
        bpy.ops.object.mode_set(mode='OBJECT')

        # 步骤 3：创建 FakeBones 集合
        if "FakeBones" not in bpy.data.collections:
            fake_bones_coll = bpy.data.collections.new("FakeBones")
            context.scene.collection.children.link(fake_bones_coll)
        else:
            fake_bones_coll = bpy.data.collections["FakeBones"]
        fake_bones_coll.hide_select = True  # 设置禁用选中

        # 步骤 4：创建 Joint 空物体（球形）
        bpy.ops.object.empty_add(type='SPHERE')
        joint_empty = context.active_object
        joint_empty.name = "Joint"
        joint_empty.empty_display_size = 0.1  # 初始尺寸为 0.1
        fake_bones_coll.objects.link(joint_empty)  # 仅添加到 FakeBones 集合

        # 步骤 5 & 6：将 Joint 空物体设为所有骨骼的自定义形状，并启用“缩放到骨骼长度”
        context.view_layer.objects.active = armature
        armature.select_set(True)
        bpy.ops.object.mode_set(mode='POSE')  # 切换到姿势模式
        for pose_bone in armature.pose.bones:
            pose_bone.custom_shape = joint_empty
            pose_bone.use_custom_shape_bone_size = True  # 启用“缩放到骨骼长度”
        bpy.ops.object.mode_set(mode='OBJECT')

        # 步骤 7：创建 Bone 空物体（锥形）模板
        bpy.ops.object.empty_add(type='CONE')
        bone_empty_template = context.active_object
        bone_empty_template.name = "Bone_Template"
        fake_bones_coll.objects.link(bone_empty_template)  # 仅添加到 FakeBones 集合

        # 步骤 8：为每根骨骼创建 Bone 空物体并设置约束
        bpy.ops.object.mode_set(mode='OBJECT')
        for bone in armature.data.bones:
            if not bone.parent:  # 跳过根骨骼
                continue

            # 获取父骨骼
            parent_bone = bone.parent
            if not parent_bone:
                continue

            # 计算锥体空物体的尺寸（骨骼长度除以 1000）
            bone_length = bone_lengths.get(bone.name, 0.1)  # 如果找不到长度，默认使用 0.1
            bone_empty_size = bone_length / 1000

            # 复制 Bone 空物体
            bone_empty = bone_empty_template.copy()
            bone_empty.name = f"{bone.name}_Bone"
            bone_empty.empty_display_size = bone_empty_size  # 动态设置尺寸
            fake_bones_coll.objects.link(bone_empty)  # 仅添加到 FakeBones 集合

            # 添加约束
            # 复制位置
            loc_constraint = bone_empty.constraints.new(type='COPY_LOCATION')
            loc_constraint.target = armature
            loc_constraint.subtarget = parent_bone.name

            # 复制旋转
            rot_constraint = bone_empty.constraints.new(type='COPY_ROTATION')
            rot_constraint.target = armature
            rot_constraint.subtarget = parent_bone.name

            # 拉伸到目标
            stretch_constraint = bone_empty.constraints.new(type='STRETCH_TO')
            stretch_constraint.target = armature
            stretch_constraint.subtarget = bone.name
            stretch_constraint.rest_length = bone_empty_size * 2  # 初始长度为锥体尺寸的 2 倍
            stretch_constraint.volume = 'NO_VOLUME'  # 不保持体积
            stretch_constraint.keep_axis = 'SWING_Y'  # 沿 Y 轴拉伸

        # 步骤 9：设置 FakeBones 集合中所有物体的视图显示为前置
        for obj in fake_bones_coll.objects:
            obj.show_in_front = True

        # 步骤 10：报告成功
        self.report({'INFO'}, "FakeBones 创建成功！")
        return {'FINISHED'}

# UI 面板类（位于属性 > 数据面板）
class FAKEBONES_PT_Panel(Panel):
    bl_label = "FakeBones"
    bl_idname = "FAKEBONES_PT_Panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"  # 位于数据选项卡
    bl_category = "FakeBones"

    def draw(self, context):
        layout = self.layout
        layout.operator("fakebones.create_fake_bones", text="Create Fake Bones")

# 注册和卸载
classes = (FAKEBONES_OT_CreateFakeBones, FAKEBONES_PT_Panel)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()