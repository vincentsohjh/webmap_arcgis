"""
Python script to convert CityJSON files to 3D Tiles format.

This script:
- Loads a CityJSON file.
- Extracts building geometries.
- Converts geometries to glTF files using pygltflib.
- Generates a tileset.json referencing the glTF files as tiles.

Dependencies:
- numpy
- pygltflib

Install dependencies with:
pip install numpy pygltflib

Usage:
python cityjson_to_3dtiles.py input_cityjson.json output_3dtiles_folder

Note:
This is a basic implementation and may need enhancements for complex CityJSON files.
"""

import os
import sys
import json
import numpy as np
from pygltflib import GLTF2, Scene, Node, Mesh, Buffer, BufferView, Accessor, Asset, Primitive, Material

def create_gltf_from_mesh(vertices, indices, output_path):
    """
    Create a simple glTF file from vertices and triangle indices.
    vertices: Nx3 numpy array
    indices: Mx3 numpy array (triangles)
    output_path: path to save the glTF file
    """
    gltf = GLTF2()
    gltf.asset = Asset(version="2.0")

    # Flatten vertex data
    vertex_data = vertices.astype(np.float32).tobytes()
    index_data = indices.astype(np.uint16).tobytes()

    # Create buffer
    buffer = Buffer()
    buffer.byteLength = len(vertex_data) + len(index_data)
    gltf.buffers.append(buffer)

    # BufferViews
    vertex_buffer_view = BufferView(buffer=0, byteOffset=0, byteLength=len(vertex_data), target=34962)  # ARRAY_BUFFER
    index_buffer_view = BufferView(buffer=0, byteOffset=len(vertex_data), byteLength=len(index_data), target=34963)  # ELEMENT_ARRAY_BUFFER
    gltf.bufferViews.extend([vertex_buffer_view, index_buffer_view])

    # Accessors
    # Positions
    accessor_positions = Accessor(bufferView=0, byteOffset=0, componentType=5126, count=len(vertices), type="VEC3",
                                  min=[float(np.min(vertices[:,0])), float(np.min(vertices[:,1])), float(np.min(vertices[:,2]))],
                                  max=[float(np.max(vertices[:,0])), float(np.max(vertices[:,1])), float(np.max(vertices[:,2]))])
    # Indices
    accessor_indices = Accessor(bufferView=1, byteOffset=0, componentType=5123, count=len(indices)*3, type="SCALAR")

    gltf.accessors.extend([accessor_positions, accessor_indices])

    # Mesh primitive
    primitive = Primitive(attributes={"POSITION":0}, indices=1, mode=4)  # TRIANGLES

    # Material (default)
    material = Material()
    gltf.materials.append(material)
    primitive.material = 0

    mesh = Mesh(primitives=[primitive])
    gltf.meshes.append(mesh)

    # Node
    node = Node(mesh=0)
    gltf.nodes.append(node)

    # Scene
    scene = Scene(nodes=[0])
    gltf.scenes.append(scene)
    gltf.scene = 0

    # Set buffer data
    gltf.set_binary_blob(vertex_data + index_data)

    # Save glTF
    gltf.save(output_path)

def parse_cityjson_geometry(cityjson):
    """
    Parse CityJSON geometries into a list of (vertices, indices) tuples.
    This function assumes simple geometry types (e.g. MultiSurface or Solid).
    """
    vertices_list = []
    indices_list = []

    vertices_global = cityjson.get("vertices", [])
    vertices_global = np.array(vertices_global, dtype=np.float32)

    city_objects = cityjson.get("CityObjects", {})

    for obj_id, obj in city_objects.items():
        geom = obj.get("geometry", [])
        for g in geom:
            # We handle only 'Solid' or 'MultiSurface' types here
            geom_type = g.get("type")
            boundaries = g.get("boundaries", [])

            if geom_type == "Solid":
                # Solid boundaries: list of shells, each shell is list of surfaces
                for shell in boundaries:
                    for surface in shell:
                        # surface is list of rings, first ring is exterior
                        exterior_ring = surface[0]
                        # Convert vertex indices to coordinates
                        verts = vertices_global[exterior_ring]
                        # Triangulate polygon (assuming convex polygon)
                        # Simple fan triangulation
                        indices = []
                        for i in range(1, len(exterior_ring)-1):
                            indices.append([0, i, i+1])
                        vertices_list.append(verts)
                        indices_list.append(np.array(indices, dtype=np.uint16))
            elif geom_type == "MultiSurface":
                # MultiSurface boundaries: list of surfaces
                for surface in boundaries:
                    # surface is list of rings, first ring is exterior
                    exterior_ring = surface[0]
                    verts = vertices_global[exterior_ring]
                    indices = []
                    for i in range(1, len(exterior_ring)-1):
                        indices.append([0, i, i+1])
                    vertices_list.append(verts)
                    indices_list.append(np.array(indices, dtype=np.uint16))
            else:
                # Unsupported geometry type
                continue

    return vertices_list, indices_list

def generate_tileset_json(tiles, output_folder):
    """
    Generate a tileset.json file for 3D Tiles referencing the glTF tiles.
    tiles: list of dicts with keys: 'gltf', 'boundingVolume' (box)
    output_folder: folder to save tileset.json
    """
    tileset = {
        "asset": {
            "version": "1.0"
        },
        "geometricError": 500,
        "root": {
            "boundingVolume": {
                "box": [0,0,0, 1000,0,0, 0,1000,0, 0,0,1000]  # Placeholder box
            },
            "geometricError": 250,
            "refine": "ADD",
            "children": []
        }
    }

    for tile in tiles:
        tile_entry = {
            "boundingVolume": {
                "box": tile["boundingVolume"]
            },
            "geometricError": 0,
            "content": {
                "uri": tile["gltf"]
            }
        }
        tileset["root"]["children"].append(tile_entry)

    tileset_path = os.path.join(output_folder, "tileset.json")
    with open(tileset_path, "w") as f:
        json.dump(tileset, f, indent=2)

import math

def main():
    if len(sys.argv) != 3:
        print("Usage: python cityjson_to_3dtiles.py input_cityjson.json output_3dtiles_folder")
        sys.exit(1)

    input_path = sys.argv[1]
    output_folder = sys.argv[2]

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    with open(input_path, "r") as f:
        cityjson = json.load(f)

    vertices_list, indices_list = parse_cityjson_geometry(cityjson)

    # Singapore bounding box in meters (approximate, adjust if needed)
    # Assuming CityJSON coordinates are in meters in a projected CRS
    min_x, min_y = 0, 0
    max_x, max_y = 10000, 10000  # Example 10km x 10km area covering Singapore approx

    # Define grid size (number of tiles in x and y)
    grid_x, grid_y = 7, 7  # Approx 49 tiles, close to 50 as requested

    tile_size_x = (max_x - min_x) / grid_x
    tile_size_y = (max_y - min_y) / grid_y

    # Assign buildings to tiles based on centroid
    tiles_dict = {}  # key: (ix, iy), value: list of (verts, inds)

    for verts, inds in zip(vertices_list, indices_list):
        centroid = verts.mean(axis=0)
        ix = int(math.floor((centroid[0] - min_x) / tile_size_x))
        iy = int(math.floor((centroid[1] - min_y) / tile_size_y))
        # Clamp indices
        ix = max(0, min(grid_x -1, ix))
        iy = max(0, min(grid_y -1, iy))
        key = (ix, iy)
        if key not in tiles_dict:
            tiles_dict[key] = []
        tiles_dict[key].append((verts, inds))

    tiles = []
    for (ix, iy), geom_list in tiles_dict.items():
        # Merge geometries in geom_list
        merged_verts = []
        merged_inds = []
        vert_offset = 0
        for verts, inds in geom_list:
            merged_verts.append(verts)
            merged_inds.append(inds + vert_offset)
            vert_offset += len(verts)
        merged_verts = np.vstack(merged_verts)
        merged_inds = np.vstack(merged_inds)

        gltf_filename = f"tile_{ix}_{iy}.gltf"
        gltf_path = os.path.join(output_folder, gltf_filename)
        create_gltf_from_mesh(merged_verts, merged_inds, gltf_path)

        # Bounding box for tile
        min_xyz = merged_verts.min(axis=0)
        max_xyz = merged_verts.max(axis=0)
        center = ((min_xyz + max_xyz) / 2).tolist()
        half_sizes = ((max_xyz - min_xyz) / 2).tolist()
        bounding_box = [
            center[0], center[1], center[2],
            half_sizes[0], 0, 0,
            0, half_sizes[1], 0,
            0, 0, half_sizes[2]
        ]

        tiles.append({
            "gltf": gltf_filename,
            "boundingVolume": bounding_box
        })

    generate_tileset_json(tiles, output_folder)
    print(f"3D Tiles generated in folder: {output_folder}")

if __name__ == "__main__":
    main()
