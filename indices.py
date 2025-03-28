# -*- coding: utf-8 -*-
"""
Módulo para el cálculo de índices radiométricos a partir de imágenes Landsat
"""

import rasterio
import numpy as np
import os
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import json


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
        from procesar import determine_required_bands

    # Encontrar la primera banda disponible para obtener el perfil
    profile = None
    ref_bands = determine_required_bands(selected_indices)  # Reutilizar la función existente
    
    # Intentar abrir una de las bandas para obtener su perfil
    for band in ref_bands:
        try:
            band_path = f"{base_path}_{band}.TIF"
            if os.path.exists(band_path):
                with rasterio.open(band_path) as src:
                    profile = src.profile.copy()
                    profile.update(dtype=rasterio.float32)
                print(f"Usando {band} como referencia para metadatos")
                break
        except Exception as e:
            continue
    
    # Si no se pudo obtener un perfil, mostrar un error claro
    if not profile:
        raise ValueError("No se encontró ninguna banda de referencia para obtener metadatos")
    
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

def process_indices_from_cutouts(recortes_path, output_path, selected_indices):
    """
    Procesa los índices a partir de recortes generados previamente.
    
    Args:
        recortes_path (str): Ruta donde se encuentran los archivos de recortes
        output_path (str): Ruta donde guardar los índices calculados
        selected_indices (list): Lista de índices a calcular
        
    Returns:
        dict: Diccionario con información de los índices calculados
    """
    print("\n==== CALCULANDO ÍNDICES A PARTIR DE RECORTES ====")
    
    # Crear directorio para resultados si no existe
    os.makedirs(output_path, exist_ok=True)
    
    # Buscar recortes disponibles
    print("Buscando recortes disponibles...")
    recortes = {}
    for file in os.listdir(recortes_path):
        if file.startswith("recorte_B") and file.endswith(".tif"):
            banda = file.replace("recorte_", "").replace(".tif", "")
            recortes[banda] = os.path.join(recortes_path, file)
    
    if not recortes:
        print("No se encontraron archivos de recortes en", recortes_path)
        return {}
    
    print(f"Recortes encontrados: {', '.join(recortes.keys())}")
    
    # Verificar qué índices podemos calcular con las bandas disponibles
    indices_realizables = []
    indices_no_realizables = {}
    
    for indice in selected_indices:
        bandas_necesarias = get_required_bands_for_index(indice)
        
        # Verificar qué bandas faltan
        bandas_faltantes = [banda for banda in bandas_necesarias if banda not in recortes]
        
        if not bandas_faltantes:
            indices_realizables.append(indice)
        else:
            indices_no_realizables[indice] = bandas_faltantes
    
    if not indices_realizables:
        print("No se pueden calcular los índices solicitados debido a bandas faltantes:")
        for indice, faltantes in indices_no_realizables.items():
            print(f" - {indice}: Faltan bandas {', '.join(faltantes)}")
        return {}
    
    print(f"Índices a calcular: {', '.join(indices_realizables)}")
    
    # Preparar estructura para los resultados
    output_files = {}
    
    # Cargar todas las bandas necesarias de una sola vez
    bands = {}
    for banda_code in recortes.keys():
        try:
            print(f"Cargando banda {banda_code}...")
            bands[banda_code] = read_band(recortes[banda_code])
            print(f" - {banda_code}: OK")
        except Exception as e:
            print(f" - {banda_code}: ERROR - {str(e)}")
    
    # Procesar cada índice
    for index in indices_realizables:
        try:
            print(f"\nCalculando índice {index}...")
            
            # Configurar rutas de salida para este índice
            tiff_path = os.path.join(output_path, f"{index}.tif")
            png_path = os.path.join(output_path, f"{index}.png")
            output_files[index] = {'tiff': tiff_path, 'png': png_path}
            
            # Calcular el índice según su tipo
            if index == "NDVI":
                # Verificar que tenemos las bandas necesarias
                if "B4" in bands and "B5" in bands:
                    red_data = bands["B4"]
                    nir_data = bands["B5"]
                    
                    epsilon = 1e-10
                    index_data = (nir_data - red_data) / (nir_data + red_data + epsilon)
                    
                    cmap_name = "RdYlGn"  # Rojo-Amarillo-Verde
                    vmin, vmax = -1.0, 1.0
                    title = "Índice de Vegetación de Diferencia Normalizada (NDVI)"
                else:
                    print(f"Error: Faltan bandas necesarias para NDVI")
                    continue
                
            elif index == "NDWI":
                if "B3" in bands and "B5" in bands:
                    green_data = bands["B3"]
                    nir_data = bands["B5"]
                    
                    epsilon = 1e-10
                    index_data = (green_data - nir_data) / (green_data + nir_data + epsilon)
                    
                    cmap_name = "Blues"  # Azules
                    vmin, vmax = -1.0, 1.0
                    title = "Índice de Agua de Diferencia Normalizada (NDWI)"
                else:
                    print(f"Error: Faltan bandas necesarias para NDWI")
                    continue
                
            elif index == "NDSI":
                if "B3" in bands and "B6" in bands:
                    green_data = bands["B3"]
                    swir_data = bands["B6"]
                    
                    epsilon = 1e-10
                    index_data = (green_data - swir_data) / (green_data + swir_data + epsilon)
                    
                    cmap_name = "Blues_r"  # Azules invertido
                    vmin, vmax = -1.0, 1.0
                    title = "Índice de Nieve de Diferencia Normalizada (NDSI)"
                else:
                    print(f"Error: Faltan bandas necesarias para NDSI")
                    continue
                
            elif index == "BSI":
                if "B2" in bands and "B4" in bands and "B5" in bands and "B6" in bands:
                    blue_data = bands["B2"]
                    red_data = bands["B4"]
                    nir_data = bands["B5"]
                    swir_data = bands["B6"]
                    
                    epsilon = 1e-10
                    num = (swir_data + red_data) - (nir_data + blue_data)
                    den = (swir_data + red_data) + (nir_data + blue_data) + epsilon
                    index_data = num / den
                    
                    cmap_name = "YlOrBr"  # Amarillo-Naranja-Marrón
                    vmin, vmax = -1.0, 1.0
                    title = "Índice de Suelo Desnudo (BSI)"
                else:
                    print(f"Error: Faltan bandas necesarias para BSI")
                    continue
                
            elif index == "LST":
                if "B10" in bands:
                    thermal_data = bands["B10"]
                    
                    # Constantes para Landsat 8/9
                    K1 = 774.8853
                    K2 = 1321.0789
                    
                    # Convertir los números digitales a radiancia (aproximación)
                    radiance = thermal_data * 0.1
                    
                    # Calcular temperatura en Kelvin a partir de radiancia
                    epsilon = 0.95  # Emisividad (aproximada)
                    index_data = K2 / (np.log((K1 / (radiance + 1e-10)) + 1))
                    
                    # Convertir de Kelvin a Celsius
                    index_data = index_data - 273.15
                    
                    cmap_name = "jet"  # Jet (azul-cian-amarillo-rojo)
                    vmin, vmax = 0, 50  # Celsius
                    title = "Temperatura de Superficie (LST)"
                else:
                    print(f"Error: Faltan bandas necesarias para LST")
                    continue
                
            else:
                print(f"Índice {index} no implementado")
                continue
            
            # Obtener el perfil (metadatos geoespaciales) de una de las bandas originales
            profile = None
            for band_code in get_required_bands_for_index(index):
                try:
                    with rasterio.open(recortes[band_code]) as src:
                        profile = src.profile.copy()
                        profile.update(dtype=rasterio.float32)
                    break
                except Exception as e:
                    continue
            
            if not profile:
                print(f"Error: No se pudo obtener el perfil de metadatos para {index}")
                continue
            
            # Guardar el índice como archivo GeoTIFF
            with rasterio.open(tiff_path, 'w', **profile) as dst:
                # Reemplazar NaN con nodata
                result_data_clean = np.where(np.isnan(index_data), -9999, index_data)
                dst.write(result_data_clean.astype(np.float32), 1)
            
            print(f"Índice {index} guardado en {tiff_path}")
            
            # Generar visualización del índice
            print(f"Generando visualización para {index}...")
            plt.figure(figsize=(12, 8))
            
            # Enmascarar valores nodata o NaN
            masked_data = np.ma.masked_where(
                (np.isnan(index_data)) | (index_data == -9999), 
                index_data
            )
            
            # Crear visualización con escala de colores apropiada
            plt.imshow(masked_data, cmap=plt.get_cmap(cmap_name), norm=Normalize(vmin=vmin, vmax=vmax))
            plt.colorbar(label=index)
            plt.title(title)
            
            # Guardar como imagen PNG
            plt.savefig(png_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"Visualización guardada en {png_path}")
            
            # Calcular estadísticas básicas
            valid_data = index_data[~np.isnan(index_data)]
            stats = {
                'min': float(np.min(valid_data)) if len(valid_data) > 0 else None,
                'max': float(np.max(valid_data)) if len(valid_data) > 0 else None,
                'mean': float(np.mean(valid_data)) if len(valid_data) > 0 else None,
                'std': float(np.std(valid_data)) if len(valid_data) > 0 else None
            }
            
            # Añadir información de estadísticas a la salida
            output_files[index].update(stats)
            
        except Exception as e:
            import traceback
            print(f"Error al calcular índice {index}: {str(e)}")
            print(traceback.format_exc())
    
    # Guardar un registro de los índices procesados
    if output_files:
        registro_path = os.path.join(output_path, "registro_indices.json")
        with open(registro_path, 'w') as f:
            json.dump(output_files, f, indent=4)
        print(f"\nRegistro de índices guardado en {registro_path}")
    
    return output_files

def get_required_bands_for_index(index_name):
    """
    Devuelve las bandas necesarias para calcular un índice determinado.
    
    Args:
        index_name (str): Nombre del índice
        
    Returns:
        list: Lista de bandas necesarias
    """
    index_requirements = {
        "NDVI": ["B4", "B5"],      # Rojo, NIR
        "NDWI": ["B3", "B5"],      # Verde, NIR
        "NDSI": ["B3", "B6"],      # Verde, SWIR
        "BSI": ["B2", "B4", "B5", "B6"],  # Azul, Rojo, NIR, SWIR1
        "LST": ["B10"]             # Térmico
    }
    
    # Siempre devolver una lista (incluso vacía) para evitar el error NoneType
    return index_requirements.get(index_name, [])

def process_indices_from_cutouts_wrapper(recortes_path, selected_indices):
    """
    Función envoltorio para procesar índices desde recortes.
    
    Args:
        recortes_path (str): Ruta donde se encuentran los recortes
        selected_indices (list): Lista de índices a calcular
        
    Returns:
        bool: True si el proceso fue exitoso, False en caso contrario
    """
    try:
        # Verificar que la ruta de recortes existe
        if not os.path.exists(recortes_path):
            print(f"Error: La ruta de recortes {recortes_path} no existe")
            return False
            
        # Verificar que hay índices seleccionados
        if not selected_indices or len(selected_indices) == 0:
            print("Error: No hay índices seleccionados para calcular")
            return False
            
        print(f"Índices seleccionados para calcular: {', '.join(selected_indices)}")
        
        # Crear directorio para salida
        output_path = "data/indices"
        os.makedirs(output_path, exist_ok=True)
        
        # Llamar a la función principal con manejo de errores
        try:
            results = process_indices_from_cutouts(recortes_path, output_path, selected_indices)
        except Exception as e:
            import traceback
            print(f"Error al procesar índices: {str(e)}")
            print(traceback.format_exc())
            return False
        
        # Verificar resultados
        if not results:
            print("No se pudieron calcular los índices solicitados.")
            return False
        
        # Mostrar resumen de los índices calculados
        print("\n==== RESUMEN DE ÍNDICES CALCULADOS ====")
        for index, info in results.items():
            stats_str = ""
            if 'min' in info and info['min'] is not None:
                stats_str = f"Min={info['min']:.2f}, Max={info['max']:.2f}, Media={info['mean']:.2f}"
            
            print(f"{index}: {os.path.basename(info['tiff'])} → {os.path.basename(info['png'])} {stats_str}")
        
        return True
    
    except Exception as e:
        import traceback
        print(f"Error al procesar índices: {str(e)}")
        print(traceback.format_exc())
        return False