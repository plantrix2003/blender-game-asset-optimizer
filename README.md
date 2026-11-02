# Blender Game Asset Optimizer

A small open-source Blender add-on for inspecting and preparing selected meshes for real-time/game workflows.

## Features
- Report selected mesh polygon counts and dimensions to the system console.
- Report unique image textures used by selected mesh materials, including dimensions and estimated uncompressed RGBA8 size.
- Inspect mesh topology for non-manifold edges, boundaries, wire edges, loose vertices, and degenerate faces.
- Repair a duplicate by welding nearby vertices, removing loose geometry and zero-area faces, and recalculating face normals.
- Repair normals and hard-surface shading on a safe copy, with optional smooth shading, sharp-edge detection by angle, and a weighted-normal modifier.
- Apply location, rotation and scale transforms.
- Create decimated LOD copies while preserving the original objects.
- Export selected objects to FBX.

> Early-stage project. Features have not yet been validated across Blender versions or production pipelines. Test on duplicate files before production use. No usage, download or adoption figures are claimed.

## Compatibility
Blender 3.6+ is the initial target. Blender-specific behavior must be tested in the target release.

## Install
1. Download this repository as a ZIP.
2. In Blender, go to **Edit → Preferences → Add-ons → Install from Disk**.
3. Select the ZIP and enable **Game Asset Optimizer**.
4. In the 3D Viewport press `N`, then open the **Game Asset** tab.

## Use
Select one or more mesh objects and use the panel actions. **Repair Normals & Shading** creates a copy by default, can recalculate face orientation, optionally enables smooth shading, marks edges sharp using the chosen angle, and can add a Weighted Normal modifier. Keep smooth shading and weighted normals optional for hard-surface assets. The decimation action duplicates the selected objects and adds a Decimate modifier to the copies. FBX export uses Blender's FBX exporter.

## Roadmap
- Texture resolution and image-size reporting.
- Batch export presets.
- Configurable LOD and game-engine budgets.
- Blender background tests and CI.

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md). Please open an issue before large changes.

## License
MIT. See [LICENSE](LICENSE).
