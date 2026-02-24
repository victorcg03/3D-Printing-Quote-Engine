"""
Configuration management for Machine Shop Suite - 3D Printing Quote Engine
"""
import os
import hashlib
import json
from pathlib import Path


class Config:
    """Application configuration with support for JSON file storage"""

    # Default PrusaSlicer path (overridden by environment variable or config file)
    DEFAULT_SLICER_PATH = "prusa-slicer"  # Assumes prusa-slicer is in PATH

    def get_config_version(self) -> str:
        """
        Hash estable de la config actual para invalidar quotes cuando cambian settings.
        """
        payload = json.dumps(self.config_data, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]

    def __init__(self, config_file=os.environ.get("CONFIG_FILE", "/app/data/config.json")):
        """Initialize configuration from file or defaults"""
        self.config_file = config_file
        self.config_data = self._load_config()

    def _load_config(self):
        """Load configuration from JSON file or return defaults"""
        if os.path.exists(self.config_file):
            try:
              with open(self.config_file, "r", encoding="utf-8") as f:
                   return json.load(f)
            except Exception as e:
                print(f"Error loading config file: {e}")
                return self._default_config()
        data = self._default_config()
        self.config_data = data
        self.save()
        return data

    def _default_config(self):
        """Return default configuration"""
        return {
            "application": {
                "name": "Machine Shop Suite",
                "version": "1.0.0",
                "description": "Motor de presupuestos de impresión 3D"
            },
            "slicer": {
                "path": os.getenv("PRUSA_SLICER_PATH", self.DEFAULT_SLICER_PATH),
                "timeout_seconds": 300
            },
            "materials": {
                "pla": {
                    "name": "PLA (Polylactic Acid)",
                    "description": "Fácil de imprimir, biodegradable, bueno para prototipos",
                    "density_g_cm3": 1.24,
                    "price_per_kg": 800,
                    "per_gram_price": 1.0,
                    "bed_temp": 55,
                    "extruder_temp": 215,
                    "perimeter_speed": 100,
                    "infill_speed": 180,
                    "solid_infill_speed": 160,
                    "colors": ["White", "Black", "Red", "Blue", "Green", "Yellow", "Orange", "Gray"]
                },
                "abs": {
                    "name": "ABS (Acrylonitrile Butadiene Styrene)",
                    "description": "Fuerte y duradero, resistente al calor, bueno para piezas funcionales",
                    "density_g_cm3": 1.04,
                    "price_per_kg": 1000,
                    "per_gram_price": 1.2,
                    "bed_temp": 90,
                    "extruder_temp": 245,
                    "perimeter_speed": 80,
                    "infill_speed": 160,
                    "solid_infill_speed": 140,
                    "colors": ["White", "Black", "Red", "Blue", "Natural"]
                },
                "petg": {
                    "name": "PETG (Polyethylene Terephthalate Glycol)",
                    "description": "Fuerte, flexible, resistente a químicos, opción apta para alimentos",
                    "density_g_cm3": 1.27,
                    "price_per_kg": 1000,
                    "per_gram_price": 1.2,
                    "bed_temp": 70,
                    "extruder_temp": 240,
                    "perimeter_speed": 70,
                    "infill_speed": 150,
                    "solid_infill_speed": 120,
                    "colors": ["Clear", "White", "Black", "Blue", "Red"]
                },
                "tpu": {
                    "name": "TPU (Thermoplastic Polyurethane)",
                    "description": "Flexible y elástico, excelente para agarres y amortiguación",
                    "density_g_cm3": 1.21,
                    "price_per_kg": 1500,
                    "per_gram_price": 2.0,
                    "bed_temp": 60,
                    "extruder_temp": 230,
                    "perimeter_speed": 30,
                    "infill_speed": 40,
                    "solid_infill_speed": 35,
                    "colors": ["Black", "White", "Red", "Blue", "Clear"]
                },
                "nylon": {
                    "name": "Nylon (Polyamide)",
                    "description": "Muy fuerte y duradero, excelente adhesión entre capas",
                    "density_g_cm3": 1.14,
                    "price_per_kg": 1800,
                    "per_gram_price": 2.5,
                    "bed_temp": 80,
                    "extruder_temp": 250,
                    "perimeter_speed": 60,
                    "infill_speed": 100,
                    "solid_infill_speed": 80,
                    "colors": ["Natural", "Black", "White"]
                }
            },
            "print_quality": {
                "draft": {
                    "name": "Borrador (Rápido)",
                    "layer_height": 0.3,
                    "description": "Impresión más rápida, capas visibles, buena para prototipos"
                },
                "standard": {
                    "name": "Estándar (Equilibrado)",
                    "layer_height": 0.2,
                    "description": "Buen equilibrio entre velocidad y calidad"
                },
                "fine": {
                    "name": "Fino (Detallado)",
                    "layer_height": 0.15,
                    "description": "Mayor detalle, mayor tiempo de impresión"
                },
                "ultra_fine": {
                    "name": "Ultrafino (Máximo detalle)",
                    "layer_height": 0.1,
                    "description": "Mejor calidad, impresión más lenta, líneas de capa mínimas"
                }
            },
            "infill_options": {
                "min_percentage": 5,
                "max_percentage": 100,
                "default_percentage": 20,
                "recommended": {
                    "prototype": 10,
                    "standard": 20,
                    "functional": 40,
                    "structural": 80,
                    "solid": 100
                }
            },
            "pricing": {
                "pricing_mode": "custom",
                "base_cost": 150,
                "electricity_rate_per_kwh": 7,
                "printer_power_watts": 1000,
                "depreciation_per_hour": 50,
                "other_costs_per_print": 20,
                "gst_rate": 0.18,
                "currency": "EUR",
                "currency_symbol": "€"
            },
            "printers": {
                "prusa_mk3s": {
                    "name": "Prusa i3 MK3S+",
                    "description": "Impresora FDM Original Prusa i3 MK3S+",
                    "bed_size_mm": [250, 210, 210],
                    "nozzle_diameter_mm": 0.4,
                    "max_print_speed_mm_s": 200,
                    "markup_multiplier": 1.3,
                    "enabled": True
                },
                "ender3_v2": {
                    "name": "Creality Ender 3 V2",
                    "description": "Impresora FDM económica Creality Ender 3 V2",
                    "bed_size_mm": [220, 220, 250],
                    "nozzle_diameter_mm": 0.4,
                    "max_print_speed_mm_s": 180,
                    "markup_multiplier": 1.25,
                    "enabled": True
                },
                "bambu_x1": {
                    "name": "Bambu Lab X1 Carbon",
                    "description": "Impresora de alta velocidad Bambu Lab X1 Carbon",
                    "bed_size_mm": [256, 256, 256],
                    "nozzle_diameter_mm": 0.4,
                    "max_print_speed_mm_s": 500,
                    "markup_multiplier": 1.4,
                    "enabled": True
                }
            },
            "post_processing": {
                "sanding": {
                    "name": "Lijado y alisado",
                    "description": "Lijado manual para un acabado de superficie suave",
                    "price": 500,
                    "enabled": True
                },
                "painting": {
                    "name": "Pintura",
                    "description": "Pintura en spray profesional con imprimación y capa final",
                    "price": 1500,
                    "enabled": True
                },
                "polishing": {
                    "name": "Pulido",
                    "description": "Pulido de alto brillo para un acabado estético",
                    "price": 800,
                    "enabled": True
                },
                "threading": {
                    "name": "Roscado/Machuelado",
                    "description": "Añadir rosca a los orificios para tornillos/pernos",
                    "price": 300,
                    "enabled": True
                }
            },
            "file_settings": {
                "max_file_size_mb": 100,
                "allowed_extensions": ["stl"],
                "upload_timeout_seconds": 300
            }
        }

    def save(self):
      """Save current configuration to JSON file (atomic write)"""
      try:
        config_path = Path(self.config_file)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = config_path.with_suffix(config_path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.config_data, f, indent=2, ensure_ascii=False)

        os.replace(tmp_path, config_path)  # atomic on same filesystem
        return True
      except Exception as e:
        print(f"Error saving config: {e}")
        return False

    def get(self, *keys, default=None):
        """Get nested configuration value using dot notation or keys"""
        data = self.config_data
        for key in keys:
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return default
        return data

    def set(self, value, *keys):
        """Set nested configuration value"""
        data = self.config_data
        for key in keys[:-1]:
            if key not in data:
                data[key] = {}
            data = data[key]
        data[keys[-1]] = value

    def get_materials(self):
        """Get all available materials"""
        return self.config_data.get('materials', {})

    def get_material(self, material_key):
        """Get specific material configuration"""
        return self.config_data.get('materials', {}).get(material_key)

    def get_print_qualities(self):
        """Get all print quality options"""
        return self.config_data.get('print_quality', {})

    def get_pricing_config(self):
        """Get pricing configuration"""
        return self.config_data.get('pricing', {})

    def get_pricing_mode(self):
        """Get pricing mode (custom or per_gram)"""
        return self.config_data.get('pricing', {}).get('pricing_mode', 'custom')

    def get_slicer_path(self):
        """Get PrusaSlicer executable path"""
        return self.config_data.get('slicer', {}).get('path', self.DEFAULT_SLICER_PATH)

    def get_printers(self):
        """Get all available printers"""
        return self.config_data.get('printers', {})

    def get_enabled_printers(self):
        """Get only enabled printers"""
        all_printers = self.get_printers()
        return {key: printer for key, printer in all_printers.items() if printer.get('enabled', True)}

    def get_printer(self, printer_key):
        """Get specific printer configuration"""
        return self.config_data.get('printers', {}).get(printer_key)

    def get_post_processing_options(self):
        """Get all available post-processing options"""
        return self.config_data.get('post_processing', {})

    def get_enabled_post_processing(self):
        """Get only enabled post-processing options"""
        all_options = self.get_post_processing_options()
        return {key: option for key, option in all_options.items() if option.get('enabled', True)}

    def get_post_processing(self, key):
        """Get specific post-processing option"""
        return self.config_data.get('post_processing', {}).get(key)


# Global configuration instance
config = Config()
