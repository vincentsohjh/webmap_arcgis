import osmnx as ox
import shapely.geometry
import numpy as np
import json
import os
from pygltflib import GLTF2, Scene, Node, Mesh, Buffer, BufferView, Accessor, Asset, Primitive, Material, PbrMetallicRoughness
import trimesh

def extract_3d_models_from_osm(place_name, output_dir="output_3dtiles"):
    """
    Extract 3D building models from OSM for the given place and convert them to 3D Tiles format.
    Also generates a full Singapore model in one OBJ file.
    
    Args:
        place_name (str): The place name or query to download OSM data.
        output_dir (str): Directory to save the 3D Tiles output and OBJ file.
        
    Returns:
        tuple: (str) Path to the generated 3D Tiles tileset.json file,
               (str) Path to the generated full OBJ model file.
    """
    # Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Download building footprints with height data
    tags = {"building": True}
    print(f"Downloading building footprints for {place_name}...")
    gdf = ox.features_from_place(place_name, tags)
    
    # Filter buildings with height or levels attribute
    def get_height(row):
        if 'height' in row and row['height'] is not None:
            try:
                # height might be in meters or string like '10 m'
                h = float(str(row['height']).replace(' m','').strip())
                return h
            except:
                return None
        elif 'building:levels' in row and row['building:levels'] is not None:
            try:
                levels = float(str(row['building:levels']).strip())
                return levels * 3  # approx 3 meters per level
            except:
                return None
        else:
            return None
    
    gdf['height_m'] = gdf.apply(get_height, axis=1)
    gdf = gdf[gdf['height_m'].notnull()]
    
    if gdf.empty:
        raise ValueError("No buildings with height information found in the area.")
    
    print(f"Found {len(gdf)} buildings with height data.")
    
    # For simplicity, create a glTF file for each building as an extruded polygon
    gltf_files = []
    # For merging all buildings into one mesh
    merged_meshes = []
    
    for idx, row in gdf.iterrows():
        footprint = row.geometry
        height = row['height_m']
        if not isinstance(footprint, shapely.geometry.Polygon):
            # skip non-polygon geometries
            continue
        
        gltf = create_extruded_building_gltf(footprint, height)
        gltf_filename = os.path.join(output_dir, f"building_{idx}.gltf")
        gltf.save(gltf_filename)
        gltf_files.append(gltf_filename)
        
        # Create trimesh mesh for merging
        mesh = create_trimesh_extruded_building(footprint, height)
        merged_meshes.append(mesh)
    
    # Merge all building meshes into one
    full_mesh = trimesh.util.concatenate(merged_meshes)
    obj_path = os.path.join(output_dir, "singapore_full_model.obj")
    full_mesh.export(obj_path)
    print(f"Full Singapore model exported as OBJ at {obj_path}")
    
    # Create a basic tileset.json referencing the glTF files as individual tiles
    tileset = create_basic_tileset_json(gltf_files)
    tileset_path = os.path.join(output_dir, "tileset.json")
    with open(tileset_path, "w") as f:
        json.dump(tileset, f, indent=2)
    
    print(f"3D Tiles generated at {tileset_path}")
    return tileset_path, obj_path

def create_trimesh_extruded_building(footprint, height):
    """
    Create a trimesh mesh of an extruded polygon footprint.
    Args:
        footprint (shapely.geometry.Polygon): 2D footprint polygon.
        height (float): extrusion height in meters.
    Returns:
        trimesh.Trimesh: extruded mesh.
    """
    exterior_coords = np.array(footprint.exterior.coords)
    # Create vertices for bottom and top
    bottom = np.column_stack((exterior_coords, np.zeros(len(exterior_coords))))
    top = np.column_stack((exterior_coords, np.full(len(exterior_coords), height)))
    
    vertices = np.vstack((bottom, top))
    
    n = len(exterior_coords)
    faces = []
    # Bottom face (triangle fan)
    for i in range(1, n-1):
        faces.append([0, i, i+1])
    # Top face (triangle fan)
    for i in range(1, n-1):
        faces.append([n, n+i+1, n+i])
    # Side faces (quads split into two triangles)
    for i in range(n-1):
        a = i
        b = i+1
        c = n + b
        d = n + a
        faces.append([a, b, c])
        faces.append([a, c, d])
    
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    return mesh

def create_extruded_building_gltf(footprint, height):
    """
    Create a simple glTF model of an extruded polygon footprint.
    Args:
        footprint (shapely.geometry.Polygon): 2D footprint polygon.
        height (float): extrusion height in meters.
    Returns:
        GLTF2: glTF model object.
    """
    # Extract exterior coords
    exterior_coords = np.array(footprint.exterior.coords)
    # Create vertices for bottom and top
    vertices = []
    for x, y in exterior_coords:
        vertices.append([x, y, 0])       # bottom
    for x, y in exterior_coords:
        vertices.append([x, y, height])  # top
    
    # Create faces (triangles) for sides and top/bottom
    # Indices for bottom and top rings
    n = len(exterior_coords)
    # Bottom face (triangle fan)
    bottom_faces = []
    for i in range(1, n-1):
        bottom_faces.append([0, i, i+1])
    # Top face (triangle fan)
    top_faces = []
    for i in range(1, n-1):
        top_faces.append([n, n+i+1, n+i])
    # Side faces (quads split into two triangles)
    side_faces = []
    for i in range(n-1):
        a = i
        b = i+1
        c = n + b
        d = n + a
        side_faces.append([a, b, c])
        side_faces.append([a, c, d])
    
    # Flatten faces
    faces = bottom_faces + top_faces + side_faces
    
    # Convert vertices and faces to glTF buffers
    vertices_flat = np.array(vertices, dtype=np.float32).flatten()
    indices_flat = np.array(faces, dtype=np.uint16).flatten()
    
    # Create glTF structure using pygltflib
    gltf = GLTF2()
    gltf.asset = Asset(version="2.0")
    
    # Buffer data
    vertex_bytes = vertices_flat.tobytes()
    index_bytes = indices_flat.tobytes()
    buffer_data = vertex_bytes + index_bytes
    
    buffer = Buffer(byteLength=len(buffer_data))
    gltf.buffers.append(buffer)
    
    # BufferViews
    vertex_buffer_view = BufferView(buffer=0, byteOffset=0, byteLength=len(vertex_bytes), target=34962)  # ARRAY_BUFFER
    index_buffer_view = BufferView(buffer=0, byteOffset=len(vertex_bytes), byteLength=len(index_bytes), target=34963)  # ELEMENT_ARRAY_BUFFER
    gltf.bufferViews.extend([vertex_buffer_view, index_buffer_view])
    
    # Accessors
    vertex_accessor = Accessor(bufferView=0, byteOffset=0, componentType=5126, count=len(vertices), type="VEC3", max=[float(np.max(vertices_flat[0::3])), float(np.max(vertices_flat[1::3])), float(np.max(vertices_flat[2::3]))], min=[float(np.min(vertices_flat[0::3])), float(np.min(vertices_flat[1::3])), float(np.min(vertices_flat[2::3]))])
    index_accessor = Accessor(bufferView=1, byteOffset=0, componentType=5123, count=len(indices_flat), type="SCALAR")
    gltf.accessors.extend([vertex_accessor, index_accessor])
    
    # Mesh primitive
    primitive = Primitive(attributes={"POSITION": 0}, indices=1)
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
    gltf.set_binary_blob(buffer_data)
    
    return gltf

def create_basic_tileset_json(gltf_files):
    """
    Create a basic 3D Tiles tileset.json referencing the given glTF files as individual tiles.
    Args:
        gltf_files (list of str): List of glTF file paths.
    Returns:
        dict: tileset JSON structure.
    """
    root = {
        "asset": {
            "version": "1.0"
        },
        "geometricError": 500,
        "root": {
            "boundingVolume": {
                "region": [1.808, 0.021, 1.815, 0.026, 0, 1000]  # Singapore bounding box in radians
            },
            "geometricError": 0,
            "refine": "ADD",
            "children": []
        }
    }
    
    for i, gltf_path in enumerate(gltf_files):
        tile = {
            "boundingVolume": {
                "region": [1.808, 0.021, 1.815, 0.026, 0, 1000]  # Singapore bounding box in radians, should be updated per building
            },
            "geometricError": 0,
            "content": {
                "uri": os.path.basename(gltf_path)
            }
        }
        root["root"]["children"].append(tile)
    
    return root

if __name__ == "__main__":
    # Example usage
    place = "Singapore"
    extract_3d_models_from_osm(place)
