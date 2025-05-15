import requests
import logging
from typing import Dict, Any, Optional, Tuple, List
import urllib3 # Для подавления InsecureRequestWarning - новый вариант
from urllib3.exceptions import InsecureRequestWarning

# Импорт датаклассов
from scripts.data_structures import (
    NSPDCrsProperties,
    NSPDCadastralObjectGeometry,
    NSPDCadastralObjectOptions,
    NSPDCadastralObjectPropertiesMain,
    NSPDCadastralFeature
)

# Импорт функции конвертации геометрии и расчета метрик
from scripts.geometry_processing import (
    nspd_geometry_to_shapely, 
    DEFAULT_PLANAR_CRS,
    calculate_area,
    calculate_length,
    calculate_perimeter
)

# Подавляем InsecureRequestWarning глобально, если SSL проверка отключена где-либо
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Настройка логирования
logger = logging.getLogger(__name__)

# Базовый URL для API Росреестра (PKK)
# Это предположение, нужно будет уточнить на основе Задачи 2 и Директивы.md
PKK_API_BASE_URL = "https://pkk.rosreestr.ru/api/"

# Кастомный User-Agent для обхода блокировок
# (взят из успешных тестов в Задаче 2)
CUSTOM_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"

DEFAULT_HEADERS = {
    "User-Agent": CUSTOM_USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

# Таймаут для запросов по умолчанию (в секундах)
DEFAULT_TIMEOUT = 30

# Новые константы
NSPD_GEOPORTAL_API_URL = "https://nspd.gov.ru/api/geoportal/v2/search/geoportal"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

def make_api_request(
    base_url: str,
    endpoint: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,  # Добавлен параметр для JSON тела
    headers: Optional[Dict[str, str]] = None,
    verify_ssl: bool = True,
    allow_redirects: bool = True,
    timeout: int = DEFAULT_TIMEOUT
) -> Tuple[Optional[Dict[str, Any]], Optional[int], Optional[str]]:
    full_url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    # Убираем лишний слэш, если endpoint пустой
    if not endpoint:
        full_url = base_url

    effective_headers = DEFAULT_HEADERS.copy()
    if headers:
        effective_headers.update(headers)

    logger.debug(f"Выполнение {method} запроса к {full_url} с параметрами: {params}, данными: {data}, json: {json_data}")
    response_text = None
    status_code_val = None
    try:
        response = requests.request(
            method,
            full_url,
            params=params,
            data=data,
            json=json_data,
            headers=effective_headers,
            verify=verify_ssl,
            allow_redirects=allow_redirects,
            timeout=timeout
        )
        response_text = response.text
        status_code_val = response.status_code
        response.raise_for_status()  # Проверка на HTTP ошибки (4xx и 5xx)
        
        # Попытка декодировать JSON, если статус код успешный (2xx)
        # Некоторые API могут возвращать пустой ответ с кодом 200 или 204, что не является ошибкой JSON
        if not response_text and response.ok:
            return {}, status_code_val, None # Успешно, но пустое тело
        if not response_text and not response.ok:
             return None, status_code_val, f"HTTP {status_code_val} with empty response body."

        return response.json(), status_code_val, None

    except requests.exceptions.HTTPError as http_err:
        error_message = f"HTTP ошибка: {http_err}. URL: {full_url}. Ответ: {response_text[:500] if response_text else 'N/A'}"
        logger.error(error_message)
        return None, status_code_val, error_message
    except requests.exceptions.JSONDecodeError as json_err:
        error_message = f"Ошибка декодирования JSON: {json_err}. URL: {full_url}. Ответ: {response_text[:500] if response_text else 'N/A'}"
        logger.error(error_message)
        return None, status_code_val, error_message
    except requests.exceptions.RequestException as req_err:
        error_message = f"Ошибка запроса: {req_err}. URL: {full_url}"
        logger.error(error_message)
        # В этом случае status_code_val может быть None, если запрос не дошел до сервера
        return None, status_code_val, error_message
    except Exception as e: # Отлов всех остальных непредвиденных ошибок
        error_message = f"Неожиданная ошибка при запросе к {full_url}: {e}"
        logger.exception(error_message) # Используем logger.exception для вывода стека вызовов
        return None, status_code_val, error_message

def search_cadastral_data_by_text(search_text: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    Выполняет поиск кадастровых данных по текстовому запросу (например, кадастровому номеру)
    через API nspd.gov.ru.

    Args:
        search_text: Текст для поиска (например, "69:27:0000021:400").

    Returns:
        Кортеж: (список найденных features, сообщение об ошибке или None).
              None в первом элементе, если произошла ошибка или ничего не найдено.
    """
    logger.info(f"Поиск кадастровых данных по запросу: '{search_text}'")
    
    params = {"query": search_text}
    
    json_response, status_code, error = make_api_request(
        base_url=NSPD_GEOPORTAL_API_URL,
        endpoint="", # API URL уже полный
        method="GET",
        params=params,
        headers={"User-Agent": DEFAULT_USER_AGENT},
        verify_ssl=False, # Отключаем проверку SSL для nspd.gov.ru
        allow_redirects=True
    )

    if error:
        logger.error(f"Ошибка при поиске данных для '{search_text}': {error}. Статус: {status_code}")
        return None, error

    if not json_response:
        logger.warning(f"Пустой JSON ответ от API для запроса '{search_text}'. Статус: {status_code}")
        return None, f"Пустой JSON ответ от API (статус {status_code})"
        
    data_dict = json_response.get("data")
    if not isinstance(data_dict, dict):
        logger.error(f"Ответ API для запроса '{search_text}' не содержит ожидаемый словарь 'data'. Ответ: {json_response}")
        return None, f"Ответ API не содержит 'data' (статус {status_code})"

    raw_features = data_dict.get("features")
    
    if raw_features is None:
        logger.info(f"Ключ 'features' отсутствует в 'data' для запроса '{search_text}', но запрос успешен. Считаем, что объектов нет. Ответ: {json_response}")
        return [], None 
    
    if not isinstance(raw_features, list):
        logger.error(f"Ожидался список для 'features' в 'data', но получен {type(raw_features)}. Запрос: '{search_text}'. Ответ: {json_response}")
        return None, f"Некорректный тип для 'features' в ответе API (статус {status_code})"

    # Парсим каждый feature
    parsed_features: List[NSPDCadastralFeature] = []
    for feature_dict in raw_features:
        parsed = parse_nspd_feature(feature_dict)
        if parsed:
            parsed_features.append(parsed)
        else:
            logger.warning(f"Не удалось распарсить feature: {feature_dict} для запроса '{search_text}'")
            
    logger.info(f"Успешно распарсено {len(parsed_features)} из {len(raw_features)} объектов для запроса '{search_text}'")
    return parsed_features, None

def parse_nspd_feature(feature_dict: Dict[str, Any]) -> Optional[NSPDCadastralFeature]:
    """
    Парсит один объект (feature) из ответа API НСПД в датакласс NSPDCadastralFeature.

    Args:
        feature_dict: Словарь, представляющий один feature.

    Returns:
        Экземпляр NSPDCadastralFeature или None, если не удалось распарсить.
    """
    if not isinstance(feature_dict, dict):
        logger.error(f"Ошибка парсинга NSPDCadastralFeature: входные данные не являются словарем: {type(feature_dict)}")
        return None

    try:
        # --- Парсинг геометрии --- 
        geom_dict = feature_dict.get("geometry")
        parsed_geometry = None
        if isinstance(geom_dict, dict):
            crs_dict = geom_dict.get("crs", {}).get("properties", {})
            parsed_crs = NSPDCrsProperties(name=crs_dict.get("name"))
            parsed_geometry = NSPDCadastralObjectGeometry(
                type=geom_dict.get("type"),
                coordinates=geom_dict.get("coordinates"),
                crs=parsed_crs
            )
        
        # --- Парсинг основных свойств (feature.properties) ---
        props_dict = feature_dict.get("properties", {})
        parsed_main_properties = None
        if isinstance(props_dict, dict):
            parsed_main_properties = NSPDCadastralObjectPropertiesMain(
                categoryName=props_dict.get("categoryName"),
                descr=props_dict.get("descr"),
                label=props_dict.get("label"),
                externalKey=props_dict.get("externalKey"),
                interactionId=props_dict.get("interactionId"),
                score=props_dict.get("score"),
                subcategory=props_dict.get("subcategory")
            )

            # --- Парсинг вложенных свойств (feature.properties.options) ---
            options_dict = props_dict.get("options", {})
            parsed_options_properties = None
            if isinstance(options_dict, dict):
                # Собираем известные поля
                known_options_args = {
                    "cad_num": options_dict.get("cad_num"),
                    "readable_address": options_dict.get("readable_address"),
                    "area": options_dict.get("area"),
                    "status": options_dict.get("status"),
                    "registration_date": options_dict.get("registration_date"),
                    "land_record_reg_date": options_dict.get("land_record_reg_date"),
                    "cost_value": options_dict.get("cost_value"),
                    "type": options_dict.get("type"),
                    "building_name": options_dict.get("building_name"),
                    "purpose": options_dict.get("purpose"),
                    "floor": options_dict.get("floor"),
                    "materials": options_dict.get("materials"),
                    "year_built": options_dict.get("year_built"),
                    "year_commisioning": options_dict.get("year_commisioning"),
                    "land_record_category_type": options_dict.get("land_record_category_type"),
                    "permitted_use_established_by_document": options_dict.get("permitted_use_established_by_document"),
                    "specified_area": options_dict.get("specified_area"),
                    "quarter_cad_number": options_dict.get("quarter_cad_number"),
                    "ownership_type": options_dict.get("ownership_type")
                }
                # Собираем остальные поля в other_options
                other_opts = {k: v for k, v in options_dict.items() if k not in known_options_args}
                known_options_args["other_options"] = other_opts
                
                parsed_options_properties = NSPDCadastralObjectOptions(**known_options_args)
        
        return NSPDCadastralFeature(
            nspd_id=feature_dict.get("id"),
            type=feature_dict.get("type"), # Обычно "Feature"
            geometry=parsed_geometry,
            main_properties=parsed_main_properties,
            options_properties=parsed_options_properties,
            raw_feature_dict=feature_dict # Сохраняем исходный словарь для отладки
        )

    except Exception as e:
        logger.error(f"Исключение при парсинге NSPDCadastralFeature: {e}. Входные данные: {feature_dict}")
        return None

def test_nspd_geoportal_search():
    """
    Тестирует доступ к эндпоинту nspd.gov.ru/api/geoportal/v2/search/geoportal.
    """
    print("\n--- Testing NSPD Geoportal Search API ---")
    
    # Простой GET запрос без параметров
    json_response, status_code, error = make_api_request(
        base_url=NSPD_GEOPORTAL_API_URL,
        endpoint="",
        method="GET",
        headers={"User-Agent": DEFAULT_USER_AGENT},
        verify_ssl=False, # На случай проблем с SSL сертификатом на их стороне
        allow_redirects=True
    )

    print(f"NSPD Geoportal Search API (GET, no params):")
    print(f"Status Code: {status_code}")
    if error:
        print(f"Error: {error}")
    if json_response:
        print(f"JSON Response: {json.dumps(json_response, indent=2, ensure_ascii=False)}")
    
    # Попробуем с каким-нибудь общим параметром, например, query (предположение)
    test_params = {"query": "Москва"} 
    json_response_with_params, status_code_with_params, error_with_params = make_api_request(
        base_url=NSPD_GEOPORTAL_API_URL,
        endpoint="",
        method="GET",
        params=test_params,
        headers={"User-Agent": DEFAULT_USER_AGENT},
        verify_ssl=False,
        allow_redirects=True
    )
    
    print(f"\nNSPD Geoportal Search API (GET, params={test_params}):")
    print(f"Status Code: {status_code_with_params}")
    if error_with_params:
        print(f"Error: {error_with_params}")
    if json_response_with_params:
        print(f"JSON Response: {json.dumps(json_response_with_params, indent=2, ensure_ascii=False)}")

    # Тест новой функции поиска
    print("\n--- Testing search_cadastral_data_by_text function ---")
    
    # --- Тест 1: Существующий КН ---
    print("\nПоиск существующего КН: 33:00-7.127")
    parsed_features_exist, error_exist = search_cadastral_data_by_text("33:00-7.127")

    if error_exist:
        print(f"Ошибка: {error_exist}")
    elif parsed_features_exist is not None: # Проверяем, что не None (пустой список - это ОК)
        print(f"Найдено и распарсено {len(parsed_features_exist)} объектов.")
        if parsed_features_exist:
            first_parsed = parsed_features_exist[0]
            print("Данные первого распарсенного объекта:")
            print(f"  NSPD ID: {first_parsed.nspd_id}")
            print(f"  Тип Feature: {first_parsed.type}")
            if first_parsed.main_properties:
                print(f"  Категория: {first_parsed.main_properties.categoryName}")
                print(f"  Описание/КН: {first_parsed.main_properties.descr}")
            if first_parsed.options_properties:
                print(f"  Адрес: {first_parsed.options_properties.readable_address}")
                print(f"  КН (из options): {first_parsed.options_properties.cad_num}")
            if first_parsed.geometry:
                if first_parsed.geometry.crs:
                    print(f"  CRS геометрии (из данных): {first_parsed.geometry.crs.name}")
                # Тестируем конвертацию в Shapely
                shapely_geom = nspd_geometry_to_shapely(first_parsed.geometry)
                if shapely_geom:
                    print(f"  Shapely геометрия: {shapely_geom.geom_type}, Валидна: {shapely_geom.is_valid}")
                    # Можно добавить вывод WKT, если нужно, но он может быть длинным
                    # print(f"    WKT: {shapely_geom.wkt[:100]}...") 

                    # --- ДОБАВЛЕНО: Расчет метрик ---
                    source_crs_from_data = first_parsed.geometry.crs.name if first_parsed.geometry.crs else DEFAULT_PLANAR_CRS # EPSG:3857
                    
                    area = calculate_area(shapely_geom, source_crs_str=source_crs_from_data, project_to_planar=True, target_planar_crs_str=DEFAULT_PLANAR_CRS)
                    length = calculate_length(shapely_geom, source_crs_str=source_crs_from_data, project_to_planar=True, target_planar_crs_str=DEFAULT_PLANAR_CRS)
                    perimeter = calculate_perimeter(shapely_geom, source_crs_str=source_crs_from_data, project_to_planar=True, target_planar_crs_str=DEFAULT_PLANAR_CRS)
                    
                    if area is not None:
                        print(f"    Расчетная площадь: {area:.2f} кв.м. (в CRS: {DEFAULT_PLANAR_CRS})")
                    if length is not None:
                        print(f"    Расчетная длина: {length:.2f} м. (в CRS: {DEFAULT_PLANAR_CRS})")
                    if perimeter is not None:
                        print(f"    Расчетный периметр: {perimeter:.2f} м. (в CRS: {DEFAULT_PLANAR_CRS})")
                    # --- КОНЕЦ ДОБАВЛЕННОГО БЛОКА ---
                else:
                    print("  Не удалось конвертировать геометрию НСПД в Shapely.")
            else:
                print("  Геометрия в распарсенных данных отсутствует.")
    else:
        # Сюда не должны попасть, если только не было ошибки И features is None
        print("Неожиданный результат: parsed_features_exist is None, но ошибки нет.")

    # --- Тест 2: НЕсуществующий КН ---
    print("\nПоиск НЕсуществующего КН: 00:00:0000000:123456789")
    parsed_features_non_exist, error_non_exist = search_cadastral_data_by_text("00:00:0000000:123456789")
    if error_non_exist:
        print(f"Ошибка (ожидаемо): {error_non_exist}")
    elif parsed_features_non_exist:
        print(f"Найдено {len(parsed_features_non_exist)} объектов (неожиданно).")
    else:
        print("Объекты не найдены (ожидаемо, ошибки не было, вернулся пустой список или None).")

if __name__ == '__main__':
    # Пример использования (для отладки)
    logging.basicConfig(level=logging.DEBUG)
    
    # Эндпоинт для получения информации об объекте по типу и ID
    # object_type = 1 # Пример: Земельные участки
    # object_id = "50:13:0000000:52357" # Пример кадастрового номера
    # endpoint_example = f"features/{object_type}/{object_id}"

    # Более простой эндпоинт из pkk_api_test.py для проверки связи
    # (например, поиск объектов в bbox, но это требует параметров)
    # Для простого GET, возможно, потребуется найти публичный эндпоинт, не требующий сложных параметров.
    # В pkk_api_test.py использовался 'https://pkk.rosreestr.ru/api/features/1?sqo=50:27:30213:134'
    # Это можно разбить на endpoint = 'features/1' и params = {'sqo': '50:27:30213:134'}
    
    logger.info("Тестирование pkk_api_client...")
    # Пример вызова (нужен конкретный рабочий эндпоинт для теста)
    # response_data = make_api_request("GET", "features/1", params={"text": "50:27:30213:134", "limit": 1}) 
    # logger.info(f"Ответ API: {response_data}")

    # Тест из Директивы.md: поиск по кадастровому номеру
    # https://pkk.rosreestr.ru/api/features/1?text=69:27:0000021:400&limit=1&tolerance=2&skip=0
    test_endpoint = "features/1"
    test_params = {
        "text": "69:27:0000021:400",
        "limit": 1,
        "tolerance": 2,
        "skip": 0
    }
    # SSL проверка отключена для этого теста
    # Также отключаем редиректы, чтобы посмотреть исходный ответ от pkk.rosreestr.ru
    logger.info("Тестовый запрос к pkk.rosreestr.ru (без редиректов, без SSL проверки):")
    response_data_no_redirect = make_api_request(
        "GET", 
        test_endpoint, 
        params=test_params, 
        verify_ssl=False, 
        allow_redirects=False
    )
    if response_data_no_redirect:
        logger.info("Успешный тестовый запрос (без редиректов):")
        import json
        logger.info(json.dumps(response_data_no_redirect, indent=2, ensure_ascii=False))
    else:
        logger.info("Тестовый запрос (без редиректов) не вернул JSON или не удался (см. логи выше).")

    # Тест с редиректами (как было до этого, чтобы увидеть конечный результат)
    logger.info("Тестовый запрос к pkk.rosreestr.ru (С РЕДИРЕКТАМИ, без SSL проверки):")
    response_data_with_redirects = make_api_request("GET", test_endpoint, params=test_params, verify_ssl=False, allow_redirects=True)
    if response_data_with_redirects:
        logger.info("Успешный тестовый запрос (с редиректами):")
        import json
        logger.info(json.dumps(response_data_with_redirects, indent=2, ensure_ascii=False))
    else:
        logger.error("Тестовый запрос (с редиректами) не удался.")

    # Тестирование нового предполагаемого API (nspd.gov.ru)
    test_nspd_geoportal_search() 