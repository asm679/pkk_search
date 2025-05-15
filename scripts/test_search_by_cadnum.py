import requests
import json

def get_object_details_by_cadnum(cadastral_number):
    search_url = f"https://pkk.rosreestr.ru/api/features/1?text={cadastral_number}&tolerance=1&limit=1"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        print(f"Searching for: {cadastral_number} at {search_url}")
        requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
        search_response = requests.get(search_url, headers=headers, timeout=30, verify=False)
        search_response.raise_for_status() # Check for HTTP errors
        search_data = search_response.json()
        print(f"Search response status: {search_response.status_code}")

        if search_data and search_data.get('features') and len(search_data['features']) > 0:
            feature_id = search_data['features'][0].get('attrs', {}).get('id')
            if not feature_id:
                if search_data['features'][0].get('feature', {}).get('attrs', {}).get('id'):
                     feature_id = search_data['features'][0].get('feature', {}).get('attrs', {}).get('id')
                else:
                    print(f"Error: Could not find feature ID for {cadastral_number} in search results.")
                    print(f"Search data: {json.dumps(search_data, indent=2, ensure_ascii=False)}")
                    return None
            
            print(f"Found feature ID: {feature_id}")

            details_url = f"https://pkk.rosreestr.ru/api/features/1/{feature_id}"
            print(f"Fetching details from: {details_url}")
            details_response = requests.get(details_url, headers=headers, timeout=30, verify=False)
            details_response.raise_for_status()
            details_data = details_response.json()
            print(f"Details response status: {details_response.status_code}")
            
            return details_data
        else:
            print(f"No features found for {cadastral_number}.")
            print(f"Search response: {json.dumps(search_data, indent=2, ensure_ascii=False)}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        if 'search_response' in locals() and search_response is not None:
            print(f"Response content: {search_response.text}")
        return None
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON: {e}")
        if 'search_response' in locals() and search_response is not None and search_response.text:
             print(f"Non-JSON search response: {search_response.text[:500]}...")
        elif 'details_response' in locals() and details_response is not None and details_response.text:
             print(f"Non-JSON details response: {details_response.text[:500]}...")
        return None

if __name__ == "__main__":
    cad_num_example = "23:49:0308001:102" # Example cadastral number (Krasnodar Krai)
    
    print(f"Attempting to get details for cadastral number: {cad_num_example}")
    object_info = get_object_details_by_cadnum(cad_num_example)

    if object_info and object_info.get('feature'):
        print("\n--- Object Details ---")
        attrs = object_info['feature'].get('attrs', {})
        geometry_data = object_info['feature'].get('geometry')
        geometry_type = geometry_data.get('type') if geometry_data else 'No geometry'
        
        print(f"  ID: {attrs.get('id')}")
        print(f"  Cadastral Number: {attrs.get('cn')}")
        print(f"  Address: {attrs.get('address')}")
        print(f"  Area Value: {attrs.get('area_value')} {attrs.get('area_unit')}")
        print(f"  Category: {attrs.get('category_type')}")
        print(f"  Utilization: {attrs.get('util_code_description')} (Code: {attrs.get('util_code')}, By doc: {attrs.get('util_by_doc')})")
        print(f"  Geometry Type: {geometry_type}")
    elif object_info:
        print("\n--- Received data, but 'feature' key is missing ---")
        print(json.dumps(object_info, indent=2, ensure_ascii=False))
    else:
        print("Failed to retrieve object details.") 