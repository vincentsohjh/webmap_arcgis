import osmnx as ox
import shapely.geometry
import numpy as np
import os
import trimesh
import json
from datetime import datetime

def extract_singapore_obj(output_dir="output_obj"):
    """
    Extract 3D building models from OSM for Singapore and export as a single OBJ file.
    Also export all building footprints as GeoJSON including those without height data.
    Also export buildings as CityJSON including all attributes.
    
    Args:
        output_dir (str): Directory to save the OBJ, GeoJSON, and CityJSON files.
        
    Returns:
        tuple: (str) Path to the generated OBJ file,
               (str) Path to the generated GeoJSON file,
               (str) Path to the generated CityJSON file.
    """
    # Create output directory
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    place_name = "Singapore"
    tags = {"building": True}
    print(f"Downloading building footprints for {place_name}...")
    gdf = ox.features_from_place(place_name, tags)
    
    # Save all building footprints as GeoJSON (including those without height)
    geojson_filename = f"singapore_building_footprints_{timestamp}.geojson"
    geojson_path = os.path.join(output_dir, geojson_filename)
    gdf.to_file(geojson_path, driver="GeoJSON")
    print(f"All building footprints exported as GeoJSON at {geojson_path}")
    
    # Export CityJSON
    cityjson_filename = f"singapore_buildings_{timestamp}.city.json"
    cityjson_path = os.path.join(output_dir, cityjson_filename)
    cityjson_data = {
        "type": "CityJSON",
        "version": "1.0",
        "CityObjects": {},
        "vertices": [],
        "transform": {
            "scale": [1, 1, 1],
            "translate": [0, 0, 0]
        }
    }
    
    vertex_index = 0
    vertices = []
    for idx, row in gdf.iterrows():
        geom = row.geometry
        if not isinstance(geom, shapely.geometry.Polygon):
            continue
        coords = list(geom.exterior.coords)
        # Add vertices
        vert_indices = []
        for coord in coords:
            vertices.append([coord[0], coord[1], 0])
            vert_indices.append(vertex_index)
            vertex_index += 1
        # Create CityObject
        cityjson_data["CityObjects"][str(idx)] = {
            "type": "Building",
            "geometry": [{
                "type": "Solid",
                "boundaries": [[[vert_indices]]]
            }],
            "attributes": row.drop("geometry").to_dict()
        }
    cityjson_data["vertices"] = vertices
    
    with open(cityjson_path, "w") as f:
        json.dump(cityjson_data, f, indent=2)
    print(f"All building footprints exported as CityJSON at {cityjson_path}")
    
    # Project to Singapore TM (EPSG:3414) for proper metric coordinates
    gdf = gdf.to_crs(epsg=3414)
    
    # Filter buildings with height or levels attribute
    def get_height(row):
        MIN_HEIGHT = 3.0  # minimum height in meters if no data available
        if 'height' in row and row['height'] is not None:
            try:
                h = float(str(row['height']).replace(' m','').strip())
                return h
            except:
                return MIN_HEIGHT
        elif 'building:levels' in row and row['building:levels'] is not None:
            try:
                levels = float(str(row['building:levels']).strip())
    
                return levels * 3  # approx 3 meters per level
            except:
                return MIN_HEIGHT
        else:
            return MIN_HEIGHT
    
    gdf['height_m'] = gdf.apply(get_height, axis=1)
    # Do not filter out buildings without height, assign minimum height instead
    # gdf = gdf[gdf['height_m'].notnull()]
    
    if gdf.empty:
        raise ValueError("No buildings found in the area.")
    
    print(f"Found {len(gdf)} buildings with height data or assigned minimum height.")
    
    def create_trimesh_extruded_building(footprint, height):
        exterior_coords = np.array(footprint.exterior.coords)
        bottom = np.column_stack((exterior_coords, np.zeros(len(exterior_coords))))
        top = np.column_stack((exterior_coords, np.full(len(exterior_coords), height)))
        vertices = np.vstack((bottom, top))
        n = len(exterior_coords)
        faces = []
        for i in range(1, n-1):
            faces.append([0, i, i+1])
        for i in range(1, n-1):
            faces.append([n, n+i+1, n+i])
        for i in range(n-1):
            a = i
            b = i+1
            c = n + b
            d = n + a
            faces.append([a, b, c])
            faces.append([a, c, d])
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
        return mesh
    
    merged_meshes = []
    for idx, row in gdf.iterrows():
        footprint = row.geometry
        height = row['height_m']
        if not isinstance(footprint, shapely.geometry.Polygon):
            continue
        mesh = create_trimesh_extruded_building(footprint, height)
        merged_meshes.append(mesh)
    
    full_mesh = trimesh.util.concatenate(merged_meshes)
    
    # Debug prints
    print(f"Final merged mesh has {len(full_mesh.vertices)} vertices and {len(full_mesh.faces)} faces.")
    if len(full_mesh.vertices) == 0 or len(full_mesh.faces) == 0:
        print("Warning: The merged mesh is empty. No geometry to export.")
    
    obj_filename = f"singapore_full_model_{timestamp}.obj"
    obj_path = os.path.join(output_dir, obj_filename)
    full_mesh.export(obj_path)
    print(f"Full Singapore model exported as OBJ at {obj_path}")
    return obj_path, geojson_path, cityjson_path

if __name__ == "__main__":
    extract_singapore_obj()
