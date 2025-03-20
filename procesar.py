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
        for i, feature in enumerate(features[:3]):  # Mostrar solo las 3 primeras
            img_id = feature.get('id', 'Desconocido')
            properties = feature.get('properties', {})
            cloud = properties.get('eo:cloud_cover', 'N/A')
            date = properties.get('datetime', 'Fecha desconocida')
            
            print(f"Imagen {i+1}: {img_id} - {date[:10]} - Nubes: {cloud}%")
        
        if len(features) > 3:
            print(f"... y {len(features) - 3} imágenes más.")
        
        # 7. Descargar la primera imagen
        if len(features) > 0:
            print("\nDescargando imágenes...")
            
            # Si hay índices seleccionados, determinar las bandas necesarias
            if selected_indices:
                required_bands = determine_required_bands(selected_indices)
                print(f"Bandas necesarias para los índices: {', '.join(required_bands)}")
                
                # Descargar sólo las bandas necesarias
                base_path = download_selective_bands(features[0], required_bands)
                
                if base_path:
                    print("Descarga completada. Calculando índices...")
                    # Procesar los índices
                    results = process_selected_indices(base_path, selected_indices)
                    print(f"Se calcularon {len(results)} índices: {', '.join(results.keys())}")
                    return True
                else:
                    print("Error al descargar las bandas necesarias")
                    return False
            else:
                # Si no hay índices seleccionados, descargar solo una banda (B4)
                print("No hay índices seleccionados. Descargando solo banda B4 (roja)...")
                success = download_images([features[0]], band="B4")
                
                if success:
                    print("Descarga completada")
                    return True
                else:
                    print("Error al descargar la imagen")
                    return False
        
        return True
        
    except Exception as e:
        print(f"Error: {str(e)}")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    # Ejecutar el procesamiento directamente si se llama como script
    success = process_data()
    if success:
        print("Procesamiento completado con éxito")
    else:
        print("El procesamiento falló")

