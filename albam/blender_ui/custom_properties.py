import bpy
import json

from albam.registry import blender_registry


@blender_registry.register_blender_prop
class CopyPasterBuff(bpy.types.PropertyGroup):
    mat_buff: bpy.props.StringProperty()
    mesh_buff: bpy.props.StringProperty()


@blender_registry.register_blender_type
class CopyCustomPropertiesMat(bpy.types.Operator):
    """Copy Albam material properties from the active material"""
    bl_idname = "material.custom_property_copy"
    bl_label = "Copy Properties"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        mat = bpy.context.active_object.active_material.name
        if mat:
            bpy.context.scene.albam_copypaster.mat_buff = mat
            print(mat)
        return {'FINISHED'}


@blender_registry.register_blender_type
class PasteCustomPropertiesMat(bpy.types.Operator):
    """Paste Albam material properties to the active material"""
    bl_idname = "material.custom_property_paste"
    bl_label = "Paste Properties"

    @classmethod
    def poll(cls, context):
        if not context.scene.albam_copypaster.mat_buff:
            return False
        return True

    def execute(self, context):
        active_mat = context.material
        mat_name = context.scene.albam_copypaster.mat_buff
        try:
            copied_mat = bpy.data.materials.get(mat_name)
        except:
            context.scene.albam_copypaster.mat_buff = ""
        albam_asset = self.albam_asset_uses_mat(active_mat)
        app_id = albam_asset.app_id
        custom_props = active_mat.albam_custom_properties.get_appid_custom_properties(app_id)
        for attr_name in custom_props.__annotations__:
            if app_id == "re5":
                setattr(active_mat.albam_custom_properties.mod_156_material,
                        attr_name,
                        getattr(copied_mat.albam_custom_properties.mod_156_material, attr_name))
            else:
                setattr(active_mat.albam_custom_properties.mrl_params,
                        attr_name,
                        getattr(copied_mat.albam_custom_properties.mrl_params, attr_name))
        return {'FINISHED'}

    @staticmethod
    def albam_asset_uses_mat(mat):
        # XXX case where same material used in different
        # albam assets with different app_ids not supported yet
        albam_asset = None
        for obj in bpy.data.objects:
            if not obj.albam_asset.relative_path:
                continue
            children = [c.data for c in obj.children_recursive if c.type == "MESH"]
            is_mat_used = any(mesh.user_of_id(mat) for mesh in children)
            if is_mat_used:
                albam_asset = obj.albam_asset
        return albam_asset


@blender_registry.register_blender_type
class StoreCustomPropertiesMat(bpy.types.Operator):
    """Copy Albam material properties from the active material"""
    bl_idname = "material.custom_property_store"
    bl_label = "Store to a file"

    filepath: bpy.props.StringProperty(subtype="DIR_PATH")
    filename = bpy.props.StringProperty(default="")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        active_mat = context.material
        params = {}
        albam_asset = self.albam_asset_uses_mat(active_mat)
        app_id = albam_asset.app_id
        custom_props = active_mat.albam_custom_properties.get_appid_custom_properties(app_id)
        for attr_name in custom_props.__annotations__:
            if app_id == "re5":
                params[attr_name] = getattr(active_mat.albam_custom_properties.mod_156_material, attr_name)
            else:
                params[attr_name] = getattr(active_mat.albam_custom_properties.mrl_params, attr_name)
        with open(self.filepath, "w") as file:
            file.write(json.dumps(params, indent=4))
            print("store mat params")
        return {'FINISHED'}

    def invoke(self, context, event):
        self.filepath = bpy.context.active_object.active_material.name + ".json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    @staticmethod
    def albam_asset_uses_mat(mat):
        # XXX case where same material used in different
        # albam assets with different app_ids not supported yet
        albam_asset = None
        for obj in bpy.data.objects:
            if not obj.albam_asset.relative_path:
                continue
            children = [c.data for c in obj.children_recursive if c.type == "MESH"]
            is_mat_used = any(mesh.user_of_id(mat) for mesh in children)
            if is_mat_used:
                albam_asset = obj.albam_asset
        return albam_asset


class LoadCustomPropertiesMat(bpy.types.Operator):
    """Load Albam material properties from a file to the active material"""
    bl_idname = "material.custom_property_load"
    bl_label = "Load from a file"

    filepath: bpy.props.StringProperty(subtype="DIR_PATH")
    filename = bpy.props.StringProperty(default="")
    filter_glob: bpy.props.StringProperty(
        default="*.json",
        options={'HIDDEN'},
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        active_mat = bpy.context.active_object.active_material

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


@blender_registry.register_blender_type
class ALBAM_PT_CustomPropertiesMaterial(bpy.types.Panel):
    bl_idname = "ALBAM_PT_CustomPropertiesMaterial"
    bl_label = "Custom Properties (Albam)"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"

    @classmethod
    def poll(cls, context):  # pragma: no cover
        return context.material and bool(cls.albam_asset_uses_mat(context.material))

    def draw(self, context):
        mat = context.material
        layout = self.layout  # add layout for Albam material panel
        row = layout.row()
        row.operator("material.custom_property_copy")
        row.operator("material.custom_property_store",
                     icon="SORT_ASC", text="")
        row = layout.row()
        row.operator("material.custom_property_paste")
        row.operator("material.custom_property_load",
                     icon="SORT_DESC", text="")
        albam_asset = self.albam_asset_uses_mat(mat)  # already called in poll, can we save this?
        app_id = albam_asset.app_id
        custom_props = mat.albam_custom_properties.get_appid_custom_properties(app_id)
        for k in custom_props.__annotations__:
            self.layout.prop(custom_props, k)

    @staticmethod
    def albam_asset_uses_mat(mat):
        # XXX case where same material used in different
        # albam assets with different app_ids not supported yet
        albam_asset = None
        for obj in bpy.data.objects:
            if not obj.albam_asset.relative_path:
                continue
            children = [c.data for c in obj.children_recursive if c.type == "MESH"]
            is_mat_used = any(mesh.user_of_id(mat) for mesh in children)
            if is_mat_used:
                albam_asset = obj.albam_asset
        return albam_asset


@blender_registry.register_blender_type
class ALBAM_PT_CustomPropertiesMesh(bpy.types.Panel):
    bl_idname = "ALBAM_PT_CustomPropertiesMesh"
    bl_label = "Custom Properties (Albam)"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):  # pragma: no cover
        return context.mesh and bool(cls.albam_asset_uses_mesh(context.mesh))

    def draw(self, context):
        albam_asset = self.albam_asset_uses_mesh(context.mesh)  # already called in poll, can we save this?
        app_id = albam_asset.app_id
        custom_props = context.mesh.albam_custom_properties.get_appid_custom_properties(app_id)
        for k in custom_props.__annotations__:
            self.layout.prop(custom_props, k)

    @staticmethod
    def albam_asset_uses_mesh(mesh):
        # XXX case where same material used in different
        # albam assets with different app_ids not supported yet
        albam_asset = None
        for obj in bpy.data.objects:
            if not obj.albam_asset.relative_path:
                continue
            children = {c.data for c in obj.children_recursive if c.type == "MESH"}
            if mesh in children:
                albam_asset = obj.albam_asset
                break
        return albam_asset
