# -*- coding: utf-8 -*-
"""
Created on Wed Mar  5 11:14:17 2025

@author: robin
"""

import os
import requests
from bs4 import BeautifulSoup
#from .config import USGS_USERNAME, USGS_PASSWORD
from config import USGS_USERNAME, USGS_PASSWORD

LOGIN_URL = "https://ers.cr.usgs.gov/login"

def login_usgs():
    """Logs into the USGS system and returns an authenticated session."""
    session = requests.Session()
    
    # Get the login page to extract the CSRF token
    response = session.get(LOGIN_URL)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.content, 'html.parser')
    csrf_token = soup.find('input', attrs={'name': 'csrf'})['value']

    # Login form data
    login_data = {
        "username": USGS_USERNAME,
        "password": USGS_PASSWORD,
        "csrf": csrf_token
    }

    # Send the login request
    login_response = session.post(LOGIN_URL, data=login_data)
    login_response.raise_for_status()

    if login_response.status_code == 200:
        print("Successfully logged into USGS")
    else:
        print("Authentication failed")

    return session

def download_images(features, download_path="data/downloads", band="B4"):
    """
    Descarga imágenes Landsat utilizando acceso autenticado a USGS.
    
    Args:
        features: Lista de características (imágenes) de Landsat
        download_path: Ruta donde guardar las descargas
        band: Banda específica a descargar (por defecto: B4 - banda roja)
    """
    import os
    
    os.makedirs(download_path, exist_ok=True)
    session = login_usgs()

    # Primero, imprimir la estructura del primer feature para depuración
    if features and len(features) > 0:
        feature = features[0]
        print("\nEstructura de la primera imagen:")
        print(f"ID: {feature.get('id', 'No ID')}")
        print("Claves disponibles:", list(feature.keys()))
        
        if 'assets' in feature:
            print("Assets disponibles:", list(feature['assets'].keys()))
        else:
            print("La clave 'assets' no está presente en la imagen")
            return False
    
    for feat in features:
        # Verificar que existe la clave 'assets'
        if 'assets' not in feat:
            print(f"Error: La imagen {feat.get('id', 'desconocida')} no tiene la clave 'assets'")
            continue
        
        # Intentar encontrar la banda específica primero
        download_url = None
        
        # 1. Intentar con la banda específica
        band_key = band.lower()  # Convertir a minúsculas para buscar
        
        # Buscar la banda en los assets (probar diferentes posibles nombres)
        potential_band_keys = [band, band.lower(), f"band{band[1:]}", f"band_{band[1:]}"]
        
        for key in potential_band_keys:
            if key in feat['assets'] and 'href' in feat['assets'][key]:
                download_url = feat['assets'][key]['href']
                print(f"Encontrada banda {band} como {key}")
                break
        
        # 2. Si no encontramos la banda específica, buscar en todas las claves de assets
        if not download_url:
            print(f"No se encontró la banda {band} directamente, buscando entre todos los assets...")
            
            # Buscar cualquier asset que contenga el nombre de la banda
            for asset_key, asset_data in feat['assets'].items():
                if 'href' in asset_data and band.lower() in asset_key.lower():
                    download_url = asset_data['href']
                    print(f"Usando asset relacionado con banda {band}: {asset_key}")
                    break
        
        # 3. Si todavía no hay URL, buscar cualquier asset que termine en .TIF o similar
        if not download_url:
            for asset_key, asset_data in feat['assets'].items():
                if 'href' in asset_data and (asset_data['href'].endswith('.TIF') or 
                                            asset_data['href'].endswith('.tif') or
                                            asset_data['href'].endswith('.tiff') or
                                            asset_data['href'].endswith('.TIFF')):
                    download_url = asset_data['href']
                    print(f"Usando asset alternativo con extensión TIFF: {asset_key}")
                    break
        
        # Verificar si encontramos una URL
        if not download_url:
            print(f"Error: No se encontró URL de descarga para la banda {band} en la imagen {feat.get('id', 'desconocida')}")
            print("Assets disponibles:", list(feat['assets'].keys()))
            continue
        
        # Crear el nombre del archivo local
        file_name = os.path.join(download_path, os.path.basename(download_url))
        print(f"Descargando: {os.path.basename(download_url)}")

        try:
            # Descargar la imagen con autenticación
            with session.get(download_url, stream=True) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                
                # Mostrar progreso
                print(f"Tamaño: {total_size / (1024*1024):.1f} MB")
                
                with open(file_name, 'wb') as file:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                        downloaded += len(chunk)
                        # Mostrar progreso cada 10%
                        if total_size > 0 and downloaded % (total_size // 10) < 8192:
                            percent = (downloaded / total_size) * 100
                            print(f"Progreso: {percent:.1f}%")
            
            print(f"Descargado: {file_name}")
        except Exception as e:
            print(f"Error al descargar {download_url}: {str(e)}")
    
        
def download_selective_bands(feature, required_bands, download_path="data/downloads"):
    """
    Descarga solo las bandas específicas de una imagen Landsat.
    
    Args:
        feature: Característica de imagen Landsat
        required_bands: Lista de bandas requeridas (ej: ["B4", "B5"])
        download_path: Directorio para guardar las descargas
    
    Returns:
        str: Ruta base de las bandas descargadas
    """
    os.makedirs(download_path, exist_ok=True)
    session = login_usgs()
    
    # Obtener la URL base y el ID de la imagen
    base_url = feature['assets']['sr']['href']
    image_id = os.path.basename(base_url).split('_')[0]
    base_path = os.path.join(download_path, image_id)
    
    for band in required_bands:
        # Construir URL específica para cada banda
        band_url = base_url.replace("sr.tif", f"{band}.TIF")
        file_name = os.path.join(download_path, os.path.basename(band_url))
        
        # Descargar la banda con autenticación
        with session.get(band_url, stream=True) as response:
            response.raise_for_status()
            with open(file_name, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
        print(f"Descargada banda {band}: {file_name}")
    
    return base_path    
