from dataclasses import dataclass, field
from typing import List, Tuple, Union, Optional, Dict, Any

# Общий тип для координат (пока что строка, но можно уточнить в будущем,
# например, List[Tuple[float, float, Optional[float]]]
CoordinateString = str 

@dataclass
class PointGeom:
    coordinates: CoordinateString # "x,y,z"

@dataclass
class LineStringGeom:
    coordinates: CoordinateString # "x1,y1,z1 x2,y2,z2 ..."

@dataclass
class LinearRingGeom:
    coordinates: CoordinateString # "x1,y1,z1 ... x1,y1,z1" (замкнутый)

@dataclass
class PolygonGeom:
    outer_boundary: LinearRingGeom
    inner_boundaries: List[LinearRingGeom] = field(default_factory=list)

@dataclass
class SubGeometryData:
    type: str # 'Point', 'LineString', 'Polygon', 'LinearRing'
    # Теперь храним сам объект KML-геометрии, а не просто координаты
    data: Union[PointGeom, LineStringGeom, PolygonGeom, LinearRingGeom]

@dataclass
class MultiGeometryGeom:
    # Храним список объектов SubGeometryData, чтобы сохранить тип каждой под-геометрии
    geometries: List[SubGeometryData] 

# Обобщенный Placemark
@dataclass
class ExtractedPlacemark:
    name: Optional[str]
    id: Optional[str]
    geometry_type: str # 'Point', 'LineString', 'Polygon', 'LinearRing', 'MultiGeometry', 'Unknown'
    # Геометрия может быть одним из определенных типов или None/исходный словарь для необработанных/неизвестных случаев
    geometry_data: Union[PointGeom, LineStringGeom, PolygonGeom, LinearRingGeom, MultiGeometryGeom, Dict, None]
    # Опционально: ссылка на исходный pykml объект для отладки или доступа к доп. KML данным (например, Style, ExtendedData)
    raw_kml_placemark_obj: Optional[Any] = field(default=None, repr=False) # не выводить в repr для краткости 

# --- Датаклассы для данных от API НСПД (nspd.gov.ru) ---

@dataclass
class NSPDCrsProperties:
    name: Optional[str] = None # Например, "EPSG:3857"

@dataclass
class NSPDCadastralObjectGeometry:
    type: Optional[str] = None # Например, "Point", "Polygon", "MultiPolygon"
    coordinates: Optional[Any] = None # Структура координат зависит от типа геометрии
    crs: Optional[NSPDCrsProperties] = None

@dataclass
class NSPDCadastralObjectOptions: # Данные из feature.properties.options
    # Общие поля, которые могут встречаться
    cad_num: Optional[str] = None
    readable_address: Optional[str] = None
    area: Optional[Union[float, str]] = None # Может быть числом или строкой, требующей парсинга
    status: Optional[str] = None
    registration_date: Optional[str] = None # Дата регистрации/постановки на учет
    land_record_reg_date: Optional[str] = None # Альтернативная дата для ЗУ
    cost_value: Optional[Union[float, str]] = None # Кадастровая стоимость
    type: Optional[str] = None # Тип объекта, например, "Помещение"
    building_name: Optional[str] = None
    purpose: Optional[str] = None # Назначение
    floor: Optional[Union[str, List[str]]] = None # Этаж/этажность
    materials: Optional[str] = None # Материал стен (для зданий)
    year_built: Optional[str] = None
    year_commisioning: Optional[str] = None
    
    # Специфичные для земельных участков (ЗУ)
    land_record_category_type: Optional[str] = None # Категория земель
    permitted_use_established_by_document: Optional[str] = None # Разрешенное использование
    specified_area: Optional[Union[float, str]] = None # Уточненная площадь
    quarter_cad_number: Optional[str] = None # Номер кадастрового квартала
    ownership_type: Optional[str] = None # Форма собственности

    # Поля могут добавляться по мере обнаружения в API
    # Используем **kwargs для сбора всех остальных полей из options
    other_options: Dict[str, Any] = field(default_factory=dict)

@dataclass
class NSPDCadastralObjectPropertiesMain: # Данные из feature.properties (кроме options)
    categoryName: Optional[str] = None
    descr: Optional[str] = None # Часто содержит кадастровый номер или код зоны
    label: Optional[str] = None
    externalKey: Optional[str] = None
    interactionId: Optional[int] = None
    score: Optional[float] = None
    subcategory: Optional[int] = None
    # ... другие поля из properties, если понадобятся

@dataclass
class NSPDCadastralFeature:
    nspd_id: Optional[Union[str, int]] = None # id самого feature (может быть строкой или числом)
    type: Optional[str] = None # Обычно "Feature"
    geometry: Optional[NSPDCadastralObjectGeometry] = None
    main_properties: Optional[NSPDCadastralObjectPropertiesMain] = None # Из feature.properties
    options_properties: Optional[NSPDCadastralObjectOptions] = None # Из feature.properties.options
    raw_feature_dict: Optional[Dict[str, Any]] = field(default=None, repr=False) # Исходный словарь для отладки 