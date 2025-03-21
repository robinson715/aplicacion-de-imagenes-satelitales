# -*- coding: utf-8 -*-
"""
Módulo para generar y ejecutar consultas a la API de LandsatLook
"""

import requests
import itertools
import json
import geopandas as gpd

def generate_landsat_query(file_path, start_date, end_date, cloud_cover=5, platform=["LANDSAT_8"], 
                           collections=["landsat-c2l2-sr"], limit=100, path=None, row=None):
     
    # Cargar el archivo en un GeoDataFrame
    gdf = gpd.read_file(file_path)
    
    # Obtener la geometría en formato GeoJSON
    geom = json.loads(gdf.to_json())['features'][0]['geometry']
    
    # Crear el query
    query = {
        "intersects": geom,
        "collections": collections,
        "query": {
            "eo:cloud_cover": {"lte": cloud_cover},
            "platform": {"in": platform},
            "landsat:collection_category": {"in": ["T1", "T2", "RT"]}
        },
        "datetime": f"{start_date}T00:00:00.000Z/{end_date}T23:59:59.999Z",
        "page": 1,
        "limit": limit
    }
    
    # Añadir filtros de path y row si se especifican
    if path is not None and path.strip():
        query["query"]["landsat:wrs_path"] = int(path)
    
    if row is not None and row.strip():
        query["query"]["landsat:wrs_row"] = int(row)
    
    return query

def fetch_stac_server(query):
    """
    Consulta el servidor STAC (LandsatLook) con manejo de paginación.
    
    Args:
        query: Diccionario Python para enviar como JSON en la petición
        
    Returns:
        list: Lista de características (imágenes) encontradas
    """
    headers = {
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip",
        "Accept": "application/geo+json",
    }

    url = "https://landsatlook.usgs.gov/stac-server/search"
    data = requests.post(url, headers=headers, json=query).json()
    error = data.get("message", "")
    if error:
        raise Exception(f"STAC-Server falló y devolvió: {error}")

    context = data.get("context", {})
    if not context.get("matched"):
        return []
        
    # Mostrar solo información relevante sobre los resultados
    print(f"Resultados: {context.get('matched')} imágenes, {context.get('returned')} en esta página")

    features = data["features"]
    if data["links"]:
        query["page"] += 1
        query["limit"] = context["limit"]

        features = list(itertools.chain(features, fetch_stac_server(query)))

    return features

