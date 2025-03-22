# -*- coding: utf-8 -*-
"""
Módulo para la descarga de imágenes Landsat desde USGS
"""

import os
import requests
from bs4 import BeautifulSoup
from config import USGS_USERNAME, USGS_PASSWORD

LOGIN_URL = "https://ers.cr.usgs.gov/login"

def login_usgs():
    """Inicia sesión en el sistema USGS y devuelve una sesión autenticada."""
    session = requests.Session()
    
    # Obtener la página de login para extraer el token CSRF
    response = session.get(LOGIN_URL)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.content, 'html.parser')
    csrf_token = soup.find('input', attrs={'name': 'csrf'})['value']

    # Datos del formulario de login
    login_data = {
        "username": USGS_USERNAME,
        "password": USGS_PASSWORD,
        "csrf": csrf_token
    }

    # Enviar la solicitud de login
    login_response = session.post(LOGIN_URL, data=login_data)
    login_response.raise_for_status()

    if login_response.status_code == 200:
        print("Sesión USGS iniciada correctamente")
    else:
        print("Falló la autenticación USGS")

    return session

def download_images(features, download_path="data/downloads", band="B4"):
    
    os.makedirs(download_path, exist_ok=True)
    session = login_usgs()
    
    if not features or len(features) == 0:
        print("No hay imágenes para descargar")
        return False
        
    for feat in features:
        # Verificar que existe la clave 'assets'
        if 'assets' not in feat:
            print(f"Error: La imagen {feat.get('id', 'desconocida')} no tiene la clave 'assets'")
            continue
        
        # Buscar la URL de descarga para la banda específica
        download_url = None
        potential_band_keys = [band, band.lower(), f"band{band[1:]}", f"band_{band[1:]}"]
        
        for key in potential_band_keys:
            if key in feat['assets'] and 'href' in feat['assets'][key]:
                download_url = feat['assets'][key]['href']
                print(f"Encontrada banda {band} como {key}")
                break
        
        # Si no encontramos la banda específica, buscar entre todos los assets
        if not download_url:
            for asset_key, asset_data in feat['assets'].items():
                if 'href' in asset_data and band.lower() in asset_key.lower():
                    download_url = asset_data['href']
                    print(f"Usando asset relacionado con banda {band}: {asset_key}")
                    break
        
        # Si todavía no hay URL, buscar cualquier archivo TIFF
        if not download_url:
            for asset_key, asset_data in feat['assets'].items():
                if ('href' in asset_data and 
                    any(asset_data['href'].lower().endswith(ext) for ext in ['.tif', '.tiff'])):
                    download_url = asset_data['href']
                    print(f"Usando asset alternativo con extensión TIFF: {asset_key}")
                    break
        
        if not download_url:
            print(f"Error: No se encontró URL de descarga para la banda {band}")
            continue
        
        # Crear el nombre del archivo local
        file_name = os.path.join(download_path, os.path.basename(download_url))
        print(f"Descargando: {os.path.basename(download_url)}")

        try:
            # Descargar la imagen con autenticación
            with session.get(download_url, stream=True) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                
                with open(file_name, 'wb') as file:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                        downloaded += len(chunk)
                        # Mostrar progreso cada 20%
                        if total_size > 0 and downloaded % (total_size // 5) < 8192:
                            percent = (downloaded / total_size) * 100
                            print(f"Progreso: {percent:.1f}%")
            
            print(f"Descargado: {file_name}")
            return True
        except Exception as e:
            print(f"Error al descargar {download_url}: {str(e)}")
            return False

def download_selective_bands(feature, required_bands, download_path="data/downloads"):
    """
    Descarga solo las bandas específicas de una imagen Landsat.
    
    Args:
        feature: Característica (feature) de Landsat
        required_bands: Lista de bandas requeridas (e.g., ["B2", "B4", "B5"])
        download_path: Ruta donde guardar las imágenes descargadas
        
    Returns:
        str: Ruta base para los archivos descargados, o None si falló
    """
    import os
    import requests
    from config import USGS_USERNAME, USGS_PASSWORD
    
    os.makedirs(download_path, exist_ok=True)
    
    # Iniciar sesión en USGS
    from downloader import login_usgs
    session = login_usgs()
    
    # Verificar si tiene assets
    if 'assets' not in feature:
        print(f"Error: La imagen {feature.get('id', 'desconocida')} no tiene la clave 'assets'")
        return None
    
    # Obtener ID de la escena
    scene_id = feature.get('id', 'unknown')
    print(f"Descargando bandas {', '.join(required_bands)} para la escena {scene_id}")
    
    # Mostrar los assets disponibles para diagnóstico
    print(f"Assets disponibles: {', '.join(feature['assets'].keys())}")
    
    # Determinar la ruta base para los archivos
    base_path = os.path.join(download_path, scene_id.split('_SR')[0])
    
    # Bandera para verificar si todas las descargas fueron exitosas
    all_successful = True
    downloaded_bands = []
    
    # Intentar diferentes estrategias para encontrar y descargar cada banda
    for band in required_bands:
        band_found = False
        
        # Lista de posibles variantes para cada banda
        band_variants = [
            band,                     # Ejemplo: "B4"
            band.lower(),             # Ejemplo: "b4"
            f"band{band[1:]}",        # Ejemplo: "band4"
            f"band_{band[1:]}",       # Ejemplo: "band_4"
            f"sr_{band.lower()}",     # Ejemplo: "sr_b4"
            f"{band.lower()}"         # Ejemplo: "b4"
        ]
        
        # Buscar la banda en todas sus variantes
        for variant in band_variants:
            if variant in feature['assets'] and 'href' in feature['assets'][variant]:
                download_url = feature['assets'][variant]['href']
                print(f"Encontrada banda {band} como '{variant}'")
                band_found = True
                break
        
        # Si no se encontró por nombre exacto, buscar cualquier asset que contenga el nombre de la banda
        if not band_found:
            for asset_key, asset_info in feature['assets'].items():
                if 'href' in asset_info and band.lower() in asset_key.lower():
                    download_url = asset_info['href']
                    print(f"Encontrada banda {band} en asset '{asset_key}'")
                    band_found = True
                    break
        
        # Si aún no se encuentra, intentar con otros patrones conocidos
        if not band_found:
            # Para Landsat, a veces las bandas están en URLs que siguen patrones específicos
            # Intentar construir la URL basada en otra URL conocida
            base_url = None
            
            # Buscar cualquier URL de asset que podamos usar como base
            for asset_key, asset_info in feature['assets'].items():
                if 'href' in asset_info and asset_info['href'].lower().endswith('.tif'):
                    base_url = asset_info['href']
                    break
            
            if base_url:
                # Intentar deducir el patrón de nombrado
                for pattern in [
                    lambda url, b: url.replace(url.split('_')[-1], f"{b}.TIF"),  # Reemplazar último segmento
                    lambda url, b: url.replace(url.split('_')[-1].split('.')[0], b)  # Reemplazar solo el nombre de banda
                ]:
                    try:
                        test_url = pattern(base_url, band)
                        # Verificar si la URL existe con una solicitud HEAD
                        head_response = session.head(test_url)
                        if head_response.status_code == 200:
                            download_url = test_url
                            print(f"Deducida URL para banda {band}: {download_url}")
                            band_found = True
                            break
                    except:
                        pass
        
        # Si no se pudo encontrar la banda, registrar el error
        if not band_found:
            print(f"Error: No se pudo encontrar la banda {band} en los assets disponibles")
            all_successful = False
            continue
        
        # Crear el nombre del archivo local
        file_name = os.path.join(download_path, f"{scene_id.split('_SR')[0]}_{band}.TIF")
        print(f"Descargando: {os.path.basename(file_name)}")

        try:
            # Descargar la imagen con autenticación
            with session.get(download_url, stream=True) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                
                with open(file_name, 'wb') as file:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                        downloaded += len(chunk)
                        # Mostrar progreso cada 20%
                        if total_size > 0 and downloaded % (total_size // 5) < 8192:
                            percent = (downloaded / total_size) * 100
                            print(f"Progreso: {percent:.1f}%")
            
            print(f"Descargado: {file_name}")
            downloaded_bands.append(band)
        except Exception as e:
            print(f"Error al descargar la banda {band}: {str(e)}")
            all_successful = False
    
    # Verificar que se descargaron todas las bandas requeridas
    if all_successful:
        print(f"Se descargaron todas las bandas requeridas: {', '.join(downloaded_bands)}")
        return base_path
    elif downloaded_bands:
        print(f"Advertencia: Solo se descargaron algunas bandas: {', '.join(downloaded_bands)}")
        print(f"Faltan las bandas: {', '.join(set(required_bands) - set(downloaded_bands))}")
        return base_path  # Devolver la ruta base para las bandas que sí se pudieron descargar
    else:
        print("Error: No se pudo descargar ninguna banda")
        return None
