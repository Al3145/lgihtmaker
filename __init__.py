bl_info = {
    "name": "Batch Import/Export",
    "author": "Al Ansari",
    "version": (0, 3, 0),
    "blender": (4, 1, 0),
    "location": "",
    "description": "Lightmap Baking Addon",
    "warning": "",
    "doc_url": "",
    "category": "Bake",
}

import numpy as np
import bpy
from bpy.props import StringProperty, IntProperty
from bpy.types import PropertyGroup, Operator, Panel
import pathlib
files = []
texture_folders = []
bakes = []


class BaseList(PropertyGroup):

    name: StringProperty(
            name="Name",
            description="Main Property Name",
            default="") # type: ignore

    random_prop: StringProperty(
            name="Any other property you want",
            description="",
            default="") # type: ignore

class List_of_glTFs(BaseList):
    pass

class LIST_OT_DeleteItem(Operator):

    bl_idname = "my_list.delete_item"
    bl_label = "Deletes an item"
    bl_description = "Export out asset as glTF to designated path"
    @classmethod
    def poll(cls, context):
        return context.scene.my_glTFs

    def execute(self, context):
        my_glTFs = context.scene.my_glTFs
        index = context.scene.list_index

        my_glTFs.remove(index)
        context.scene.list_index = min(max(0, index - 1), len(my_glTFs) - 1)

        return{'FINISHED'}
class LIST_OT_CreateGroup(Operator):
    bl_idname = "my_list.my_group"
    bl_label = "create group"
    bl_description = "Create glTF necessary nodetree to be appended before export"

    def execute(self, context):
        group_name = "glTF Material Output"
        
        if group_name in bpy.data.node_groups:
            self.report({'INFO'}, f"Node group '{group_name}' already exists.")
            return {'CANCELLED'}

        group = bpy.data.node_groups.new(type="ShaderNodeTree", name=group_name)
        bpy.data.node_groups[group_name].use_fake_user = True

        occlusion_socket = bpy.data.node_groups[group_name].interface.new_socket(name='Occlusion', in_out='INPUT', socket_type='NodeSocketFloat',)
        thickness_socket = bpy.data.node_groups[group_name].interface.new_socket(name='Thickness', in_out='INPUT', socket_type='NodeSocketFloat',)
        

        input_node = group.nodes.new("NodeGroupInput") 
        output_node = group.nodes.new("NodeGroupOutput") 
        
        return{'FINISHED'}

class TEX_OT_BakeItem(Operator):
    bl_idname = "my_list.bake_item"
    bl_label = "bake lightmap pass"
    bl_description = "Bakes a lightmap pass mix between a shadow bake and an AO bake"
    def __init__(self):
        self.old_mat = None
        self.shadowImg = None
        self.aoImg = None
        self.nodes = None
        self.ao_node = None
        self.shadow_node = None
        self.combinedImage = None

    def ensure_uv_map(self, obj, uv_map_name):
        uv_map_exists = False
        for uv_layer in obj.data.uv_layers:
            if uv_layer.name == uv_map_name:
                uv_map_exists = True
                break
        if not uv_map_exists:
            obj.data.uv_layers.new(name=uv_map_name)
            print(f"UV map '{uv_map_name}' created for object '{obj.name}'")
        else:
            print(f"UV map '{uv_map_name}' already exists for object '{obj.name}'")

    def create_and_save_image(self, geo_selected, image_suffix, save_path):
        image_name = geo_selected.name + image_suffix

        if image_name in bpy.data.images:
            image = bpy.data.images[image_name]
            print(f"Image '{image_name}' already exists. Reusing existing image.")
        else:
            image = bpy.data.images.new(image_name, 512, 512)
            image.filepath = str(save_path / image_name)
            image.save()
            print(f"Image '{image_name}' created and saved.")
        return image

    def setup_shader_node(self, image, node_name):
        geo_selected = bpy.context.selected_objects[0]
        if not geo_selected:
            self.report({'INFO'}, f"No object selected.")
            return

        for material in geo_selected.data.materials:
            material.use_nodes = True
            nodes = material.node_tree.nodes

            if node_name in nodes:
                self.report({'INFO'}, f"Node '{node_name}' already exists in material '{material.name}'.")
                existing_node = nodes[node_name]
                existing_node.select = True
                nodes.active = existing_node
                return existing_node

            shader_node = nodes.new('ShaderNodeTexImage')
            shader_node.name = node_name
            shader_node.select = True
            nodes.active = shader_node
            shader_node.image = image
            print(f"Shader node '{node_name}' added to material '{material.name}' with image '{image.name}'.")
            return shader_node

    def get_or_create_node(self, node_name, node_type):
        if not bpy.context.selected_objects:
            self.report({'INFO'}, f"No Object Is Selected, Please Select One.")
            return None

        geo_selected = bpy.context.selected_objects[0]
        
        for material in geo_selected.data.materials:
            if not material.use_nodes:
                material.use_nodes = True
            
            nodes = material.node_tree.nodes
            node = nodes.get(node_name)
            
            if node is None:
                node = nodes.new(type=node_type)
                node.name = node_name
                
            return node
    
    def bake_lightmap(self, context):
        bpy.context.scene.render.engine = 'CYCLES'
        if context.preferences.addons["cycles"].preferences.has_active_device():
            bpy.context.scene.cycles.device = 'GPU'

        geo_selected = bpy.context.active_object
        self.ensure_uv_map(geo_selected, 'lightmap')

        self.old_mat = bpy.context.object.active_material
        save_path = pathlib.Path(bpy.context.scene.TEX_bakes_path)
        
        
        self.shadowImg = self.create_and_save_image(geo_selected, '_shadowTEX.jpg', save_path)
        self.aoImg = self.create_and_save_image(geo_selected, '_aoTEX.jpg', save_path)
        self.lightmapImg = self.create_and_save_image(geo_selected, '_combinedTEX', save_path)
        path_shadow = str(save_path / (geo_selected.name + '_shadowTEX.jpg'))
        path_ao = str(save_path / (geo_selected.name + '_aoTEX.jpg'))
        bpy.context.scene.render.bake.use_selected_to_active = False

        self.ao_node = self.setup_shader_node(self.shadowImg, 'Bake_node')
        bpy.ops.object.bake(type='AO', save_mode='INTERNAL', uv_layer="lightmap", filepath=path_ao)
        
        self.shadow_node = self.setup_shader_node(self.aoImg, 'shadow_node')
        bpy.ops.object.bake(type='SHADOW', save_mode='INTERNAL', uv_layer="lightmap", filepath=path_shadow) 

        bpy.context.object.active_material = self.old_mat

        aoPixels = np.array(self.aoImg.pixels[:])
        print(aoPixels)

        print("this was pixels")
        shadowPixels = np.array(self.shadowImg.pixels[:])
        
        combinedPixels = (aoPixels + shadowPixels) / 2
        combinedImage = bpy.data.images[self.lightmapImg.name]
        combinedImage.pixels = combinedPixels.tolist()

        self.node_tree = self.old_mat.node_tree
        self.nodes = self.node_tree.nodes
        self.bsdf = self.nodes.get("Principled BSDF")
        self.material_output = self.nodes.get("Material Output")

        group = bpy.data.node_groups["glTF Material Output"]
        group_node = self.get_or_create_node("ShaderNodeGroup", "ShaderNodeGroup")
        
        group_node.name = "glTF Material Output"
        group_node.node_tree = group

        self.combined_texture_node= self.get_or_create_node("ShaderNodeTexImage", "ShaderNodeTexImage")
        self.separateRGB_node_AO = self.get_or_create_node("ShaderNodeSeparateRGB", "ShaderNodeSeparateRGB")
        self.UVMap_node = self.get_or_create_node("ShaderNodeUVMap", "ShaderNodeUVMap") 
        self.UVMap_node.uv_map = "lightmap"


        self.link_RGB_Group = self.old_mat.node_tree.links.new(self.separateRGB_node_AO.outputs[0], group_node.inputs[0]) 
        self.link_lightmap_RGB = self.old_mat.node_tree.links.new(self.combined_texture_node.outputs['Color'], self.separateRGB_node_AO.inputs[0]) 
        self.link_UV_AO = self.old_mat.node_tree.links.new(self.UVMap_node.outputs[0], self.combined_texture_node.inputs[0]) 
        self.ao_node.image = self.aoImg
        self.shadow_node.image = self.shadowImg
        self.combined_texture_node.image = combinedImage

    def execute(self, context):
        selected_objs = [mesh for mesh in bpy.context.selected_objects if mesh.type == 'MESH'] 
        for obj in selected_objs:

            bpy.ops.object.select_all(action='DESELECT')
            object = str(obj.name)
            bpy.data.objects[object].select_set(True)
            bpy.context.view_layer.objects.active = obj
            self.bake_lightmap(context)

        return{'FINISHED'}

class LIST_OT_ExportglTF(Operator):
    bl_idname = "my_list.export_item"
    bl_label =  "Export out asset as glTF to designated path"
    bl_description = "Export out asset as glTF to designated path"
    
    def execute(self, context):
        active_object = bpy.context.view_layer.objects.active
        path_to_glTF_dir = pathlib.Path(bpy.context.scene.glTF_export_path)
        if active_object:
            export_path = str(path_to_glTF_dir / (active_object.name + ".gltf"))
            bpy.ops.export_scene.gltf(filepath=export_path, use_selection=True)
            glTF = context.scene.my_glTFs.add()
            glTF.name = export_path
            glTF.val = active_object.name
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No active object to export.")
            return {'CANCELLED'}


class ADDON_PT_my_panel(Panel):
    bl_label = "Bake Lightmap"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Lightmap Baker"
    bl_label = "Bake Lightmap"

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        col = layout.column(align=True) 
        col.prop(context.scene, 'TEX_bakes_path')

        col = layout.column(align=True)
        col = layout.column(align=True)
        col.operator('my_list.bake_item', text='Bake Lightmap')
        col.operator('my_list.my_group', text='Make Node Group')
        col = layout.column(align=True)

        col = layout.column(align=True) 
        col.prop(context.scene, 'glTF_export_path')
        col = layout.column(align=True)
        col.operator('my_list.export_item', text='Export glTF')
        layout.label(text="Exported glTF Files:")
        col = layout.column(align=True) 
        col.template_list("UI_UL_list", "The_List", scene, "my_glTFs", scene, "list_index", rows = scene.list_index)
        row=layout.row()
        row.operator('my_list.delete_item', text='Remove Item')
        

def register():
    bpy.utils.register_class(LIST_OT_DeleteItem)
    bpy.types.Scene.TEX_bakes_path = bpy.props.StringProperty(
        name= 'Bakes Path',
        subtype = 'DIR_PATH',
        default=r"C:\\Users\\Kafxa\\Documents\\BakesTEst\\"
        )
    
    bpy.types.Scene.glTF_export_path = bpy.props.StringProperty(
        name= 'glTF Export Path',
        subtype = 'DIR_PATH',
        default=r"C:\\Users\\Kafxa\Documents\\glTF Export Path\\"
        )  

    bpy.utils.register_class(TEX_OT_BakeItem)
    bpy.utils.register_class(LIST_OT_CreateGroup)
    bpy.utils.register_class(ADDON_PT_my_panel)
    bpy.utils.register_class(LIST_OT_ExportglTF)
    bpy.utils.register_class(BaseList)
    bpy.utils.register_class(List_of_glTFs)

    bpy.types.Scene.my_glTFs = bpy.props.CollectionProperty(type=List_of_glTFs)
    bpy.types.Scene.list_index = IntProperty(name = "Index for my_glTFs",
                                             default = 0)


def unregister():
    del bpy.types.Scene.TEX_bakes_path
    del bpy.types.Scene.glTF_export_path
    del bpy.types.Scene.my_glTFs
    del bpy.types.Scene.list_index
    bpy.utils.unregister_class(TEX_OT_BakeItem)
    bpy.utils.unregister_class(LIST_OT_CreateGroup)
    bpy.utils.unregister_class(ADDON_PT_my_panel)
    bpy.utils.unregister_class(LIST_OT_ExportglTF)
    bpy.utils.unregister_class(BaseList)
    bpy.utils.unregister_class(List_of_glTFs)
    bpy.utils.unregister_class(LIST_OT_DeleteItem)
if __name__ == "__main__":
    register()
