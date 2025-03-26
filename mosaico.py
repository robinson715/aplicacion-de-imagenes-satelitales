# -*- coding: utf-8 -*-
"""
Módulo para crear mosaicos de bandas y recortar según polígono de interés.
Este script trabaja con las bandas ya descargadas por el flujo existente.

Dependencias:
- GDAL/OGR: Para procesamiento geoespacial
- Rasterio: Para manejo de archivos raster
- NumPy: Para operaciones numéricas
- Geopandas: Para manejo de archivos vectoriales/polígonos
"""

import os
import sys
import glob
import json
import shutil
import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.mask import mask
from rasterio.warp import calculate_default_transform, reproject, Resampling
import geopandas as gpd
from shapely.geometry import shape, mapping
import logging
from osgeo import gdal

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mosaico')

def obtener_escenas_por_banda(download_path):
    """
    Busca todas las bandas descargadas y las organiza por tipo de banda.
    
    Args:
        download_path (str): Ruta donde se encuentran las carpetas de escenas descargadas
        
    Returns:
        dict: Diccionario con claves = nombres de bandas y valores = lista de tuplas 
              (ruta_archivo, cloud_cover)
    """
    logger.info("Buscando archivos de bandas descargadas...")
    
    bandas_organizadas = {}
    
    # Buscar todas las carpetas de escenas (asumimos que son subdirectorios del download_path)
    for scene_dir in glob.glob(os.path.join(download_path, "scene_*")):
        # Obtener el porcentaje de nubosidad de la escena
        # Buscamos en el nombre del directorio o en algún archivo de metadatos
        try:
            # Intentar obtener desde un archivo de metadatos si existe
            cloud_cover = obtener_cloud_cover_de_metadatos(scene_dir)
        except:
            # Si no hay metadatos, asumimos un valor alto para priorizar otras escenas
            cloud_cover = 100
            logger.warning(f"No se pudo determinar la nubosidad para {scene_dir}, asumiendo 100%")
        
        # Buscar todos los archivos TIF en esta carpeta
        for tif_file in glob.glob(os.path.join(scene_dir, "*.TIF")):
            # Determinar a qué banda corresponde el archivo
            # Ejemplo: LC09_L2SP_007057_20220315_20220317_02_T1_B4.TIF -> B4
            filename = os.path.basename(tif_file)
            
            # Extraer el nombre de la banda (asumimos formato *_B[número].TIF)
            for i in range(1, 12):  # Bandas de Landsat 8/9
                banda = f"B{i}"
                if f"_{banda}." in filename:
                    # Si la banda no está en el diccionario, crear una lista vacía
                    if banda not in bandas_organizadas:
                        bandas_organizadas[banda] = []
                    
                    # Agregar la ruta del archivo y el porcentaje de nubosidad
                    bandas_organizadas[banda].append((tif_file, cloud_cover))
                    break
    
    # Verificar si encontramos bandas
    if not bandas_organizadas:
        logger.error(f"No se encontraron archivos de bandas en {download_path}")
        return None
    
    # Mostrar información de las bandas encontradas
    for banda, archivos in bandas_organizadas.items():
        logger.info(f"Banda {banda}: {len(archivos)} archivos encontrados")
    
    return bandas_organizadas

def obtener_cloud_cover_de_metadatos(scene_dir):
    """
    Intenta obtener el porcentaje de nubosidad de los metadatos de la escena.
    
    Args:
        scene_dir (str): Ruta del directorio de la escena
        
    Returns:
        float: Porcentaje de nubosidad
    """
    # Buscar archivos de metadatos (MTL.txt, MTL.json, etc.)
    mtl_files = glob.glob(os.path.join(scene_dir, "*MTL.txt"))
    if mtl_files:
        try:
            # Leer el archivo de metadatos
            with open(mtl_files[0], 'r') as mtl_file:
                mtl_content = mtl_file.read()
                
                # Buscar la línea que contiene el porcentaje de nubosidad
                for line in mtl_content.split('\n'):
                    if 'CLOUD_COVER' in line:
                        # Extraer el valor numérico
                        cloud_cover = float(line.split('=')[1].strip())
                        return cloud_cover
        except Exception as e:
            logger.warning(f"Error al leer metadatos: {str(e)}")
    
    # Intentar obtener de otros archivos o del nombre de la carpeta
    # Si extraemos del nombre de la carpeta, la lógica dependerá de tu convención de nombres
    
    # Si estamos usando la información del script `download_optimal_scenes`, 
    # es posible que tengamos información en el directorio o en un archivo JSON específico
    info_files = glob.glob(os.path.join(scene_dir, "*_info.json"))
    if info_files:
        try:
            with open(info_files[0], 'r') as info_file:
                info_data = json.load(info_file)
                if 'cloud_cover' in info_data:
                    return float(info_data['cloud_cover'])
        except Exception as e:
            logger.warning(f"Error al leer archivo de info: {str(e)}")
    
    # Si no encontramos la información, lanzar excepción
    raise ValueError(f"No se pudo obtener la nubosidad para {scene_dir}")

def crear_mosaico_por_banda(archivos_banda, output_path, nombre_banda, temp_dir=None):
    """
    Crea un mosaico para una banda específica, priorizando escenas con menor nubosidad.
    
    Args:
        archivos_banda (list): Lista de tuplas (ruta_archivo, cloud_cover)
        output_path (str): Directorio donde guardar el mosaico resultante
        nombre_banda (str): Nombre de la banda (ej: "B4")
        temp_dir (str, optional): Directorio para archivos temporales
        
    Returns:
        str: Ruta al mosaico creado
    """
    logger.info(f"Creando mosaico para la banda {nombre_banda}...")
    
    # Crear directorio para mosaicos si no existe
    os.makedirs(output_path, exist_ok=True)
    
    # Crear directorio temporal si es necesario
    if temp_dir is None:
        temp_dir = os.path.join(output_path, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Ordenar archivos por nubosidad (menor a mayor)
    archivos_ordenados = sorted(archivos_banda, key=lambda x: x[1])
    
    # Ruta del mosaico final
    output_mosaic = os.path.join(output_path, f"mosaico_{nombre_banda}.tif")
    
    # Enfoque usando GDAL directamente (más control sobre el proceso)
    # Crear un archivo VRT para el mosaico
    vrt_path = os.path.join(temp_dir, f"mosaico_{nombre_banda}.vrt")
    
    # Definir opciones para el VRT
    # -allow_projection_difference: Permitir diferencias menores en proyecciones
    # -input_file_list: Usar un archivo con la lista de archivos de entrada
    # -resolution highest: Usar la resolución más alta disponible
    
    # Crear un archivo de texto con la lista de archivos ordenados por nubosidad
    list_file = os.path.join(temp_dir, f"filelist_{nombre_banda}.txt")
    with open(list_file, 'w') as f:
        for archivo, _ in archivos_ordenados:
            f.write(archivo + '\n')
    
    # Construir el comando para crear el VRT
    gdal_build_vrt_cmd = [
        'gdalbuildvrt',
        '-allow_projection_difference',
        '-resolution', 'highest',
        '-input_file_list', list_file,
        vrt_path
    ]
    
    # Ejecutar el comando
    cmd = ' '.join(gdal_build_vrt_cmd)
    logger.info(f"Ejecutando: {cmd}")
    
    try:
        gdal.BuildVRT(
            vrt_path, 
            [archivo for archivo, _ in archivos_ordenados],
            options=gdal.BuildVRTOptions(
                resolution='highest',
                separate=False,
                allowProjectionDifference=True
            )
        )
    except Exception as e:
        logger.error(f"Error al crear VRT: {str(e)}")
        # Ejecutar como proceso externo si falla la API
        import subprocess
        subprocess.run(cmd, shell=True, check=True)
    
    # Convertir el VRT al mosaico GeoTIFF final
    # -co COMPRESS=DEFLATE: Usar compresión DEFLATE
    # -co PREDICTOR=2: Usar predictor para mejorar compresión
    # -co TILED=YES: Usar estructura de tiles
    
    gdal_translate_cmd = [
        'gdal_translate',
        '-co', 'COMPRESS=DEFLATE',
        '-co', 'PREDICTOR=2',
        '-co', 'TILED=YES',
        vrt_path,
        output_mosaic
    ]
    
    cmd = ' '.join(gdal_translate_cmd)
    logger.info(f"Ejecutando: {cmd}")
    
    try:
        gdal.Translate(
            output_mosaic,
            vrt_path,
            options=gdal.TranslateOptions(
                creationOptions=['COMPRESS=DEFLATE', 'PREDICTOR=2', 'TILED=YES']
            )
        )
    except Exception as e:
        logger.error(f"Error al convertir VRT a GeoTIFF: {str(e)}")
        # Ejecutar como proceso externo si falla la API
        import subprocess
        subprocess.run(cmd, shell=True, check=True)
    
    logger.info(f"Mosaico para banda {nombre_banda} creado en {output_mosaic}")
    
    return output_mosaic

def recortar_mosaico_con_poligono(mosaico_path, poligono_path, output_path):
    """
    Recorta un mosaico de banda utilizando un polígono con manejo de diferentes CRS.
    
    Args:
        mosaico_path (str): Ruta al archivo mosaico
        poligono_path (str): Ruta al archivo del polígono (GeoJSON o Shapefile)
        output_path (str): Directorio donde guardar el recorte resultante
        
    Returns:
        str: Ruta al archivo recortado o None si ocurre un error
    """
    import os
    import rasterio
    from rasterio.mask import mask
    import geopandas as gpd
    from shapely.geometry import mapping, box
    import traceback
    
    try:
        print(f"Recortando mosaico {os.path.basename(mosaico_path)} con polígono...")
        
        # Crear directorio para recortes si no existe
        os.makedirs(output_path, exist_ok=True)
        
        # Ruta del archivo de salida
        nombre_banda = os.path.basename(mosaico_path).replace("mosaico_", "").replace(".tif", "")
        output_file = os.path.join(output_path, f"recorte_{nombre_banda}.tif")
        
        # Abrir el mosaico para obtener su CRS y extensión
        with rasterio.open(mosaico_path) as src:
            raster_crs = src.crs
            raster_bounds = src.bounds
            raster_bbox = box(raster_bounds.left, raster_bounds.bottom, 
                             raster_bounds.right, raster_bounds.top)
            
            print(f"CRS del raster: {raster_crs}")
            print(f"Extensión del raster: {raster_bounds}")
        
        # Cargar el polígono desde el archivo
        poligono_gdf = gpd.read_file(poligono_path)
        poligono_crs = poligono_gdf.crs
        
        print(f"CRS del polígono: {poligono_crs}")
        print(f"Extensión del polígono: {poligono_gdf.total_bounds}")
        
        # Verificar si los CRS son diferentes y reproyectar si es necesario
        if poligono_crs != raster_crs:
            print(f"Reproyectando polígono de {poligono_crs} a {raster_crs}")
            poligono_gdf = poligono_gdf.to_crs(raster_crs)
        
        # Crear un GeoDataFrame con el bbox del raster para verificar intersección
        raster_gdf = gpd.GeoDataFrame(geometry=[raster_bbox], crs=raster_crs)
        
        # Verificar intersección espacial antes de intentar recortar
        intersects = False
        for geom in poligono_gdf.geometry:
            if geom.intersects(raster_bbox):
                intersects = True
                break
        
        if not intersects:
            print("ERROR: El polígono no intersecta con el raster.")
            print("Intentando generar un recorte del área completa del raster como alternativa...")
            
            # Como alternativa, usar el bbox del raster como geometría de recorte
            geometries = [mapping(raster_bbox)]
        else:
            print("El polígono intersecta con el raster. Procediendo con el recorte normal.")
            geometries = [mapping(geom) for geom in poligono_gdf.geometry]
        
        # Abrir el mosaico y realizar el recorte
        with rasterio.open(mosaico_path) as src:
            # Realizar el recorte
            out_image, out_transform = mask(src, geometries, crop=True, all_touched=True)
            
            # Actualizar metadatos
            out_meta = src.meta.copy()
            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform,
                "compress": "deflate",
                "predictor": 2,
                "tiled": True
            })
            
            # Guardar el resultado
            with rasterio.open(output_file, "w", **out_meta) as dest:
                dest.write(out_image)
        
        # Verificar que el archivo se haya creado correctamente
        if os.path.exists(output_file):
            print(f"Recorte para banda {nombre_banda} creado en {output_file}")
            return output_file
        else:
            print(f"Error: No se pudo crear el archivo {output_file}")
            return None
            
    except Exception as e:
        print(f"Error al recortar mosaico {mosaico_path}: {str(e)}")
        print(traceback.format_exc())
        return None

def procesar_bandas_a_mosaicos_y_recortes(download_path, output_mosaicos, output_recortes, poligono_path, temp_dir=None):
    """
    Función principal que coordina el proceso completo:
    1. Busca todas las bandas descargadas
    2. Crea mosaicos por banda
    3. Recorta los mosaicos según el polígono
    
    Args:
        download_path (str): Ruta donde se encuentran las carpetas de escenas descargadas
        output_mosaicos (str): Directorio donde guardar los mosaicos resultantes
        output_recortes (str): Directorio donde guardar los recortes resultantes
        poligono_path (str): Ruta al archivo del polígono (GeoJSON o Shapefile)
        temp_dir (str, optional): Directorio para archivos temporales
        
    Returns:
        dict: Diccionario con rutas a los archivos generados
    """
    print("Iniciando proceso de creación de mosaicos y recortes...")
    
    # Verificar que el archivo del polígono exista
    if not os.path.exists(poligono_path):
        print(f"Error: El archivo del polígono {poligono_path} no existe")
        return None
    
    # Paso 1: Organizar las bandas descargadas
    bandas_organizadas = obtener_escenas_por_banda(download_path)
    
    if not bandas_organizadas:
        print("No se encontraron bandas para procesar")
        return None
    
    # Paso 2: Crear mosaicos para cada banda
    mosaicos_creados = {}
    
    for banda, archivos in bandas_organizadas.items():
        try:
            print(f"Creando mosaico para banda {banda}...")
            mosaico_path = crear_mosaico_por_banda(archivos, output_mosaicos, banda, temp_dir)
            
            if mosaico_path and os.path.exists(mosaico_path):
                mosaicos_creados[banda] = mosaico_path
                print(f"Mosaico creado exitosamente: {mosaico_path}")
            else:
                print(f"Error: No se pudo crear el mosaico para la banda {banda}")
        except Exception as e:
            import traceback
            print(f"Error al crear mosaico para banda {banda}: {str(e)}")
            print(traceback.format_exc())
            continue
    
    if not mosaicos_creados:
        print("No se pudo crear ningún mosaico")
        return None
    
    # Paso 3: Recortar los mosaicos según el polígono
    recortes_creados = {}
    
    for banda, mosaico_path in mosaicos_creados.items():
        try:
            print(f"Recortando mosaico para banda {banda}...")
            recorte_path = recortar_mosaico_con_poligono(mosaico_path, poligono_path, output_recortes)
            
            # Solo añadir al diccionario si se creó correctamente (no es None)
            if recorte_path is not None:
                recortes_creados[banda] = recorte_path
                print(f"Recorte creado exitosamente: {recorte_path}")
            else:
                print(f"Error: No se pudo crear el recorte para la banda {banda}")
        except Exception as e:
            import traceback
            print(f"Error al recortar mosaico para banda {banda}: {str(e)}")
            print(traceback.format_exc())
            continue
    
    # Resultados
    resultados = {
        "mosaicos": mosaicos_creados,
        "recortes": recortes_creados
    }
    
    # Guardar un registro de los archivos generados
    registro_path = os.path.join(output_recortes, "registro_procesamiento.json")
    with open(registro_path, 'w') as f:
        json.dump(resultados, f, indent=4)
    
    print(f"Procesamiento completado. Se generaron {len(mosaicos_creados)} mosaicos y {len(recortes_creados)} recortes.")
    print(f"Registro guardado en {registro_path}")
    
    return resultados

def limpiar_archivos_temporales(temp_dir):
    """
    Elimina archivos temporales generados durante el proceso.
    
    Args:
        temp_dir (str): Directorio de archivos temporales
    """
    if os.path.exists(temp_dir):
        logger.info(f"Limpiando archivos temporales en {temp_dir}")
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"Error al limpiar archivos temporales: {str(e)}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Crear mosaicos de bandas y recortar según polígono de interés")
    
    parser.add_argument("--download_path", type=str, required=True,
                        help="Ruta donde se encuentran las carpetas de escenas descargadas")
    
    parser.add_argument("--output_mosaicos", type=str, required=True,
                        help="Directorio donde guardar los mosaicos resultantes")
    
    parser.add_argument("--output_recortes", type=str, required=True,
                        help="Directorio donde guardar los recortes resultantes")
    
    parser.add_argument("--poligono", type=str, required=True,
                        help="Ruta al archivo del polígono (GeoJSON o Shapefile)")
    
    parser.add_argument("--temp_dir", type=str, default=None,
                        help="Directorio para archivos temporales")
    
    parser.add_argument("--limpiar_temp", action="store_true",
                        help="Limpiar archivos temporales al finalizar")
    
    args = parser.parse_args()
    
    # Ejecutar el proceso completo
    try:
        resultados = procesar_bandas_a_mosaicos_y_recortes(
            args.download_path,
            args.output_mosaicos,
            args.output_recortes,
            args.poligono,
            args.temp_dir
        )
        
        if args.limpiar_temp and args.temp_dir:
            limpiar_archivos_temporales(args.temp_dir)
        
        if resultados:
            logger.info("Proceso completado exitosamente")
            
            # Mostrar lista de archivos generados
            logger.info("Mosaicos generados:")
            for banda, ruta in resultados["mosaicos"].items():
                logger.info(f"  {banda}: {ruta}")
            
            logger.info("Recortes generados:")
            for banda, ruta in resultados["recortes"].items():
                logger.info(f"  {banda}: {ruta}")
            
            sys.exit(0)
        else:
            logger.error("No se generaron resultados")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Error en el proceso principal: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

