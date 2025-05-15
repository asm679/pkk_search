import requests
import json

def get_features_in_bbox(xmin, ymin, xmax, ymax, layer_id=21, wkid=102100):
    query_url = f"https://pkk.rosreestr.ru/arcgis/rest/services/PKK6/CadastreSelected/MapServer/{layer_id}/query"
    
    params = {
        "f": "json",
        "returnGeometry": "true", # Set to false if geometry is not needed
        "spatialRel": "esriSpatialRelIntersects",
        "geometry": json.dumps({
            "xmin": xmin,
            "ymin": ymin,
            "xmax": xmax,
            "ymax": ymax,
            "spatialReference": {"wkid": wkid}
        }),
        "geometryType": "esriGeometryEnvelope",
        "inSR": wkid,
        "outFields": "*", # Request all attribute fields
        "outSR": wkid
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        print(f"Querying layer {layer_id} in bbox: ({xmin},{ymin}),({xmax},{ymax}) at {query_url}")
        # Добавляем verify=False и отключаем предупреждения
        requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
        response = requests.post(query_url, data=params, headers=headers, timeout=60, verify=False) # Using POST as params can be long
        response.raise_for_status() # Check for HTTP errors
        data = response.json()
        print(f"Query response status: {response.status_code}")
        return data

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        if response is not None:
            print(f"Response content: {response.text}")
        return None
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON: {e}")
        if response is not None and response.text:
            print(f"Non-JSON response: {response.text[:500]}...")
        return None

if __name__ == "__main__":
    # Example Bounding Box (Krasnodar region, near Anapa)
    # These coordinates are in Web Mercator (WKID 102100)
    bbox_xmin = 4160000
    bbox_ymin = 5620000
    bbox_xmax = 4170000
    bbox_ymax = 5630000
    
    # Layer ID 21 corresponds to Земельные участки (polygons)
    print(f"Attempting to get features in BBOX: ({bbox_xmin},{bbox_ymin}), ({bbox_xmax},{bbox_ymax})")
    features_data = get_features_in_bbox(bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax, layer_id=21)

    if features_data and features_data.get('features'):
        print(f"\n--- Found {len(features_data['features'])} Features ---")
        for i, feature in enumerate(features_data['features'][:5]): # Print details of first 5 features
            attrs = feature.get('attributes', {})
            print(f"\nFeature {i+1}:")
            print(f"  Cadastral Number: {attrs.get('CAD_NOMER')}") # Note: field name might vary, CAD_NOMER is common for ArcGIS services
            print(f"  Address: {attrs.get('ADDRESS')}")
            print(f"  Area: {attrs.get('AREA_VAL')} {attrs.get('AREA_UOM')}")
            if feature.get('geometry'):
                print(f"  Geometry Type: {feature['geometry'].get('rings','No rings data')[0][:2]}... (first 2 points of first ring)" if feature['geometry'].get('rings') else "Point or other geometry")
            else:
                print("  No geometry returned")
        if len(features_data['features']) > 5:
            print("\n... and more features.")
            
    elif features_data and 'error' in features_data:
        print("\n--- Error from API ---")
        print(json.dumps(features_data['error'], indent=2, ensure_ascii=False))
    elif features_data:
        print("\n--- Received data, but 'features' key is missing or empty ---")
        print(json.dumps(features_data, indent=2, ensure_ascii=False))
    else:
        print("Failed to retrieve features in BBOX.") 