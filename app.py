"""
Machine Shop Suite - 3D Printing Quote Engine
Open source quote calculator for 3D printing services
"""
from flask import Flask, render_template, request, jsonify, abort
from werkzeug.utils import secure_filename
import os
import tempfile
import logging
from logging.handlers import RotatingFileHandler
from quotes_store import QuotesStore
from security import sign_quote, verify_quote
from config import config
from utils import allowed_file, convert_stl_to_gcode, extract_filament_usage

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")

ERR_NOT_FOUND = "No encontrado"

def require_admin():
    if not ADMIN_TOKEN:
        return True
    token = (
        request.args.get("token")
        or request.headers.get("X-Admin-Token")
        or request.headers.get("x-admin-token")
    )
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    return token == ADMIN_TOKEN
# Initialize Flask app
app = Flask(__name__)
quotes_store = QuotesStore()
app.config['MAX_CONTENT_LENGTH'] = config.get('file_settings', 'max_file_size_mb', default=100) * 1024 * 1024
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
# Configure logging
if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/quote_engine.log', maxBytes=10240000, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Machine Shop Suite startup')


def _is_enabled_printer(printer_key: str) -> bool:
    p = config.get_printer(printer_key)
    return bool(p and p.get("enabled", True))

def validate_quote_params(params: dict) -> dict:
    """
    Normaliza y valida params mínimos del quote.
    Devuelve params normalizados.
    Lanza ValueError con mensaje si no cuadra.
    """
    if not isinstance(params, dict):
        raise ValueError("params debe ser un objeto")

    material = (params.get("material") or "").strip().lower()
    quality = (params.get("quality") or "").strip().lower()
    printer = (params.get("printer") or "prusa_mk3s").strip().lower()

    # qty: aceptamos qty o quantity
    qty_raw = params.get("qty", params.get("quantity", 1))
    try:
        qty = int(qty_raw)
    except Exception:
        raise ValueError("qty debe ser un entero")
    if qty < 1:
        raise ValueError("qty debe ser >= 1")

    # infill_density opcional
    infill_raw = params.get("infill_density", 20)
    try:
        infill_density = int(infill_raw)
    except Exception:
        raise ValueError("infill_density debe ser un entero")
    if infill_density < 5 or infill_density > 100:
        raise ValueError("infill_density debe estar entre 5 y 100")

    if not material or not config.get_material(material):
        raise ValueError(f"material inválido: {material or '(vacío)'}")

    if not quality or not config.get("print_quality", quality):
        raise ValueError(f"calidad inválida: {quality or '(vacío)'}")

    # printer debe existir y estar enabled
    if not config.get_printer(printer) or not _is_enabled_printer(printer):
        raise ValueError(f"impresora inválida o deshabilitada: {printer}")

    # devuelve params normalizados
    return {
        "material": material,
        "quality": quality,
        "printer": printer,
        "qty": qty,
        "infill_density": infill_density,
        # puedes añadir aquí más campos permitidos si quieres
    }

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    """Main quote engine page"""
    materials = config.get_materials()
    qualities = config.get_print_qualities()
    infill_options = config.get('infill_options')
    printers = config.get_enabled_printers()

    return render_template('index.html',
                         materials=materials,
                         qualities=qualities,
                         infill_options=infill_options,
                         printers=printers)

@app.errorhandler(401)
def unauthorized(_):
    return jsonify({'success': False, 'error': 'No autorizado'}), 401

@app.route('/settings')
def settings_page():
    """Configuration settings page for admin"""
    if not require_admin():
        abort(401)
    return render_template('settings.html', config=config.config_data)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration (for frontend)"""
    try:
        return jsonify({
            'success': True,
            'config': {
                'materials': config.get_materials(),
                'print_qualities': config.get_print_qualities(),
                'infill_options': config.get('infill_options'),
                'pricing': config.get_pricing_config(),
                'printers': config.get_enabled_printers(),
                'post_processing': config.get_enabled_post_processing()
            }
        })
    except Exception as e:
        app.logger.error(f"Error getting config: {str(e)}")
        return jsonify({'success': False, 'error': 'No se pudo cargar la configuración'}), 500


@app.route('/api/materials', methods=['GET'])
def get_materials():
    """Get all available materials"""
    try:
        materials = config.get_materials()
        return jsonify({'success': True, 'materials': materials})
    except Exception as e:
        app.logger.error(f"Error getting materials: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/slice', methods=['POST'])
def analyze_stl():
    """
    Analyze STL file and calculate print requirements
    Returns filament usage and estimated time
    """
    # Validate file upload
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No se subió ningún archivo'}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'success': False, 'error': 'No se seleccionó ningún archivo'}), 400

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Tipo de archivo no válido. Solo se permiten archivos STL.'}), 400

    # Get parameters
    material = request.form.get('material', 'pla').lower()
    quality = request.form.get('quality', 'standard').lower()
    infill_density = request.form.get('infill_density', '20')
    support = request.form.get('support', 'false').lower() == 'true'
    printer = request.form.get('printer', 'prusa_mk3s').lower()

    # Validate material
    material_config = config.get_material(material)
    if not material_config:
        return jsonify({'success': False, 'error': f'Material inválido: {material}'}), 400

    # Validate quality
    quality_config = config.get('print_quality', quality)
    if not quality_config:
        return jsonify({'success': False, 'error': f'Calidad inválida: {quality}'}), 400

    # Validate printer
    printer_config = config.get_printer(printer)
    if not printer_config:
        return jsonify({'success': False, 'error': f'Impresora inválida: {printer}'}), 400

    # Validate infill
    try:
        infill_density = max(5, min(100, int(infill_density)))
    except ValueError:
        return jsonify({'success': False, 'error': 'Densidad de relleno no válida'}), 400

    # Prepare slicing parameters
    params = {
        'layer_height': quality_config.get('layer_height', 0.2),
        'infill_density': infill_density,
        'bed_temp': material_config.get('bed_temp', 60),
        'extruder_temp': material_config.get('extruder_temp', 210),
        'perimeter_speed': material_config.get('perimeter_speed', 60),
        'infill_speed': material_config.get('infill_speed', 80),
        'solid_infill_speed': material_config.get('solid_infill_speed', 60),
        'support': support
    }

    input_path = None
    output_path = None

    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{os.getpid()}_{filename}")
        output_filename = os.path.splitext(filename)[0] + ".gcode"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{os.getpid()}_{output_filename}")

        file.save(input_path)
        app.logger.info(f"Processing STL file: {filename}")

        # Convert STL to G-code
        slicer_path = config.get_slicer_path()
        success, error = convert_stl_to_gcode(input_path, output_path, params, slicer_path)

        if not success:
            app.logger.error(f"Slicing failed: {error}")
            return jsonify({'success': False, 'error': error}), 500

        # Extract filament usage and time
        filament_info = extract_filament_usage(output_path)

        if 'error' in filament_info:
            app.logger.error(f"Failed to extract filament info: {filament_info['error']}")
            return jsonify({'success': False, 'error': filament_info['error']}), 500

        return jsonify({
            'success': True,
            'data': filament_info
        })

    except Exception as e:
        app.logger.error(f"Error processing STL: {str(e)}")
        return jsonify({'success': False, 'error': f'El procesamiento falló: {str(e)}'}), 500

    finally:
        # Clean up temporary files
        for path in [input_path, output_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    app.logger.warning(f"Failed to delete temp file {path}: {str(e)}")


@app.route('/api/calculate-quote', methods=['POST'])
def calculate_quote():
    """
    Calculate complete quote with pricing breakdown
    """
    try:
        data = request.get_json()

        # Extract parameters
        material = data.get('material', 'pla').lower()
        quality = data.get('quality', 'standard').lower()
        printer = data.get('printer', 'prusa_mk3s').lower()
        infill_density = int(data.get('infill_density', 20))
        quantity = int(data.get('quantity', 1))
        filament_weight_g = float(data.get('filament_weight_g', 0))
        print_time_hours = float(data.get('print_time_hours', 0))

        # Optional post-processing
        post_processing_keys = data.get('post_processing', [])
        if isinstance(post_processing_keys, str):
            post_processing_keys = [post_processing_keys] if post_processing_keys else []

        # Get configuration
        material_config = config.get_material(material)
        printer_config = config.get_printer(printer)
        pricing_config = config.get_pricing_config()
        pricing_mode = config.get_pricing_mode()

        if not material_config:
            return jsonify({'success': False, 'error': 'Material inválido'}), 400
        if not printer_config:
            return jsonify({'success': False, 'error': 'Impresora inválida'}), 400

        # Currency
        currency = pricing_config.get('currency', 'EUR')
        currency_symbol = pricing_config.get('currency_symbol', '€')
        gst_rate = pricing_config.get('gst_rate', 0.18)

        # Check pricing mode
        if pricing_mode == 'per_gram':
            # Simple per-gram pricing
            per_gram_price = material_config.get('per_gram_price', 1.0)
            material_cost = filament_weight_g * per_gram_price

            # Post-processing costs (per unit)
            post_processing_cost_per_unit = 0
            post_processing_details = []

            for pp_key in post_processing_keys:
                pp_option = config.get_post_processing(pp_key)
                if pp_option and pp_option.get('enabled', True):
                    pp_price = pp_option.get('price', 0)
                    post_processing_cost_per_unit += pp_price
                    post_processing_details.append({
                        'key': pp_key,
                        'name': pp_option.get('name', pp_key),
                        'price': pp_price
                    })

            # Simple calculation: material_cost + post_processing per unit
            subtotal_per_unit = material_cost

            # Total before tax
            total_before_tax = (subtotal_per_unit * quantity) + (post_processing_cost_per_unit * quantity)

            # GST calculation
            gst_amount = total_before_tax * gst_rate

            # Final total
            total_price = total_before_tax + gst_amount

            # Return simplified breakdown for per-gram pricing
            return jsonify({
                'success': True,
                'quote': {
                    'breakdown': {
                        'pricing_mode': 'per_gram',
                        'per_gram_price': round(per_gram_price, 2),
                        'filament_weight_g': filament_weight_g,
                        'material_cost_per_unit': round(material_cost, 2),
                        'subtotal_per_unit': round(subtotal_per_unit, 2),
                        'quantity': quantity,
                        'subtotal_all_units': round(subtotal_per_unit * quantity, 2),
                        'post_processing_cost_per_unit': round(post_processing_cost_per_unit, 2),
                        'post_processing_cost_total': round(post_processing_cost_per_unit * quantity, 2),
                        'post_processing_details': post_processing_details,
                        'total_before_tax': round(total_before_tax, 2),
                        'gst_rate_percent': round(gst_rate * 100, 2),
                        'gst_amount': round(gst_amount, 2),
                        'total_price': round(total_price, 2)
                    },
                    'currency': currency,
                    'currency_symbol': currency_symbol,
                    'print_details': {
                        'material': material,
                        'material_name': material_config.get('name', material.upper()),
                        'printer': printer,
                        'printer_name': printer_config.get('name', printer.upper()),
                        'quality': quality,
                        'infill_density': infill_density,
                        'filament_weight_g': filament_weight_g,
                        'print_time_hours': print_time_hours,
                        'quantity': quantity
                    }
                }
            })

        # Custom pricing mode (original complex logic)
        # Calculate costs
        # 1. Material cost
        material_price_per_kg = material_config.get('price_per_kg', 1000)
        material_cost = (filament_weight_g / 1000) * material_price_per_kg

        # 2. Electricity cost
        electricity_rate = pricing_config.get('electricity_rate_per_kwh', 7)
        printer_power_kw = pricing_config.get('printer_power_watts', 1000) / 1000
        electricity_cost = printer_power_kw * print_time_hours * electricity_rate

        # 3. Depreciation cost (machine wear and tear)
        depreciation_cost = pricing_config.get('depreciation_per_hour', 50) * print_time_hours

        # 4. Other operational costs
        other_costs = pricing_config.get('other_costs_per_print', 20)

        # 5. Base cost (setup, handling, etc.)
        base_cost = pricing_config.get('base_cost', 150)

        # Cost before markup
        cost_before_markup = material_cost + electricity_cost + depreciation_cost + other_costs + base_cost

        # 6. Apply printer-specific markup
        markup_multiplier = printer_config.get('markup_multiplier', 1.3)
        subtotal_per_unit = cost_before_markup * markup_multiplier

        # Post-processing costs (per unit)
        post_processing_cost_per_unit = 0
        post_processing_details = []

        for pp_key in post_processing_keys:
            pp_option = config.get_post_processing(pp_key)
            if pp_option and pp_option.get('enabled', True):
                pp_price = pp_option.get('price', 0)
                post_processing_cost_per_unit += pp_price
                post_processing_details.append({
                    'key': pp_key,
                    'name': pp_option.get('name', pp_key),
                    'price': pp_price
                })

        # Total before tax
        total_before_tax = (subtotal_per_unit * quantity) + (post_processing_cost_per_unit * quantity)

        # GST calculation
        gst_amount = total_before_tax * gst_rate

        # Final total
        total_price = total_before_tax + gst_amount

        # Return custom pricing breakdown
        return jsonify({
            'success': True,
            'quote': {
                'breakdown': {
                    'pricing_mode': 'custom',
                    'material_cost_per_unit': round(material_cost, 2),
                    'electricity_cost_per_unit': round(electricity_cost, 2),
                    'depreciation_cost_per_unit': round(depreciation_cost, 2),
                    'other_costs_per_unit': round(other_costs, 2),
                    'base_cost_per_unit': round(base_cost, 2),
                    'cost_before_markup': round(cost_before_markup, 2),
                    'markup_multiplier': markup_multiplier,
                    'subtotal_per_unit': round(subtotal_per_unit, 2),
                    'quantity': quantity,
                    'subtotal_all_units': round(subtotal_per_unit * quantity, 2),
                    'post_processing_cost_per_unit': round(post_processing_cost_per_unit, 2),
                    'post_processing_cost_total': round(post_processing_cost_per_unit * quantity, 2),
                    'post_processing_details': post_processing_details,
                    'total_before_tax': round(total_before_tax, 2),
                    'gst_rate_percent': round(gst_rate * 100, 2),
                    'gst_amount': round(gst_amount, 2),
                    'total_price': round(total_price, 2)
                },
                'currency': currency,
                'currency_symbol': currency_symbol,
                'print_details': {
                    'material': material,
                    'material_name': material_config.get('name', material.upper()),
                    'printer': printer,
                    'printer_name': printer_config.get('name', printer.upper()),
                    'quality': quality,
                    'infill_density': infill_density,
                    'filament_weight_g': filament_weight_g,
                    'print_time_hours': print_time_hours,
                    'quantity': quantity
                }
            }
        })

    except Exception as e:
        app.logger.error(f"Error calculating quote: {str(e)}")
        return jsonify({'success': False, 'error': f'Falló el cálculo del presupuesto: {str(e)}'}), 500


@app.route('/api/settings', methods=['GET', 'POST'])
def manage_settings():
    """
    Get or update application settings
    GET: Return current settings
    POST: Update settings
    """
    if not require_admin():
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
    if request.method == 'GET':
        try:
            return jsonify({
                'success': True,
                'settings': config.config_data
            })
        except Exception as e:
            app.logger.error(f"Error getting settings: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

    elif request.method == 'POST':
        try:
            new_settings = request.get_json()

            # Update configuration
            config.config_data = new_settings

            # Save to file
            if config.save():
                app.logger.info("Settings updated successfully")
                return jsonify({'success': True, 'message': 'Ajustes actualizados correctamente'})
            else:
                return jsonify({'success': False, 'error': 'No se pudieron guardar los ajustes'}), 500

        except Exception as e:
            app.logger.error(f"Error updating settings: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500

@app.route("/api/quotes", methods=["POST"])
def create_quote():
    try:
        data = request.get_json() or {}

        # acepta payload plano o anidado
        params_in = data.get("params") or data.get("print_details") or data.get("printDetails") or data
        params = validate_quote_params(params_in)

        computed = data.get("computed") or data.get("quote") or data.get("breakdown") or {}

        quote_id = quotes_store.new_id()
        now = quotes_store.now()
        ttl = int(os.environ.get("QUOTE_TTL_SECONDS", "1800"))
        expires_at = now + ttl

        quote = {
            "quoteId": quote_id,
            "status": "estimated",
            "createdAtTs": now,
            "expiresAtTs": expires_at,
            "configVersion": config.get_config_version(),
            "params": params,
            "computed": computed,
            "price": computed.get("price") or computed.get("total_price") or computed.get("totalPrice"),
            "currency": computed.get("currency") or computed.get("currency_symbol") or "EUR",
        }

        quote["signature"] = sign_quote(quote)

        quotes_store.save(quote_id, quote)
        return jsonify({"success": True, "quote": quote}), 201

    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        app.logger.error(f"Error creating quote: {str(e)}")
        return jsonify({"success": False, "error": "No se pudo crear el presupuesto"}), 500
@app.route("/api/quotes", methods=["GET"])
def list_quotes():
    if not require_admin():
        return jsonify({"success": False, "error": "No autorizado"}), 401

    try:
        # paginación simple
        limit = int(request.args.get("limit", 50))
        limit = max(1, min(200, limit))

        cursor = request.args.get("cursor")  # opcional (si tu store lo soporta)
        status = request.args.get("status")  # opcional
        q = (request.args.get("q") or "").strip().lower()  # opcional

        # si tu QuotesStore todavía no tiene list(), lo implementamos después
        items = quotes_store.list(limit=limit, cursor=cursor, status=status, q=q)

        # listado "lite" (no devuelvas computed completo por defecto)
        lite = []
        for it in items.get("items", []):
            lite.append({
                "quoteId": it.get("quoteId"),
                "status": it.get("status"),
                "createdAtTs": it.get("createdAtTs"),
                "expiresAtTs": it.get("expiresAtTs"),
                "price": it.get("price"),
                "currency": it.get("currency", "EUR"),
                "params": it.get("params", {}),
            })

        return jsonify({
            "success": True,
            "items": lite,
            "nextCursor": items.get("nextCursor"),
        })

    except Exception as e:
        app.logger.error(f"Error listing quotes: {str(e)}")
        return jsonify({"success": False, "error": "No se pudieron listar los presupuestos"}), 500
    
@app.route("/api/quotes/<quote_id>", methods=["GET"])
def get_quote(quote_id: str):
    quote = quotes_store.load(quote_id)
    if not quote:
        return jsonify({"success": False, "error": ERR_NOT_FOUND}), 404

    # expira
    if quotes_store.is_expired(quote):
        quote["status"] = "expired"
        quote["signature"] = sign_quote(quote)
        quotes_store.save(quote_id, quote)

    return jsonify({"success": True, "quote": quote})

@app.route("/api/quotes/<quote_id>/refresh", methods=["POST"])
def refresh_quote(quote_id: str):
    """
    Refresca/normaliza un quote:
    - locked => 409
    - si config cambió => recalc_required (invalidamos computed/price)
    - si expiró => renueva TTL y vuelve a estimated (si config no cambió)
    """
    quote = quotes_store.load(quote_id)
    if not quote:
        return jsonify({"success": False, "error": ERR_NOT_FOUND}), 404

    if quote.get("status") == "locked":
        return jsonify({"success": False, "error": "El presupuesto está bloqueado"}), 409

    now = quotes_store.now()

    # Revalida params por si el storage tenía algo viejo/corrupto
    try:
        quote["params"] = validate_quote_params(quote.get("params") or {})
    except ValueError as ve:
        quote["status"] = "recalc_required"
        quote["error"] = f"parámetros inválidos: {str(ve)}"
        quote["computed"] = {}
        quote["price"] = None
        quote["signature"] = sign_quote(quote)
        quotes_store.save(quote_id, quote)
        return jsonify({"success": True, "quote": quote}), 200

    current_version = config.get_config_version()
    if quote.get("configVersion") != current_version:
        quote["status"] = "recalc_required"
        quote["requiredConfigVersion"] = current_version
        quote["computed"] = {}
        quote["price"] = None
        quote["currency"] = quote.get("currency", "EUR")
        quote["refreshedAtTs"] = now

        ttl = int(os.environ.get("QUOTE_TTL_SECONDS", "1800"))
        quote["expiresAtTs"] = now + ttl

        quote["signature"] = sign_quote(quote)
        quotes_store.save(quote_id, quote)
        return jsonify({"success": True, "quote": quote}), 200

    # si expiró, renueva
    if quotes_store.is_expired(quote):
        quote["status"] = "estimated"
        quote["refreshedAtTs"] = now
        ttl = int(os.environ.get("QUOTE_TTL_SECONDS", "1800"))
        quote["expiresAtTs"] = now + ttl

        quote["signature"] = sign_quote(quote)
        quotes_store.save(quote_id, quote)
        return jsonify({"success": True, "quote": quote}), 200

    # no expiró y config igual -> opcionalmente solo “tocar” TTL o no hacer nada
    extend_ttl = (request.get_json() or {}).get("extendTtl", False)
    if extend_ttl:
        ttl = int(os.environ.get("QUOTE_TTL_SECONDS", "1800"))
        quote["expiresAtTs"] = now + ttl

    quote["refreshedAtTs"] = now
    quote["signature"] = sign_quote(quote)
    quotes_store.save(quote_id, quote)

    return jsonify({"success": True, "quote": quote}), 200

@app.route("/api/quotes/<quote_id>/lock", methods=["POST"])
def lock_quote(quote_id: str):
    quote = quotes_store.load(quote_id)
    if not quote:
        return jsonify({"success": False, "error": ERR_NOT_FOUND}), 404

    if quotes_store.is_expired(quote):
        return jsonify({"success": False, "error": "El presupuesto ha expirado"}), 410

    # valida firma actual (si viene)
    body = request.get_json() or {}
    provided_sig = body.get("signature")
    if provided_sig and not verify_quote(quote, provided_sig):
        return jsonify({"success": False, "error": "Firma no válida"}), 400

    # si cambió config -> obliga recalcular (en este paso solo avisamos)
    current_version = config.get_config_version()
    required = quote.get("requiredConfigVersion") or quote.get("configVersion")
    if required != current_version:
        return jsonify({"success": False, "error": "La configuración cambió; es necesario recalcular"}), 409

    quote["status"] = "locked"
    quote["lockedAtTs"] = quotes_store.now()
    # opcional: reduce TTL al lock (ej: 10 min)
    lock_ttl = int(os.environ.get("QUOTE_LOCK_TTL_SECONDS", "600"))
    quote["expiresAtTs"] = quotes_store.now() + lock_ttl

    quote["signature"] = sign_quote(quote)
    quotes_store.save(quote_id, quote)

    return jsonify({"success": True, "quote": quote})
# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error"""
    max_size = config.get('file_settings', 'max_file_size_mb', default=100)
    return jsonify({
        'success': False,
        'error': f'Archivo demasiado grande. El tamaño máximo es {max_size}MB'
    }), 413


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'success': False, 'error': 'Recurso no encontrado'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    app.logger.error(f'Server Error: {error}')
    return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
