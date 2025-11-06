"""
Machine Shop Suite - 3D Printing Quote Engine
Open source quote calculator for 3D printing services
"""
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
import tempfile
import logging
from logging.handlers import RotatingFileHandler

from config import config
from utils import allowed_file, convert_stl_to_gcode, extract_filament_usage

# Initialize Flask app
app = Flask(__name__)
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


@app.route('/settings')
def settings_page():
    """Configuration settings page for admin"""
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
        return jsonify({'success': False, 'error': 'Failed to load configuration'}), 500


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
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Invalid file type. Only STL files are allowed.'}), 400

    # Get parameters
    material = request.form.get('material', 'pla').lower()
    quality = request.form.get('quality', 'standard').lower()
    infill_density = request.form.get('infill_density', '20')
    support = request.form.get('support', 'false').lower() == 'true'
    printer = request.form.get('printer', 'prusa_mk3s').lower()

    # Validate material
    material_config = config.get_material(material)
    if not material_config:
        return jsonify({'success': False, 'error': f'Invalid material: {material}'}), 400

    # Validate quality
    quality_config = config.get('print_quality', quality)
    if not quality_config:
        return jsonify({'success': False, 'error': f'Invalid quality: {quality}'}), 400

    # Validate printer
    printer_config = config.get_printer(printer)
    if not printer_config:
        return jsonify({'success': False, 'error': f'Invalid printer: {printer}'}), 400

    # Validate infill
    try:
        infill_density = max(5, min(100, int(infill_density)))
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid infill density'}), 400

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
        return jsonify({'success': False, 'error': f'Processing failed: {str(e)}'}), 500

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

        if not material_config:
            return jsonify({'success': False, 'error': 'Invalid material'}), 400
        if not printer_config:
            return jsonify({'success': False, 'error': 'Invalid printer'}), 400

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
        gst_rate = pricing_config.get('gst_rate', 0.18)
        gst_amount = total_before_tax * gst_rate

        # Final total
        total_price = total_before_tax + gst_amount

        # Currency
        currency = pricing_config.get('currency', 'INR')
        currency_symbol = pricing_config.get('currency_symbol', '₹')

        return jsonify({
            'success': True,
            'quote': {
                'breakdown': {
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
        return jsonify({'success': False, 'error': f'Calculation failed: {str(e)}'}), 500


@app.route('/api/settings', methods=['GET', 'POST'])
def manage_settings():
    """
    Get or update application settings
    GET: Return current settings
    POST: Update settings
    """
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
                return jsonify({'success': True, 'message': 'Settings updated successfully'})
            else:
                return jsonify({'success': False, 'error': 'Failed to save settings'}), 500

        except Exception as e:
            app.logger.error(f"Error updating settings: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error"""
    max_size = config.get('file_settings', 'max_file_size_mb', default=100)
    return jsonify({
        'success': False,
        'error': f'File too large. Maximum size is {max_size}MB'
    }), 413


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'success': False, 'error': 'Resource not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    app.logger.error(f'Server Error: {error}')
    return jsonify({'success': False, 'error': 'Internal server error'}), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
