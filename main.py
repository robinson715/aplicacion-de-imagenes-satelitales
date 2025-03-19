# -*- coding: utf-8 -*-
"""
Created on Tue Mar 18 00:03:38 2025

@author: robin
"""

import sys
import json
import os
from PyQt5.QtWidgets import QApplication

# Importaciones directas sin estructura jerárquica
from interfazz1 import MapAppWindow
from query import generate_landsat_query, fetch_stac_server
from downloader import download_images


# Mantener la configuración actual en memoria
current_config = {
    "import_mode": False,
    "generate_mode": False,
    "path_row_mode": False,
    "file_path": "",
    "path": "",
    "row": "",
    "start_date": "",
    "end_date": "",
    "diff_date_enabled": False,
    "diff_start_date": "",
    "diff_end_date": "",
    "cloud_cover": 50,
    "platform": "Landsat 8",
    "selected_indices": []
}

# Bandera para saber si hay una nueva configuración lista para procesar
new_config_ready = False

def update_config(config):
    """
    Actualiza la configuración en memoria y establece la bandera.
    
    Args:
        config (dict): Nueva configuración
    
    Returns:
        None
    """
    global current_config, new_config_ready
    current_config = config.copy()  # Copia para evitar referencias no deseadas
    new_config_ready = True
      
    print("Configuración actualizada y lista para procesar")

def get_config():
    """
    Obtiene la configuración actual.
    
    Returns:
        dict: Configuración actual
    """
    return current_config.copy()

def is_config_ready():
    """
    Verifica si hay una nueva configuración lista para procesar.
    
    Returns:
        bool: True si hay nueva configuración, False en caso contrario
    """
    return new_config_ready

def reset_config_flag():
    """
    Restablece la bandera de nueva configuración después de procesarla.
    
    Returns:
        None
    """
    global new_config_ready
    new_config_ready = False


# Variable global para almacenar la última configuración procesada
last_processed_config = None

def process_landsat_data(config):
    """
    Procesa datos Landsat basados en la configuración proporcionada.
    
    Args:
        config (dict): Diccionario con la configuración.
    
    Returns:
        bool: True si el procesamiento fue exitoso, False en caso contrario.
    """
    global last_processed_config
    last_processed_config = config
    
    try:
        # Verificar el modo de procesamiento
        if config['import_mode'] and config['imported_file_path']:
            # Modo de importación de archivo
            file_path = config['imported_file_path']
            if not os.path.exists(file_path):
                print(f"Error: El archivo {file_path} no existe")
                return False
                
            start_date = config['start_date']
            end_date = config['end_date']
            
            if not start_date or not end_date:
                print("Error: Fechas no especificadas")
                return False
            
            cloud_cover = config.get('cloud_cover', 50)
            
            print(f"Procesando archivo: {file_path}")
            print(f"Período: {start_date} a {end_date}")
            print(f"Cobertura de nubes: {cloud_cover}%")
            
            # Generar consulta
            query = generate_landsat_query(
                file_path,
                start_date,
                end_date,
                cloud_cover=cloud_cover
            )
            
            # Buscar imágenes
            features = fetch_stac_server(query)
            
            if features:
                print(f"Se encontraron {len(features)} imágenes")
                
                # Descargar la primera imagen como ejemplo
                if len(features) > 0:
                    print("Descargando la primera imagen...")
                    download_images([features[0]])
                    print("Descarga completada")
                    return True
            else:
                print("No se encontraron imágenes con los criterios especificados")
                
        elif config['path_row_enabled'] and config['path'] and config['row']:
            # Modo de Path/Row
            print(f"Procesando Path {config['path']} / Row {config['row']}")
            # Implementar lógica específica para path/row
            
        elif config.get('polygons'):
            # Modo de polígonos dibujados
            print(f"Procesando polígonos dibujados: {len(config['polygons'])} polígonos")
            # Implementar lógica para polígonos
            
        return False
    
    except Exception as e:
        print(f"Error durante el procesamiento: {str(e)}")
        return False

def get_last_config():
    """
    Retorna la última configuración procesada.
    
    Returns:
        dict: Última configuración procesada o None si no hay ninguna.
    """
    return last_processed_config

if __name__ == "__main__":
    # Iniciar la aplicación con interfaz gráfica
    app = QApplication(sys.argv)
    window = MapAppWindow()
    
    # Conectar el botón PROCESS con la función de procesamiento
    # Esta conexión se hará internamente en MapAppWindow
    
    # Mostrar la ventana principal
    window.show()
    
    # Ejecutar la aplicación
    sys.exit(app.exec_())