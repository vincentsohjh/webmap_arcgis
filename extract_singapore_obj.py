import osmnx as ox
import shapely.geometry
import numpy as np
import os
import trimesh
import json
from datetime import datetime
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

def extract_singapore_obj(output_dir="output_obj", csv_path="HDBPropertyInformation_geocoded.csv"):
    """
    Extract 3D building models from OSM for Singapore and export as a single OBJ file.
    Also export all building footprints as GeoJSON including those without height data.
    Also export buildings as CityJSON including all attributes.
    Update building heights based on CSV max_floor_lvl data for intersecting buildings.
    
    Args:
        output_dir (str): Directory to save the OBJ, GeoJSON, and CityJSON files.
        csv_path (str): Path to the CSV file with max_floor_lvl, longitude, latitude.
        
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
    
    # Read CSV and create GeoDataFrame of points
    print(f"Reading CSV data from {csv_path}...")
    df_csv = pd.read_csv(csv_path)
    # Create geometry column from longitude and latitude
    geometry = [Point(xy) for xy in zip(df_csv['longitude'], df_csv['latitude'])]
    gdf_csv = gpd.GeoDataFrame(df_csv, geometry=geometry, crs="EPSG:4326")
    
    # Project both GeoDataFrames to Singapore TM (EPSG:3414) for spatial operations
    gdf = gdf.to_crs(epsg=3414)
    gdf_csv = gdf_csv.to_crs(epsg=3414)
    
    # Spatial join: find buildings intersecting with CSV points
    print("Performing spatial join to update building heights from CSV data...")
    joined = gdf.sjoin(gdf_csv, how="left", predicate="intersects")
    
    # Update height_m using max_floor_lvl from CSV if available
    def get_height(row):
        MIN_HEIGHT = 3.0  # minimum height in meters if no data available
        if pd.notnull(row.get('max_floor_lvl')):
            try:
                levels = float(row['max_floor_lvl'])
                return levels * 3  # approx 3 meters per level
            except:
                pass
        if 'height' in row and pd.notnull(row['height']):
            try:
                h = float(str(row['height']).replace(' m','').strip())
                return h
            except:
                return MIN_HEIGHT
        elif 'building:levels' in row and pd.notnull(row['building:levels']):
            try:
                levels = float(str(row['building:levels']).strip())
                return levels * 3
            except:
                return MIN_HEIGHT
        else:
            return MIN_HEIGHT
    
    joined['height_m'] = joined.apply(get_height, axis=1)
    
    # Remove duplicates after join, keep first occurrence
    joined = joined[~joined.index.duplicated(keep='first')]
    
    # Save all building footprints as GeoJSON (including those without height)
    geojson_filename = f"singapore_building_footprints_{timestamp}.geojson"
    geojson_path = os.path.join(output_dir, geojson_filename)
    joined.to_file(geojson_path, driver="GeoJSON")
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
    for idx, row in joined.iterrows():
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
    for idx, row in joined.iterrows():
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
