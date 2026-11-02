bl_info = {
    "name": "Game Asset Optimizer",
    "author": "Community contributors",
    "version": (0, 3, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Game Asset",
    "description": "Inspect and prepare selected meshes for real-time workflows",
    "category": "Object",
}

import bpy
import bmesh
import math


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


def inspect_mesh_data(mesh):
    """Return basic topology diagnostics for a mesh datablock."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    report = {
        "vertices": len(bm.verts),
        "edges": len(bm.edges),
        "faces": len(bm.faces),
        "non_manifold_edges": sum(not edge.is_manifold for edge in bm.edges),
        "boundary_edges": sum(edge.is_boundary for edge in bm.edges),
        "wire_edges": sum(edge.is_wire for edge in bm.edges),
        "loose_vertices": sum(not vert.link_edges for vert in bm.verts),
        "degenerate_faces": sum(face.calc_area() <= 1e-12 for face in bm.faces),
    }
    bm.free()
    return report


class GAO_OT_mesh_health_report(bpy.types.Operator):
    bl_idname = "gao.mesh_health_report"
    bl_label = "Check Mesh Issues"
    bl_description = "Report non-manifold edges, loose geometry, and degenerate faces"

    @classmethod
    def poll(cls, context):
        return bool(selected_meshes(context))

    def execute(self, context):
        meshes = selected_meshes(context)
        print("[Game Asset Optimizer] Mesh health report")
        for obj in meshes:
            stats = inspect_mesh_data(obj.data)
            print(f"  {obj.name}: " + ", ".join(
                f"{key}={value}" for key, value in stats.items()
            ))
        self.report({"INFO"}, f"Mesh report printed for {len(meshes)} object(s); see system console")
        return {"FINISHED"}


class GAO_OT_repair_mesh(bpy.types.Operator):
    bl_idname = "gao.repair_mesh"
    bl_label = "Repair Mesh (Safe Copy)"
    bl_description = "Duplicate selected meshes, weld close vertices, remove loose geometry and recalculate normals"

    merge_distance: bpy.props.FloatProperty(
        name="Merge Distance",
        description="Vertices closer than this distance are merged",
        default=0.0001,
        min=0.0,
        precision=6,
        subtype="DISTANCE",
    )
    duplicate_before_repair: bpy.props.BoolProperty(
        name="Keep Original (Create Copy)",
        description="Repair duplicates and leave the original mesh objects untouched",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(selected_meshes(context))

    def execute(self, context):
        source_objects = selected_meshes(context)
        if self.duplicate_before_repair:
            bpy.ops.object.duplicate()
            targets = selected_meshes(context)
            for obj in targets:
                obj.name = f"{obj.name}_Repaired"
                obj.data = obj.data.copy()
        else:
            targets = source_objects

        repaired = 0
        for obj in targets:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            if self.merge_distance > 0 and bm.verts:
                bmesh.ops.remove_doubles(
                    bm, verts=list(bm.verts), dist=self.merge_distance
                )

            # Remove isolated vertices and wire/loose edges.
            loose_edges = [edge for edge in bm.edges if edge.is_wire]
            if loose_edges:
                bmesh.ops.delete(bm, geom=loose_edges, context="EDGES")
            loose_verts = [vert for vert in bm.verts if not vert.link_edges]
            if loose_verts:
                bmesh.ops.delete(bm, geom=loose_verts, context="VERTS")

            # Remove zero-area/near-zero-area faces and recalculate consistent outward normals.
            bm.faces.ensure_lookup_table()
            degenerate_faces = [face for face in bm.faces if face.calc_area() <= 1e-12]
            if degenerate_faces:
                bmesh.ops.delete(bm, geom=degenerate_faces, context="FACES")
            if bm.faces:
                bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))

            bm.to_mesh(obj.data)
            bm.free()
            obj.data.update()
            repaired += 1

        self.report(
            {"WARNING"} if self.duplicate_before_repair else {"INFO"},
            f"Processed {repaired} mesh(es). Inspect the result; some topology defects need manual repair.",
        )
        return {"FINISHED"}



class GAO_OT_repair_normals_shading(bpy.types.Operator):
    bl_idname = "gao.repair_normals_shading"
    bl_label = "Repair Normals & Shading"
    bl_description = "Create safe copies and repair face orientation and hard-surface shading"

    duplicate_before_repair: bpy.props.BoolProperty(
        name="Keep Original (Create Copy)",
        description="Duplicate selected meshes before changing normals or shading",
        default=True,
    )
    recalculate_normals: bpy.props.BoolProperty(
        name="Recalculate Outside",
        description="Make connected face normals consistent and orient them outward",
        default=True,
    )
    smooth_shading: bpy.props.BoolProperty(
        name="Enable Smooth Shading",
        description="Enable smooth shading on faces while retaining detected hard edges",
        default=False,
    )
    preserve_sharp_edges: bpy.props.BoolProperty(
        name="Detect Hard Edges",
        description="Mark edges sharper than the angle threshold as sharp",
        default=True,
    )
    sharp_angle: bpy.props.FloatProperty(
        name="Hard Edge Angle",
        description="Edges at or above this angle remain sharp",
        default=math.radians(30.0),
        min=0.0,
        max=math.pi,
        subtype="ANGLE",
    )
    weighted_normals: bpy.props.BoolProperty(
        name="Add Weighted Normal Modifier",
        description="Add a non-destructive weighted-normal modifier for suitable hard-surface meshes",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(selected_meshes(context))

    def execute(self, context):
        source_objects = selected_meshes(context)
        if self.duplicate_before_repair:
            bpy.ops.object.duplicate()
            targets = selected_meshes(context)
            for obj in targets:
                obj.name = f"{obj.name}_NormalsFixed"
                obj.data = obj.data.copy()
        else:
            targets = source_objects

        processed = 0
        for obj in targets:
            mesh = obj.data
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bm.normal_update()

            if self.recalculate_normals and bm.faces:
                bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))

            if self.preserve_sharp_edges:
                threshold = self.sharp_angle
                for edge in bm.edges:
                    if len(edge.link_faces) == 2:
                        try:
                            edge.smooth = edge.calc_face_angle(0.0) < threshold
                        except ValueError:
                            edge.smooth = False
                    elif len(edge.link_faces) != 2:
                        edge.smooth = False

            if self.smooth_shading:
                for face in bm.faces:
                    face.smooth = True

            bm.to_mesh(mesh)
            bm.free()
            mesh.update()

            if self.weighted_normals:
                modifier = next(
                    (m for m in obj.modifiers
                     if m.type == "WEIGHTED_NORMAL" and m.name == "GAO_WeightedNormal"),
                    None,
                )
                if modifier is None:
                    modifier = obj.modifiers.new(
                        name="GAO_WeightedNormal", type="WEIGHTED_NORMAL"
                    )
                if hasattr(modifier, "keep_sharp"):
                    modifier.keep_sharp = True
                if hasattr(modifier, "weight"):
                    modifier.weight = 50

            processed += 1

        self.report(
            {"INFO"},
            f"Processed {processed} mesh(es). Review the result, especially open or intentionally inverted surfaces.",
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
        layout.separator()
        layout.label(text="Mesh diagnostics & repair")
        layout.operator("gao.mesh_health_report", icon="VIEWZOOM")
        layout.operator("gao.repair_mesh", icon="MODIFIER")
        layout.operator("gao.repair_normals_shading", icon="NORMALS_FACE")
        layout.operator("gao.apply_transforms", icon="OBJECT_ORIGIN")
        layout.operator("gao.make_decimated_copy", icon="MOD_DECIM")
        layout.operator("gao.export_selected_fbx", icon="EXPORT")


CLASSES = (
    GAO_OT_report,
    GAO_OT_report_textures,
    GAO_OT_mesh_health_report,
    GAO_OT_repair_mesh,
    GAO_OT_repair_normals_shading,
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
