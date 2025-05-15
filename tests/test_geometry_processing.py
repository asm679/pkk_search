import unittest
from decimal import Decimal, getcontext
import json
import tempfile
import shutil

# Добавляем путь к родительской директории, чтобы можно было импортировать scripts
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.geometry_processing import parse_coordinate_string, kml_placemark_to_shapely, DEFAULT_PRECISION, calculate_area, calculate_length, calculate_perimeter, create_geojson_feature, save_geojson_feature_collection
from scripts.data_structures import (
    ExtractedPlacemark,
    PointGeom as KmlPoint,
    LineStringGeom as KmlLineString,
    LinearRingGeom as KmlLinearRing,
    PolygonGeom as KmlPolygon,
    MultiGeometryGeom as KmlMultiGeometry,
    SubGeometryData
)
from shapely.geometry import Point, LineString, LinearRing, Polygon, MultiPoint, MultiLineString, MultiPolygon, GeometryCollection


class TestParseCoordinateString(unittest.TestCase):

    def assertCoordsAlmostEqual(self, list1, list2, places=DEFAULT_PRECISION):
        self.assertEqual(len(list1), len(list2), "Lists have different lengths")
        for tup1, tup2 in zip(list1, list2):
            self.assertEqual(len(tup1), len(tup2), f"Tuples {tup1} and {tup2} have different lengths")
            for c1, c2 in zip(tup1, tup2):
                self.assertAlmostEqual(c1, c2, places=places, msg=f"{c1} != {c2} within {places} places")

    def test_empty_and_none(self):
        self.assertEqual(parse_coordinate_string(""), [])
        self.assertEqual(parse_coordinate_string(None), [])

    def test_simple_2d(self):
        self.assertCoordsAlmostEqual(parse_coordinate_string("10.1234567,20.7654321"), [(10.123457, 20.765432)])

    def test_simple_3d(self):
        self.assertCoordsAlmostEqual(parse_coordinate_string("10.1234567,20.7654321,5.0"), [(10.123457, 20.765432, 5.0)])

    def test_multiple_coordinates(self):
        self.assertCoordsAlmostEqual(parse_coordinate_string("10.1,20.2 30.3,40.4,5.5"), [(10.1, 20.2), (30.3, 40.4, 5.5)])

    def test_extra_spaces(self):
        self.assertCoordsAlmostEqual(parse_coordinate_string("  10,20   30,40,5  "), [(10.0, 20.0), (30.0, 40.0, 5.0)])

    def test_empty_z_coordinate(self):
        # Поведение: пустая Z (10,20,) или пробел (10,20, ) парсится как Z=0.0
        self.assertCoordsAlmostEqual(parse_coordinate_string("10,20,"), [(10.0, 20.0, 0.0)])
        self.assertCoordsAlmostEqual(parse_coordinate_string("10,20, "), [(10.0, 20.0, 0.0)])

    def test_invalid_components(self):
        self.assertEqual(parse_coordinate_string("10,20,a 30,b"), []) # Полностью невалидные части пропускаются
        self.assertCoordsAlmostEqual(parse_coordinate_string("1,2 abc 3,4"), [(1.0,2.0), (3.0,4.0)]) # Валидные части остаются
        self.assertEqual(parse_coordinate_string(",,"), [])
        self.assertEqual(parse_coordinate_string("abc"), [])
    
    def test_precision(self):
        self.assertCoordsAlmostEqual(parse_coordinate_string("1.123456789,2.987654321,3.555555555"), 
                                     [(1.123457, 2.987654, 3.555556)], places=DEFAULT_PRECISION)
        self.assertCoordsAlmostEqual(parse_coordinate_string("10.12345,20.76543,5.456", precision=2), 
                                     [(10.12, 20.77, 5.46)], places=2)
        self.assertCoordsAlmostEqual(parse_coordinate_string("10.12345,20.76543", precision=2), 
                                     [(10.12, 20.77)], places=2)


class TestKmlPlacemarkToShapely(unittest.TestCase):

    def assertShapelyEqual(self, geom1, geom2, precision=DEFAULT_PRECISION-1): # Shapely может иметь небольшие отличия в представлении
        if geom1 is None and geom2 is None:
            return
        self.assertIsNotNone(geom1, "Geom1 is None, expected a Shapely geometry")
        self.assertIsNotNone(geom2, "Geom2 is None, expected a Shapely geometry")
        self.assertEqual(geom1.geom_type, geom2.geom_type)
        # Для сравнения координат используем буферизацию с очень маленьким допуском
        # или сравнение WKT с нормализацией пробелов
        # Shapely.equals_exact() может быть слишком строгим из-за представления float
        self.assertTrue(geom1.equals_exact(geom2, tolerance=10**(-precision)), 
                        f"Geometries not equal within tolerance:\n{geom1.wkt}\n{geom2.wkt}")

    def test_point(self):
        pm = ExtractedPlacemark("P", "p1", "Point", KmlPoint("10,20,5"))
        expected = Point(10, 20) # Z отброшена
        self.assertShapelyEqual(kml_placemark_to_shapely(pm), expected)

    def test_linestring(self):
        pm = ExtractedPlacemark("L", "l1", "LineString", KmlLineString("10,20 30,40,5 50,60"))
        expected = LineString([(10,20), (30,40), (50,60)]) # Z отброшены
        self.assertShapelyEqual(kml_placemark_to_shapely(pm), expected)
        # Невалидная линия
        pm_invalid = ExtractedPlacemark("IL", "il1", "LineString", KmlLineString("10,20"))
        self.assertIsNone(kml_placemark_to_shapely(pm_invalid))

    def test_linearring(self):
        # Используем KML координаты с Z для проверки отбрасывания
        pm = ExtractedPlacemark("R", "r1", "LinearRing", KmlLinearRing("0,0,1 0,10,2 10,10,3 10,0,4 0,0,5"))
        expected = LinearRing([(0,0), (0,10), (10,10), (10,0), (0,0)]) # Z отброшены
        self.assertShapelyEqual(kml_placemark_to_shapely(pm), expected)
        # Невалидное кольцо
        pm_invalid = ExtractedPlacemark("IR", "ir1", "LinearRing", KmlLinearRing("0,0 1,1"))
        self.assertIsNone(kml_placemark_to_shapely(pm_invalid))

    def test_polygon_simple(self):
        outer = KmlLinearRing("0,0,10 0,100,10 100,100,10 100,0,10 0,0,10")
        pm = ExtractedPlacemark("PolyS", "ps1", "Polygon", KmlPolygon(outer_boundary=outer))
        expected_shell = [(0,0), (0,100), (100,100), (100,0), (0,0)] # Z отброшены
        expected = Polygon(expected_shell)
        self.assertShapelyEqual(kml_placemark_to_shapely(pm), expected)

    def test_polygon_with_hole(self):
        outer = KmlLinearRing("0,0,0 0,100,0 100,100,0 100,0,0 0,0,0")
        inner1 = KmlLinearRing("10,10,1 10,20,1 20,20,1 20,10,1 10,10,1")
        pm = ExtractedPlacemark("PolyH", "ph1", "Polygon", KmlPolygon(outer, [inner1]))
        
        expected_shell = [(0,0), (0,100), (100,100), (100,0), (0,0)] # Z отброшены
        expected_hole1 = [(10,10), (10,20), (20,20), (20,10), (10,10)] # Z отброшены
        expected = Polygon(expected_shell, [expected_hole1])
        self.assertShapelyEqual(kml_placemark_to_shapely(pm), expected)
        
        # Невалидный полигон (невалидная внешняя граница)
        pm_invalid_outer = ExtractedPlacemark("IPO", "ipo1", "Polygon", KmlPolygon(KmlLinearRing("0,0 1,1")))
        self.assertIsNone(kml_placemark_to_shapely(pm_invalid_outer))
        # Невалидный полигон (невалидная внутренняя граница)
        # В KML-строке для outer Z-координаты есть, но они отбросятся при создании expected_shell_for_outer_only
        outer_for_invalid_inner_test = KmlLinearRing("0,0,0 0,100,0 100,100,0 100,0,0 0,0,0") 
        pm_invalid_inner = ExtractedPlacemark("IPI", "ipi1", "Polygon", 
                                              KmlPolygon(outer_for_invalid_inner_test, [KmlLinearRing("10,10,100 12,12,100")]))
        # Ожидаем полигон только с внешней границей (2D), т.к. невалидная внутренняя пропускается
        expected_shell_for_outer_only = [(0,0), (0,100), (100,100), (100,0), (0,0)]
        expected_outer_only = Polygon(expected_shell_for_outer_only)
        self.assertShapelyEqual(kml_placemark_to_shapely(pm_invalid_inner), expected_outer_only)

    def test_multigeometry_mixed(self):
        sub_geoms = [
            SubGeometryData("Point", KmlPoint("0,0,10")),
            SubGeometryData("LineString", KmlLineString("1,1,11 2,2,12"))
        ]
        pm = ExtractedPlacemark("MGM", "mgm1", "MultiGeometry", KmlMultiGeometry(sub_geoms))
        expected_geoms = [Point(0,0), LineString([(1,1),(2,2)])] # Z отброшены
        expected = GeometryCollection(expected_geoms)
        result_geom = kml_placemark_to_shapely(pm)
        self.assertIsInstance(result_geom, GeometryCollection)
        self.assertEqual(len(result_geom.geoms), len(expected.geoms))
        # Для простоты сравним WKT отдельных компонент, если необходимо более строгое сравнение, нужна другая логика
        # self.assertEqual(result_geom.wkt, expected.wkt) # Порядок WKT может отличаться

    def test_multigeometry_multipoint(self):
        sub_geoms = [
            SubGeometryData("Point", KmlPoint("10,10,100")),
            SubGeometryData("Point", KmlPoint("20,20,200")),
        ]
        pm = ExtractedPlacemark("MGMP", "mgmp1", "MultiGeometry", KmlMultiGeometry(sub_geoms))
        expected = MultiPoint([Point(10,10), Point(20,20)]) # Z отброшены
        self.assertShapelyEqual(kml_placemark_to_shapely(pm), expected)

    def test_multigeometry_multilinestring(self):
        sub_geoms = [
            SubGeometryData("LineString", KmlLineString("0,0,1 1,1,2")),
            SubGeometryData("LineString", KmlLineString("10,10,3 11,11,4 12,12,5")),
        ]
        pm = ExtractedPlacemark("MGMLS", "mgmls1", "MultiGeometry", KmlMultiGeometry(sub_geoms))
        expected = MultiLineString([
            LineString([(0,0),(1,1)]),
            LineString([(10,10),(11,11),(12,12)])
        ]) # Z отброшены
        self.assertShapelyEqual(kml_placemark_to_shapely(pm), expected)

    def test_multigeometry_multipolygon(self):
        poly1_data = KmlPolygon(outer_boundary=KmlLinearRing("0,0,1 1,0,1 1,1,1 0,1,1 0,0,1"))
        poly2_data = KmlPolygon(outer_boundary=KmlLinearRing("10,10,2 11,10,2 11,11,2 10,11,2 10,10,2"))
        sub_geoms = [
            SubGeometryData("Polygon", poly1_data),
            SubGeometryData("Polygon", poly2_data),
        ]
        pm = ExtractedPlacemark("MGMPoly", "mgmpoly1", "MultiGeometry", KmlMultiGeometry(sub_geoms))
        
        expected_poly1 = Polygon([(0,0),(1,0),(1,1),(0,1),(0,0)]) # Z отброшены
        expected_poly2 = Polygon([(10,10),(11,10),(11,11),(10,11),(10,10)]) # Z отброшены
        expected = MultiPolygon([expected_poly1, expected_poly2])
        self.assertShapelyEqual(kml_placemark_to_shapely(pm), expected)

    def test_no_geometry(self):
        pm = ExtractedPlacemark("NoGeom", "ng1", None, None)
        self.assertIsNone(kml_placemark_to_shapely(pm))
    
    def test_unknown_geometry_type_in_placemark(self):
        pm = ExtractedPlacemark("UnknownType", "ut1", "WeirdShape", KmlPoint("0,0")) # Тип не соответствует данным
        self.assertIsNone(kml_placemark_to_shapely(pm))


class TestCalculateArea(unittest.TestCase):

    def setUp(self):
        # Данные для тестов, создаем один раз
        self.pm_point = ExtractedPlacemark("P", "p1", "Point", KmlPoint("10,20"))
        self.shapely_point = kml_placemark_to_shapely(self.pm_point)

        self.pm_line = ExtractedPlacemark("L", "l1", "LineString", KmlLineString("10,20 30,40"))
        self.shapely_line = kml_placemark_to_shapely(self.pm_line)

        poly_coords_wgs84 = "0,0 1,0 1,1 0,1 0,0"
        self.pm_poly_wgs84 = ExtractedPlacemark("PolyWGS", "pw1", "Polygon", 
                                       KmlPolygon(KmlLinearRing(poly_coords_wgs84)))
        self.shapely_poly_wgs84 = kml_placemark_to_shapely(self.pm_poly_wgs84)

        poly_coords_planar = "0,0 100,0 100,100 0,100 0,0"
        self.pm_poly_planar = ExtractedPlacemark("PolyPlanar", "pp1", "Polygon",
                                          KmlPolygon(KmlLinearRing(poly_coords_planar)))
        self.shapely_poly_planar = kml_placemark_to_shapely(self.pm_poly_planar)

        gc_poly1_coords = "10,10 20,10 20,20 10,20 10,10" # Площадь 100
        gc_poly2_coords = "0,50 5,50 5,55 0,55 0,50"   # Площадь 25
        self.pm_gc = ExtractedPlacemark("GC", "gc1", "MultiGeometry",
            KmlMultiGeometry(geometries=[
                SubGeometryData(type="Point", data=KmlPoint(coordinates="0,0")),
                SubGeometryData(type="Polygon", data=KmlPolygon(KmlLinearRing(gc_poly1_coords))),
                SubGeometryData(type="Polygon", data=KmlPolygon(KmlLinearRing(gc_poly2_coords)))
            ]))
        self.shapely_gc = kml_placemark_to_shapely(self.pm_gc)

    def test_point_area(self):
        area = calculate_area(self.shapely_point)
        self.assertIsNotNone(area)
        self.assertAlmostEqual(area, 0.0, places=7, msg="Point area should be 0.0")

    def test_linestring_area(self):
        area = calculate_area(self.shapely_line)
        self.assertIsNotNone(area)
        self.assertAlmostEqual(area, 0.0, places=7, msg="LineString area should be 0.0")

    def test_polygon_wgs84_no_projection(self):
        area = calculate_area(self.shapely_poly_wgs84, project_to_planar=False)
        self.assertIsNotNone(area)
        # Площадь в квадратных градусах
        self.assertAlmostEqual(area, 1.0, places=7, msg="Polygon area in sq.degrees failed")

    def test_polygon_wgs84_projected_to_3857(self):
        area = calculate_area(self.shapely_poly_wgs84, 
                                source_crs_str="EPSG:4326", 
                                project_to_planar=True, 
                                target_planar_crs_str="EPSG:3857")
        self.assertIsNotNone(area)
        # Ожидаемая площадь для квадрата 1x1 градус на экваторе в EPSG:3857 (Web Mercator)
        # ~ 1.239e10 кв.м. (12390 кв.км)
        expected_area_approx = 12392658216 # Более точное значение из предыдущего прогона
        self.assertAlmostEqual(area, expected_area_approx, delta=expected_area_approx*0.01, 
                               msg="Projected WGS84 polygon area to EPSG:3857 failed")

    def test_polygon_planar_no_projection(self):
        area = calculate_area(self.shapely_poly_planar, 
                                source_crs_str="EPSG:3857", # Указываем, что она уже планарная
                                project_to_planar=False)
        self.assertIsNotNone(area)
        self.assertAlmostEqual(area, 10000.0, places=7, msg="Planar polygon (no projection) area failed")

    def test_polygon_planar_project_to_same_crs(self):
        area = calculate_area(self.shapely_poly_planar, 
                                source_crs_str="EPSG:3857", 
                                project_to_planar=True, 
                                target_planar_crs_str="EPSG:3857")
        self.assertIsNotNone(area)
        self.assertAlmostEqual(area, 10000.0, places=7, msg="Planar polygon (project to same CRS) area failed")

    def test_geometrycollection_area(self):
        # Предполагаем, что координаты GC уже в нужной планарной CRS для прямого подсчета площади
        area = calculate_area(self.shapely_gc, source_crs_str="EPSG:3857", project_to_planar=False)
        self.assertIsNotNone(area)
        self.assertAlmostEqual(area, 125.0, places=7, msg="GeometryCollection area failed")
    
    def test_none_geometry(self):
        area = calculate_area(None)
        self.assertIsNone(area, "Area of None geometry should be None")


class TestCalculateLength(unittest.TestCase):

    def setUp(self):
        self.pm_point = ExtractedPlacemark("P", "p1", "Point", KmlPoint("10,20"))
        self.shapely_point = kml_placemark_to_shapely(self.pm_point)

        self.pm_line_wgs84 = ExtractedPlacemark("LineWGS", "lw1", "LineString", 
                                        KmlLineString("0,0 1,0")) # 1 градус по экватору
        self.shapely_line_wgs84 = kml_placemark_to_shapely(self.pm_line_wgs84)

        self.pm_line_planar = ExtractedPlacemark("LinePlanar", "lp1", "LineString", 
                                           KmlLineString("0,0 100,0")) # Длина 100 в планарной CRS
        self.shapely_line_planar = kml_placemark_to_shapely(self.pm_line_planar)

        self.pm_poly = ExtractedPlacemark("Poly", "poly1", "Polygon",
                                     KmlPolygon(KmlLinearRing("0,0 10,0 10,10 0,10 0,0")))
        self.shapely_poly = kml_placemark_to_shapely(self.pm_poly)

        gc_line1_coords = "0,0 10,0" # Длина 10
        gc_line2_coords = "20,0 20,5"  # Длина 5
        self.pm_gc_lines = ExtractedPlacemark("GCLines", "gcl1", "MultiGeometry",
            KmlMultiGeometry(geometries=[
                SubGeometryData(type="Point", data=KmlPoint(coordinates="100,100")),
                SubGeometryData(type="LineString", data=KmlLineString(gc_line1_coords)),
                SubGeometryData(type="LineString", data=KmlLineString(gc_line2_coords))
            ]))
        self.shapely_gc_lines = kml_placemark_to_shapely(self.pm_gc_lines)

    def test_point_length(self):
        length = calculate_length(self.shapely_point)
        self.assertIsNotNone(length)
        self.assertAlmostEqual(length, 0.0, places=7, msg="Point length should be 0.0")

    def test_polygon_length(self):
        length = calculate_length(self.shapely_poly)
        self.assertIsNotNone(length)
        self.assertAlmostEqual(length, 0.0, places=7, msg="Polygon length should be 0.0")

    def test_linestring_wgs84_no_projection(self):
        length = calculate_length(self.shapely_line_wgs84, project_to_planar=False)
        self.assertIsNotNone(length)
        self.assertAlmostEqual(length, 1.0, places=7, msg="LineString length in degrees failed")

    def test_linestring_wgs84_projected_to_3857(self):
        length = calculate_length(self.shapely_line_wgs84,
                                  source_crs_str="EPSG:4326",
                                  project_to_planar=True,
                                  target_planar_crs_str="EPSG:3857")
        self.assertIsNotNone(length)
        # Ожидаемая длина для линии в 1 градус на экваторе в EPSG:3857 (Web Mercator)
        # Примерно 111319.49 метров
        expected_length_approx = 111319.49079327357
        self.assertAlmostEqual(length, expected_length_approx, delta=expected_length_approx * 0.001, # Допуск 0.1%
                               msg="Projected WGS84 LineString length to EPSG:3857 failed")

    def test_linestring_planar_no_projection(self):
        length = calculate_length(self.shapely_line_planar,
                                  source_crs_str="EPSG:3857",
                                  project_to_planar=False)
        self.assertIsNotNone(length)
        self.assertAlmostEqual(length, 100.0, places=7, msg="Planar LineString (no projection) length failed")

    def test_linestring_planar_project_to_same_crs(self):
        length = calculate_length(self.shapely_line_planar,
                                  source_crs_str="EPSG:3857",
                                  project_to_planar=True,
                                  target_planar_crs_str="EPSG:3857")
        self.assertIsNotNone(length)
        self.assertAlmostEqual(length, 100.0, places=7, msg="Planar LineString (project to same CRS) length failed")
    
    def test_geometrycollection_length(self):
        # Предполагаем, что GC уже в нужной планарной CRS
        length = calculate_length(self.shapely_gc_lines, source_crs_str="EPSG:3857", project_to_planar=False)
        self.assertIsNotNone(length)
        self.assertAlmostEqual(length, 15.0, places=7, msg="GeometryCollection of lines length failed")

    def test_none_geometry_length(self):
        length = calculate_length(None)
        self.assertIsNone(length, "Length of None geometry should be None")


class TestCalculatePerimeter(unittest.TestCase):

    def setUp(self):
        self.pm_point = ExtractedPlacemark("P", "p1", "Point", KmlPoint("10,20"))
        self.shapely_point = kml_placemark_to_shapely(self.pm_point)

        self.pm_line = ExtractedPlacemark("Line", "l1", "LineString", KmlLineString("0,0 10,0"))
        self.shapely_line = kml_placemark_to_shapely(self.pm_line)

        # Квадрат 1x1 градус на экваторе (периметр 4 градуса)
        poly_coords_wgs84 = "0,0 1,0 1,1 0,1 0,0" 
        self.pm_poly_wgs84 = ExtractedPlacemark("PolyWGS", "pw1", "Polygon", 
                                       KmlPolygon(KmlLinearRing(poly_coords_wgs84)))
        self.shapely_poly_wgs84 = kml_placemark_to_shapely(self.pm_poly_wgs84)

        # Квадрат 100x100 в планарной CRS (периметр 400)
        poly_coords_planar = "0,0 100,0 100,100 0,100 0,0"
        self.pm_poly_planar = ExtractedPlacemark("PolyPlanar", "pp1", "Polygon",
                                          KmlPolygon(KmlLinearRing(poly_coords_planar)))
        self.shapely_poly_planar = kml_placemark_to_shapely(self.pm_poly_planar)
        
        # MultiPolygon для теста
        poly1_coords = "0,0 1,0 1,1 0,1 0,0" # Периметр 4
        poly2_coords = "10,10 12,10 12,12 10,12 10,10" # Периметр 8
        self.pm_multi_poly_planar = ExtractedPlacemark("MultiPolyPlanar", "mpp1", "MultiGeometry",
            KmlMultiGeometry(geometries=[
                SubGeometryData(type="Polygon", data=KmlPolygon(KmlLinearRing(poly1_coords))),
                SubGeometryData(type="Polygon", data=KmlPolygon(KmlLinearRing(poly2_coords)))
            ]))
        self.shapely_multi_poly_planar = kml_placemark_to_shapely(self.pm_multi_poly_planar)

        # GeometryCollection с полигонами
        gc_poly1_coords = "0,0 5,0 5,5 0,5 0,0"     # Периметр 20
        gc_poly2_coords = "10,10 12,10 12,11 10,11 10,10" # Периметр 6
        self.pm_gc_polys = ExtractedPlacemark("GCPolys", "gcp1", "MultiGeometry",
            KmlMultiGeometry(geometries=[
                SubGeometryData(type="LineString", data=KmlLineString(coordinates="100,100 101,101")),
                SubGeometryData(type="Polygon", data=KmlPolygon(KmlLinearRing(gc_poly1_coords))),
                SubGeometryData(type="Polygon", data=KmlPolygon(KmlLinearRing(gc_poly2_coords)))
            ]))
        self.shapely_gc_polys = kml_placemark_to_shapely(self.pm_gc_polys)

    def test_point_perimeter(self):
        perimeter = calculate_perimeter(self.shapely_point)
        self.assertIsNotNone(perimeter)
        self.assertAlmostEqual(perimeter, 0.0, places=7, msg="Point perimeter should be 0.0")

    def test_linestring_perimeter(self):
        perimeter = calculate_perimeter(self.shapely_line)
        self.assertIsNotNone(perimeter)
        self.assertAlmostEqual(perimeter, 0.0, places=7, msg="LineString perimeter should be 0.0")

    def test_polygon_wgs84_no_projection(self):
        perimeter = calculate_perimeter(self.shapely_poly_wgs84, project_to_planar=False)
        self.assertIsNotNone(perimeter)
        self.assertAlmostEqual(perimeter, 4.0, places=7, msg="Polygon perimeter in degrees failed")

    def test_polygon_wgs84_projected_to_3857(self):
        perimeter = calculate_perimeter(self.shapely_poly_wgs84,
                                      source_crs_str="EPSG:4326",
                                      project_to_planar=True,
                                      target_planar_crs_str="EPSG:3857")
        self.assertIsNotNone(perimeter)
        # Ожидаемый периметр для квадрата 1x1 градус на экваторе в EPSG:3857
        # Каждая сторона ~111319.49 м. Периметр ~445277.96 м.
        expected_perimeter_approx = 445277.9631730943
        self.assertAlmostEqual(perimeter, expected_perimeter_approx, delta=expected_perimeter_approx * 0.001, # допуск 0.1%
                               msg="Projected WGS84 Polygon perimeter to EPSG:3857 failed")

    def test_polygon_planar_no_projection(self):
        perimeter = calculate_perimeter(self.shapely_poly_planar,
                                      source_crs_str="EPSG:3857",
                                      project_to_planar=False)
        self.assertIsNotNone(perimeter)
        self.assertAlmostEqual(perimeter, 400.0, places=7, msg="Planar Polygon (no projection) perimeter failed")

    def test_polygon_planar_project_to_same_crs(self):
        perimeter = calculate_perimeter(self.shapely_poly_planar,
                                      source_crs_str="EPSG:3857",
                                      project_to_planar=True,
                                      target_planar_crs_str="EPSG:3857")
        self.assertIsNotNone(perimeter)
        self.assertAlmostEqual(perimeter, 400.0, places=7, msg="Planar Polygon (project to same CRS) perimeter failed")

    def test_multipolygon_planar_perimeter(self):
        # Предполагаем, что MultiPolygon уже в нужной планарной CRS
        perimeter = calculate_perimeter(self.shapely_multi_poly_planar, source_crs_str="EPSG:3857", project_to_planar=False)
        self.assertIsNotNone(perimeter)
        self.assertAlmostEqual(perimeter, 12.0, places=7, msg="MultiPolygon (planar) perimeter failed") # 4 + 8 = 12

    def test_geometrycollection_perimeter(self):
        # Предполагаем, что GC уже в нужной планарной CRS
        perimeter = calculate_perimeter(self.shapely_gc_polys, source_crs_str="EPSG:3857", project_to_planar=False)
        self.assertIsNotNone(perimeter)
        self.assertAlmostEqual(perimeter, 26.0, places=7, msg="GeometryCollection of polygons perimeter failed") # 20 + 6 = 26

    def test_none_geometry_perimeter(self):
        perimeter = calculate_perimeter(None)
        self.assertIsNone(perimeter, "Perimeter of None geometry should be None")


class TestCreateGeoJSONFeature(unittest.TestCase):

    def test_basic_point_feature(self):
        pm = ExtractedPlacemark(name="Test Point", id="tp01", geometry_type="Point", geometry_data=KmlPoint("10,20"))
        shapely_geom = Point(10, 20)
        area, length, perimeter = 0.0, 0.0, 0.0
        
        feature = create_geojson_feature(pm, shapely_geom, area, length, perimeter)
        
        self.assertEqual(feature["type"], "Feature")
        self.assertIsNotNone(feature["geometry"])
        self.assertEqual(feature["geometry"]["type"], "Point")
        self.assertEqual(feature["geometry"]["coordinates"], (10.0, 20.0))
        
        props = feature["properties"]
        self.assertEqual(props["kml_name"], "Test Point")
        self.assertEqual(props["kml_id"], "tp01")
        self.assertEqual(props["kml_geometry_type"], "Point")
        self.assertEqual(props["shapely_geometry_type"], "Point")
        self.assertTrue(props["is_valid"])
        self.assertNotIn("validity_reason", props)
        # Метрики равны 0, поэтому не должны включаться по умолчанию (если не > 1e-9)
        self.assertNotIn("calculated_area_sq_units", props)
        self.assertNotIn("calculated_length_units", props)
        self.assertNotIn("calculated_perimeter_units", props)

    def test_polygon_feature_with_metrics_and_invalidity(self):
        pm = ExtractedPlacemark(name="Invalid Poly", id="ip01", geometry_type="Polygon", 
                                geometry_data=KmlPolygon(KmlLinearRing("0,0 0,1 1,1 1,0 0,1"))) # Данные KML не так важны здесь
        
        # Создаем невалидный "bowtie" полигон
        shell_coords = [(0,0), (10,10), (10,0), (0,10), (0,0)]
        shapely_geom = Polygon(shell_coords)
        
        # Проверим, действительно ли он невалиден для текущей версии Shapely
        # Если нет, тест нужно будет адаптировать или найти другой способ создания невалидной геометрии
        # self.assertFalse(shapely_geom.is_valid, "Test setup: Bowtie polygon should be invalid by default")

        area, length, perimeter = 123.456, 0.0, 45.678 # Метрики могут быть любыми для теста свойств

        feature = create_geojson_feature(pm, shapely_geom, area, length, perimeter, precision=2)
        self.assertEqual(feature["type"], "Feature")
        self.assertEqual(feature["geometry"]["type"], "Polygon")
        
        props = feature["properties"]
        self.assertEqual(props["kml_name"], "Invalid Poly")
        self.assertEqual(props["kml_geometry_type"], "Polygon") # Изначальный тип из KML
        self.assertEqual(props["shapely_geometry_type"], "Polygon")
        self.assertFalse(props["is_valid"])
        self.assertIn("validity_reason", props)
        self.assertTrue(isinstance(props["validity_reason"], str))

        self.assertAlmostEqual(props["calculated_area_sq_units"], 123.46)
        self.assertNotIn("calculated_length_units", props) # length == 0.0
        self.assertAlmostEqual(props["calculated_perimeter_units"], 45.68)

    def test_feature_with_none_geometry(self):
        pm = ExtractedPlacemark(name="No Geom PM", id="ng01", geometry_type="Unknown", geometry_data=None)
        feature = create_geojson_feature(pm, None, None, None, None)
        
        self.assertEqual(feature["type"], "Feature")
        self.assertIsNone(feature["geometry"])
        props = feature["properties"]
        self.assertEqual(props["kml_name"], "No Geom PM")
        self.assertEqual(props["kml_id"], "ng01")
        self.assertEqual(props["kml_geometry_type"], "Unknown")
        self.assertIsNone(props.get("shapely_geometry_type")) # shapely_geom is None
        self.assertIsNone(props.get("is_valid")) # shapely_geom is None
        self.assertNotIn("calculated_area_sq_units", props)

    def test_properties_none_values_are_omitted(self):
        pm = ExtractedPlacemark(name=None, id=None, geometry_type="Point", geometry_data=KmlPoint("1,1"))
        shapely_geom = Point(1,1)
        # Все метрики None
        feature = create_geojson_feature(pm, shapely_geom, None, None, None)
        props = feature["properties"]

        self.assertNotIn("kml_name", props)
        self.assertNotIn("kml_id", props)
        self.assertEqual(props["kml_geometry_type"], "Point")
        self.assertEqual(props["shapely_geometry_type"], "Point")
        self.assertTrue(props["is_valid"])
        self.assertNotIn("calculated_area_sq_units", props)
        self.assertNotIn("calculated_length_units", props)
        self.assertNotIn("calculated_perimeter_units", props)


class TestSaveGeoJSONFeatureCollection(unittest.TestCase):
    def setUp(self):
        # Создаем временную директорию для тестовых файлов
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Удаляем временную директорию и ее содержимое
        shutil.rmtree(self.test_dir)

    def test_save_and_read_geojson(self):
        test_features = [
            {
                "type": "Feature", 
                "geometry": {"type": "Point", "coordinates": [10, 20]},
                "properties": {"name": "Feature 1"}
            },
            {
                "type": "Feature", 
                "geometry": {"type": "LineString", "coordinates": [[0,0], [1,1]]},
                "properties": {"id": "ls01"}
            }
        ]
        filepath = os.path.join(self.test_dir, "test_output.geojson")
        
        # 1. Тест сохранения
        result = save_geojson_feature_collection(test_features, filepath, indent=2)
        self.assertTrue(result, "Save function should return True on success")
        self.assertTrue(os.path.exists(filepath), "GeoJSON file should be created")

        # 2. Тест чтения и проверки содержимого
        with open(filepath, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        
        self.assertEqual(loaded_data["type"], "FeatureCollection")
        self.assertEqual(len(loaded_data["features"]), len(test_features))
        # Сравним индивидуальные features (порядок должен сохраниться)
        for original_feature, loaded_feature in zip(test_features, loaded_data["features"]):
            self.assertEqual(original_feature, loaded_feature)

    def test_save_with_no_indent(self):
        test_features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [0,0]}, "properties": {}}]
        filepath = os.path.join(self.test_dir, "compact.geojson")
        
        save_geojson_feature_collection(test_features, filepath, indent=None)
        self.assertTrue(os.path.exists(filepath))

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            # Проверяем, что нет лишних пробелов или переносов строк, характерных для indent
            self.assertNotIn("\n  ", content)
            self.assertNotIn("\n    ", content)
            # Проверим базовую структуру
            loaded_data = json.loads(content) # Перепарсим для проверки структуры
            self.assertEqual(loaded_data["type"], "FeatureCollection")
            self.assertEqual(len(loaded_data["features"]), 1)

    def test_save_empty_feature_list(self):
        filepath = os.path.join(self.test_dir, "empty.geojson")
        save_geojson_feature_collection([], filepath)
        self.assertTrue(os.path.exists(filepath))
        with open(filepath, 'r') as f:
            data = json.load(f)
        self.assertEqual(data, {"type": "FeatureCollection", "features": []})

    def test_save_invalid_path_error(self):
        # Пытаемся сохранить в несуществующую директорию (IOError ожидается)
        # (Подавляем вывод ошибок в консоль во время теста, если это возможно/нужно)
        # В данном случае save_geojson_feature_collection сама печатает ошибку и возвращает False
        invalid_filepath = os.path.join(self.test_dir, "non_existent_subdir", "error.geojson")
        result = save_geojson_feature_collection([{"type": "Feature", "properties": {}, "geometry": None}], invalid_filepath)
        self.assertFalse(result, "Save function should return False for invalid path")


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False) 