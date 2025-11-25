"""
Python script to convert CityJSON files to ArcGIS Scene Layer Package (SLPK).

This script:
- Loads a CityJSON file.
- Extracts building geometries.
- Converts geometries to glTF files using pygltflib.
- Generates a 3D Tiles tileset.json referencing the glTF files as tiles.
- Packages the 3D Tiles folder into an SLPK archive with required Esri metadata.

Dependencies:
- numpy
- pygltflib
- zipfile (standard library)
- json
- os
- sys

Install dependencies with:
pip install numpy pygltflib

Usage:
python cityjson_to_slpk.py input_cityjson.json output_slpk_folder output_slpk_filename.slpk

Note:
This is a basic implementation and may need enhancements for complex CityJSON files or full Esri SLPK compliance.
"""

import os
import sys
import json
import math
import numpy as np
from pygltflib import GLTF2, Scene, Node, Mesh, Buffer, BufferView, Accessor, Asset, Primitive, Material
import zipfile
import tempfile
import shutil

def create_gltf_from_mesh(vertices, indices, output_path):
    """
    Create a simple glTF file from vertices and triangle indices.
    vertices: Nx3 numpy array
    indices: Mx3 numpy array (triangles)
    output_path: path to save the glTF file
    """
    gltf = GLTF2()
    gltf.asset = Asset(version="2.0")

    vertex_data = vertices.astype(np.float32).tobytes()
    index_data = indices.astype(np.uint16).tobytes()

    buffer = Buffer()
    buffer.byteLength = len(vertex_data) + len(index_data)
    gltf.buffers.append(buffer)

    vertex_buffer_view = BufferView(buffer=0, byteOffset=0, byteLength=len(vertex_data), target=34962)  # ARRAY_BUFFER
    index_buffer_view = BufferView(buffer=0, byteOffset=len(vertex_data), byteLength=len(index_data), target=34963)  # ELEMENT_ARRAY_BUFFER
    gltf.bufferViews.extend([vertex_buffer_view, index_buffer_view])

    accessor_positions = Accessor(bufferView=0, byteOffset=0, componentType=5126, count=len(vertices), type="VEC3",
                                  min=[float(np.min(vertices[:,0])), float(np.min(vertices[:,1])), float(np.min(vertices[:,2]))],
                                  max=[float(np.max(vertices[:,0])), float(np.max(vertices[:,1])), float(np.max(vertices[:,2]))])
    accessor_indices = Accessor(bufferView=1, byteOffset=0, componentType=5123, count=len(indices)*3, type="SCALAR")

    gltf.accessors.extend([accessor_positions, accessor_indices])

    primitive = Primitive(attributes={"POSITION":0}, indices=1, mode=4)  # TRIANGLES

    material = Material()
    gltf.materials.append(material)
    primitive.material = 0

    mesh = Mesh(primitives=[primitive])
    gltf.meshes.append(mesh)

    node = Node(mesh=0)
    gltf.nodes.append(node)

    scene = Scene(nodes=[0])
    gltf.scenes.append(scene)
    gltf.scene = 0

    gltf.set_binary_blob(vertex_data + index_data)

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
            geom_type = g.get("type")
            boundaries = g.get("boundaries", [])

            if geom_type == "Solid":
                for shell in boundaries:
                    for surface in shell:
                        exterior_ring = surface[0]
                        verts = vertices_global[exterior_ring]
                        indices = []
                        for i in range(1, len(exterior_ring)-1):
                            indices.append([0, i, i+1])
                        vertices_list.append(verts)
                        indices_list.append(np.array(indices, dtype=np.uint16))
            elif geom_type == "MultiSurface":
                for surface in boundaries:
                    exterior_ring = surface[0]
                    verts = vertices_global[exterior_ring]
                    indices = []
                    for i in range(1, len(exterior_ring)-1):
                        indices.append([0, i, i+1])
                    vertices_list.append(verts)
                    indices_list.append(np.array(indices, dtype=np.uint16))
            else:
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
                "box": [0,0,0, 1000,0,0, 0,1000,0, 0,0,1000]
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

def create_slpk_metadata(output_folder):
    """
    Create minimal Esri SLPK metadata files required for ArcGIS.
    """
    # Create scene layer package info json
    slpk_info = {
        "layerType": "Scene Layer",
        "layerTypeName": "3D Object Scene Layer",
        "version": "1.0",
        "layerDefinition": {
            "type": "3DObject",
            "geometryType": "esriGeometryPolygon",
            "hasZ": True,
            "hasM": False,
            "drawingInfo": {
                "renderer": {
                    "type": "simple",
                    "symbol": {
                        "type": "esri3DObject",
                        "symbolLayers": [
                            {
                                "type": "object",
                                "resource": "3dtiles/tileset.json"
                            }
                        ]
                    }
                }
            }
        }
    }
    with open(os.path.join(output_folder, "layer.json"), "w") as f:
        json.dump(slpk_info, f, indent=2)

def package_slpk(source_folder, slpk_path):
    """
    Package the source_folder contents into a .slpk zip archive.
    """
    with zipfile.ZipFile(slpk_path, 'w', zipfile.ZIP_DEFLATED) as slpk_zip:
        for root, dirs, files in os.walk(source_folder):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, source_folder)
                slpk_zip.write(abs_path, rel_path)

def main():
    if len(sys.argv) != 4:
        print("Usage: python cityjson_to_slpk.py input_cityjson.json output_slpk_folder output_slpk_filename.slpk")
        sys.exit(1)

    input_path = sys.argv[1]
    output_folder = sys.argv[2]
    slpk_filename = sys.argv[3]

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    with open(input_path, "r", encoding="utf-8") as f:
        cityjson = json.load(f)

    vertices_list, indices_list = parse_cityjson_geometry(cityjson)

    # Define bounding box and grid for tiling (example values)
    min_x, min_y = 0, 0
    max_x, max_y = 10000, 10000
    grid_x, grid_y = 7, 7

    tile_size_x = (max_x - min_x) / grid_x
    tile_size_y = (max_y - min_y) / grid_y

    tiles_dict = {}

    for verts, inds in zip(vertices_list, indices_list):
        centroid = verts.mean(axis=0)
        ix = int(math.floor((centroid[0] - min_x) / tile_size_x))
        iy = int(math.floor((centroid[1] - min_y) / tile_size_y))
        ix = max(0, min(grid_x -1, ix))
        iy = max(0, min(grid_y -1, iy))
        key = (ix, iy)
        if key not in tiles_dict:
            tiles_dict[key] = []
        tiles_dict[key].append((verts, inds))

    tiles_folder = os.path.join(output_folder, "3dtiles")
    if not os.path.exists(tiles_folder):
        os.makedirs(tiles_folder)

    tiles = []
    for (ix, iy), geom_list in tiles_dict.items():
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
        gltf_path = os.path.join(tiles_folder, gltf_filename)
        create_gltf_from_mesh(merged_verts, merged_inds, gltf_path)

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

    generate_tileset_json(tiles, tiles_folder)
    create_slpk_metadata(output_folder)

    slpk_path = os.path.join(output_folder, slpk_filename)
    package_slpk(output_folder, slpk_path)

    print(f"SLPK package created at: {slpk_path}")

if __name__ == "__main__":
    main()
