import unittest
from unittest.mock import patch, mock_open, MagicMock, call
import os
import sys
from click.testing import CliRunner

# Добавляем путь к родительской директории для импорта модулей проекта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kadastr_cli import cli
from scripts.data_structures import ExtractedPlacemark, PointGeom
from scripts.geometry_processing import DEFAULT_PRECISION # Оставляем только DEFAULT_PRECISION

class TestKadastrCli(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    @patch('kadastr_cli.load_kml_file')
    @patch('kadastr_cli.extract_placemark_geometries_recursive')
    @patch('kadastr_cli.get_kml_document_name')
    @patch('kadastr_cli.kml_placemark_to_shapely')
    @patch('kadastr_cli.calculate_area')
    @patch('kadastr_cli.calculate_length')
    @patch('kadastr_cli.calculate_perimeter')
    @patch('kadastr_cli.create_geojson_feature')
    @patch('kadastr_cli.save_geojson_feature_collection')
    @patch('kadastr_cli.os.path.exists')
    def test_process_kmls_single_file_no_output(self, mock_os_path_exists, mock_save_geojson, mock_create_feature, 
                                               mock_calc_perimeter, mock_calc_length, mock_calc_area, 
                                               mock_to_shapely, mock_get_doc_name, mock_extract_placemarks, 
                                               mock_load_kml):
        mock_os_path_exists.return_value = True
        mock_kml_root = MagicMock()
        mock_kml_root.Document.name.text = "TestKMLDoc"
        mock_load_kml.return_value = mock_kml_root
        mock_get_doc_name.return_value = "TestKMLDocName"
        placemark_data = ExtractedPlacemark(
            name="TestPlacemark", id="p1", geometry_type="Point", 
            geometry_data=PointGeom(coordinates="10,20,0"),
            raw_kml_placemark_obj=MagicMock()
        )
        mock_extract_placemarks.return_value = [placemark_data]
        mock_shapely_geom = MagicMock()
        mock_shapely_geom.is_valid = True
        mock_shapely_geom.wkt = "POINT (10 20)"
        mock_to_shapely.return_value = mock_shapely_geom
        mock_calc_area.return_value = 0.0
        mock_calc_length.return_value = 0.0
        mock_calc_perimeter.return_value = 0.0
        mock_geojson_feature = {"type": "Feature", "properties": {}, "geometry": None}
        mock_create_feature.return_value = mock_geojson_feature

        kml_file_path = 'test1.kml'
        result = self.runner.invoke(cli, ['process-kmls', '-k', kml_file_path])

        self.assertEqual(result.exit_code, 0)
        self.assertIn(call(kml_file_path), mock_os_path_exists.call_args_list)
        mock_load_kml.assert_called_once_with(kml_file_path)
        mock_get_doc_name.assert_called_once_with(mock_kml_root)
        self.assertTrue(hasattr(mock_kml_root, 'Document'))
        mock_extract_placemarks.assert_called_once_with(mock_kml_root.Document)
        mock_to_shapely.assert_called_once_with(placemark_data, precision=DEFAULT_PRECISION)
        mock_calc_area.assert_called_with(mock_shapely_geom)
        mock_calc_length.assert_called_with(mock_shapely_geom)
        mock_calc_perimeter.assert_called_with(mock_shapely_geom)
        mock_create_feature.assert_called_once()
        default_output_path = 'test1.geojson'
        mock_save_geojson.assert_called_once_with([mock_geojson_feature], default_output_path, indent=2)

        self.assertIn(f"Processing KML file: {kml_file_path}", result.output)
        self.assertIn("KML Document Name: TestKMLDocName", result.output)
        self.assertIn("Name: TestPlacemark", result.output)
        self.assertIn("ID: p1", result.output)
        self.assertIn("Type: Point", result.output)
        self.assertIn("Coordinates: 10,20,0", result.output)
        self.assertIn("Shapely WKT: POINT (10 20)", result.output)

    @patch('kadastr_cli.load_kml_file')
    @patch('kadastr_cli.extract_placemark_geometries_recursive')
    @patch('kadastr_cli.get_kml_document_name')
    @patch('kadastr_cli.kml_placemark_to_shapely')
    @patch('kadastr_cli.create_geojson_feature')
    @patch('kadastr_cli.save_geojson_feature_collection')
    @patch('kadastr_cli.os.path.exists')
    @patch('kadastr_cli.calculate_area')
    @patch('kadastr_cli.calculate_length')
    @patch('kadastr_cli.calculate_perimeter')
    def test_process_kmls_with_geojson_output(self,
                                                mock_calc_perimeter,
                                                mock_calc_length,
                                                mock_calc_area,
                                                mock_os_path_exists,
                                                mock_save_geojson,
                                                mock_create_feature,
                                                mock_to_shapely,
                                                mock_get_doc_name,
                                                mock_extract_placemarks,
                                                mock_load_kml):
        mock_os_path_exists.return_value = True
        mock_kml_root = MagicMock()
        mock_load_kml.return_value = mock_kml_root
        mock_get_doc_name.return_value = "TestDoc"
        placemark_data = ExtractedPlacemark(name="P1", id="p1", geometry_type="Point", geometry_data=PointGeom(coordinates="0,0"), raw_kml_placemark_obj=MagicMock())
        mock_extract_placemarks.return_value = [placemark_data]
        mock_shapely_geom = MagicMock(is_valid=True)
        mock_to_shapely.return_value = mock_shapely_geom
        mock_calc_area.return_value = 123.45
        mock_calc_length.return_value = 67.89
        mock_calc_perimeter.return_value = 101.12
        mock_geojson_feature = {"type": "Feature"}
        mock_create_feature.return_value = mock_geojson_feature
        mock_save_geojson.return_value = True

        kml_file_path = 'input.kml'
        output_geojson_path = 'output.geojson'
        
        result = self.runner.invoke(cli, ['process-kmls', '-k', kml_file_path, '--output-geojson', output_geojson_path, '--geojson-indent', '2'])
        
        self.assertEqual(result.exit_code, 0, msg=f"CLI exited with {result.exit_code}, output: {result.output}")
        self.assertIn(call(kml_file_path), mock_os_path_exists.call_args_list)
        
        mock_to_shapely.assert_called_with(placemark_data, precision=DEFAULT_PRECISION)
        mock_calc_area.assert_called_with(mock_shapely_geom)
        mock_calc_length.assert_called_with(mock_shapely_geom)
        mock_calc_perimeter.assert_called_with(mock_shapely_geom)
        mock_create_feature.assert_called_with(
            placemark_data=placemark_data, 
            shapely_geom=mock_shapely_geom, 
            area=123.45, 
            length=67.89, 
            perimeter=101.12, 
            precision=DEFAULT_PRECISION
        )
        
        expected_output_path = os.path.abspath(output_geojson_path)
        mock_save_geojson.assert_called_once_with([mock_geojson_feature], expected_output_path, indent=2)
        self.assertIn(f"Saving 1 features to GeoJSON: {expected_output_path}", result.output)
        self.assertIn("GeoJSON successfully saved.", result.output)

    def test_process_kmls_kml_file_not_found(self):
        kml_file_path = 'nonexistent.kml'
        with patch('kadastr_cli.os.path.exists', return_value=False) as mock_exists:
            result = self.runner.invoke(cli, ['process-kmls', '-k', kml_file_path])
            self.assertEqual(result.exit_code, 0)
            self.assertIn(call(kml_file_path), mock_exists.call_args_list)
            self.assertIn(f"Error: KML file not found: {kml_file_path}", result.output)

    def test_process_kmls_no_kml_files_provided(self):
        result = self.runner.invoke(cli, ['process-kmls']) # Не передаем -k
        # Click должен сам обработать отсутствие обязательного параметра
        self.assertNotEqual(result.exit_code, 0) # Ожидаем ошибку, так как -k обязательный
        self.assertIn("Missing option '-k' / '--kml-files'", result.output)

    @patch('kadastr_cli.load_kml_file', return_value=None)
    @patch('kadastr_cli.os.path.exists', return_value=True)
    def test_process_kmls_load_kml_fails(self, mock_os_path_exists, mock_load_kml):
        kml_file_path = 'bad_kml.kml'
        result = self.runner.invoke(cli, ['process-kmls', '-k', kml_file_path])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(call(kml_file_path), mock_os_path_exists.call_args_list)
        mock_load_kml.assert_called_once_with(kml_file_path)
        self.assertIn(f"Error: Could not load or parse KML file: {kml_file_path}", result.output)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False) 