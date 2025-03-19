# -*- coding: utf-8 -*-
"""
Created on Tue Mar 18 11:13:00 2025

@author: robin
"""

# use_config.py
# Este script muestra cómo usar la configuración generada por el botón PROCESS

import json
import os
from query import generate_landsat_query, fetch_stac_server
from downloader import download_images

def load_last_config():
    """
    Carga la última configuración guardada por la interfaz.
    
    Returns:
        dict: Configuración cargada o None si no existe el archivo.
    """
    config_file = "process_config.json"
    
    if not os.path.exists(config_file):
        print(f"Error: No se encontró el archivo de configuración {config_file}")
        print("Asegúrate de haber presionado el botón PROCESS en la interfaz primero.")
        return None
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        print(f"Configuración cargada desde {config_file}")
        return config
    
    except Exception as e:
        print(f"Error al cargar la configuración: {str(e)}")
        return None

def process_with_last_config():
    """
    Procesa datos usando la última configuración guardada.
    """
    config = load_last_config()
    
    if not config:
        return False
    
    print("\n=== Procesando con la última configuración ===")
    print(f"Modo: {'Importar archivo' if config.get('import_mode') else 'Generar polígono'}")
    print(f"Fechas: {config.get('start_date')} a {config.get('end_date')}")
    
    # Verificar el modo de procesamiento
    if config.get('import_mode') and config.get('imported_file_path'):
        # Procesar archivo importado
        file_path = config.get('imported_file_path')
        if not os.path.exists(file_path):
            print(f"Error: El archivo {file_path} no existe")
            return False
        
        # Generar consulta Landsat
        query = generate_landsat_query(
            file_path,
            config.get('start_date'),
            config.get('end_date'),
            cloud_cover=config.get('cloud_cover', 50)
        )
        
        # Buscar imágenes
        features = fetch_stac_server(query)
        
        if features:
            print(f"Se encontraron {len(features)} imágenes")
            
            # Descargar la primera imagen
            if len(features) > 0:
                print("Descargando la primera imagen...")
                download_images([features[0]])
                print("Descarga completada")
                return True
        else:
            print("No se encontraron imágenes con los criterios especificados")
    
    elif config.get('path_row_enabled') and config.get('path') and config.get('row'):
        # Procesar usando Path/Row
        print(f"Procesando Path {config.get('path')} / Row {config.get('row')}")
        # Implementar lógica para Path/Row
    
    return False

if __name__ == "__main__":
    # Procesar con la última configuración guardada
    process_with_last_config()
Última edición hace 11 horas