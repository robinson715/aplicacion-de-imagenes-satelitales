# -*- coding: utf-8 -*-
"""
Created on Tue Mar 18 18:37:27 2025

@author: robin
"""

import rasterio
import numpy as np

def process_selected_indices(base_path, selected_indices):
    """
    Procesa solo los índices seleccionados.
    
    Args:
        base_path: Ruta base de las imágenes descargadas
        selected_indices: Lista de índices a calcular
    
    Returns:
        dict: Resultados de los índices calculados
    """
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
        
        # Añadir lógica similar para otros índices...
    
    # Guardar resultados
    for name, data in results.items():
        output_file = f"{base_path}_{name}.TIF"
        # Guardar como GeoTIFF con metadatos de la imagen original
        # ...
    
    return results

def read_band(file_path):
    """Reads a single band from a .tif file and returns it as a numpy array."""
    with rasterio.open(file_path) as dataset:
        return dataset.read(1).astype(np.float32)

def calculate_ndvi(nir_band, red_band):
    """Calculates the Normalized Difference Vegetation Index (NDVI)."""
    ndvi = (nir_band - red_band) / (nir_band + red_band + 1e-10)  # Avoid division by zero
    return ndvi

def calculate_ndsi(swir_band, green_band):
    """Calculates the Normalized Difference Snow Index (NDSI)."""
    ndsi = (green_band - swir_band) / (green_band + swir_band + 1e-10)
    return ndsi

def calculate_ndwi(nir_band, green_band):
    """Calculates the Normalized Difference Water Index (NDWI)."""
    ndwi = (green_band - nir_band) / (green_band + nir_band + 1e-10)
    return ndwi

def calculate_bsi(nir_band, red_band, swir1_band, blue_band):
    """Calculates the Bare Soil Index (BSI)."""
    bsi = ((swir1_band + red_band) - (nir_band + blue_band)) / ((swir1_band + red_band) + (nir_band + blue_band) + 1e-10)
    return bsi

def calculate_lst(tirs_band, metadata):
    """Calculates the Land Surface Temperature (LST) using the thermal infrared (TIRS) band and metadata."""
    # Constants
    K1 = metadata['K1_CONSTANT']  # Extract from metadata
    K2 = metadata['K2_CONSTANT']
    emissivity = 0.97  # Approximate value for vegetation

    # Convert to radiance
    radiance = K1 / (np.exp(K2 / (tirs_band + 273.15)) - 1)

    # Convert to temperature in Celsius
    lst = (radiance / emissivity) - 273.15
    return lst