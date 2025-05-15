import unittest
from unittest.mock import patch, Mock
import requests # Нужен для requests.exceptions

# Путь нужно будет настроить в зависимости от того, как запускаются тесты,
# или использовать относительные импорты, если структура проекта позволяет.
# Для простоты предположим, что scripts в PYTHONPATH или используется python -m
from scripts.pkk_api_client import make_api_request, DEFAULT_TIMEOUT, DEFAULT_HEADERS

# Добавляем импорты для тестируемых функций и моков
from scripts.pkk_api_client import search_cadastral_data_by_text, NSPD_GEOPORTAL_API_URL, DEFAULT_USER_AGENT
from scripts.data_structures import NSPDCadastralFeature # Нужен для проверки типа результата

# Добавляем тестируемую функцию
from scripts.pkk_api_client import parse_nspd_feature

# Пример успешного ответа от NSPD API (для мока)
MOCK_NSPD_SUCCESS_RESPONSE_ONE_FEATURE = {
    "data": {
        "features": [
            {
                "id": "12345",
                "type": "Feature",
                "properties": {"descr": "Test Object 1"},
                "geometry": {"type": "Point", "coordinates": [30, 50]}
            }
        ]
    }
}

MOCK_NSPD_SUCCESS_RESPONSE_NO_FEATURES = {
    "data": {
        "features": []
    }
}

MOCK_NSPD_SUCCESS_RESPONSE_DATA_NULL_FEATURES = {
    "data": {
        "features": None # Такое тоже бывает
    }
}

MOCK_NSPD_SUCCESS_RESPONSE_NO_DATA_KEY = {
    "features": [] # Отсутствует ключ data
}

MOCK_NSPD_SUCCESS_RESPONSE_FEATURES_NOT_LIST = {
    "data": {
        "features": "не список" 
    }
}

class TestMakeApiRequest(unittest.TestCase):

    @patch('scripts.pkk_api_client.requests.request')
    def test_successful_get_request(self, mock_request):
        """Тест успешного GET запроса."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"key": "value"}'
        mock_response.json.return_value = {"key": "value"}
        mock_response.ok = True
        mock_request.return_value = mock_response

        base_url = "http://example.com"
        endpoint = "api/data"
        
        json_data, status_code, error = make_api_request(base_url, endpoint, method="GET")

        mock_request.assert_called_once_with(
            "GET",
            f"{base_url}/{endpoint}",
            params=None,
            data=None,
            json=None,
            headers=DEFAULT_HEADERS,
            verify=True,
            allow_redirects=True,
            timeout=DEFAULT_TIMEOUT
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(json_data, {"key": "value"})
        self.assertIsNone(error)

    @patch('scripts.pkk_api_client.requests.request')
    def test_successful_post_request_with_json_data(self, mock_request):
        """Тест успешного POST запроса с JSON телом."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.text = '{"id": 1, "message": "created"}'
        mock_response.json.return_value = {"id": 1, "message": "created"}
        mock_response.ok = True
        mock_request.return_value = mock_response

        base_url = "http://example.com"
        endpoint = "api/create"
        payload = {"name": "test_object"}
        custom_headers = {"X-Custom-Header": "TestValue"}
        
        expected_headers = DEFAULT_HEADERS.copy()
        expected_headers.update(custom_headers)

        json_data, status_code, error = make_api_request(
            base_url, 
            endpoint, 
            method="POST", 
            json_data=payload,
            headers=custom_headers,
            verify_ssl=False,
            allow_redirects=False,
            timeout=15
        )

        mock_request.assert_called_once_with(
            "POST",
            f"{base_url}/{endpoint}",
            params=None,
            data=None,
            json=payload,
            headers=expected_headers,
            verify=False, 
            allow_redirects=False,
            timeout=15
        )
        self.assertEqual(status_code, 201)
        self.assertEqual(json_data, {"id": 1, "message": "created"})
        self.assertIsNone(error)

    @patch('scripts.pkk_api_client.requests.request')
    def test_http_error_404(self, mock_request):
        """Тест обработки HTTP ошибки 404."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = '{"error": "Not Found"}'
        mock_response.ok = False
        # raise_for_status должен сгенерировать HTTPError
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Client Error")
        mock_request.return_value = mock_response

        base_url = "http://example.com"
        endpoint = "api/nonexistent"
        
        json_data, status_code, error = make_api_request(base_url, endpoint)

        self.assertEqual(status_code, 404)
        self.assertIsNone(json_data)
        self.assertIsNotNone(error)
        self.assertIn("HTTP ошибка: 404 Client Error", error)
        self.assertIn('Ответ: {"error": "Not Found"}', error)


    @patch('scripts.pkk_api_client.requests.request')
    def test_json_decode_error(self, mock_request):
        """Тест обработки ошибки декодирования JSON."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'Невалидный JSON' # Это вызовет JSONDecodeError
        mock_response.ok = True
        mock_response.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "doc", 0)
        mock_request.return_value = mock_response
        
        base_url = "http://example.com"
        endpoint = "api/badjson"

        json_data, status_code, error = make_api_request(base_url, endpoint)

        self.assertEqual(status_code, 200)
        self.assertIsNone(json_data)
        self.assertIsNotNone(error)
        self.assertIn("Ошибка декодирования JSON", error)
        self.assertIn("Ответ: Невалидный JSON", error)

    @patch('scripts.pkk_api_client.requests.request')
    def test_request_exception_connection_error(self, mock_request):
        """Тест обработки общей ошибки запроса (например, ConnectionError)."""
        mock_request.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        base_url = "http://unreachable-example.com"
        endpoint = "api/data"

        json_data, status_code, error = make_api_request(base_url, endpoint)
        
        # status_code может быть None в этом случае, если ошибка произошла до получения ответа
        self.assertIsNone(status_code) 
        self.assertIsNone(json_data)
        self.assertIsNotNone(error)
        self.assertIn("Ошибка запроса: Connection failed", error)

    @patch('scripts.pkk_api_client.requests.request')
    def test_empty_response_text_on_success(self, mock_request):
        """Тест успешного ответа с пустым телом (например, 204 No Content)."""
        mock_response = Mock()
        mock_response.status_code = 204
        mock_response.text = '' # Пустое тело
        mock_response.ok = True
        # .json() не должен вызываться, если text пустой
        mock_request.return_value = mock_response

        base_url = "http://example.com"
        endpoint = "api/empty"
        
        json_data, status_code, error = make_api_request(base_url, endpoint)

        self.assertEqual(status_code, 204)
        self.assertEqual(json_data, {}) # Ожидаем пустой словарь для успешного пустого ответа
        self.assertIsNone(error)
        mock_response.json.assert_not_called() # Убедимся, что .json() не вызывался

    @patch('scripts.pkk_api_client.requests.request')
    def test_empty_url_endpoint(self, mock_request):
        """Тест, когда endpoint пустой, используется только base_url."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"key": "value"}'
        mock_response.json.return_value = {"key": "value"}
        mock_response.ok = True
        mock_request.return_value = mock_response

        base_url = "http://example.com/api/fulldata" # base_url уже содержит полный путь
        endpoint = "" 
        
        json_data, status_code, error = make_api_request(base_url, endpoint)

        mock_request.assert_called_once_with(
            "GET",
            base_url, # Ожидается, что будет вызван только base_url
            params=None, data=None, json=None, headers=DEFAULT_HEADERS,
            verify=True, allow_redirects=True, timeout=DEFAULT_TIMEOUT
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(json_data, {"key": "value"})
        self.assertIsNone(error)

class TestSearchCadastralDataByText(unittest.TestCase):

    @patch('scripts.pkk_api_client.make_api_request')
    @patch('scripts.pkk_api_client.parse_nspd_feature') # Мокаем парсер отдельных фич
    def test_successful_search_one_feature(self, mock_parse_nspd_feature, mock_make_api_request):
        """Тест успешного поиска, найдена одна фича."""
        mock_make_api_request.return_value = (MOCK_NSPD_SUCCESS_RESPONSE_ONE_FEATURE, 200, None)
        
        # Настроим мок parse_nspd_feature, чтобы он возвращал мок-объект NSPDCadastralFeature
        # когда вызывается с ожидаемым словарем фичи
        expected_raw_feature_dict = MOCK_NSPD_SUCCESS_RESPONSE_ONE_FEATURE["data"]["features"][0]
        mock_parsed_feature = Mock(spec=NSPDCadastralFeature) # Создаем мок с сигнатурой NSPDCadastralFeature
        mock_parse_nspd_feature.return_value = mock_parsed_feature

        search_text = "some_query"
        features, error = search_cadastral_data_by_text(search_text)

        mock_make_api_request.assert_called_once_with(
            base_url=NSPD_GEOPORTAL_API_URL,
            endpoint="",
            method="GET",
            params={"query": search_text},
            headers={"User-Agent": DEFAULT_USER_AGENT},
            verify_ssl=False,
            allow_redirects=True
        )
        mock_parse_nspd_feature.assert_called_once_with(expected_raw_feature_dict)
        self.assertIsNone(error)
        self.assertIsNotNone(features)
        self.assertEqual(len(features), 1)
        self.assertIsInstance(features[0], Mock) # Проверяем, что это наш мокнутый NSPDCadastralFeature
        self.assertEqual(features[0], mock_parsed_feature)

    @patch('scripts.pkk_api_client.make_api_request')
    def test_search_api_returns_error(self, mock_make_api_request):
        """Тест, когда make_api_request возвращает ошибку."""
        mock_make_api_request.return_value = (None, 500, "Internal Server Error")

        search_text = "error_query"
        features, error = search_cadastral_data_by_text(search_text)

        self.assertIsNone(features)
        self.assertIsNotNone(error)
        self.assertEqual(error, "Internal Server Error")

    @patch('scripts.pkk_api_client.make_api_request')
    def test_search_no_features_found(self, mock_make_api_request):
        """Тест, когда API возвращает пустой список features."""
        mock_make_api_request.return_value = (MOCK_NSPD_SUCCESS_RESPONSE_NO_FEATURES, 200, None)

        search_text = "empty_query"
        features, error = search_cadastral_data_by_text(search_text)

        self.assertIsNone(error)
        self.assertIsNotNone(features)
        self.assertEqual(len(features), 0)

    @patch('scripts.pkk_api_client.make_api_request')
    def test_search_features_is_none(self, mock_make_api_request):
        """Тест, когда API возвращает features: null."""
        mock_make_api_request.return_value = (MOCK_NSPD_SUCCESS_RESPONSE_DATA_NULL_FEATURES, 200, None)

        search_text = "null_features_query"
        features, error = search_cadastral_data_by_text(search_text)

        self.assertIsNone(error)
        self.assertIsNotNone(features)
        self.assertEqual(len(features), 0) # Должен вернуть пустой список, а не ошибку

    @patch('scripts.pkk_api_client.make_api_request')
    def test_search_no_data_key_in_response(self, mock_make_api_request):
        """Тест, когда в ответе API отсутствует ключ 'data'."""
        mock_make_api_request.return_value = (MOCK_NSPD_SUCCESS_RESPONSE_NO_DATA_KEY, 200, None)

        search_text = "no_data_key_query"
        features, error = search_cadastral_data_by_text(search_text)

        self.assertIsNone(features)
        self.assertIsNotNone(error)
        self.assertIn("Ответ API не содержит 'data'", error)

    @patch('scripts.pkk_api_client.make_api_request')
    def test_search_features_not_a_list(self, mock_make_api_request):
        """Тест, когда 'features' в ответе API не является списком."""
        mock_make_api_request.return_value = (MOCK_NSPD_SUCCESS_RESPONSE_FEATURES_NOT_LIST, 200, None)

        search_text = "features_not_list_query"
        features, error = search_cadastral_data_by_text(search_text)

        self.assertIsNone(features)
        self.assertIsNotNone(error)
        self.assertIn("Некорректный тип для 'features'", error)

    @patch('scripts.pkk_api_client.make_api_request')
    @patch('scripts.pkk_api_client.parse_nspd_feature')
    def test_search_one_feature_fails_to_parse(self, mock_parse_nspd_feature, mock_make_api_request):
        """Тест, когда одна из фич не может быть распарсена."""
        mock_make_api_request.return_value = (MOCK_NSPD_SUCCESS_RESPONSE_ONE_FEATURE, 200, None)
        mock_parse_nspd_feature.return_value = None # Имитируем ошибку парсинга

        search_text = "parse_fail_query"
        features, error = search_cadastral_data_by_text(search_text)

        self.assertIsNone(error)
        self.assertIsNotNone(features)
        self.assertEqual(len(features), 0) # Ожидаем пустой список, т.к. единственная фича не распарсилась

class TestParseNspdFeature(unittest.TestCase):

    def test_parse_full_valid_feature(self):
        """Тест парсинга полностью корректного feature."""
        raw_feature = {
            "id": "test_id_123",
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [10.0, 20.0],
                "crs": {"type": "name", "properties": {"name": "EPSG:4326"}}
            },
            "properties": {
                "descr": "Test Description",
                "categoryName": "Test Category",
                "label": "Test Label",
                "externalKey": "ext_key",
                "interactionId": 987,
                "score": 0.5,
                "subcategory": 17,
                "options": {
                    "cad_num": "12:34:567890:123",
                    "readable_address": "123 Test St",
                    "area": 100.5,
                    "custom_field": "custom_value" # Дополнительное поле
                }
            }
        }
        parsed = parse_nspd_feature(raw_feature)
        self.assertIsNotNone(parsed)
        self.assertIsInstance(parsed, NSPDCadastralFeature)
        self.assertEqual(parsed.nspd_id, "test_id_123")
        self.assertEqual(parsed.type, "Feature")
        # Проверка геометрии
        self.assertIsNotNone(parsed.geometry)
        self.assertEqual(parsed.geometry.type, "Point")
        self.assertEqual(parsed.geometry.coordinates, [10.0, 20.0])
        self.assertIsNotNone(parsed.geometry.crs)
        self.assertEqual(parsed.geometry.crs.name, "EPSG:4326")
        # Проверка основных свойств
        self.assertIsNotNone(parsed.main_properties)
        self.assertEqual(parsed.main_properties.descr, "Test Description")
        self.assertEqual(parsed.main_properties.categoryName, "Test Category")
        # Проверка опциональных свойств
        self.assertIsNotNone(parsed.options_properties)
        self.assertEqual(parsed.options_properties.cad_num, "12:34:567890:123")
        self.assertEqual(parsed.options_properties.readable_address, "123 Test St")
        self.assertEqual(parsed.options_properties.area, 100.5)
        self.assertIn("custom_field", parsed.options_properties.other_options)
        self.assertEqual(parsed.options_properties.other_options["custom_field"], "custom_value")
        # Проверка сохранения сырого словаря
        self.assertEqual(parsed.raw_feature_dict, raw_feature)

    def test_parse_feature_with_missing_optional_fields(self):
        """Тест парсинга, когда некоторые опциональные поля отсутствуют."""
        raw_feature = {
            "id": "minimal_id",
            "type": "Feature",
            "properties": {
                "descr": "Minimal Description"
                # options, geometry, categoryName и т.д. отсутствуют
            }
        }
        parsed = parse_nspd_feature(raw_feature)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.nspd_id, "minimal_id")
        self.assertIsNone(parsed.geometry)
        self.assertIsNotNone(parsed.main_properties)
        self.assertEqual(parsed.main_properties.descr, "Minimal Description")
        self.assertIsNone(parsed.main_properties.categoryName)
        self.assertIsNotNone(parsed.options_properties) # Ожидаем объект
        self.assertIsNone(parsed.options_properties.cad_num) # Поля должны быть None
        self.assertEqual(parsed.options_properties.other_options, {}) # other_options пустой

    def test_parse_feature_with_empty_options_and_geometry(self):
        """Тест парсинга с пустыми, но существующими dicts для options и geometry."""
        raw_feature = {
            "id": "empty_dicts_id",
            "type": "Feature",
            "geometry": {},
            "properties": {
                "options": {}
            }
        }
        parsed = parse_nspd_feature(raw_feature)
        self.assertIsNotNone(parsed)
        self.assertIsNotNone(parsed.geometry) # Должен создаться объект NSPDCadastralObjectGeometry
        self.assertIsNone(parsed.geometry.type) # ...но его поля будут None
        self.assertIsNotNone(parsed.options_properties) # Должен создаться объект NSPDCadastralObjectOptions
        self.assertIsNone(parsed.options_properties.cad_num) # ...но его поля будут None
        self.assertEqual(parsed.options_properties.other_options, {}) # other_options будет пустым dict

    def test_parse_invalid_input_not_dict(self):
        """Тест с некорректным типом входных данных (не словарь)."""
        parsed = parse_nspd_feature("Это не словарь")
        self.assertIsNone(parsed)

    def test_parse_empty_dict_input(self):
        """Тест с пустым словарем на входе."""
        parsed = parse_nspd_feature({})
        self.assertIsNotNone(parsed) # Должен вернуть объект, но все поля будут None или default
        self.assertIsNone(parsed.nspd_id)
        self.assertIsNone(parsed.type)
        self.assertIsNone(parsed.geometry)      # geometry будет None
        self.assertIsNotNone(parsed.main_properties) # main_properties - объект, поля None
        self.assertIsNone(parsed.main_properties.descr)
        self.assertIsNotNone(parsed.options_properties) # options_properties - объект, поля None
        self.assertIsNone(parsed.options_properties.cad_num)
        self.assertEqual(parsed.options_properties.other_options, {}) # other_options пустой

    def test_parse_feature_geometry_not_dict(self):
        """Тест, когда geometry не является словарем."""
        raw_feature = {
            "id": "geom_not_dict",
            "geometry": "не словарь"
        }
        parsed = parse_nspd_feature(raw_feature)
        self.assertIsNotNone(parsed)
        self.assertIsNone(parsed.geometry) # Геометрия не должна парситься

    def test_parse_feature_properties_not_dict(self):
        """Тест, когда properties не является словарем."""
        raw_feature = {
            "id": "props_not_dict",
            "properties": "не словарь"
        }
        parsed = parse_nspd_feature(raw_feature)
        self.assertIsNone(parsed) # Ожидаем None из-за исключения при парсинге

    def test_parse_feature_options_not_dict(self):
        """Тест, когда properties.options не является словарем."""
        raw_feature = {
            "id": "options_not_dict",
            "properties": {
                "options": "не словарь"
            }
        }
        parsed = parse_nspd_feature(raw_feature)
        self.assertIsNotNone(parsed)
        self.assertIsNotNone(parsed.main_properties) # main_properties должно быть, т.к. properties есть
        self.assertIsNone(parsed.options_properties) # options не распарсится

if __name__ == '__main__':
    unittest.main() 