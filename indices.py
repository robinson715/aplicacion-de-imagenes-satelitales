# -*- coding: utf-8 -*-
"""
Módulo para el cálculo de índices radiométricos a partir de imágenes Landsat
"""

import rasterio
import numpy as np

def process_selected_indices(base_path, selected_indices):
    
    results = {}
    bands = {}
    
    # Cargar bandas según sea necesario
    for index in selected_indices:
        if index == "NDVI":
            if "red" not in bands:
                bands["red"] = read_band(f"{base_path}_B4.TIF")
            if "nir" not in bands:
                bands["nir"] = read_band(f"{base_path}_B5.TIF")
            results["NDVI"] = calculate_ndvi(bands["nir"], bands["red"])
            
        elif index == "NDWI":
            if "green" not in bands:
                bands["green"] = read_band(f"{base_path}_B3.TIF")
            if "nir" not in bands:
                bands["nir"] = read_band(f"{base_path}_B5.TIF")
            results["NDWI"] = calculate_ndwi(bands["nir"], bands["green"])
            
        elif index == "NDSI":
            if "green" not in bands:
                bands["green"] = read_band(f"{base_path}_B3.TIF")
            if "swir" not in bands:
                bands["swir"] = read_band(f"{base_path}_B6.TIF")
            results["NDSI"] = calculate_ndsi(bands["swir"], bands["green"])
            
        elif index == "BSI":
            if "blue" not in bands:
                bands["blue"] = read_band(f"{base_path}_B2.TIF")
            if "red" not in bands:
                bands["red"] = read_band(f"{base_path}_B4.TIF")
            if "nir" not in bands:
                bands["nir"] = read_band(f"{base_path}_B5.TIF")
            if "swir1" not in bands:
                bands["swir1"] = read_band(f"{base_path}_B6.TIF")
            results["BSI"] = calculate_bsi(bands["nir"], bands["red"], bands["swir1"], bands["blue"])
            
        elif index == "LST":
            if "tirs" not in bands:
                bands["tirs"] = read_band(f"{base_path}_B10.TIF")
            # Para LST necesitaríamos los metadatos, que podrían leerse del archivo original
            with rasterio.open(f"{base_path}_B10.TIF") as src:
                metadata = {
                    "K1_CONSTANT": 774.8853,  # Valores por defecto para Landsat 8
                    "K2_CONSTANT": 1321.0789
                }
                # En una implementación real, se deberían leer los metadatos del archivo
            results["LST"] = calculate_lst(bands["tirs"], metadata)
    
    # Guardar resultados
    for name, data in results.items():
        output_file = f"{base_path}_{name}.TIF"
        print(f"Guardando índice {name} en {output_file}")
        
        # Guardar como GeoTIFF con metadatos de la imagen original
        with rasterio.open(f"{base_path}_B4.TIF") as src:
            profile = src.profile
            profile.update(dtype=rasterio.float32)
            
            with rasterio.open(output_file, 'w', **profile) as dst:
                dst.write(data.astype(rasterio.float32), 1)
    
    return results

def read_band(file_path):
    """
    Lee una banda desde un archivo .tif y la devuelve como array numpy.
    
    Args:
        file_path: Ruta al archivo TIFF
        
    Returns:
        numpy.ndarray: Datos de la banda
    """
    import os
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"El archivo {file_path} no existe")
    
    try:
        with rasterio.open(file_path) as dataset:
            return dataset.read(1).astype(np.float32)
    except Exception as e:
        raise IOError(f"Error al leer el archivo {file_path}: {str(e)}")

def calculate_ndvi(nir_band, red_band):
    """
    Calcula el Índice de Vegetación de Diferencia Normalizada (NDVI).
    
    Args:
        nir_band: Banda del infrarrojo cercano
        red_band: Banda roja
        
    Returns:
        numpy.ndarray: NDVI calculado
    """
    ndvi = (nir_band - red_band) / (nir_band + red_band + 1e-10)  # Evitar división por cero
    return ndvi

def calculate_ndsi(swir_band, green_band):
    """
    Calcula el Índice de Nieve de Diferencia Normalizada (NDSI).
    
    Args:
        swir_band: Banda del infrarrojo de onda corta
        green_band: Banda verde
        
    Returns:
        numpy.ndarray: NDSI calculado
    """
    ndsi = (green_band - swir_band) / (green_band + swir_band + 1e-10)
    return ndsi

def calculate_ndwi(nir_band, green_band):
    """
    Calcula el Índice de Agua de Diferencia Normalizada (NDWI).
    
    Args:
        nir_band: Banda del infrarrojo cercano
        green_band: Banda verde
        
    Returns:
        numpy.ndarray: NDWI calculado
    """
    ndwi = (green_band - nir_band) / (green_band + nir_band + 1e-10)
    return ndwi

def calculate_bsi(nir_band, red_band, swir1_band, blue_band):
    """
    Calcula el Índice de Suelo Desnudo (BSI).
    
    Args:
        nir_band: Banda del infrarrojo cercano
        red_band: Banda roja
        swir1_band: Banda del infrarrojo de onda corta 1
        blue_band: Banda azul
        
    Returns:
        numpy.ndarray: BSI calculado
    """
    bsi = ((swir1_band + red_band) - (nir_band + blue_band)) / ((swir1_band + red_band) + (nir_band + blue_band) + 1e-10)
    return bsi

def calculate_lst(tirs_band, metadata):
    """
    Calcula la Temperatura de la Superficie Terrestre (LST) usando la banda térmica y metadatos.
    
    Args:
        tirs_band: Banda térmica (TIRS)
        metadata: Diccionario con constantes K1 y K2
        
    Returns:
        numpy.ndarray: LST calculado en grados Celsius
    """
    # Constantes
    K1 = metadata['K1_CONSTANT']
    K2 = metadata['K2_CONSTANT']
    emissivity = 0.97  # Valor aproximado para vegetación

    # Convertir a radiancia
    radiance = K1 / (np.exp(K2 / (tirs_band + 273.15)) - 1)

    # Convertir a temperatura en Celsius
    lst = (radiance / emissivity) - 273.15
    return lst

