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
    """
    os.makedirs(download_path, exist_ok=True)
    session = login_usgs()
    
    # Verificar si tiene assets
    if 'assets' not in feature:
        print(f"Error: La imagen {feature.get('id', 'desconocida')} no tiene la clave 'assets'")
        return None
    
    # Encontrar una URL base para las bandas
    base_url = None
    for asset_key in ['sr', 'surface_reflectance', 'reflectance']:
        if asset_key in feature['assets'] and 'href' in feature['assets'][asset_key]:
            base_url = feature['assets'][asset_key]['href']
            break
    
    if not base_url:
        # Si no hay URL específica, usar la primera disponible
        for asset_key, asset_data in feature['assets'].items():
            if 'href' in asset_data:
                base_url = asset_data['href']
                break
    
    if not base_url:
        print("No se pudo encontrar una URL base para descargar las bandas")
        return None
    
    # Obtener el ID de la imagen desde la URL
    image_id = os.path.basename(base_url).split('_')[0]
    base_path = os.path.join(download_path, image_id)
    
    for band in required_bands:
        # Construir URL específica para cada banda (adaptable a diferentes formatos de nombre)
        band_url = None
        if base_url.lower().endswith('.tif'):
            # Si termina en .tif, sustituir la extensión
            band_url = base_url.replace(".tif", f"_{band}.TIF").replace(".TIF", f"_{band}.TIF")
        else:
            # En otro caso, simplemente añadir la banda
            band_url = f"{base_url}_{band}.TIF"
        
        file_name = os.path.join(download_path, os.path.basename(band_url))
        
        try:
            # Descargar la banda con autenticación
            with session.get(band_url, stream=True) as response:
                response.raise_for_status()
                with open(file_name, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
            print(f"Descargada banda {band}: {file_name}")
        except Exception as e:
            print(f"Error al descargar la banda {band}: {str(e)}")
    
    return base_path

