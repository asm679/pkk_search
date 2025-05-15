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