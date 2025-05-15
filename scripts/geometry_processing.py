from typing import List, Tuple, Optional, Union, Any, Dict
from shapely.geometry import Point, LineString, LinearRing, Polygon, MultiPoint, MultiLineString, MultiPolygon, GeometryCollection
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform
from shapely.geometry import mapping
from pyproj import CRS, Transformer
import json

# Изменяем на абсолютный импорт от корня проекта
from scripts.data_structures import (
    PointGeom as KmlPoint, LineStringGeom as KmlLineString, LinearRingGeom as KmlLinearRing, 
    PolygonGeom as KmlPolygon, MultiGeometryGeom as KmlMultiGeometry, ExtractedPlacemark, 
    SubGeometryData
)

DEFAULT_PRECISION = 6 # Количество знаков после запятой для округления координат

def parse_coordinate_string(coord_str: str, precision: int = DEFAULT_PRECISION) -> List[Tuple[float, ...]]:
    """
    Парсит строку координат KML в список кортежей чисел (float).
    Поддерживает 2D (x,y) и 3D (x,y,z) координаты.
    Координаты округляются до указанного количества знаков (precision).

    Пример строки: "10.1234567,20.7654321,5.0 11.123,22.321"
    Результат для precision=6: [(10.123457, 20.765432, 5.0), (11.123, 22.321)]
    Если z отсутствует, кортеж будет (x, y).

    Args:
        coord_str: Строка с координатами, разделенными пробелами.
                     Каждая координата - это x,y[,z], разделенные запятыми.
        precision: Количество знаков после запятой для округления.

    Returns:
        Список кортежей с числовыми координатами.
        Возвращает пустой список, если строка пуста или некорректна.
    """
    if not coord_str or not isinstance(coord_str, str):
        return []

    numeric_coords_list = []
    parts = coord_str.strip().split()

    for part in parts:
        if not part.strip(): # Пропускаем пустые части, если они есть (например, из-за двойных пробелов)
            continue
        coords = part.split(',')
        try:
            if len(coords) == 2:
                x = round(float(coords[0]), precision)
                y = round(float(coords[1]), precision)
                numeric_coords_list.append((x, y))
            elif len(coords) == 3:
                x = round(float(coords[0]), precision)
                y = round(float(coords[1]), precision)
                z_str = coords[2].strip()
                # Обработка случая, когда z может быть пустой строкой (например, "x,y,")
                # или содержать нечисловое значение после попытки парсинга в float
                z = round(float(z_str), precision) if z_str else 0.0 # или None, если предпочтительнее
                numeric_coords_list.append((x, y, z))
            else:
                # Некорректное количество компонентов в координате
                # Можно здесь логировать предупреждение, если нужно
                # print(f"Warning: Skipping invalid coordinate part: '{part}'")
                continue
        except ValueError:
            # Ошибка преобразования в float
            # print(f"Warning: ValueError parsing coordinate part: '{part}'")
            continue 
            
    return numeric_coords_list

def kml_placemark_to_shapely(kml_placemark: ExtractedPlacemark, precision: int = DEFAULT_PRECISION) -> Optional[Union[Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon, GeometryCollection]]:
    """
    Конвертирует объект ExtractedPlacemark (содержащий геометрию KML) 
    в соответствующий объект Shapely.

    Args:
        kml_placemark: Объект ExtractedPlacemark.
        precision: Точность для парсинга координат.

    Returns:
        Объект Shapely или None, если геометрия отсутствует или не может быть сконвертирована.
    """
    if not kml_placemark or not kml_placemark.geometry_data:
        return None

    geom_type = kml_placemark.geometry_type
    geom_data = kml_placemark.geometry_data # Это KmlPoint, KmlLineString и т.д.

    try:
        if geom_type == "Point" and isinstance(geom_data, KmlPoint):
            coords_parsed = parse_coordinate_string(geom_data.coordinates, precision)
            # Всегда берем X, Y. Если Z есть, он будет в coords_parsed[0][2], но мы его игнорируем для Shapely Point.
            return Point(coords_parsed[0][:2]) if coords_parsed and len(coords_parsed[0]) >= 2 else None
        
        elif geom_type == "LineString" and isinstance(geom_data, KmlLineString):
            coords_parsed = parse_coordinate_string(geom_data.coordinates, precision)
            # Преобразуем все координаты в 2D для Shapely
            coords_2d = [c[:2] for c in coords_parsed if len(c) >= 2]
            return LineString(coords_2d) if len(coords_2d) >= 2 else None
            
        elif geom_type == "LinearRing" and isinstance(geom_data, KmlLinearRing):
            coords_parsed = parse_coordinate_string(geom_data.coordinates, precision)
            coords_2d = [c[:2] for c in coords_parsed if len(c) >= 2]
            return LinearRing(coords_2d) if len(coords_2d) >= 3 else None

        elif geom_type == "Polygon" and isinstance(geom_data, KmlPolygon):
            outer_coords_parsed = parse_coordinate_string(geom_data.outer_boundary.coordinates, precision)
            outer_coords_2d = [c[:2] for c in outer_coords_parsed if len(c) >= 2]
            if len(outer_coords_2d) < 3: return None
            
            inner_rings_coords_2d = []
            if geom_data.inner_boundaries:
                for inner_kml_ring in geom_data.inner_boundaries:
                    inner_c_parsed = parse_coordinate_string(inner_kml_ring.coordinates, precision)
                    inner_c_2d = [c[:2] for c in inner_c_parsed if len(c) >= 2]
                    if len(inner_c_2d) >= 3:
                        inner_rings_coords_2d.append(inner_c_2d)
            
            shell = LinearRing(outer_coords_2d)
            holes = [LinearRing(h_coords_2d) for h_coords_2d in inner_rings_coords_2d] if inner_rings_coords_2d else None
            return Polygon(shell, holes)

        elif geom_type == "MultiGeometry" and isinstance(geom_data, KmlMultiGeometry):
            shapely_geoms = []
            for sub_geom_data in geom_data.geometries:
                # Рекурсивно создаем "фиктивный" ExtractedPlacemark для каждой под-геометрии
                # чтобы переиспользовать эту же функцию.
                fake_placemark = ExtractedPlacemark(
                    name=f"{kml_placemark.name}_sub" if kml_placemark.name else "sub_geom",
                    id=None, 
                    geometry_type=sub_geom_data.type,
                    geometry_data=sub_geom_data.data # Используем sub_geom_data.data
                )
                shapely_sub_geom = kml_placemark_to_shapely(fake_placemark, precision)
                if shapely_sub_geom:
                    shapely_geoms.append(shapely_sub_geom)
            
            if not shapely_geoms:
                return None

            # Попытка сгруппировать по типу для MultiPoint, MultiLineString, MultiPolygon
            # Если типы разные, вернем GeometryCollection
            first_type = type(shapely_geoms[0])
            if all(isinstance(g, first_type) for g in shapely_geoms):
                if first_type is Point:
                    return MultiPoint(shapely_geoms)
                elif first_type is LineString:
                    return MultiLineString(shapely_geoms)
                elif first_type is Polygon:
                    return MultiPolygon(shapely_geoms)
            
            return GeometryCollection(shapely_geoms)
        
        else:
            # Неизвестный тип геометрии или несоответствие типа и данных
            # print(f"Warning: Unknown or mismatched geometry type: {geom_type} for data: {type(geom_data)}")
            return None
            
    except Exception as e:
        # print(f"Error converting KML geometry to Shapely for placemark '{kml_placemark.name}': {e}")
        # import traceback
        # traceback.print_exc()
        return None

GEOGRAPHIC_CRS_WGS84 = "EPSG:4326"
DEFAULT_PLANAR_CRS = "EPSG:3857" # Web Mercator

def calculate_area(
    shapely_geom: Optional[BaseGeometry],
    source_crs_str: str = GEOGRAPHIC_CRS_WGS84, # Предполагаем, что исходные KML данные в WGS84
    project_to_planar: bool = True,
    target_planar_crs_str: str = DEFAULT_PLANAR_CRS
) -> Optional[float]:
    """
    Вычисляет площадь геометрии Shapely, опционально перепроецируя ее в планарную CRS.

    Args:
        shapely_geom: Геометрия Shapely (Polygon, MultiPolygon, GeometryCollection).
        source_crs_str: Строка CRS для исходной геометрии (например, "EPSG:4326").
        project_to_planar: Если True, геометрия будет перепроецирована в target_planar_crs_str.
        target_planar_crs_str: Целевая планарная CRS для вычисления площади (например, "EPSG:3857").

    Returns:
        Площадь в квадратных единицах целевой планарной CRS (обычно метры),
        или 0.0 для Point/LineString, или None если геометрия None или произошла ошибка.
    """
    if shapely_geom is None:
        return None

    # Точки и линии не имеют площади в контексте Shapely
    if shapely_geom.geom_type in ["Point", "MultiPoint", "LineString", "MultiLineString"]:
        return 0.0

    geom_to_calculate = shapely_geom

    if project_to_planar:
        try:
            source_crs = CRS.from_string(source_crs_str)
            target_crs = CRS.from_string(target_planar_crs_str)

            # Проверяем, действительно ли нужно перепроецирование
            # (Например, если исходная CRS уже планарная и совпадает с целевой)
            # Однако, CRS.equals() может быть строгим. Проще проверить, является ли исходная географической.
            if source_crs.is_geographic:
                transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
                geom_to_calculate = shapely_transform(transformer.transform, shapely_geom)
            elif source_crs.is_projected and not source_crs.equals(target_crs):
                # Если исходная уже планарная, но не совпадает с целевой
                print(f"Warning: Source CRS '{source_crs_str}' is projected but does not match target '{target_planar_crs_str}'. Reprojecting.")
                transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
                geom_to_calculate = shapely_transform(transformer.transform, shapely_geom)
            # else: исходная CRS либо уже целевая планарная, либо не географическая и не проекционная (что странно)
            # в этом случае, или если project_to_planar=False, просто используем .area

        except Exception as e:
            print(f"Error during CRS transformation: {e}")
            # Если перепроецирование не удалось, попробуем посчитать площадь в исходной CRS
            # но это может дать бессмысленные единицы (например, кв. градусы)
            print(f"Calculating area in original CRS '{source_crs_str}' due to transformation error.")
            # geom_to_calculate остается shapely_geom
    
    try:
        # Для GeometryCollection суммируем площади полигональных компонентов
        if geom_to_calculate.geom_type == "GeometryCollection":
            total_area = 0.0
            for g in geom_to_calculate.geoms:
                if g.geom_type in ["Polygon", "MultiPolygon"]:
                    # Рекурсивный вызов для каждого компонента, но без повторного перепроецирования
                    # так как geom_to_calculate уже (предположительно) в нужной CRS
                    component_area = calculate_area(g, project_to_planar=False) 
                    if component_area is not None:
                        total_area += component_area
            return total_area
        else:
            return geom_to_calculate.area
    except Exception as e:
        print(f"Error calculating area for {geom_to_calculate.geom_type}: {e}")
        return None

def calculate_length(
    shapely_geom: Optional[BaseGeometry],
    source_crs_str: str = GEOGRAPHIC_CRS_WGS84,
    project_to_planar: bool = True,
    target_planar_crs_str: str = DEFAULT_PLANAR_CRS
) -> Optional[float]:
    """
    Вычисляет длину геометрии Shapely (LineString, MultiLineString),
    опционально перепроецируя ее в планарную CRS.

    Args:
        shapely_geom: Геометрия Shapely.
        source_crs_str: Строка CRS для исходной геометрии.
        project_to_planar: Если True, геометрия будет перепроецирована.
        target_planar_crs_str: Целевая планарная CRS для вычисления длины.

    Returns:
        Длина в единицах целевой планарной CRS (обычно метры),
        0.0 для Point/Polygon, или None если геометрия None или произошла ошибка.
    """
    if shapely_geom is None:
        return None

    # Полигоны и точки не имеют "длины" в этом контексте (для полигонов есть периметр)
    if shapely_geom.geom_type in ["Point", "MultiPoint", "Polygon", "MultiPolygon"]:
        return 0.0

    geom_to_calculate = shapely_geom

    if project_to_planar:
        try:
            source_crs = CRS.from_string(source_crs_str)
            target_crs = CRS.from_string(target_planar_crs_str)

            if source_crs.is_geographic:
                transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
                geom_to_calculate = shapely_transform(transformer.transform, shapely_geom)
            elif source_crs.is_projected and not source_crs.equals(target_crs):
                print(f"Warning: Source CRS '{source_crs_str}' is projected but does not match target '{target_planar_crs_str}' for length. Reprojecting.")
                transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
                geom_to_calculate = shapely_transform(transformer.transform, shapely_geom)
        except Exception as e:
            print(f"Error during CRS transformation for length calculation: {e}")
            print(f"Calculating length in original CRS '{source_crs_str}' due to transformation error.")
            # geom_to_calculate остается shapely_geom

    try:
        if geom_to_calculate.geom_type == "GeometryCollection":
            total_length = 0.0
            for g in geom_to_calculate.geoms:
                if g.geom_type in ["LineString", "MultiLineString"]:
                    # Рекурсивный вызов, но без повторного перепроецирования
                    component_length = calculate_length(g, project_to_planar=False)
                    if component_length is not None:
                        total_length += component_length
            return total_length
        else: # LineString, MultiLineString
            return geom_to_calculate.length
    except Exception as e:
        print(f"Error calculating length for {geom_to_calculate.geom_type}: {e}")
        return None

def calculate_perimeter(
    shapely_geom: Optional[BaseGeometry],
    source_crs_str: str = GEOGRAPHIC_CRS_WGS84,
    project_to_planar: bool = True,
    target_planar_crs_str: str = DEFAULT_PLANAR_CRS
) -> Optional[float]:
    """
    Вычисляет периметр геометрии Shapely (Polygon, MultiPolygon),
    опционально перепроецируя ее в планарную CRS.

    Args:
        shapely_geom: Геометрия Shapely.
        source_crs_str: Строка CRS для исходной геометрии.
        project_to_planar: Если True, геометрия будет перепроецирована.
        target_planar_crs_str: Целевая планарная CRS для вычисления периметра.

    Returns:
        Периметр в единицах целевой планарной CRS (обычно метры),
        0.0 для Point/LineString, или None если геометрия None или произошла ошибка.
    """
    if shapely_geom is None or not shapely_geom.is_valid:
        return None
    
    # Для полигонов и мультиполигонов perimeter это exterior.length + sum(interior.length for interior in geom.interiors)
    # GeometryCollection может содержать полигоны, для которых можно посчитать периметр.
    # Простая проверка на наличие атрибута length не всегда корректна для периметра.
    
    geom_to_calculate = shapely_geom

    if project_to_planar:
        try:
            source_crs = CRS.from_string(source_crs_str)
            target_crs = CRS.from_string(target_planar_crs_str)
            if source_crs != target_crs:
                transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
                geom_to_calculate = shapely_transform(transformer.transform, shapely_geom)
        except Exception as e:
            # print(f"Error transforming geometry for perimeter calculation: {e}")
            return None # Ошибка трансформации

    try:
        if geom_to_calculate.geom_type in ['Polygon', 'MultiPolygon']:
            return geom_to_calculate.length # Для Polygon/MultiPolygon .length это внешний периметр
        elif geom_to_calculate.geom_type == 'GeometryCollection':
            total_perimeter = 0
            for sub_geom in geom_to_calculate.geoms:
                if sub_geom.geom_type in ['Polygon', 'MultiPolygon']:
                    # Рекурсивный вызов для полигональных частей GeometryCollection, 
                    # но уже без перепроецирования, т.к. коллекция уже перепроецирована
                    sub_perimeter = calculate_perimeter(sub_geom, project_to_planar=False)
                    if sub_perimeter is not None:
                        total_perimeter += sub_perimeter
            return total_perimeter if total_perimeter > 0 else 0.0
        else:
            # Для других типов (Point, LineString) периметр не имеет смысла в данном контексте
            return 0.0
    except Exception as e:
        # print(f"Error calculating perimeter: {e}")
        return None

def create_geojson_feature(
    placemark_data: ExtractedPlacemark, 
    shapely_geom: Optional[BaseGeometry], 
    area: Optional[float], 
    length: Optional[float], 
    perimeter: Optional[float],
    precision: int = DEFAULT_PRECISION 
) -> Dict:
    """
    Converts an ExtractedPlacemark and its associated Shapely geometry
    and calculated metrics into a GeoJSON Feature dictionary.

    Args:
        placemark_data: The ExtractedPlacemark object.
        shapely_geom: The corresponding Shapely geometry object.
        area: Calculated area (in projected units).
        length: Calculated length (in projected units).
        perimeter: Calculated perimeter (in projected units).
        precision: Number of decimal places to round calculated metrics.

    Returns:
        A dictionary representing a GeoJSON Feature.
    """
    properties = {
        "kml_name": placemark_data.name if placemark_data.name else None,
        "kml_id": placemark_data.id if placemark_data.id else None,
        "kml_geometry_type": placemark_data.geometry_type,
        "shapely_geometry_type": shapely_geom.geom_type if shapely_geom else None,
        "is_valid": shapely_geom.is_valid if shapely_geom else None,
    }

    if shapely_geom and not shapely_geom.is_valid:
        # Пытаемся получить причину невалидности, если доступно
        try:
            from shapely.validation import explain_validity
            properties["validity_reason"] = explain_validity(shapely_geom)
        except ImportError: # Для старых версий Shapely, где explain_validity может отсутствовать
            properties["validity_reason"] = "N/A (explain_validity not available)"
        except Exception: # На случай других ошибок при вызове explain_validity
            properties["validity_reason"] = "Error explaining validity"

    # Сохраняем метрики, только если они не None и больше 0 (или просто не None для is_valid)
    # Округляем до указанной точности
    if area is not None:
        rounded_area = round(area, precision)
        if abs(rounded_area) > 1e-9: # Добавляем, если не ноль (с учетом погрешности)
            properties["calculated_area_sq_units"] = rounded_area
    
    if length is not None:
        rounded_length = round(length, precision)
        if abs(rounded_length) > 1e-9:
            properties["calculated_length_units"] = rounded_length
        
    if perimeter is not None:
        rounded_perimeter = round(perimeter, precision)
        if abs(rounded_perimeter) > 1e-9:
            properties["calculated_perimeter_units"] = rounded_perimeter

    # Удаляем свойства со значением None для более чистого GeoJSON
    properties = {k: v for k, v in properties.items() if v is not None}

    feature = {
        "type": "Feature",
        "geometry": mapping(shapely_geom) if shapely_geom else None,
        "properties": properties,
    }
    
    return feature

def save_geojson_feature_collection(features: List[Dict], output_filepath: str, indent: Optional[int] = 2) -> bool:
    """
    Saves a list of GeoJSON Feature dictionaries as a FeatureCollection to a .geojson file.

    Args:
        features: A list of dictionaries, where each dictionary is a GeoJSON Feature.
        output_filepath: The path to the output .geojson file.
        indent: Indentation level for pretty-printing the JSON. 
                Set to None for a compact output.

    Returns:
        True if saving was successful, False otherwise.
    """
    if not output_filepath.lower().endswith(".geojson"):
        print(f"Warning: Output filepath '{output_filepath}' does not end with .geojson. Saving anyway.")
        # Можно добавить автоматическое добавление расширения, если его нет:
        # if not output_filepath.lower().endswith(('.geojson', '.json')):
        #     output_filepath += '.geojson'

    feature_collection = {
        "type": "FeatureCollection",
        "features": features
    }

    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(feature_collection, f, ensure_ascii=False, indent=indent)
        # print(f"Successfully saved GeoJSON FeatureCollection to: {output_filepath}") # Убрал принт, CLI будет сам сообщать
        return True
    except IOError as e:
        print(f"Error saving GeoJSON to file '{output_filepath}': {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while saving GeoJSON: {e}")
        return False

# Конец файла, блок if __name__ == '__main__' удален. 