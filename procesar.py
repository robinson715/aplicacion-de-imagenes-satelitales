# -*- coding: utf-8 -*-
"""
Created on Tue Mar 18 20:02:17 2025

@author: robin
"""

import os
from query import generate_landsat_query, fetch_stac_server
from downloader import download_selective_bands
from indices import process_selected_indices

def determine_required_bands(selected_indices):
    """
    Determina qué bandas son necesarias según los índices seleccionados.
    
    Returns:
        list: Lista de bandas necesarias
    """
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
    # Importaciones necesarias
    import os
    import json
    import traceback
    from query import generate_landsat_query, fetch_stac_server
    from downloader import download_images
    import main
    
    config = main.get_config()
    
    print("\n==== VALORES DE CONFIGURACIÓN OBTENIDOS ====")
    for key, value in config.items():
        print(f"{key}: {value}")
    print("============================================\n")
    
    # 1. Verificar y obtener path del archivo
    file_path = config.get("file_path", "")
    if not file_path:
        print("Error: No se especificó un archivo GeoJSON/Shapefile")
        return False
    
    # Verificar que el archivo existe
    if not os.path.exists(file_path):
        print(f"Error: El archivo {file_path} no existe")
        return False
    
    # Verificar que podemos leer el archivo
    try:
        with open(file_path, 'r') as f:
            content = f.read(200)  # Leer los primeros 200 caracteres
            print(f"Contenido del archivo: {content}...")
    except Exception as e:
        print(f"Error al leer el archivo: {str(e)}")
        return False
    
    # 2. Obtener y convertir fechas
    start_date = config.get("start_date", "")
    end_date = config.get("end_date", "")
    
    if not start_date or not end_date:
        print("Error: No se especificaron fechas válidas")
        return False
    
    # Convertir fechas del formato dd/MM/yyyy al formato YYYY-MM-DD que espera la API
    if "/" in start_date:
        try:
            day, month, year = start_date.split("/")
            start_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            print(f"Fecha inicio convertida: {start_date}")
        except Exception as e:
            print(f"Error al convertir la fecha inicial: {str(e)}")
            print(f"Valor original: {start_date}")
            return False
    
    if "/" in end_date:
        try:
            day, month, year = end_date.split("/")
            end_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            print(f"Fecha fin convertida: {end_date}")
        except Exception as e:
            print(f"Error al convertir la fecha final: {str(e)}")
            print(f"Valor original: {end_date}")
            return False
    
    # 3. Obtener y verificar otros parámetros
    # Asegurarse que cloud_cover es un número
    try:
        cloud_cover = int(config.get("cloud_cover", 50))
    except ValueError:
        print(f"Error: El valor de cloud_cover no es válido: {config.get('cloud_cover')}")
        cloud_cover = 50  # Valor por defecto
    
    # Plataforma seleccionada
    platform = config.get("platform", "Landsat 8")
    if platform == "Landsat 8":
        platform_value = ["LANDSAT_8"]
    elif platform == "Landsat 9":
        platform_value = ["LANDSAT_9"]
    else:
        platform_value = ["LANDSAT_8", "LANDSAT_9"]  # Usar ambos por defecto
    
    print(f"\nParámetros de consulta:")
    print(f"- Archivo: {file_path}")
    print(f"- Fecha inicio: {start_date}")
    print(f"- Fecha fin: {end_date}")
    print(f"- Cobertura de nubes máxima: {cloud_cover}%")
    print(f"- Plataformas: {platform_value}")
    
    # 4. Generar la consulta
    try:
        query = generate_landsat_query(
            file_path,
            start_date,
            end_date,
            cloud_cover=cloud_cover,
            platform=platform_value
        )
        
        # Mostrar la consulta completa
        try:
            # Intentar imprimir la consulta, pero si falla, continuar de todos modos
            print("\nConsulta generada:")
            print(json.dumps(query, indent=2))
        except Exception as e:
            print(f"No se pudo imprimir la consulta completa: {str(e)}")
            print("Continuando con el procesamiento...")
        
    except Exception as e:
        print(f"Error al generar la consulta: {str(e)}")
        print(traceback.format_exc())
        return False
    
    # 5. Ejecutar la consulta
    try:
        print("\nEnviando consulta a la API de Landsat...")
        features = fetch_stac_server(query)
        
        if not features:
            print("No se encontraron imágenes con los criterios especificados.")
            
            # Sugerencias para el usuario
            print("\nSugerencias para obtener resultados:")
            print("1. Amplía el rango de fechas")
            print("2. Aumenta el porcentaje de cobertura de nubes permitido")
            print("3. Verifica que el polígono está en un área con cobertura de Landsat")
            print("4. Prueba con una plataforma diferente (Landsat 8 o 9)")
            
            return False
        
        print(f"\nSe encontraron {len(features)} imágenes que cumplen con los criterios.")
        
        # 6. Mostrar información de las imágenes encontradas
        print(f"\nSe encontraron {len(features)} imágenes que cumplen con los criterios.")
        
        for i, feature in enumerate(features[:5]):  # Mostrar hasta 5 imágenes
            img_id = feature.get('id', 'Desconocido')
            properties = feature.get('properties', {})
            cloud = properties.get('eo:cloud_cover', 'N/A')
            date = properties.get('datetime', 'Fecha desconocida')
            
            print(f"\nImagen {i+1}: {img_id}")
            print(f"- Fecha: {date}")
            print(f"- Cobertura de nubes: {cloud}%")
        
        if len(features) > 5:
            print(f"\n... y {len(features) - 5} imágenes más.")
        
        # 7. Descargar la primera imagen
        if len(features) > 0:
            print("\nInspeccionando estructura de datos de la primera imagen antes de descargar...")
            first_feature = features[0]
            
            # Verificar estructura de assets
            if 'assets' in first_feature:
                print("Assets disponibles:")
                for asset_key in first_feature['assets'].keys():
                    asset_data = first_feature['assets'][asset_key]
                    if 'href' in asset_data:
                        print(f"- {asset_key}: {asset_data['href']}")
            
            print("\nDescargando la primera imagen...")
            if len(features) > 0:
                print("\nDescargando la primera imagen, banda B4 (roja)...")
                success = download_images([features[0]], band="B4")
                
                if success:
                    print("Descarga de banda B4 completada con éxito!")
                    return True
                else:
                    print("Error al descargar la banda")
                    return False
        
        # 8. Resetear la bandera de nueva configuración
        main.reset_config_flag()
        return True
        
    except Exception as e:
        print(f"Error al consultar el servidor: {str(e)}")
        print(traceback.format_exc())
        return False