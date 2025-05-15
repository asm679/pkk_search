import os
#os.environ['FASTKML_USE_LXML'] = '1' # Больше не нужно
#from fastkml import kml # Больше не нужно
#from fastkml import geometry as fastkml_geometry # Больше не нужно
from lxml import etree # pykml использует lxml
from pykml import parser as pykml_parser
from pykml.factory import KML_ElementMaker as KML # Для создания KML элементов, если нужно
from pykml.factory import GX_ElementMaker as GX # Для gx элементов, если нужно
import traceback
from typing import List, Optional, Any

# Изменяем на абсолютный импорт от корня проекта
from scripts.data_structures import (
    PointGeom, LineStringGeom, LinearRingGeom, PolygonGeom, 
    MultiGeometryGeom, SubGeometryData, ExtractedPlacemark, CoordinateString
)

# Add a global list to store debug messages
DEBUG_LOG = []

def load_kml_file(kml_file_path):
    DEBUG_LOG.append(f"Attempting to load KML with pykml: {kml_file_path}")
    try:
        with open(kml_file_path, 'rb') as kml_file_bytes_io:
            kml_content_bytes = kml_file_bytes_io.read()
            
            DEBUG_LOG.append("Parsing KML bytes with pykml.parser.fromstring...")
            kml_root_pykml_obj = pykml_parser.fromstring(kml_content_bytes)
            
            if kml_root_pykml_obj is not None:
                DEBUG_LOG.append(f"pykml parsed. Root object type: {type(kml_root_pykml_obj)}")
                document_node = getattr(kml_root_pykml_obj, 'Document', None)
                if document_node is not None:
                    doc_name_node = getattr(document_node, 'name', None)
                    doc_name_text = doc_name_node.text if doc_name_node is not None and hasattr(doc_name_node, 'text') else 'Unnamed'
                    DEBUG_LOG.append(f"Document found. Name: {doc_name_text}")
                else:
                    DEBUG_LOG.append("No Document found directly under root KML object.")
            else:
                DEBUG_LOG.append("pykml.parser.fromstring returned None.")
            return kml_root_pykml_obj
    except FileNotFoundError:
        DEBUG_LOG.append(f"Error: KML file not found at {kml_file_path}")
        return None
    except etree.XMLSyntaxError as xml_err:
        DEBUG_LOG.append(f"pykml (lxml.etree.XMLSyntaxError): {xml_err}")
        DEBUG_LOG.append(traceback.format_exc())
        return None
    except Exception as e: 
        DEBUG_LOG.append(f"Error in load_kml_file (pykml path): {e} (Type: {type(e)})")
        DEBUG_LOG.append(traceback.format_exc())
        return None

def get_kml_document_name(kml_root_pykml_obj):
    DEBUG_LOG.append("--- Inside get_kml_document_name (pykml) ---")
    if kml_root_pykml_obj is None:
        DEBUG_LOG.append("kml_root_pykml_obj is None")
        return "KML Root is None"
    
    doc_candidate = None
    document_node = getattr(kml_root_pykml_obj, 'Document', None)
    folder_node = getattr(kml_root_pykml_obj, 'Folder', None)

    if document_node is not None:
        doc_candidate = document_node
        DEBUG_LOG.append("Found Document directly under kml_root.")
    elif folder_node is not None: 
        DEBUG_LOG.append("kml_root_pykml_obj seems to be a Folder itself or contains a Folder directly.")
        doc_candidate = folder_node
    elif hasattr(kml_root_pykml_obj, 'tag') and kml_root_pykml_obj.tag.endswith('Document'):
        DEBUG_LOG.append("kml_root_pykml_obj is a Document node itself.")
        doc_candidate = kml_root_pykml_obj
    elif hasattr(kml_root_pykml_obj, 'tag') and kml_root_pykml_obj.tag.endswith('Folder'):
        DEBUG_LOG.append("kml_root_pykml_obj is a Folder node itself.")
        doc_candidate = kml_root_pykml_obj

    if doc_candidate is not None:
        doc_name_element = getattr(doc_candidate, 'name', None)
        if doc_name_element is not None and hasattr(doc_name_element, 'text') and doc_name_element.text is not None:
            name_text = doc_name_element.text.strip()
            DEBUG_LOG.append(f"Container name: '{name_text}'")
            return name_text if name_text else f"{type(doc_candidate).__name__} (name is empty string)"
        else:
            DEBUG_LOG.append(f"{type(doc_candidate).__name__} found, but has no name element or name is empty/None.")
            return f"{type(doc_candidate).__name__} (Unnamed)"
    else:
        DEBUG_LOG.append(f"No Document or recognizable container with a name found in KML root type: {type(kml_root_pykml_obj).__name__}.")
        return "No Document/Folder in KML"

def get_geometry_from_placemark(placemark_pykml_obj):
    DEBUG_LOG.append(f"-- Inside get_geometry_from_placemark (pykml) for Placemark --")
    placemark_name_el = getattr(placemark_pykml_obj, 'name', None)
    placemark_name = placemark_name_el.text.strip() if placemark_name_el is not None and hasattr(placemark_name_el, 'text') and placemark_name_el.text is not None else "Unnamed Placemark"
    placemark_id = placemark_pykml_obj.get('id')

    DEBUG_LOG.append(f"Processing Placemark: '{placemark_name}' (ID: {placemark_id})")

    current_geometry_type: Optional[str] = None
    current_geometry_data: Any = None

    point_node = getattr(placemark_pykml_obj, 'Point', None)
    linestring_node = getattr(placemark_pykml_obj, 'LineString', None)
    polygon_node = getattr(placemark_pykml_obj, 'Polygon', None)
    linearring_node = getattr(placemark_pykml_obj, 'LinearRing', None)
    multigeometry_node = getattr(placemark_pykml_obj, 'MultiGeometry', None)

    if point_node is not None:
        current_geometry_type = 'Point'
        coords_el = getattr(point_node, 'coordinates', None)
        coords_str = coords_el.text.strip() if coords_el is not None and hasattr(coords_el, 'text') and coords_el.text is not None else ""
        current_geometry_data = PointGeom(coordinates=coords_str)
        DEBUG_LOG.append(f"  Found Point: {coords_str}")
    elif linestring_node is not None:
        current_geometry_type = 'LineString'
        coords_el = getattr(linestring_node, 'coordinates', None)
        coords_str = coords_el.text.strip() if coords_el is not None and hasattr(coords_el, 'text') and coords_el.text is not None else ""
        current_geometry_data = LineStringGeom(coordinates=coords_str)
        DEBUG_LOG.append(f"  Found LineString: {coords_str}")
    elif polygon_node is not None:
        current_geometry_type = 'Polygon'
        outer_coords_text = ""
        outer_boundary_is_node = getattr(polygon_node, 'outerBoundaryIs', None)
        if outer_boundary_is_node is not None:
            lr_node = getattr(outer_boundary_is_node, 'LinearRing', None)
            if lr_node is not None:
                coords_node = getattr(lr_node, 'coordinates', None)
                if coords_node is not None and hasattr(coords_node, 'text') and coords_node.text is not None:
                    outer_coords_text = coords_node.text.strip()
        
        outer_ring = LinearRingGeom(coordinates=outer_coords_text)
        inner_rings_data = []
        DEBUG_LOG.append(f"    Checking for innerBoundaryIs in Polygon '{placemark_name}'")
        for child in polygon_node.iterchildren():
            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag_name == 'innerBoundaryIs':
                DEBUG_LOG.append(f"      Found an innerBoundaryIs element.")
                lr_node_inner = getattr(child, 'LinearRing', None)
                if lr_node_inner is not None:
                    coords_node_inner = getattr(lr_node_inner, 'coordinates', None)
                    if coords_node_inner is not None and hasattr(coords_node_inner, 'text') and coords_node_inner.text is not None:
                        inner_coords_str = coords_node_inner.text.strip()
                        inner_rings_data.append(LinearRingGeom(coordinates=inner_coords_str))
                        DEBUG_LOG.append(f"        Extracted coordinates from innerBoundaryIs's LinearRing.")
                    else:
                        DEBUG_LOG.append(f"        innerBoundaryIs LinearRing has no coordinates.")
                else:
                    DEBUG_LOG.append(f"        innerBoundaryIs has no LinearRing.")
        
        current_geometry_data = PolygonGeom(outer_boundary=outer_ring, inner_boundaries=inner_rings_data)
        DEBUG_LOG.append(f"  Found Polygon: Outer present={bool(outer_coords_text)}, Inner count={len(inner_rings_data)}")
    elif linearring_node is not None: 
        current_geometry_type = 'LinearRing'
        coords_el = getattr(linearring_node, 'coordinates', None)
        coords_str = coords_el.text.strip() if coords_el is not None and hasattr(coords_el, 'text') and coords_el.text is not None else ""
        current_geometry_data = LinearRingGeom(coordinates=coords_str)
        DEBUG_LOG.append(f"  Found LinearRing directly in Placemark: {coords_str}")
    elif multigeometry_node is not None:
        current_geometry_type = 'MultiGeometry' # Тип установлен
        DEBUG_LOG.append(f"  Found MultiGeometry. Extracting sub-geometries...")
        multi_geom_parts = []
        
        # Итерируемся по дочерним элементам MultiGeometry, а не Placemark
        for element in multigeometry_node.iterchildren(): 
            sub_geom_type_str = element.tag.split('}')[-1] if '}' in element.tag else element.tag
            coords_node = getattr(element, 'coordinates', None)
            coords_text = coords_node.text.strip() if coords_node is not None and hasattr(coords_node, 'text') and coords_node.text is not None else None

            if sub_geom_type_str == "Point" and coords_text is not None:
                multi_geom_parts.append(SubGeometryData(type="Point", data=PointGeom(coordinates=coords_text)))
            elif sub_geom_type_str == "LineString" and coords_text is not None:
                multi_geom_parts.append(SubGeometryData(type="LineString", data=LineStringGeom(coordinates=coords_text)))
            elif sub_geom_type_str == "LinearRing" and coords_text is not None:
                multi_geom_parts.append(SubGeometryData(type="LinearRing", data=LinearRingGeom(coordinates=coords_text)))
            elif sub_geom_type_str == "Polygon":
                poly_outer_coords_text = ""
                poly_inner_rings_data = []
                poly_outer_boundary_is = getattr(element, 'outerBoundaryIs', None)
                if poly_outer_boundary_is is not None:
                    poly_lr_node = getattr(poly_outer_boundary_is, 'LinearRing', None)
                    if poly_lr_node is not None:
                        poly_coords_node = getattr(poly_lr_node, 'coordinates', None)
                        if poly_coords_node is not None and hasattr(poly_coords_node, 'text') and poly_coords_node.text is not None:
                            poly_outer_coords_text = poly_coords_node.text.strip()
                
                for poly_child_el in element.iterchildren():
                    poly_child_tag = poly_child_el.tag.split('}')[-1] if '}' in poly_child_el.tag else poly_child_el.tag
                    if poly_child_tag == 'innerBoundaryIs':
                        poly_inner_lr = getattr(poly_child_el, 'LinearRing', None)
                        if poly_inner_lr is not None:
                            poly_inner_coords_node = getattr(poly_inner_lr, 'coordinates', None)
                            if poly_inner_coords_node is not None and hasattr(poly_inner_coords_node, 'text') and poly_inner_coords_node.text is not None:
                                poly_inner_rings_data.append(LinearRingGeom(coordinates=poly_inner_coords_node.text.strip()))
                
                if poly_outer_coords_text: # Только если есть внешняя граница
                    multi_geom_parts.append(SubGeometryData(type="Polygon", data=PolygonGeom(
                        outer_boundary=LinearRingGeom(coordinates=poly_outer_coords_text),
                        inner_boundaries=poly_inner_rings_data
                    )))
        
        current_geometry_data = MultiGeometryGeom(geometries=multi_geom_parts)
        if not multi_geom_parts:
             DEBUG_LOG.append(f"  MultiGeometry for '{placemark_name}' is empty or contains no recognized sub-geometries.")
             # Тип остается MultiGeometry, но данные могут быть пустыми

    else:
        # Этот блок else теперь относится к случаю, когда ни один из основных типов геометрий не найден
        child_tags = [c.tag.split('}')[-1] for c in placemark_pykml_obj.iterchildren() if hasattr(c, 'tag')]
        DEBUG_LOG.append(f"  Placemark '{placemark_name}' (ID: {placemark_id}) has no directly recognized geometry. Child elements: {child_tags}")
        current_geometry_type = 'Unknown' # Устанавливаем Unknown только если ни один тип не подошел
        current_geometry_data = None

    if current_geometry_type and current_geometry_type != 'Unknown': # Не создаем ExtractedPlacemark для 'Unknown' если не было данных
        return ExtractedPlacemark(
            name=placemark_name,
            id=placemark_id,
            geometry_type=current_geometry_type,
            geometry_data=current_geometry_data,
            raw_kml_placemark_obj=placemark_pykml_obj
        )
    elif current_geometry_type == 'Unknown': # Если тип Unknown, но мы все же хотим его вернуть
         return ExtractedPlacemark(
            name=placemark_name, id=placemark_id, geometry_type='Unknown',
            geometry_data=None, raw_kml_placemark_obj=placemark_pykml_obj
        )

    return None

def extract_placemark_geometries_recursive(feature_container_pykml_obj) -> List[ExtractedPlacemark]:
    DEBUG_LOG.append(f"--- Inside extract_placemark_geometries_recursive (pykml) for container type: {type(feature_container_pykml_obj).__name__} ---")
    
    all_extracted_placemarks = []

    container_name_el = getattr(feature_container_pykml_obj, 'name', None)
    container_name = container_name_el.text.strip() if container_name_el is not None and hasattr(container_name_el, 'text') and container_name_el.text is not None else f"Unnamed {type(feature_container_pykml_obj).__name__}"
    DEBUG_LOG.append(f"Processing container: '{container_name}'")

    child_count = 0
    placemark_count = 0
    folder_count = 0
    document_count = 0

    # Проверяем, что feature_container_pykml_obj не None и имеет iterchildren
    if feature_container_pykml_obj is None or not hasattr(feature_container_pykml_obj, 'iterchildren'):
        DEBUG_LOG.append(f"Container is None or does not support iterchildren. Type: {type(feature_container_pykml_obj).__name__}")
        return all_extracted_placemarks

    for child in feature_container_pykml_obj.iterchildren():
        child_count += 1
        # Получаем имя тега без namespace, если он есть
        tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        
        if tag_name == 'Placemark':
            placemark_count += 1
            DEBUG_LOG.append(f"  Found Placemark node. Number: {placemark_count}")
            geom_data = get_geometry_from_placemark(child)
            if geom_data is not None: # Убедимся, что геометрия была извлечена
                all_extracted_placemarks.append(geom_data)
                DEBUG_LOG.append(f"    Added geometry data for Placemark: {geom_data.name if geom_data else 'N/A'}")
            else:
                DEBUG_LOG.append(f"    No geometry data returned for Placemark node {placemark_count}")
        elif tag_name == 'Folder':
            folder_count += 1
            DEBUG_LOG.append(f"  Found Folder node. Number: {folder_count}. Recursing...")
            all_extracted_placemarks.extend(extract_placemark_geometries_recursive(child))
        elif tag_name == 'Document': # Редко, но документ может быть вложен
            document_count +=1
            DEBUG_LOG.append(f"  Found nested Document node. Number: {document_count}. Recursing...")
            all_extracted_placemarks.extend(extract_placemark_geometries_recursive(child))
        else:
            DEBUG_LOG.append(f"  Skipping child type: {tag_name}")

    DEBUG_LOG.append(f"Finished processing container '{container_name}'. Total children: {child_count}, Placemarks found: {placemark_count}, Folders found: {folder_count}, Nested Docs: {document_count}")
    return all_extracted_placemarks


if __name__ == '__main__':
    DEBUG_LOG.clear()
    output_file_path = "scripts/test_output.txt"
    
    # Используем complex_kml_content
    complex_kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2">
  <Document>
    <name>Test KML Geometries</name>
    <Folder>
      <name>Points and Lines</name>
      <Placemark id="pm1">
        <name>Simple Point</name>
        <Point><coordinates>10,10,0</coordinates></Point>
      </Placemark>
      <Placemark id="pm2">
        <name>Simple LineString</name>
        <LineString>
          <coordinates>
            11,11,0 12,12,0 13,13,0
          </coordinates>
        </LineString>
      </Placemark>
    </Folder>
    <Folder>
      <name>Polygons</name>
      <Placemark id="pm3">
        <name>Simple Polygon</name>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                20,20,0 21,20,0 21,21,0 20,21,0 20,20,0
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>
      <Placemark id="pm4">
        <name>Polygon with Hole</name>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                30,30,0 35,30,0 35,35,0 30,35,0 30,30,0
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
          <innerBoundaryIs>
            <LinearRing>
              <coordinates>
                31,31,0 32,31,0 32,32,0 31,32,0 31,31,0
              </coordinates>
            </LinearRing>
          </innerBoundaryIs>
           <innerBoundaryIs>
            <LinearRing>
              <coordinates>
                33,33,0 34,33,0 34,34,0 33,34,0 33,33,0
              </coordinates>
            </LinearRing>
          </innerBoundaryIs>
        </Polygon>
      </Placemark>
    </Folder>
    <Placemark id="pm5">
        <name>Placemark with LinearRing directly</name>
        <LinearRing>
            <coordinates>1,1,0 2,1,0 2,2,0 1,2,0 1,1,0</coordinates>
        </LinearRing>
    </Placemark>
    <Placemark id="pm6_no_geom">
        <name>Placemark without Geometry</name>
        <description>This has no geometry tag</description>
    </Placemark>
  </Document>
</kml>""" 
    
    test_kml_file_valid = "test_complex_pykml.kml"
    
    try:
        with open(test_kml_file_valid, 'w', encoding='utf-8') as f:
            f.write(complex_kml_content) 
        DEBUG_LOG.append(f"Created test file: {test_kml_file_valid}")
    except IOError as e:
        DEBUG_LOG.append(f"Error creating test file {test_kml_file_valid}: {e}")

    DEBUG_LOG.append(f"\n--- Main Test (pykml): Loading KML: {test_kml_file_valid} ---")
    kml_root = load_kml_file(test_kml_file_valid)
    
    final_geometries = []
    document_name_for_output = "Unknown KML Document (pykml)"

    if kml_root:
        document_name_for_output = get_kml_document_name(kml_root)
        DEBUG_LOG.append(f"Document name (pykml): '{document_name_for_output}'")
        
        # Начальный объект для рекурсии - это Document внутри KML root, или сам KML root если Document нет.
        # Или если kml_root - это уже Document/Folder, переданный напрямую (для тестов).
        start_node_for_extraction = None
        if hasattr(kml_root, 'Document') and kml_root.Document is not None:
            start_node_for_extraction = kml_root.Document
            DEBUG_LOG.append(f"Starting geometry extraction (pykml) from root's Document: {type(start_node_for_extraction).__name__}")
        elif hasattr(kml_root, 'Folder') or hasattr(kml_root, 'Placemark'): # Если kml_root сам по себе контейнер
            start_node_for_extraction = kml_root
            DEBUG_LOG.append(f"Starting geometry extraction (pykml) directly from kml_root (type: {type(start_node_for_extraction).__name__}) as it appears to be a container.")
        else:
            DEBUG_LOG.append("KML root is not None, but no Document found and it's not a known container itself.")


        if start_node_for_extraction:
            final_geometries = extract_placemark_geometries_recursive(start_node_for_extraction)
        else:
            DEBUG_LOG.append("No suitable start node for geometry extraction (pykml).")
    else:
        DEBUG_LOG.append(f"Failed to load KML file with pykml: {test_kml_file_valid}")

    with open(output_file_path, 'w', encoding='utf-8') as outfile:
        outfile.write(f"KML Document Name (pykml): {document_name_for_output}\n")
        outfile.write(f"Found {len(final_geometries)} geometries from placemarks (pykml):\n")
        if final_geometries:
            for idx, geom_placemark in enumerate(final_geometries): # geom_placemark это ExtractedPlacemark
                outfile.write(f"  Geometry {idx + 1}:\n")
                outfile.write(f"    Name: {geom_placemark.name if geom_placemark.name else 'N/A'}\n")
                outfile.write(f"    ID: {geom_placemark.id if geom_placemark.id else 'N/A'}\n")
                outfile.write(f"    Type: {geom_placemark.geometry_type}\n")
                
                # Вывод координат в зависимости от типа геометрии
                coords_data = geom_placemark.geometry_data
                if isinstance(coords_data, PointGeom):
                    outfile.write(f"    Coordinates: {coords_data.coordinates}\n")
                elif isinstance(coords_data, LineStringGeom):
                    outfile.write(f"    Coordinates: {coords_data.coordinates}\n")
                elif isinstance(coords_data, LinearRingGeom):
                    outfile.write(f"    Coordinates: {coords_data.coordinates}\n")
                elif isinstance(coords_data, PolygonGeom):
                    outfile.write(f"    Coordinates (Outer): {coords_data.outer_boundary.coordinates}\n")
                    if coords_data.inner_boundaries:
                        for i, inner_ring in enumerate(coords_data.inner_boundaries):
                            outfile.write(f"    Coordinates (Inner {i+1}): {inner_ring.coordinates}\n")
                elif isinstance(coords_data, MultiGeometryGeom):
                    outfile.write(f"    Sub-geometries:\n")
                    for sub_idx, sub_geom_item in enumerate(coords_data.geometries):
                        outfile.write(f"      Sub-geometry {sub_idx+1}: Type={sub_geom_item.type}")
                        # Обработка координат для SubGeometryData
                        if isinstance(sub_geom_item.coordinates, dict): # Polygon in MultiGeometry
                            outfile.write(f", Outer: {sub_geom_item.coordinates.get('outer', 'N/A')}")
                            if sub_geom_item.coordinates.get('inner'):
                                for i_sub, i_ring_sub in enumerate(sub_geom_item.coordinates.get('inner', [])):
                                    outfile.write(f", Inner {i_sub+1}: {i_ring_sub}")
                            outfile.write("\n")
                        else: # Point, LineString, LinearRing string coordinates
                            outfile.write(f", Coords: {sub_geom_item.coordinates}\n")
                elif coords_data is None and geom_placemark.geometry_type == 'Unknown':
                    outfile.write(f"    Coordinates: Not applicable (Unknown geometry type)\n")
                else:
                    outfile.write(f"    Coordinates: (Unhandled geometry data type: {type(coords_data)}) {coords_data}\n")
        else:
            outfile.write("  No geometries extracted.\n")
            
        outfile.write("\n--- DEBUG LOG (pykml) ---\n")
        for log_entry in DEBUG_LOG:
            outfile.write(f"{log_entry}\n")

    if os.path.exists(test_kml_file_valid):
        os.remove(test_kml_file_valid)

    print(f"Test output (pykml) and debug log written to {output_file_path}") 