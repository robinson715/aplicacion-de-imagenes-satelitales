# -*- coding: utf-8 -*-
import sys
from PyQt5.QtWidgets import QApplication
from interface import MapAppWindow

# Configuración global
current_config = {
    "import_mode": True,
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

# Bandera para saber si hay una nueva configuración
new_config_ready = False

def update_config(config):
    """
    Actualiza la configuración en memoria y establece la bandera.
    
    Args:
        config (dict): Nueva configuración
    """
    global current_config, new_config_ready
    current_config = config.copy()
    new_config_ready = True
    
    print("Configuración actualizada")

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
    """
    global new_config_ready
    new_config_ready = False

if __name__ == "__main__":
    # Iniciar la aplicación con interfaz gráfica
    app = QApplication(sys.argv)
    window = MapAppWindow()
    
    # Mostrar la ventana principal
    window.show()
    
    # Ejecutar la aplicación
    sys.exit(app.exec_())

