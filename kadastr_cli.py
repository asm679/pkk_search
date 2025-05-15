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
    create_geojson_feature, save_geojson_feature_collection
)

from _version import __version__

@click.group(help="Кадастровый инструмент для обработки геоданных.")
@click.version_option(version=__version__, message='%(prog)s version %(version)s')
def cli():
    """Основная группа команд для кадастрового инструмента."""
    pass

@cli.command("process-kmls")
@click.option('-k', '--kml-files', 'kml_files', 
              type=click.Path(exists=True, dir_okay=False, readable=True),
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

if __name__ == '__main__':
    cli(prog_name="kadastr_cli.py") 