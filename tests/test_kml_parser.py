import unittest
from unittest.mock import patch, mock_open
import os
import io # Добавлено для BytesIO

# Добавляем путь к родительской директории, чтобы можно было импортировать scripts
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.kml_parser import load_kml_file, extract_placemark_geometries_recursive, get_kml_document_name
from scripts.data_structures import (
    ExtractedPlacemark, PointGeom, LineStringGeom, LinearRingGeom, 
    PolygonGeom, MultiGeometryGeom, SubGeometryData
)
# Для тестов нам могут понадобиться объекты pykml для создания мок-данных KML
from pykml.factory import KML_ElementMaker as KML
from pykml.parser import parse as original_pykml_parse_file # Для парсинга из BytesIO в тестах
from lxml import etree

# Пример простого KML для тестов
SIMPLE_KML_STRING_NO_DOC_NAME = """
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Placemark>
    <name>Test Placemark 1</name>
    <Point>
      <coordinates>10,20,0</coordinates>
    </Point>
  </Placemark>
</kml>
"""

SIMPLE_KML_STRING_WITH_DOC_NAME = """
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>My KML Document</name>
    <Placemark>
      <name>Test Placemark 2</name>
      <Point>
        <coordinates>30,40,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""

KML_WITH_FOLDER_AND_NESTED = """
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Document With Folders</name>
    <Folder>
      <name>Folder 1</name>
      <Placemark>
        <name>Placemark F1P1</name>
        <Point><coordinates>1,1</coordinates></Point>
      </Placemark>
      <Folder>
        <name>Folder 1.1</name>
        <Placemark>
          <name>Placemark F1.1P1</name>
          <Point><coordinates>2,2</coordinates></Point>
        </Placemark>
      </Folder>
    </Folder>
    <Placemark>
      <name>Placemark Root</name>
      <Point><coordinates>0,0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""

class TestKMLParser(unittest.TestCase):

    def _parse_kml_string_for_test(self, kml_string):
        """Вспомогательная функция для парсинга строки в корневой элемент KML."""
        kml_file_obj = io.BytesIO(kml_string.encode('utf-8'))
        # original_pykml_parse_file (pykml.parser.parse) возвращает ElementTree
        # Нам нужен корневой элемент для тестов
        return original_pykml_parse_file(kml_file_obj).getroot()

    def test_get_kml_document_name_present(self):
        kml_root_el = self._parse_kml_string_for_test(SIMPLE_KML_STRING_WITH_DOC_NAME)
        doc_name = get_kml_document_name(kml_root_el)
        self.assertEqual(doc_name, "My KML Document")

    def test_get_kml_document_name_absent(self):
        kml_root_el = self._parse_kml_string_for_test(SIMPLE_KML_STRING_NO_DOC_NAME)
        doc_name = get_kml_document_name(kml_root_el)
        # Если нет Document, но есть Placemark, функция должна это обработать корректно
        # get_kml_document_name вернет "No Document/Folder in KML" 
        # если не найдет Document или Folder с именем.
        self.assertEqual(doc_name, "No Document/Folder in KML")

    def test_get_kml_document_name_none_input(self):
        doc_name = get_kml_document_name(None)
        self.assertEqual(doc_name, "KML Root is None")

    @patch('builtins.open', new_callable=mock_open, read_data=SIMPLE_KML_STRING_WITH_DOC_NAME.encode('utf-8'))
    # Мокаем fromstring, используемый в load_kml_file
    @patch('scripts.kml_parser.pykml_parser.fromstring') 
    def test_load_kml_file_success(self, mock_pykml_fromstring, mock_file_open):
        # Настраиваем мок, чтобы он возвращал заранее созданный корневой элемент KML
        expected_kml_root_el = self._parse_kml_string_for_test(SIMPLE_KML_STRING_WITH_DOC_NAME)
        mock_pykml_fromstring.return_value = expected_kml_root_el
        
        filepath = "dummy_valid.kml"
        kml_root_from_load = load_kml_file(filepath)
        
        self.assertIsNotNone(kml_root_from_load)
        self.assertTrue(hasattr(kml_root_from_load, 'Document'))
        self.assertEqual(kml_root_from_load.Document.name, "My KML Document")
        mock_file_open.assert_called_once_with(filepath, 'rb')
        # pykml_parser.fromstring должен быть вызван с байтовым содержимым файла
        mock_pykml_fromstring.assert_called_once_with(SIMPLE_KML_STRING_WITH_DOC_NAME.encode('utf-8'))

    @patch('builtins.open', new_callable=mock_open, read_data="<kml><Invalid_XML_Not_KML></kml>".encode('utf-8'))
    @patch('scripts.kml_parser.pykml_parser.fromstring', side_effect=etree.XMLSyntaxError("Mocked XMLSyntaxError", "", 0, 0, 0))
    def test_load_kml_file_xml_syntax_error(self, mock_pykml_fromstring, mock_file_open):
        filepath = "dummy_syntax_error.kml"
        kml_root = load_kml_file(filepath)
        self.assertIsNone(kml_root)
        mock_file_open.assert_called_once_with(filepath, 'rb')
        mock_pykml_fromstring.assert_called_once_with("<kml><Invalid_XML_Not_KML></kml>".encode('utf-8'))

    @patch('builtins.open', side_effect=IOError("File not found"))
    def test_load_kml_file_io_error(self, mock_file_open):
        # Этот тест не должен вызывать fromstring, так как open упадет первым
        filepath = "non_existent.kml"
        kml_root = load_kml_file(filepath)
        self.assertIsNone(kml_root)
        mock_file_open.assert_called_once_with(filepath, 'rb')

    def test_extract_placemarks_simple_document(self):
        kml_root_el = self._parse_kml_string_for_test(SIMPLE_KML_STRING_WITH_DOC_NAME)
        # Передаем Document элемент в функцию
        placemarks = extract_placemark_geometries_recursive(kml_root_el.Document)
        self.assertEqual(len(placemarks), 1)
        self.assertEqual(placemarks[0].name, "Test Placemark 2")
        self.assertEqual(placemarks[0].geometry_type, "Point")
        self.assertIsInstance(placemarks[0].geometry_data, PointGeom)
        self.assertEqual(placemarks[0].geometry_data.coordinates, "30,40,0")

    def test_extract_placemarks_from_root_kml_no_document(self):
        kml_root_el = self._parse_kml_string_for_test(SIMPLE_KML_STRING_NO_DOC_NAME)
        # Передаем сам корневой элемент <kml> (который не Document и не Folder)
        placemarks = extract_placemark_geometries_recursive(kml_root_el)
        self.assertEqual(len(placemarks), 1)
        self.assertEqual(placemarks[0].name, "Test Placemark 1")
        self.assertEqual(placemarks[0].geometry_type, "Point")

    def test_extract_placemarks_with_folders_and_nested(self):
        kml_root_el = self._parse_kml_string_for_test(KML_WITH_FOLDER_AND_NESTED)
        placemarks = extract_placemark_geometries_recursive(kml_root_el.Document)
        
        self.assertEqual(len(placemarks), 3)
        names = sorted([pm.name for pm in placemarks])
        expected_names = sorted(["Placemark F1P1", "Placemark F1.1P1", "Placemark Root"])
        self.assertEqual(names, expected_names)

        pm_root = next(p for p in placemarks if p.name == "Placemark Root")
        self.assertEqual(pm_root.geometry_data.coordinates, "0,0")
        
        pm_f11p1 = next(p for p in placemarks if p.name == "Placemark F1.1P1")
        self.assertEqual(pm_f11p1.geometry_data.coordinates, "2,2")

    def test_extract_placemarks_no_placemarks(self):
        kml_string = """
        <kml xmlns="http://www.opengis.net/kml/2.2">
          <Document>
            <name>Empty Document</name>
            <Folder>
                <name>Empty Folder</name>
            </Folder>
          </Document>
        </kml>
        """
        kml_root_el = self._parse_kml_string_for_test(kml_string)
        placemarks = extract_placemark_geometries_recursive(kml_root_el.Document)
        self.assertEqual(len(placemarks), 0)

    def test_extract_placemarks_various_geometry_types(self):
        kml_string_various = """
        <kml xmlns="http://www.opengis.net/kml/2.2">
          <Document>
            <name>Various Geometries</name>
            <Placemark id="pm_point">
              <name>Point1</name>
              <Point><coordinates>1,1</coordinates></Point>
            </Placemark>
            <Placemark id="pm_ls">
              <name>LineString1</name>
              <LineString><coordinates>2,2 3,3</coordinates></LineString>
            </Placemark>
            <Placemark id="pm_poly">
              <name>Polygon1</name>
              <Polygon><outerBoundaryIs><LinearRing><coordinates>4,4 5,4 5,5 4,5 4,4</coordinates></LinearRing></outerBoundaryIs></Polygon>
            </Placemark>
            <Placemark id="pm_multi">
                <name>MultiGeom1</name>
                <MultiGeometry>
                    <Point><coordinates>6,6</coordinates></Point>
                    <LineString><coordinates>7,7 8,8</coordinates></LineString>
                </MultiGeometry>
            </Placemark>
          </Document>
        </kml>
        """
        kml_root_el = self._parse_kml_string_for_test(kml_string_various)
        placemarks = extract_placemark_geometries_recursive(kml_root_el.Document)
        self.assertEqual(len(placemarks), 4)

        pm_point = next(p for p in placemarks if p.id == "pm_point")
        self.assertEqual(pm_point.geometry_type, "Point")
        self.assertIsInstance(pm_point.geometry_data, PointGeom)
        self.assertEqual(pm_point.geometry_data.coordinates, "1,1")

        pm_ls = next(p for p in placemarks if p.id == "pm_ls")
        self.assertEqual(pm_ls.geometry_type, "LineString")
        self.assertIsInstance(pm_ls.geometry_data, LineStringGeom)
        self.assertEqual(pm_ls.geometry_data.coordinates, "2,2 3,3")

        pm_poly = next(p for p in placemarks if p.id == "pm_poly")
        self.assertEqual(pm_poly.geometry_type, "Polygon")
        self.assertIsInstance(pm_poly.geometry_data, PolygonGeom)
        self.assertEqual(pm_poly.geometry_data.outer_boundary.coordinates, "4,4 5,4 5,5 4,5 4,4")
        
        pm_multi = next(p for p in placemarks if p.id == "pm_multi")
        self.assertEqual(pm_multi.geometry_type, "MultiGeometry")
        self.assertIsInstance(pm_multi.geometry_data, MultiGeometryGeom)
        self.assertEqual(len(pm_multi.geometry_data.geometries), 2)
        self.assertEqual(pm_multi.geometry_data.geometries[0].type, "Point")
        self.assertTrue(isinstance(pm_multi.geometry_data.geometries[0].data, PointGeom))
        self.assertEqual(pm_multi.geometry_data.geometries[0].data.coordinates, "6,6")
        self.assertEqual(pm_multi.geometry_data.geometries[1].type, "LineString")
        self.assertTrue(isinstance(pm_multi.geometry_data.geometries[1].data, LineStringGeom))
        self.assertEqual(pm_multi.geometry_data.geometries[1].data.coordinates, "7,7 8,8")
        

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False) 