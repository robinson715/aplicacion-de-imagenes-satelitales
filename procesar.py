# -*- coding: utf-8 -*-
"""
Módulo principal para el procesamiento de imágenes Landsat y cálculo de índices
"""

import os
import json
import traceback
from query import generate_landsat_query, fetch_stac_server
from downloader import download_images, download_selective_bands
from indices import process_selected_indices
from cobertura import analyze_coverage, visualize_coverage, download_optimal_scenes
from mosaico import obtener_escenas_por_banda,obtener_cloud_cover_de_metadatos,crear_mosaico_por_banda,recortar_mosaico_con_poligono,procesar_bandas_a_mosaicos_y_recortes,limpiar_archivos_temporales

def determine_required_bands(selected_indices):
   
    required_bands = set()
    
    for index in selected_indices:
        if index == "NDVI":
            required_bands.update(["B4", "B5"])  # Red, NIR
        elif index == "NDWI":
            required_bands.update(["B3", "B5"])  # Green, NIR
        elif index == "NDSI":
            required_bands.update(["B3", "B6"])  # Green, SWIR
        elif index == "BSI":
            required_bands.update(["B2", "B4", "B5", "B6"])  # Blue, Red, NIR, SWIR1
        elif index == "LST":
            required_bands.update(["B10"])  # TIRS1
    
    return list(required_bands)

def process_data():
    """
    Procesa los datos según la configuración actual.
    
    Returns:
        bool: True si el procesamiento fue exitoso, False en caso contrario
    """
    import main
    
    config = main.get_config()
    
    print("\n==== PROCESANDO DATOS ====")
    
    try:
        # 1. Verificar y obtener path del archivo
        file_path = config.get("file_path", "")
        if not file_path:
            print("Error: No se especificó un archivo GeoJSON/Shapefile")
            return False
        
        if not os.path.exists(file_path):
            print(f"Error: El archivo {file_path} no existe")
            return False
        
        # 2. Obtener y convertir fechas
        start_date = config.get("start_date", "")
        end_date = config.get("end_date", "")
        
        if not start_date or not end_date:
            print("Error: No se especificaron fechas válidas")
            return False
        
        # Convertir fechas del formato dd/MM/yyyy al formato YYYY-MM-DD
        if "/" in start_date:
            day, month, year = start_date.split("/")
            start_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        if "/" in end_date:
            day, month, year = end_date.split("/")
            end_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # 3. Obtener otros parámetros
        cloud_cover = int(config.get("cloud_cover", 50))
        
        # Plataforma seleccionada
        platform = config.get("platform", "Landsat 8")
        if platform == "Landsat 8":
            platform_value = ["LANDSAT_8"]
        elif platform == "Landsat 9":
            platform_value = ["LANDSAT_9"]
        else:
            platform_value = ["LANDSAT_8", "LANDSAT_9"]
        
        # Índices seleccionados
        selected_indices = config.get("selected_indices", [])
        if not selected_indices:
            print("Advertencia: No se han seleccionado índices para calcular")
        
        print(f"Archivo: {file_path}")
        print(f"Fechas: {start_date} a {end_date}")
        print(f"Cobertura de nubes máxima: {cloud_cover}%")
        print(f"Plataformas: {', '.join(platform_value)}")
        print(f"Índices: {', '.join(selected_indices) if selected_indices else 'Ninguno'}")
        
        # 4. Generar la consulta
        query = generate_landsat_query(
            file_path,
            start_date,
            end_date,
            cloud_cover=cloud_cover,
            platform=platform_value
        )
        
        # 5. Ejecutar la consulta
        print("\nConsultando imágenes disponibles...")
        features = fetch_stac_server(query)
        
        if not features:
            print("No se encontraron imágenes con los criterios especificados.")
            print("\nSugerencias:")
            print("1. Amplía el rango de fechas")
            print("2. Aumenta el porcentaje de cobertura de nubes permitido")
            print("3. Verifica que el polígono está en un área con cobertura Landsat")
            return False
        
        print(f"\nSe encontraron {len(features)} imágenes que cumplen con los criterios.")
        
        # 6. Mostrar información de las imágenes encontradas
        print("\nInformación de las imágenes encontradas (hasta 60):")
        print("-" * 100)
        print(f"{'#':<4}{'ID':<50}{'Fecha':<15}{'Nubes':<10}{'Path':<8}{'Row':<6}")
        print("-" * 100)

        max_scenes_to_show = min(60, len(features))
        for i, feature in enumerate(features[:max_scenes_to_show]):
            img_id = feature.get('id', 'Desconocido')
            properties = feature.get('properties', {})
            cloud = properties.get('eo:cloud_cover', 'N/A')
            date = properties.get('datetime', 'Fecha desconocida')[:10]  # Solo la parte de fecha
            path = properties.get('landsat:wrs_path', 'N/A')
            row = properties.get('landsat:wrs_row', 'N/A')
            
            print(f"{i+1:<4}{img_id:<50}{date:<15}{cloud:<10.2f}{path:<8}{row:<6}")

        if len(features) > max_scenes_to_show:
            print(f"\nSe omitieron {len(features) - max_scenes_to_show} imágenes adicionales.")
        
        # 7. Analizar cobertura y descargar las escenas necesarias
        if len(features) > 0:
            print("\nAnalizando cobertura del polígono...")
            
            # Analizar la cobertura
            coverage_info = analyze_coverage(file_path, features)
            
            print(f"Cobertura total: {coverage_info['total_coverage_percent']:.2f}%")
            print(f"Se necesitan {len(coverage_info['scenes_needed'])} escenas para cubrir el polígono")
            
            # Generar visualización de cobertura
            coverage_map = visualize_coverage(file_path, features)
            print(f"Mapa de cobertura generado: {coverage_map}")
            
            # Preguntar al usuario si desea descargar todas las escenas necesarias
            user_input = input("\n¿Descargar todas las escenas necesarias? (s/n): ")
            
            if user_input.lower() == 's':
                # Descargar todas las escenas necesarias
                print("\nDescargando las escenas necesarias...")
                download_path = "data/downloads/complete_coverage"
                os.makedirs(download_path, exist_ok=True)
                
                # Pasar los índices seleccionados a download_optimal_scenes
                downloaded_files = download_optimal_scenes(file_path, features, download_path, selected_indices)
                
                if downloaded_files:
                    print(f"\nSe descargaron {len(downloaded_files)} escenas con éxito")
                    
                    # NUEVA SECCIÓN: Preguntar al usuario si desea generar mosaicos y recortes
                    mosaico_input = input("\n¿Generar mosaicos por banda y recortes del polígono? (s/n): ")
                    
                    if mosaico_input.lower() == 's':
                        try:
                            # Importar el módulo de mosaicos con manejo detallado de errores
                            print("Intentando importar mosaico...")
                            #import mosaico
                            print("¡Mosaico importado correctamente!")
                            
                            print("\nGenerando mosaicos y recortes...")
                            
                            # Definir rutas de salida
                            output_mosaicos = "data/mosaicos"
                            output_recortes = "data/recortes"
                            os.makedirs(output_mosaicos, exist_ok=True)
                            os.makedirs(output_recortes, exist_ok=True)
                            
                            # Llamar a la función principal de mosaicos - NOMBRE CORREGIDO
                            resultados = procesar_bandas_a_mosaicos_y_recortes(
                                download_path,
                                output_mosaicos,
                                output_recortes,
                                file_path
                            )
                            
                            if resultados:
                                print("\nMosaicos y recortes generados exitosamente:")
                                
                                # Mostrar lista de archivos generados
                                print("\nMosaicos generados:")
                                for banda, ruta in resultados["mosaicos"].items():
                                    print(f"  {banda}: {os.path.basename(ruta)}")
                                
                                print("\nRecortes generados:")
                                for banda, ruta in resultados["recortes"].items():
                                    if ruta is not None:
                                        print(f"  {banda}: {os.path.basename(ruta)}")
                                    else:
                                        print(f"  {banda}: Error - No se generó recorte")
                            else:
                                print("\nError: No se pudieron generar los mosaicos y recortes")
                                
                        except ImportError:
                            print("\nError: No se encontró el módulo mosaico.py")
                            print("Asegúrate de que el archivo mosaico.py está en el mismo directorio que procesar.py")
                        
                        except Exception as e:
                            print(f"\nError al generar mosaicos y recortes: {str(e)}")
                            traceback.print_exc()
                    
                    return True
                else:
                    print("Error al descargar las escenas necesarias")
                    return False
            else:
                # Descargar solo la primera escena (comportamiento original)
                print("\nDescargando solo la primera escena...")
                if selected_indices:
                    required_bands = determine_required_bands(selected_indices)
                    base_path = download_selective_bands(features[0], required_bands)
                    
                    if base_path:
                        try:
                            results = process_selected_indices(base_path, selected_indices)
                            return True
                        except Exception as e:
                            print(f"Error al procesar índices: {str(e)}")
                            traceback.print_exc()
                            return False
                    else:
                        return False
                else:
                    success = download_images([features[0]], band="B4")
                    return success
                    
    except Exception as e:
        print(f"Error durante el procesamiento: {str(e)}")
        traceback.print_exc()
        return False