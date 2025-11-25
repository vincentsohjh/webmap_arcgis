import pandas as pd
from mapbox import Geocoder
import time
import os
import argparse

def geocode_csv_with_mapbox_sdk(input_csv, output_csv, access_token):
    """
    Geocode addresses in a CSV file using Mapbox Python SDK Geocoder.
    Assumes CSV has 'blk_no' and 'street' columns.
    Saves results with 'longitude' and 'latitude' columns to output_csv.
    """
    df = pd.read_csv(input_csv)
    geocoder = Geocoder(access_token=access_token)

    df['longitude'] = None
    df['latitude'] = None

    for idx, row in df.iterrows():
        blk_no = str(row['blk_no']).strip()
        street = str(row['street']).strip()
        address = f"{blk_no} {street}, Singapore"

        response = geocoder.forward(address, limit=1)
        if response.status_code == 200:
            data = response.json()
            if data['features']:
                coords = data['features'][0]['center']
                df.at[idx, 'longitude'] = coords[0]
                df.at[idx, 'latitude'] = coords[1]
                print(f"Geocoded: {address} -> ({coords[1]}, {coords[0]})")
            else:
                print(f"No results for: {address}")
        else:
            print(f"Error geocoding {address}: {response.status_code}")

        time.sleep(0.1)  # To avoid rate limits

    df.to_csv(output_csv, index=False)
    print(f"Geocoding complete. Results saved to {output_csv}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Geocode CSV addresses using Mapbox Python SDK")
    parser.add_argument("--input_csv", default="HDBPropertyInformation.csv", help="Input CSV file path (default: HDBPropertyInformation.csv)")
    parser.add_argument("--output_csv", default="HDBPropertyInformation_geocoded.csv", help="Output CSV file path (default: HDBPropertyInformation_geocoded.csv)")
    parser.add_argument("--mapbox_token", default="pk.eyJ1IjoiZ3NyMTciLCJhIjoiY21ia3hudTA1MGx1bzJqcXY5bGc3ZXI1ZCJ9.XahvXYmDAts7i3YVd2KoQg", help="Mapbox Access Token (default: from MAPBOX_ACCESS_TOKEN env variable)")

    args = parser.parse_args()

    if not args.mapbox_token:
        raise ValueError("Mapbox Access Token must be provided via --mapbox_token argument or MAPBOX_ACCESS_TOKEN environment variable")

    geocode_csv_with_mapbox_sdk(args.input_csv, args.output_csv, args.mapbox_token)
