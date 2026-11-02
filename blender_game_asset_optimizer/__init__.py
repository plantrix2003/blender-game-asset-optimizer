bl_info = {
    "name": "Game Asset Optimizer",
    "author": "Community contributors",
    "version": (0, 1, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Game Asset",
    "description": "Inspect and prepare selected meshes for real-time workflows",
    "category": "Object",
}

import bpy


def selected_meshes(context):
    return [obj for obj in context.selected_objects if obj.type == "MESH"]


class GAO_OT_report(bpy.types.Operator):
    bl_idname = "gao.report_selected"
    bl_label = "Report Selected Meshes"

    def execute(self, context):
        meshes = selected_meshes(context)
        if not meshes:
            self.report({"WARNING"}, "Select at least one mesh object")
            return {"CANCELLED"}
        for obj in meshes:
            polygons = len(obj.data.polygons)
            dimensions = tuple(round(v, 3) for v in obj.dimensions)
            print(f"[Game Asset Optimizer] {obj.name}: {polygons} polygons; dimensions={dimensions}")
        self.report({"INFO"}, f"Reported {len(meshes)} mesh(es) to the system console")
        return {"FINISHED"}


def selected_material_images(context):
    """Return unique image datablocks used by selected mesh materials."""
    images = {}
    for obj in selected_meshes(context):
        for material in obj.data.materials:
            if material is None or not material.use_nodes or material.node_tree is None:
                continue
            for node in material.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image is not None:
                    image = node.image
                    images[image.as_pointer()] = image
    return list(images.values())


class GAO_OT_report_textures(bpy.types.Operator):
    bl_idname = "gao.report_textures"
    bl_label = "Report Texture Images"
    bl_description = "List unique image textures used by selected mesh materials"

    def execute(self, context):
        images = selected_material_images(context)
        if not images:
            self.report({"INFO"}, "No image textures found on selected mesh materials")
            return {"FINISHED"}

        total_bytes = 0
        print("[Game Asset Optimizer] Texture report")
        for image in sorted(images, key=lambda item: item.name.lower()):
            width, height = image.size
            estimated_bytes = max(0, width) * max(0, height) * 4
            total_bytes += estimated_bytes
            status = "packed" if image.packed_file else "external or generated"
            print(
                f"  {image.name}: {width}x{height}, "
                f"estimated RGBA8 size={estimated_bytes / (1024 * 1024):.2f} MiB, "
                f"source={status}"
            )

        self.report(
            {"INFO"},
            f"Reported {len(images)} unique image(s); estimated RGBA8 total "
            f"{total_bytes / (1024 * 1024):.2f} MiB (see system console)",
        )
        return {"FINISHED"}


class GAO_OT_apply_transforms(bpy.types.Operator):
    bl_idname = "gao.apply_transforms"
    bl_label = "Apply Location, Rotation & Scale"

    @classmethod
    def poll(cls, context):
        return any(obj.type == "MESH" for obj in context.selected_objects)

    def execute(self, context):
        meshes = selected_meshes(context)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        self.report({"INFO"}, f"Applied transforms to {len(meshes)} mesh(es)")
        return {"FINISHED"}


class GAO_OT_make_decimated_copy(bpy.types.Operator):
    bl_idname = "gao.make_decimated_copy"
    bl_label = "Create Decimated Copy"
    ratio: bpy.props.FloatProperty(name="Ratio", default=0.5, min=0.01, max=1.0)

    @classmethod
    def poll(cls, context):
        return any(obj.type == "MESH" for obj in context.selected_objects)

    def execute(self, context):
        sources = selected_meshes(context)
        bpy.ops.object.duplicate()
        copies = selected_meshes(context)
        for obj in copies:
            obj.name = f"{obj.name}_LOD"
            modifier = obj.modifiers.new(name="GameAsset_Decimate", type="DECIMATE")
            modifier.ratio = self.ratio
        self.report({"INFO"}, f"Created {len(sources)} decimated copy/copies")
        return {"FINISHED"}


class GAO_OT_export_fbx(bpy.types.Operator):
    bl_idname = "gao.export_selected_fbx"
    bl_label = "Export Selected FBX"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH", default="//game_asset.fbx")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if not selected_meshes(context):
            self.report({"WARNING"}, "Select at least one mesh object")
            return {"CANCELLED"}
        try:
            bpy.ops.export_scene.fbx(
                filepath=self.filepath,
                use_selection=True,
                apply_unit_scale=True,
                bake_space_transform=False,
                object_types={"MESH", "EMPTY", "ARMATURE"},
            )
        except Exception as exc:
            self.report({"ERROR"}, f"FBX export failed: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Exported selection to {self.filepath}")
        return {"FINISHED"}


class GAO_PT_panel(bpy.types.Panel):
    bl_label = "Game Asset Optimizer"
    bl_idname = "GAO_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Game Asset"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Selected mesh tools")
        layout.operator("gao.report_selected", icon="INFO")
        layout.operator("gao.report_textures", icon="IMAGE_DATA")
        layout.operator("gao.apply_transforms", icon="OBJECT_ORIGIN")
        layout.operator("gao.make_decimated_copy", icon="MOD_DECIM")
        layout.operator("gao.export_selected_fbx", icon="EXPORT")


CLASSES = (
    GAO_OT_report,
    GAO_OT_report_textures,
    GAO_OT_apply_transforms,
    GAO_OT_make_decimated_copy,
    GAO_OT_export_fbx,
    GAO_PT_panel,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
