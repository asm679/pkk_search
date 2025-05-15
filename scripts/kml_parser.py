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
            # pykml.parser.fromstring ожидает байты
            # Он вернет корневой элемент <kml>, который будет объектом PyKML
            kml_root_pykml_obj = pykml_parser.fromstring(kml_content_bytes)
            
            if kml_root_pykml_obj is not None:
                DEBUG_LOG.append(f"pykml parsed. Root object type: {type(kml_root_pykml_obj)}")
                # Проверим, есть ли у него Document
                if hasattr(kml_root_pykml_obj, 'Document') and kml_root_pykml_obj.Document is not None:
                    DEBUG_LOG.append(f"Document found. Name: {kml_root_pykml_obj.Document.name.text if hasattr(kml_root_pykml_obj.Document, 'name') and kml_root_pykml_obj.Document.name is not None else 'Unnamed'}")
                else:
                    DEBUG_LOG.append("No Document found directly under root KML object.")
            else:
                DEBUG_LOG.append("pykml.parser.fromstring returned None.")
            return kml_root_pykml_obj
    except FileNotFoundError:
        DEBUG_LOG.append(f"Error: KML file not found at {kml_file_path}")
        return None
    except etree.XMLSyntaxError as xml_err: # pykml может выбрасывать ошибки lxml
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
    if hasattr(kml_root_pykml_obj, 'Document') and kml_root_pykml_obj.Document is not None:
        doc_candidate = kml_root_pykml_obj.Document
        DEBUG_LOG.append("Found Document directly under kml_root.")
    elif hasattr(kml_root_pykml_obj, 'Folder') and kml_root_pykml_obj.Folder is not None: # Если корневой элемент - папка
        # Это менее стандартно, но возможно KML без <Document> а сразу <Folder>
        # Или если kml_root_pykml_obj уже является объектом Document/Folder
        DEBUG_LOG.append("kml_root_pykml_obj seems to be a container itself (e.g. Document or Folder passed directly).")
        doc_candidate = kml_root_pykml_obj


    if doc_candidate is not None:
        doc_name_element = getattr(doc_candidate, 'name', None)
        if doc_name_element is not None and hasattr(doc_name_element, 'text'):
            name_text = doc_name_element.text
            DEBUG_LOG.append(f"Container name: '{name_text}'")
            return name_text if name_text else f"{type(doc_candidate).__name__} (name is empty)"
        else:
            DEBUG_LOG.append(f"{type(doc_candidate).__name__} found, but has no name element or name is empty.")
            return f"{type(doc_candidate).__name__} (Unnamed)"
    else:
        DEBUG_LOG.append(f"No Document or recognizable container with a name found in KML root type: {type(kml_root_pykml_obj).__name__}.")
        return "No Document/Folder in KML"

# Функции get_geometry_from_placemark и extract_placemark_geometries_recursive потребуют переписывания
# Пока оставим их как заглушки или закомментируем, чтобы скрипт не падал

def get_geometry_from_placemark(placemark_pykml_obj):
    DEBUG_LOG.append(f"-- Inside get_geometry_from_placemark (pykml) for Placemark --")
    placemark_name_el = getattr(placemark_pykml_obj, 'name', None)
    placemark_name = placemark_name_el.text.strip() if placemark_name_el and hasattr(placemark_name_el, 'text') else "Unnamed Placemark"
    placemark_id = placemark_pykml_obj.get('id') # Используем .get() для атрибутов XML

    DEBUG_LOG.append(f"Processing Placemark: '{placemark_name}' (ID: {placemark_id})")

    # geom_info = {'name': placemark_name, 'id': placemark_id, 'type': None, 'coordinates': None}
    current_geometry_type: Optional[str] = None
    current_geometry_data: Any = None

    if hasattr(placemark_pykml_obj, 'Point') and placemark_pykml_obj.Point is not None:
        # geom_info['type'] = 'Point'
        current_geometry_type = 'Point'
        coords_el = getattr(placemark_pykml_obj.Point, 'coordinates', None)
        coords_str = coords_el.text.strip() if coords_el and hasattr(coords_el, 'text') else ""
        # geom_info['coordinates'] = coords_str
        current_geometry_data = PointGeom(coordinates=coords_str)
        DEBUG_LOG.append(f"  Found Point: {coords_str}")
    elif hasattr(placemark_pykml_obj, 'LineString') and placemark_pykml_obj.LineString is not None:
        # geom_info['type'] = 'LineString'
        current_geometry_type = 'LineString'
        coords_el = getattr(placemark_pykml_obj.LineString, 'coordinates', None)
        coords_str = coords_el.text.strip() if coords_el and hasattr(coords_el, 'text') else ""
        # geom_info['coordinates'] = coords_str
        current_geometry_data = LineStringGeom(coordinates=coords_str)
        DEBUG_LOG.append(f"  Found LineString: {coords_str}")
    elif hasattr(placemark_pykml_obj, 'Polygon') and placemark_pykml_obj.Polygon is not None:
        # geom_info['type'] = 'Polygon'
        current_geometry_type = 'Polygon'
        polygon_obj = placemark_pykml_obj.Polygon
        outer_coords_text = ""
        
        if hasattr(polygon_obj, 'outerBoundaryIs') and polygon_obj.outerBoundaryIs and \
           hasattr(polygon_obj.outerBoundaryIs, 'LinearRing') and polygon_obj.outerBoundaryIs.LinearRing and \
           hasattr(polygon_obj.outerBoundaryIs.LinearRing, 'coordinates') and polygon_obj.outerBoundaryIs.LinearRing.coordinates:
            outer_coords_text = polygon_obj.outerBoundaryIs.LinearRing.coordinates.text.strip()
        
        outer_ring = LinearRingGeom(coordinates=outer_coords_text)
        inner_rings_data = []
        DEBUG_LOG.append(f"    Checking for innerBoundaryIs in Polygon '{placemark_name}'")
        for child in polygon_obj.iterchildren():
            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag_name == 'innerBoundaryIs':
                DEBUG_LOG.append(f"      Found an innerBoundaryIs element.")
                if hasattr(child, 'LinearRing') and child.LinearRing and \
                   hasattr(child.LinearRing, 'coordinates') and child.LinearRing.coordinates:
                    inner_coords_str = child.LinearRing.coordinates.text.strip()
                    inner_rings_data.append(LinearRingGeom(coordinates=inner_coords_str))
                    DEBUG_LOG.append(f"        Extracted coordinates from innerBoundaryIs's LinearRing.")
                else:
                    DEBUG_LOG.append(f"        innerBoundaryIs found, but no LinearRing/coordinates inside it.")
        
        # geom_info['coordinates'] = {'outer': outer_coords_text, 'inner': inner_coords_list}
        current_geometry_data = PolygonGeom(outer_boundary=outer_ring, inner_boundaries=inner_rings_data)
        DEBUG_LOG.append(f"  Found Polygon: Outer present={bool(outer_coords_text)}, Inner count={len(inner_rings_data)}")
    elif hasattr(placemark_pykml_obj, 'LinearRing') and placemark_pykml_obj.LinearRing is not None: 
        # geom_info['type'] = 'LinearRing'
        current_geometry_type = 'LinearRing'
        coords_el = getattr(placemark_pykml_obj.LinearRing, 'coordinates', None)
        coords_str = coords_el.text.strip() if coords_el and hasattr(coords_el, 'text') else ""
        # geom_info['coordinates'] = coords_str
        current_geometry_data = LinearRingGeom(coordinates=coords_str)
        DEBUG_LOG.append(f"  Found LinearRing directly in Placemark: {coords_str}")
    elif hasattr(placemark_pykml_obj, 'MultiGeometry') and placemark_pykml_obj.MultiGeometry is not None:
        # geom_info['type'] = 'MultiGeometry'
        current_geometry_type = 'MultiGeometry'
        DEBUG_LOG.append(f"  Found MultiGeometry. Extracting sub-geometries...")
        multi_geom_parts = []
        
        for element in placemark_pykml_obj.iterchildren():
            # Пропускаем элементы, которые не являются геометрией (например, Style, name, description)
            # KML геометрии обычно: Point, LineString, Polygon, LinearRing, Model, MultiGeometry
            # gx:MultiTrack, gx:Track
            if element.tag.endswith("Point"):
                coords = getattr(element, 'coordinates', None)
                if coords is not None and hasattr(coords, 'text') and coords.text:
                    multi_geom_parts.append(SubGeometryData(type="Point", data=PointGeom(coordinates=coords.text.strip())))
            elif element.tag.endswith("LineString"):
                coords = getattr(element, 'coordinates', None)
                if coords is not None and hasattr(coords, 'text') and coords.text:
                    multi_geom_parts.append(SubGeometryData(type="LineString", data=LineStringGeom(coordinates=coords.text.strip())))
            elif element.tag.endswith("LinearRing"):
                coords = getattr(element, 'coordinates', None)
                if coords is not None and hasattr(coords, 'text') and coords.text:
                     # LinearRing как самостоятельная геометрия в MultiGeometry - редкость, но обработаем
                    multi_geom_parts.append(SubGeometryData(type="LinearRing", data=LinearRingGeom(coordinates=coords.text.strip())))
            elif element.tag.endswith("Polygon"):
                outer_boundary_kml = None
                inner_boundaries_kml = []
                if hasattr(element, 'outerBoundaryIs') and element.outerBoundaryIs and \
                   hasattr(element.outerBoundaryIs, 'LinearRing') and element.outerBoundaryIs.LinearRing and \
                   hasattr(element.outerBoundaryIs.LinearRing, 'coordinates') and element.outerBoundaryIs.LinearRing.coordinates and \
                   element.outerBoundaryIs.LinearRing.coordinates.text:
                    outer_boundary_kml = LinearRingGeom(coordinates=element.outerBoundaryIs.LinearRing.coordinates.text.strip())
                
                for child_el in element.iterchildren():
                    if child_el.tag.endswith('innerBoundaryIs') and \
                       hasattr(child_el, 'LinearRing') and child_el.LinearRing and \
                       hasattr(child_el.LinearRing, 'coordinates') and child_el.LinearRing.coordinates and \
                       child_el.LinearRing.coordinates.text:
                        inner_boundaries_kml.append(LinearRingGeom(coordinates=child_el.LinearRing.coordinates.text.strip()))
                
                if outer_boundary_kml:
                    multi_geom_parts.append(SubGeometryData(type="Polygon", data=PolygonGeom(
                        outer_boundary=outer_boundary_kml,
                        inner_boundaries=inner_boundaries_kml
                    )))
            # MultiGeometry внутри MultiGeometry обрабатывать не будем для простоты на этом этапе
            # (хотя KML это позволяет). Можно добавить рекурсию, если понадобится.

        if multi_geom_parts:
            current_geometry_data = MultiGeometryGeom(geometries=multi_geom_parts)
        else:
            child_tags = [c.tag.split('}')[-1] for c in placemark_pykml_obj.iterchildren() if hasattr(c, 'tag')]
            DEBUG_LOG.append(f"  Placemark '{placemark_name}' (ID: {placemark_id}) has no directly recognized geometry. Child elements: {child_tags}")
            # return None 
            current_geometry_type = 'Unknown'
            current_geometry_data = None
    else:
        child_tags = [c.tag.split('}')[-1] for c in placemark_pykml_obj.iterchildren() if hasattr(c, 'tag')]
        DEBUG_LOG.append(f"  Placemark '{placemark_name}' (ID: {placemark_id}) has no directly recognized geometry. Child elements: {child_tags}")
        # return None 
        current_geometry_type = 'Unknown'
        current_geometry_data = None

    # return geom_info
    if current_geometry_type:
        return ExtractedPlacemark(
            name=placemark_name,
            id=placemark_id,
            geometry_type=current_geometry_type,
            geometry_data=current_geometry_data,
            raw_kml_placemark_obj=placemark_pykml_obj
        )
    return None # Если Placemark не содержал вообще никакой информации о геометрии

# _get_pykml_elements больше не нужна, так как extract_placemark_geometries_recursive использует iterchildren
# def _get_pykml_elements(parent_element, tag_name):
#     """Вспомогательная функция для получения дочерних элементов (одного или списка)."""
#     elements = []
#     if hasattr(parent_element, tag_name):
#         attr = getattr(parent_element, tag_name)
#         if attr is not None:
#             if isinstance(attr, list):
#                 elements.extend(val for val in attr if val is not None)
#             elif hasattr(attr, 'tag'): 
#                 elements.append(attr)
#     return elements

def extract_placemark_geometries_recursive(feature_container_pykml_obj) -> List[ExtractedPlacemark]:
    DEBUG_LOG.append(f"--- Inside extract_placemark_geometries_recursive (pykml) for container type: {type(feature_container_pykml_obj).__name__} ---")
    
    all_geometries = []

    container_name_el = getattr(feature_container_pykml_obj, 'name', None)
    container_name = container_name_el.text.strip() if container_name_el and hasattr(container_name_el, 'text') else f"Unnamed {type(feature_container_pykml_obj).__name__}"
    DEBUG_LOG.append(f"Processing container: '{container_name}'")

    # Используем iterchildren() для обхода всех дочерних элементов
    child_count = 0
    placemark_count = 0
    folder_count = 0
    document_count = 0

    for child in feature_container_pykml_obj.iterchildren():
        child_count += 1
        # Получаем имя тега без namespace, если он есть
        tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        DEBUG_LOG.append(f"  Child {child_count}: tag='{tag_name}', type={type(child).__name__}")

        if tag_name == 'Placemark':
            placemark_count +=1
            geom_data = get_geometry_from_placemark(child)
            if geom_data:
                all_geometries.append(geom_data)
                DEBUG_LOG.append(f"    Added geometry for Placemark: {geom_data.name if geom_data.name else 'N/A'} - Type: {geom_data.geometry_type}")
            else:
                pm_name_el = getattr(child, 'name', None)
                pm_name = pm_name_el.text.strip() if pm_name_el and hasattr(pm_name_el, 'text') else "Unnamed Placemark"
                DEBUG_LOG.append(f"    Placemark '{pm_name}' (child {child_count}) did not yield extractable geometry.")
        
        elif tag_name == 'Folder':
            folder_count +=1
            DEBUG_LOG.append(f"    Found Folder (child {child_count}), recursing...")
            all_geometries.extend(extract_placemark_geometries_recursive(child))
        
        elif tag_name == 'Document': # Рекурсия для вложенных документов
            document_count +=1
            DEBUG_LOG.append(f"    Found nested Document (child {child_count}), recursing...")
            all_geometries.extend(extract_placemark_geometries_recursive(child))
        else:
            # Можно добавить логирование других тегов, если это полезно для отладки
            # DEBUG_LOG.append(f"    Skipping child {child_count} with unhandled tag: '{tag_name}'")
            pass

    DEBUG_LOG.append(f"  Finished iterating children of '{container_name}'. Total children: {child_count}, Placemarks processed: {placemark_count}, Folders recursed: {folder_count}, Documents recursed: {document_count}")
    DEBUG_LOG.append(f"Finished processing container '{container_name}', total geometries collected from this level and below: {len(all_geometries)}")
    return all_geometries


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