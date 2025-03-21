# -*- coding: utf-8 -*-
"""
Módulo para verificar la cobertura de un polígono con escenas Landsat
"""

import geopandas as gpd
from shapely.geometry import shape, mapping, Polygon
import numpy as np
import matplotlib.pyplot as plt
import os

def get_footprint_from_feature(feature):
    """
    Extrae la huella (footprint) de una característica (feature) de Landsat.
    
    Args:
        feature: Característica de Landsat (de la API STAC)
        
    Returns:
        shapely.geometry.Polygon: Huella de la imagen
    """
    # Intentar obtener la huella directamente de los metadatos
    if 'geometry' in feature:
        return shape(feature['geometry'])
    
    # Si no está directamente, intentar construirla a partir de las propiedades
    if 'properties' in feature and all(k in feature['properties'] for k in ['landsat:bounds_north', 'landsat:bounds_south', 'landsat:bounds_east', 'landsat:bounds_west']):
        props = feature['properties']
        north = props['landsat:bounds_north']
        south = props['landsat:bounds_south']
        east = props['landsat:bounds_east']
        west = props['landsat:bounds_west']
        
        # Crear un polígono rectangular a partir de las coordenadas
        footprint = Polygon([
            (west, north),
            (east, north),
            (east, south),
            (west, south),
            (west, north)
        ])
        return footprint
    
    # Si no podemos determinar la huella, devolver None
    return None

def analyze_coverage(polygon_file, features):
    """
    Analiza la cobertura del polígono por las escenas Landsat con enfoque en Path/Row.
    Prioriza cobertura espacial, luego minimiza nubosidad y finalmente ajusta coherencia temporal.
    
    Args:
        polygon_file: Ruta al archivo GeoJSON o Shapefile del polígono
        features: Lista de características (features) de Landsat
        
    Returns:
        dict: Información de cobertura incluyendo porcentaje y escenas necesarias
    """
    import pandas as pd
    import numpy as np
    from shapely.ops import unary_union
    from datetime import datetime, timedelta
    
    print("Analizando cobertura con enfoque optimizado en Path/Row...")
    
    # Leer el polígono
    gdf_polygon = gpd.read_file(polygon_file)
    polygon = gdf_polygon.geometry.iloc[0]
    polygon_area = polygon.area
    
    # Lista para almacenar información de todas las escenas
    all_scenes = []
    
    # Extraer información de todas las escenas
    for i, feature in enumerate(features):
        footprint = get_footprint_from_feature(feature)
        if not footprint:
            continue
            
        # Obtener información de la escena
        props = feature.get('properties', {})
        scene_id = feature.get('id', f'Escena {i+1}')
        path = props.get('landsat:wrs_path', 'N/A')
        row = props.get('landsat:wrs_row', 'N/A')
        date_str = props.get('datetime', '')
        cloud = props.get('eo:cloud_cover', 100.0)  # Valor predeterminado alto
        
        # Convertir fecha a formato datetime
        try:
            date_obj = datetime.strptime(date_str[:10], '%Y-%m-%d') if date_str else None
        except:
            date_obj = None
        
        # Calcular intersección con el polígono
        intersection = polygon.intersection(footprint)
        intersection_area = intersection.area
        coverage_percent = (intersection_area / polygon_area) * 100
        
        # Incluir todas las escenas que tengan alguna intersección significativa con el polígono
        if coverage_percent > 0.00001:  # Umbral mínimo muy bajo para no descartar escenas importantes
            path_row = f"{path}_{row}"
            
            all_scenes.append({
                'id': scene_id,
                'path': path,
                'row': row,
                'path_row': path_row,
                'date_str': date_str[:10] if isinstance(date_str, str) else '',
                'date_obj': date_obj,
                'cloud_cover': cloud,
                'coverage_percent': coverage_percent,
                'footprint': footprint,
                'intersection_area': intersection_area
            })
    
    # Convertir a DataFrame para facilitar análisis
    scenes_df = pd.DataFrame(all_scenes)
    
    if scenes_df.empty:
        print("No se encontraron escenas con intersección significativa con el polígono.")
        return {
            'total_coverage_percent': 0,
            'coverage_by_scene': pd.DataFrame(),
            'scenes_needed': [],
            'uncovered_percent': 100
        }
    
    # FASE 1: Selección de cuadrantes Path/Row para cobertura máxima
    print("\nFASE 1: Seleccionando cuadrantes Path/Row para cobertura espacial...")
    
    # Identificar los cuadrantes Path/Row únicos
    path_row_groups = scenes_df.groupby('path_row')
    
    # Calcular la cobertura máxima que puede proporcionar cada cuadrante Path/Row
    path_row_coverage = {}
    
    for path_row, group in path_row_groups:
        # Todos los footprints son básicamente el mismo para un Path/Row dado
        # (solo varía por pequeñas diferencias de registro)
        coverage = group['coverage_percent'].max()
        path_row_coverage[path_row] = {
            'path_row': path_row,
            'path': group['path'].iloc[0],
            'row': group['row'].iloc[0],
            'coverage_percent': coverage,
            'scene_count': len(group)
        }
    
    # Convertir a DataFrame y ordenar por porcentaje de cobertura (mayor a menor)
    path_row_df = pd.DataFrame(path_row_coverage.values())
    path_row_df = path_row_df.sort_values('coverage_percent', ascending=False)
    
    print(f"Encontrados {len(path_row_df)} cuadrantes Path/Row únicos.")
    
    # Seleccionar cuadrantes hasta alcanzar cobertura completa
    selected_path_rows = []
    current_coverage = 0
    remaining_polygon = polygon
    
    for _, pr_info in path_row_df.iterrows():
        path_row = pr_info['path_row']
        
        # Tomar una escena cualquiera de este Path/Row para su footprint
        sample_scene = scenes_df[scenes_df['path_row'] == path_row].iloc[0]
        footprint = sample_scene['footprint']
        
        # Calcular cuánto del polígono restante cubre este footprint
        intersection = remaining_polygon.intersection(footprint)
        new_area_covered = intersection.area
        incremental_coverage = (new_area_covered / polygon_area) * 100
        
        # Umbral extremadamente bajo: cualquier contribución positiva es aceptada
        if incremental_coverage > 0.00001:  # Prácticamente cualquier contribución positiva
            selected_path_rows.append(path_row)
            
            # Actualizar el polígono restante y la cobertura actual
            remaining_polygon = remaining_polygon.difference(footprint)
            current_coverage += incremental_coverage
            
            print(f"Agregado cuadrante {path_row} con {pr_info['coverage_percent']:.2f}% de cobertura individual")
            print(f"Cobertura acumulada: {current_coverage:.2f}%")
            
            if current_coverage >= 99.99:  # Consideramos 99.99% como "cobertura completa"
                print("¡Cobertura completa alcanzada!")
                break
    
    if current_coverage < 99.99:
        print(f"Advertencia: Con todos los cuadrantes disponibles solo se logra {current_coverage:.2f}% de cobertura")
    
    print(f"Seleccionados {len(selected_path_rows)} cuadrantes Path/Row para lograr {current_coverage:.2f}% de cobertura")
    
    # FASE 2 y 3: Selección de escenas por nubosidad y coherencia temporal
    print("\nFASE 2 y 3: Seleccionando escenas con coherencia temporal y mínima nubosidad...")
    
    # Para cada Path/Row, obtener todas sus escenas ordenadas por nubosidad
    path_row_scenes = {}
    
    for path_row in selected_path_rows:
        # Obtener todas las escenas de este Path/Row y ordenarlas por nubosidad (menor primero)
        pr_scenes = scenes_df[scenes_df['path_row'] == path_row].copy()
        
        # Filtrar escenas sin fecha
        pr_scenes = pr_scenes[pr_scenes['date_obj'].notna()]
        
        if pr_scenes.empty:
            print(f"Advertencia: No hay escenas con fecha válida para {path_row}")
            continue
            
        # Ordenar por nubosidad
        pr_scenes = pr_scenes.sort_values('cloud_cover')
        
        # Guardar la lista ordenada de escenas
        path_row_scenes[path_row] = pr_scenes
    
    # Función para verificar si un conjunto de escenas cumple con el criterio temporal
    def check_temporal_coherence(scenes):
        if not scenes:
            return False, 0
            
        # Extraer las fechas
        dates = [scene['date_obj'] for scene in scenes if scene['date_obj'] is not None]
        
        if not dates or len(dates) < 2:
            return True, 0  # Si hay menos de 2 fechas, consideramos que cumple
            
        # Calcular diferencia entre la más reciente y la más antigua
        max_date = max(dates)
        min_date = min(dates)
        diff_days = (max_date - min_date).days
        
        return diff_days <= 120, diff_days  # 120 días = 4 meses aproximadamente
    
    # Estrategia de búsqueda de la mejor combinación
    # Comenzamos con las escenas de menor nubosidad y ajustamos iterativamente
    
    # Inicializar con la mejor escena de cada Path/Row
    best_scenes = []
    
    for path_row in path_row_scenes.keys():
        if not path_row_scenes[path_row].empty:
            best_scenes.append(path_row_scenes[path_row].iloc[0].to_dict())
    
    # Verificar coherencia temporal del conjunto inicial
    is_coherent, days_diff = check_temporal_coherence(best_scenes)
    
    print(f"Conjunto inicial: {len(best_scenes)} escenas, diferencia temporal: {days_diff} días")
    
    if is_coherent:
        print("¡El conjunto inicial ya cumple con el criterio temporal de 120 días!")
    else:
        print(f"El conjunto inicial supera el límite de 120 días. Ajustando...")
        
        # Intentaremos encontrar una combinación que cumpla el criterio temporal
        max_iterations = 1000  # Límite para evitar bucles infinitos
        iteration = 0
        
        # Estrategia de reemplazo más completa
        while not is_coherent and iteration < max_iterations:
            iteration += 1
            
            # Encontrar la escena más antigua
            dates = [(i, scene['date_obj']) for i, scene in enumerate(best_scenes) if scene['date_obj'] is not None]
            if not dates:
                break
                
            oldest_idx, oldest_date = min(dates, key=lambda x: x[1])
            oldest_scene = best_scenes[oldest_idx]
            oldest_path_row = oldest_scene['path_row']
            
            # Buscar la siguiente escena menos nubosa para este Path/Row
            pr_scenes = path_row_scenes[oldest_path_row]
            
            # Encontrar el índice de la escena actual en la lista ordenada
            current_scene_id = oldest_scene['id']
            current_idx = pr_scenes[pr_scenes['id'] == current_scene_id].index
            
            if len(current_idx) == 0:
                print(f"Error: No se pudo encontrar la escena {current_scene_id} en la lista")
                break
                
            current_idx = current_idx[0]
            
            # Verificar si hay más escenas disponibles
            next_idx = current_idx + 1
            if next_idx >= len(pr_scenes):
                print(f"No hay más escenas disponibles para {oldest_path_row}")
                
                # Probar cambiando la segunda escena más antigua
                dates = [(i, scene['date_obj']) for i, scene in enumerate(best_scenes) if scene['date_obj'] is not None]
                dates.sort(key=lambda x: x[1])  # Ordenar por fecha (ascendente)
                
                if len(dates) < 2:
                    print("No hay suficientes escenas con fecha para realizar ajustes")
                    break
                    
                # Tomar la segunda más antigua
                second_oldest_idx, _ = dates[1]
                second_oldest_scene = best_scenes[second_oldest_idx]
                second_oldest_path_row = second_oldest_scene['path_row']
                
                # Buscar la siguiente escena para este nuevo Path/Row
                pr_scenes_2 = path_row_scenes[second_oldest_path_row]
                current_scene_id_2 = second_oldest_scene['id']
                current_idx_2 = pr_scenes_2[pr_scenes_2['id'] == current_scene_id_2].index
                
                if len(current_idx_2) == 0:
                    print(f"Error: No se pudo encontrar la escena {current_scene_id_2} en la lista")
                    break
                    
                current_idx_2 = current_idx_2[0]
                next_idx_2 = current_idx_2 + 1
                
                if next_idx_2 >= len(pr_scenes_2):
                    print(f"No hay más escenas disponibles para {second_oldest_path_row} tampoco")
                    break
                    
                # Reemplazar la segunda escena más antigua
                best_scenes[second_oldest_idx] = pr_scenes_2.iloc[next_idx_2].to_dict()
            else:
                # Reemplazar la escena más antigua por la siguiente menos nubosa
                best_scenes[oldest_idx] = pr_scenes.iloc[next_idx].to_dict()
            
            # Verificar si el nuevo conjunto es coherente
            is_coherent, days_diff = check_temporal_coherence(best_scenes)
            
            if iteration % 10 == 0:  # Mostrar progreso cada 10 iteraciones
                print(f"Iteración {iteration}: diferencia temporal = {days_diff} días")
        
        if is_coherent:
            print(f"Se encontró una combinación coherente después de {iteration} iteraciones.")
            print(f"Diferencia temporal final: {days_diff} días")
        else:
            print(f"No se logró encontrar una combinación que cumpla el criterio temporal después de {iteration} iteraciones.")
            print(f"Diferencia temporal mínima encontrada: {days_diff} días")
            
            # Intentar un enfoque de ventana deslizante
            print("\nIntentando enfoque de ventana deslizante para encontrar coherencia temporal...")
            
            # Recopilar todas las escenas de los Path/Row seleccionados
            all_selected_scenes = []
            for path_row in path_row_scenes:
                all_selected_scenes.extend(path_row_scenes[path_row].to_dict('records'))
            
            # Filtrar escenas sin fecha
            all_selected_scenes = [scene for scene in all_selected_scenes if scene['date_obj'] is not None]
            
            # Ordenar por fecha
            all_selected_scenes.sort(key=lambda x: x['date_obj'])
            
            best_window_coherence = float('inf')
            best_window_scenes = None
            
            # Probar diferentes ventanas temporales
            for i, start_scene in enumerate(all_selected_scenes):
                start_date = start_scene['date_obj']
                end_date = start_date + timedelta(days=120)
                
                # Seleccionar escenas dentro de esta ventana
                window_scenes = [
                    scene for scene in all_selected_scenes 
                    if scene['date_obj'] >= start_date and scene['date_obj'] <= end_date
                ]
                
                # Verificar si esta ventana tiene al menos una escena de cada Path/Row
                path_rows_in_window = set(scene['path_row'] for scene in window_scenes)
                
                if len(path_rows_in_window) == len(selected_path_rows):
                    # Esta ventana contiene todos los Path/Row necesarios
                    # Seleccionar la mejor escena (menor nubosidad) para cada Path/Row
                    best_in_window = []
                    
                    for path_row in selected_path_rows:
                        pr_scenes_in_window = [
                            scene for scene in window_scenes if scene['path_row'] == path_row
                        ]
                        
                        if pr_scenes_in_window:
                            # Ordenar por nubosidad y tomar la mejor
                            pr_scenes_in_window.sort(key=lambda x: x['cloud_cover'])
                            best_in_window.append(pr_scenes_in_window[0])
                    
                    # Verificar coherencia temporal de esta selección
                    is_window_coherent, window_days_diff = check_temporal_coherence(best_in_window)
                    
                    if is_window_coherent and window_days_diff < best_window_coherence:
                        best_window_coherence = window_days_diff
                        best_window_scenes = best_in_window
                        print(f"Encontrada ventana coherente: {window_days_diff} días, {len(best_in_window)} escenas")
            
            if best_window_scenes:
                print(f"Se encontró una combinación coherente mediante ventana deslizante.")
                print(f"Diferencia temporal: {best_window_coherence} días")
                best_scenes = best_window_scenes
                is_coherent = True
            else:
                print("No se encontró ninguna ventana temporal que contenga todos los Path/Row necesarios.")
    
    # Preparar los datos de salida
    selected_scenes = []
    
    for scene in best_scenes:
        selected_scenes.append({
            'id': scene['id'],
            'path': scene['path'],
            'row': scene['row'],
            'date': scene['date_str'],
            'cloud_cover': scene['cloud_cover'],
            'coverage_percent': scene['coverage_percent']
        })
    
    # Calcular cobertura final con las escenas seleccionadas
    if best_scenes:
        selected_footprints = [scene['footprint'] for scene in best_scenes if 'footprint' in scene]
        final_combined = unary_union(selected_footprints)
        final_intersection = polygon.intersection(final_combined)
        final_coverage = (final_intersection.area / polygon_area) * 100
    else:
        final_coverage = 0
    
    print(f"\nResultado final: {len(selected_scenes)} escenas con {final_coverage:.2f}% de cobertura")
    
    if is_coherent:
        print("Las escenas seleccionadas cumplen con el criterio de coherencia temporal (máximo 120 días)")
    else:
        dates = [datetime.strptime(scene['date'], '%Y-%m-%d') for scene in selected_scenes if 'date' in scene]
        if dates and len(dates) >= 2:
            max_date = max(dates)
            min_date = min(dates)
            final_diff_days = (max_date - min_date).days
            final_diff_months = final_diff_days // 30
            print(f"ADVERTENCIA: Las escenas seleccionadas tienen una diferencia temporal de {final_diff_months} meses ({final_diff_days} días)")
    
    # Si no se tiene cobertura completa, advertir
    if final_coverage < 99.5:
        print(f"ADVERTENCIA: No se logró cobertura completa. Falta {100 - final_coverage:.2f}% del polígono")
    
    return {
        'total_coverage_percent': final_coverage,
        'coverage_by_scene': scenes_df.drop(columns=['footprint'], errors='ignore'),
        'scenes_needed': selected_scenes,
        'uncovered_percent': 100 - final_coverage
    }


def visualize_coverage(polygon_file, features, output_file='coverage_map.png', selected_scenes=None):
    """
    Genera una visualización de la cobertura del polígono por las escenas Landsat.
    
    Args:
        polygon_file: Ruta al archivo GeoJSON o Shapefile del polígono
        features: Lista de características (features) de Landsat
        output_file: Ruta para guardar la imagen de visualización
        selected_scenes: Lista opcional de escenas seleccionadas para destacar
        
    Returns:
        str: Ruta al archivo de visualización generado
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.colors import LinearSegmentedColormap
    import numpy as np
    
    # Leer el polígono
    gdf_polygon = gpd.read_file(polygon_file)
    
    # Crear una figura y eje
    fig, ax = plt.subplots(figsize=(14, 12))
    
    # Definir un colormap personalizado para las escenas seleccionadas
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
              '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    
    # Dibujar el polígono principal
    gdf_polygon.plot(ax=ax, color='none', edgecolor='red', linewidth=2.5, zorder=3)
    
    # Obtener IDs de escenas seleccionadas si existen
    selected_ids = []
    if selected_scenes:
        selected_ids = [scene.get('id') for scene in selected_scenes]
    
    # Crear diccionario para registrar qué path/row ya están dibujados (para escenas no seleccionadas)
    path_row_drawn = {}
    
    # Filtrar características por ID para dibujar primero las NO seleccionadas (fondo)
    for i, feature in enumerate(features):
        scene_id = feature.get('id', f'Escena {i+1}')
        
        # Si esta escena está en las seleccionadas, la dibujamos después
        if scene_id in selected_ids:
            continue
            
        # Obtener footprint e info
        footprint = get_footprint_from_feature(feature)
        if not footprint:
            continue
            
        props = feature.get('properties', {})
        path = props.get('landsat:wrs_path', 'N/A')
        row = props.get('landsat:wrs_row', 'N/A')
        path_row = f"{path}_{row}"
        
        # Si ya dibujamos este path/row, continuar
        if path_row in path_row_drawn:
            continue
            
        # Marcar este path/row como dibujado
        path_row_drawn[path_row] = True
        
        # Crear un GeoDataFrame para la huella
        gdf_footprint = gpd.GeoDataFrame(geometry=[footprint])
        
        # Dibujar la huella con color semitransparente
        gdf_footprint.plot(
            ax=ax, 
            color='lightgray', 
            alpha=0.2, 
            linewidth=0.5,
            edgecolor='gray',
            zorder=1
        )
        
        # Añadir una etiqueta muy pequeña con Path/Row
        centroid = footprint.centroid
        ax.text(
            centroid.x, centroid.y, 
            f"P{path}/R{row}",
            ha='center', va='center', 
            fontsize=6, 
            color='gray',
            zorder=2
        )
    
    # Ahora dibujar las escenas seleccionadas (primer plano)
    for i, scene_info in enumerate(selected_scenes or []):
        # Buscar la característica correspondiente
        scene_id = scene_info['id']
        scene_feature = None
        
        for feature in features:
            if feature.get('id') == scene_id:
                scene_feature = feature
                break
                
        if not scene_feature:
            continue
            
        # Obtener footprint
        footprint = get_footprint_from_feature(scene_feature)
        if not footprint:
            continue
            
        # Información adicional
        path = scene_info['path']
        row = scene_info['row']
        date = scene_info['date']
        cloud = scene_info['cloud_cover']
        
        # Crear un GeoDataFrame para la huella
        gdf_footprint = gpd.GeoDataFrame(geometry=[footprint])
        
        # Usar un color del ciclo de colores
        color_idx = i % len(colors)
        
        # Dibujar la huella con color distintivo
        gdf_footprint.plot(
            ax=ax, 
            color=colors[color_idx], 
            alpha=0.4, 
            linewidth=1.5,
            edgecolor='black',
            zorder=4
        )
        
        # Añadir etiqueta informativa
        centroid = footprint.centroid
        ax.text(
            centroid.x, centroid.y, 
            f"P{path}/R{row}\n{date}\nNubes: {cloud:.1f}%",
            ha='center', va='center', 
            fontsize=9, 
            fontweight='bold',
            bbox=dict(facecolor='white', alpha=0.8, edgecolor='black', boxstyle='round,pad=0.3'),
            zorder=5
        )
    
    # Ajustar los límites del mapa para mostrar todo el contenido
    # Añadir un margen del 5% alrededor del polígono
    minx, miny, maxx, maxy = gdf_polygon.total_bounds
    w, h = maxx - minx, maxy - miny
    ax.set_xlim(minx - 0.05*w, maxx + 0.05*w)
    ax.set_ylim(miny - 0.05*h, maxy + 0.05*h)
    
    # Título y configuración
    if selected_scenes:
        ax.set_title(f'Cobertura optimizada: {len(selected_scenes)} escenas ({coverage_info["total_coverage_percent"]:.1f}% de cobertura)', fontsize=14)
    else:
        ax.set_title('Cobertura del polígono con escenas Landsat disponibles', fontsize=14)
    
    # Configuración de ejes
    ax.set_xlabel('Longitud', fontsize=12)
    ax.set_ylabel('Latitud', fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.5)
    
    # Crear leyenda
    legend_elements = [
        mpatches.Patch(color='red', fill=False, linewidth=2.5, label='Polígono de interés'),
        mpatches.Patch(color='lightgray', alpha=0.2, linewidth=0.5, edgecolor='gray', label='Escenas disponibles')
    ]
    
    # Agregar cada escena seleccionada a la leyenda
    for i, scene_info in enumerate(selected_scenes or []):
        color_idx = i % len(colors)
        legend_elements.append(
            mpatches.Patch(
                color=colors[color_idx], 
                alpha=0.4, 
                edgecolor='black', 
                linewidth=1.5,
                label=f"P{scene_info['path']}/R{scene_info['row']} ({scene_info['date']})"
            )
        )
    
    ax.legend(handles=legend_elements, loc='lower right', fontsize=10)
    
    # Información adicional
    if selected_scenes:
        # Calcular rango de fechas
        dates = [scene.get('date') for scene in selected_scenes if scene.get('date')]
        date_range = f"{min(dates)} a {max(dates)}" if dates else "No disponible"
        
        # Calcular diferencia en meses (aproximada)
        try:
            from datetime import datetime
            date_objs = [datetime.strptime(d, '%Y-%m-%d') for d in dates]
            days_diff = (max(date_objs) - min(date_objs)).days
            months_diff = days_diff // 30
            date_diff = f"{months_diff} meses ({days_diff} días)"
        except:
            date_diff = "No calculable"
        
        info_text = (
            f"Escenas seleccionadas: {len(selected_scenes)}\n"
            f"Cobertura total: {coverage_info['total_coverage_percent']:.2f}%\n"
            f"Rango de fechas: {date_range}\n"
            f"Diferencia temporal: {date_diff}\n"
            f"Nubosidad promedio: {sum(s['cloud_cover'] for s in selected_scenes) / len(selected_scenes):.2f}%"
        )
        
        plt.figtext(0.02, 0.02, info_text, fontsize=10,
                   bbox=dict(facecolor='white', alpha=0.8, boxstyle='round'))
    
    # Guardar la figura
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    return output_file


def download_optimal_scenes(polygon_file, features, download_path='data/downloads'):
    """
    Descarga el conjunto óptimo de escenas para cubrir completamente el polígono.
    
    Args:
        polygon_file: Ruta al archivo GeoJSON o Shapefile del polígono
        features: Lista de características (features) de Landsat
        download_path: Ruta donde guardar las imágenes descargadas
        
    Returns:
        list: Lista de rutas a las imágenes descargadas
    """
    import os
    
    # Analizar la cobertura con el nuevo algoritmo optimizado
    coverage_info = analyze_coverage(polygon_file, features)
    
    # Obtener las escenas necesarias para la cobertura óptima
    scenes_needed = coverage_info['scenes_needed']
    
    if not scenes_needed:
        print("No se encontraron escenas que cubran el polígono de interés.")
        return []
    
    # Generar visualización con las escenas seleccionadas
    visualization_path = visualize_coverage(polygon_file, features, 
                                           selected_scenes=scenes_needed, 
                                           output_file='coverage_map.png')
    print(f"Mapa de cobertura generado: {visualization_path}")
    
    # Imprimir información de las escenas necesarias
    print(f"\nSe necesitan {len(scenes_needed)} escenas para cubrir el polígono:")
    for i, scene in enumerate(scenes_needed):
        print(f"{i+1}. {scene['id']} - Path {scene['path']}/Row {scene['row']} - "
              f"Fecha: {scene['date']} - Cobertura: {scene['coverage_percent']:.2f}%")
    
    # Importar la función de descarga
    from downloader import download_images
    
    # Descargar cada escena necesaria
    downloaded_files = []
    
    for i, scene_info in enumerate(scenes_needed):
        # Buscar la característica correspondiente en la lista original
        scene_id = scene_info['id']
        
        target_feature = None
        for feature in features:
            if feature.get('id') == scene_id:
                target_feature = feature
                break
        
        if target_feature:
            print(f"\nDescargando escena {i+1}/{len(scenes_needed)}: {scene_id}")
            
            # Crear un subdirectorio específico para esta escena
            scene_dir = os.path.join(download_path, f"scene_{scene_info['path']}_{scene_info['row']}")
            os.makedirs(scene_dir, exist_ok=True)
            
            # Descargar la escena
            success = download_images([target_feature], download_path=scene_dir)
            
            if success:
                print(f"Escena {scene_id} descargada correctamente")
                downloaded_files.append(scene_dir)
            else:
                print(f"Error al descargar la escena {scene_id}")
        else:
            print(f"No se encontró la característica correspondiente a {scene_id}")
    
    return downloaded_files