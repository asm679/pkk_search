import click
import os
from scripts.kml_parser import load_kml_file, extract_placemark_geometries_recursive, get_kml_document_name
# Импортируем датаклассы, которые теперь возвращает kml_parser
from scripts.data_structures import (
    ExtractedPlacemark, PointGeom, LineStringGeom, LinearRingGeom, 
    PolygonGeom, MultiGeometryGeom, SubGeometryData
)
# Импортируем функции конвертации и вычислений
from scripts.geometry_processing import (
    kml_placemark_to_shapely, DEFAULT_PRECISION, 
    calculate_area, calculate_length, calculate_perimeter,
    create_geojson_feature, save_geojson_feature_collection,
    GEOGRAPHIC_CRS_WGS84, DEFAULT_PLANAR_CRS
)
# Импорты для новой команды
from scripts.pkk_api_client import search_cadastral_data_by_text, parse_nspd_feature
from scripts.geometry_processing import nspd_geometry_to_shapely
# _version должен быть в корне проекта или доступен в PYTHONPATH
from _version import __version__
import json

@click.group(help="Кадастровый инструмент для обработки геоданных.")
@click.version_option(version=__version__, message='%(prog)s version %(version)s')
def cli():
    """Основная группа команд для кадастрового инструмента."""
    pass

@cli.command("process-kmls")
@click.option('-k', '--kml-files', 'kml_files', 
              type=click.Path(dir_okay=False, readable=True),
              multiple=True, required=True, help='Path to one or more KML files to process.')
@click.option('--output-geojson', 'output_geojson_path',
              type=click.Path(dir_okay=False, writable=True, resolve_path=True),
              default=None, help='Optional: Path to save the output as a GeoJSON file.'
              u' If not provided, defaults to <kml_filename>.geojson in the same directory as the KML file.')
@click.option('--geojson-indent', type=int, default=2, show_default=True,
              help='Indentation level for the output GeoJSON file. Use None for compact output.')
def process_kmls(kml_files, output_geojson_path, geojson_indent):
    """Processes one or more KML files, extracts geometric data, and saves it to GeoJSON."""
    click.echo(f"Received {len(kml_files)} KML file(s) to process.")

    for kml_file_path in kml_files:
        # Ручная проверка существования файла
        if not os.path.exists(kml_file_path):
            click.echo(click.style(f"  Error: KML file not found: {kml_file_path}", fg='red'))
            continue # Переход к следующему файлу, если этот не найден

        click.echo(click.style(f"\n--- Processing KML file: {kml_file_path} ---", fg='cyan'))
        
        kml_root = load_kml_file(kml_file_path)
        
        if not kml_root:
            click.echo(click.style(f"  Error: Could not load or parse KML file: {kml_file_path}", fg='red'))
            continue

        doc_name = get_kml_document_name(kml_root)
        click.echo(f"  KML Document Name: {doc_name}")

        start_node_for_extraction = None
        if hasattr(kml_root, 'Document') and kml_root.Document is not None:
            start_node_for_extraction = kml_root.Document
        elif hasattr(kml_root, 'Folder') or hasattr(kml_root, 'Placemark'):
            start_node_for_extraction = kml_root
        
        if not start_node_for_extraction:
            click.echo(click.style(f"  Error: No suitable starting node (Document/Folder) found in KML: {kml_file_path}", fg='red'))
            continue
            
        geometries = extract_placemark_geometries_recursive(start_node_for_extraction)
        
        if not geometries:
            click.echo(click.style("  No geometries found in this KML.", fg='yellow'))
            click.echo(click.style("--- End of KML file processing ---", fg='cyan'))
            continue # Переход к следующему файлу

        click.echo(click.style(f"  Found {len(geometries)} geometries:", fg='green'))
        
        geojson_features_list = [] # Список для хранения GeoJSON features

        for idx, geom_placemark in enumerate(geometries):
            click.echo(f"    Geometry {idx + 1}:")
            click.echo(f"      Name: {geom_placemark.name if geom_placemark.name else 'N/A'}")
            click.echo(f"      ID: {geom_placemark.id if geom_placemark.id else 'N/A'}")
            click.echo(f"      Type: {geom_placemark.geometry_type}")
            
            shapely_geom = kml_placemark_to_shapely(geom_placemark, precision=DEFAULT_PRECISION)
            
            area = None
            length = None
            perimeter = None

            if shapely_geom:
                click.echo(click.style(f"      Shapely WKT: {shapely_geom.wkt}", fg='yellow'))
                if not shapely_geom.is_valid:
                    click.echo(click.style(f"        WARNING: Shapely geometry is not valid!", fg='red'))
                    # Причина невалидности будет в GeoJSON properties
                
                area = calculate_area(shapely_geom)
                length = calculate_length(shapely_geom)
                perimeter = calculate_perimeter(shapely_geom)

                if area is not None:
                    click.echo(click.style(f"      Area: {area:.2f} sq. units (projected)", fg='magenta'))
                if length is not None and length > 1e-9: # Используем малый порог
                    click.echo(click.style(f"      Length: {length:.2f} units (projected)", fg='magenta'))
                if perimeter is not None and perimeter > 1e-9:
                    click.echo(click.style(f"      Perimeter: {perimeter:.2f} units (projected)", fg='magenta'))
                
                # Создаем GeoJSON feature
                feature = create_geojson_feature(
                    placemark_data=geom_placemark, 
                    shapely_geom=shapely_geom, 
                    area=area, 
                    length=length, 
                    perimeter=perimeter,
                    precision=DEFAULT_PRECISION # Используем ту же точность, что и для расчетов
                )
                geojson_features_list.append(feature)

            elif geom_placemark.geometry_type and geom_placemark.geometry_type != 'Unknown':
                click.echo(click.style("      Could not convert to Shapely geometry. Will not be included in GeoJSON.", fg='red'))
                # Создаем "пустой" feature или feature с Null геометрией, если нужно отметить его в GeoJSON
                # Пока просто пропускаем, если не удалось создать Shapely геометрию
                feature_empty = create_geojson_feature(
                    placemark_data=geom_placemark, 
                    shapely_geom=None, 
                    area=None, 
                    length=None, 
                    perimeter=None
                )
                geojson_features_list.append(feature_empty) # Добавляем с None геометрией
            else:
                click.echo(click.style("      No displayable geometry data or Unknown geometry type.", fg='yellow'))
                # Также добавляем с None геометрией, чтобы зафиксировать имя/id если есть
                feature_empty = create_geojson_feature(
                    placemark_data=geom_placemark, 
                    shapely_geom=None, 
                    area=None, 
                    length=None, 
                    perimeter=None
                )
                geojson_features_list.append(feature_empty)
            
            coords_data = geom_placemark.geometry_data # Это один из Geom датаклассов или None
            
            if isinstance(coords_data, PointGeom):
                click.echo(f"      Coordinates: {coords_data.coordinates}")
            elif isinstance(coords_data, LineStringGeom):
                click.echo(f"      Coordinates: {coords_data.coordinates}")
            elif isinstance(coords_data, LinearRingGeom):
                click.echo(f"      Coordinates: {coords_data.coordinates}")
            elif isinstance(coords_data, PolygonGeom):
                click.echo(f"      Coordinates (Outer): {coords_data.outer_boundary.coordinates}")
                if coords_data.inner_boundaries:
                    for i, inner_ring in enumerate(coords_data.inner_boundaries):
                        click.echo(f"      Coordinates (Inner {i+1}): {inner_ring.coordinates}")
            elif isinstance(coords_data, MultiGeometryGeom):
                click.echo(f"      Sub-geometries:")
                for sub_idx, sub_geom_data in enumerate(coords_data.geometries):
                    click.echo(f"        Sub-geometry {sub_idx+1}: Type={sub_geom_data.type}")
                    # sub_geom_data.coordinates это Union[CoordinateString, Dict[...]]
                    if isinstance(sub_geom_data.coordinates, dict): # Polygon in MultiGeometry
                         click.echo(f"          Outer: {sub_geom_data.coordinates.get('outer', 'N/A')}")
                         if sub_geom_data.coordinates.get('inner'):
                             for i_sub, i_ring_sub in enumerate(sub_geom_data.coordinates.get('inner', [])):
                                 click.echo(f"          Inner {i_sub+1}: {i_ring_sub}")
                    else: # Point, LineString, LinearRing string coordinates
                         click.echo(f"          Coords: {sub_geom_data.coordinates}")
            elif coords_data is None and geom_placemark.geometry_type == 'Unknown':
                 click.echo(f"      Coordinates: Not applicable (Unknown geometry type)")
            else:
                click.echo(click.style(f"      Coordinates: (Unhandled geometry data type: {type(coords_data)}) {coords_data}", fg='red'))

        # Сохранение в GeoJSON
        if geojson_features_list: # Сохраняем, только если есть что сохранять
            current_output_path = output_geojson_path
            if not current_output_path: # Если путь не задан, используем имя KML файла
                base, _ = os.path.splitext(kml_file_path)
                current_output_path = base + ".geojson"
            
            click.echo(click.style(f"  Saving {len(geojson_features_list)} features to GeoJSON: {current_output_path}", fg='blue'))
            
            # Используем indent None для компактного вывода, если geojson_indent это строка "None" или число < 0
            actual_indent = geojson_indent
            if isinstance(geojson_indent, str) and geojson_indent.lower() == 'none':
                actual_indent = None
            elif isinstance(geojson_indent, int) and geojson_indent < 0:
                 actual_indent = None

            if save_geojson_feature_collection(geojson_features_list, current_output_path, indent=actual_indent):
                click.echo(click.style("  GeoJSON successfully saved.", fg='green'))
            else:
                click.echo(click.style("  Failed to save GeoJSON.", fg='red'))
        else:
            click.echo(click.style("  No processable geometries found to save to GeoJSON.", fg='yellow'))

        click.echo(click.style("--- End of KML file processing ---", fg='cyan'))

# @cli.command(name="another_command")
# def another():
#     pass

# >>> Новая команда для работы с API PKK (НСПД)
@cli.command("search-pkk")
@click.option("-q", "--query-text", required=True, help="Кадастровый номер или текстовый запрос для поиска на ПКК (НСПД).")
@click.option("--raw-output", is_flag=True, help="Вывести полный сырой JSON ответ от API (если применимо к этапу).")
@click.option("--shapely-wkt", is_flag=True, help="Вывести геометрию в формате WKT (если доступно).")
@click.option("--no-metrics", is_flag=True, help="Не рассчитывать и не выводить геометрические метрики (площадь, периметр).")
def search_pkk(query_text: str, raw_output: bool, shapely_wkt: bool, no_metrics: bool):
    """Поиск объектов на Публичной Кадастровой Карте (через API НСПД)."""
    click.echo(f"Выполняется поиск по запросу: '{query_text}'...")

    parsed_features, error = search_cadastral_data_by_text(query_text)

    if error:
        click.secho(f"Ошибка при выполнении запроса: {error}", fg="red")
        return

    if not parsed_features:
        click.secho(f"Объекты по запросу '{query_text}' не найдены.", fg="yellow")
        return

    click.secho(f"Найдено объектов: {len(parsed_features)}", fg="green")

    if raw_output:
        click.echo("--- Сырой ответ (распарсенные features) ---")
        # parsed_features это список датаклассов, для raw вывода лучше использовать их raw_feature_dict
        raw_dicts = [feat.raw_feature_dict for feat in parsed_features if feat and feat.raw_feature_dict]
        if raw_dicts:
            try:
                click.echo(json.dumps(raw_dicts, indent=2, ensure_ascii=False))
            except TypeError as e:
                click.secho(f"Ошибка сериализации сырых данных: {e}", fg="red")
                click.echo("Попытка вывода каждого объекта отдельно:")
                for i, raw_dict in enumerate(raw_dicts):
                    try:
                        click.echo(f"Объект {i+1}:")
                        click.echo(json.dumps(raw_dict, indent=2, ensure_ascii=False))
                    except TypeError:
                        click.echo(f"  Не удалось сериализовать объект {i+1}")
        else:
            click.echo("Сырые данные для вывода отсутствуют.")
        return # При raw_output дальше не идем

    for i, feature in enumerate(parsed_features):
        click.echo(f"\n--- Объект {i + 1} ---")
        if not feature: # На случай, если в списке оказался None после парсинга
            click.secho("  Ошибка: Некорректные данные объекта.", fg="red")
            continue

        # Вывод основной информации
        if feature.main_properties:
            click.echo(f"  ID объекта (НСПД): {feature.nspd_id}")
            click.echo(f"  Тип: {feature.main_properties.categoryName if feature.main_properties.categoryName else 'N/A'}")
            click.echo(f"  Описание/КН: {feature.main_properties.descr if feature.main_properties.descr else 'N/A'}")
            click.echo(f"  Метка: {feature.main_properties.label if feature.main_properties.label else 'N/A'}")
        
        if feature.options_properties:
            click.echo(f"  Кадастровый номер (из options): {feature.options_properties.cad_num if feature.options_properties.cad_num else 'N/A'}")
            click.echo(f"  Адрес: {feature.options_properties.readable_address if feature.options_properties.readable_address else 'N/A'}")
            area_from_attrs = feature.options_properties.area
            if area_from_attrs is not None:
                click.echo(f"  Площадь (из атрибутов): {area_from_attrs}") # Единицы могут быть разные или отсутствовать
            cost = feature.options_properties.cost_value
            if cost is not None:
                click.echo(f"  Кадастровая стоимость: {cost}")
            status = feature.options_properties.status
            if status:
                click.echo(f"  Статус (из атрибутов): {status}")
            reg_date = feature.options_properties.registration_date
            if reg_date:
                click.echo(f"  Дата регистрации/учета: {reg_date}")

        # Геометрия и метрики
        if feature.geometry:
            source_crs = feature.geometry.crs.name if feature.geometry.crs else DEFAULT_PLANAR_CRS
            click.echo(f"  Тип геометрии (НСПД): {feature.geometry.type}, CRS: {source_crs}")
            
            shapely_object = nspd_geometry_to_shapely(feature.geometry)
            if shapely_object:
                click.echo(f"  Конвертировано в Shapely: {shapely_object.geom_type}, Валидность: {shapely_object.is_valid}")
                if shapely_wkt:
                    try:
                        click.echo(f"    WKT: {shapely_object.wkt}")
                    except Exception as e:
                        click.secho(f"    Ошибка при генерации WKT: {e}", fg="red")

                if not no_metrics:
                    area_calc = calculate_area(shapely_object, source_crs_str=source_crs, target_planar_crs_str=DEFAULT_PLANAR_CRS)
                    # length_calc = calculate_length(shapely_object, source_crs_str=source_crs, target_planar_crs_str=DEFAULT_PLANAR_CRS)
                    perimeter_calc = calculate_perimeter(shapely_object, source_crs_str=source_crs, target_planar_crs_str=DEFAULT_PLANAR_CRS)
                    
                    if area_calc is not None:
                        click.echo(f"    Расчетная площадь: {area_calc:.2f} кв.м (в CRS: {DEFAULT_PLANAR_CRS})")
                    # Длина имеет смысл в основном для линий, для полигонов есть периметр
                    # if length_calc is not None and shapely_object.geom_type not in ["Polygon", "MultiPolygon"]:
                    #    click.echo(f"    Расчетная длина: {length_calc:.2f} м. (в CRS: {DEFAULT_PLANAR_CRS})")
                    if perimeter_calc is not None: # and shapely_object.geom_type in ["Polygon", "MultiPolygon"]:
                        click.echo(f"    Расчетный периметр: {perimeter_calc:.2f} м. (в CRS: {DEFAULT_PLANAR_CRS})")
            else:
                click.secho("  Не удалось конвертировать геометрию в Shapely.", fg="yellow")
        else:
            click.echo("  Геометрия отсутствует в данных объекта.")

if __name__ == '__main__':
    cli(prog_name="kadastr_cli.py") 