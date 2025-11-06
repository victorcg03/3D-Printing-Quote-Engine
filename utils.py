"""
Utility functions for 3D printing quote engine
"""
import os
import subprocess
import re


def allowed_file(filename):
    """
    Check if the uploaded file has an allowed extension

    Args:
        filename: Name of the file to check

    Returns:
        bool: True if file extension is allowed, False otherwise
    """
    ALLOWED_EXTENSIONS = {'stl'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def convert_stl_to_gcode(input_path, output_path, params, slicer_path):
    """
    Convert STL file to G-code using PrusaSlicer

    Args:
        input_path: Path to input STL file
        output_path: Path to output G-code file
        params: Dictionary containing slicing parameters
        slicer_path: Path to PrusaSlicer executable

    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    try:
        # Check if slicer exists
        if not os.path.exists(slicer_path):
            return False, f"PrusaSlicer not found at: {slicer_path}"

        # Build PrusaSlicer command
        cmd = [
            slicer_path,
            '--export-gcode',
            input_path,
            '--output', output_path,
            '--layer-height', str(params.get('layer_height', 0.2)),
            '--fill-density', f"{params.get('infill_density', 20)}%",
            '--bed-temperature', str(params.get('bed_temp', 60)),
            '--temperature', str(params.get('extruder_temp', 210)),
            '--perimeter-speed', str(params.get('perimeter_speed', 60)),
            '--infill-speed', str(params.get('infill_speed', 80)),
            '--solid-infill-speed', str(params.get('solid_infill_speed', 60)),
        ]

        # Add support material if enabled
        if params.get('support', False):
            cmd.extend(['--support-material'])

        # Run PrusaSlicer
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            error_msg = result.stderr if result.stderr else "Unknown slicing error"
            return False, f"Slicing failed: {error_msg}"

        # Check if output file was created
        if not os.path.exists(output_path):
            return False, "G-code file was not created"

        return True, None

    except subprocess.TimeoutExpired:
        return False, "Slicing timeout - file may be too complex"
    except Exception as e:
        return False, f"Slicing error: {str(e)}"


def extract_filament_usage(gcode_path):
    """
    Extract filament usage and print time from G-code file

    Args:
        gcode_path: Path to G-code file

    Returns:
        dict: Dictionary containing filament usage and time information
    """
    try:
        filament_used_mm = None
        filament_used_g = None
        filament_used_cm3 = None
        estimated_time_seconds = None

        with open(gcode_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

            # Try different PrusaSlicer comment formats
            # Format 1: ; filament used [mm] = 1234.56
            mm_match = re.search(r';\s*filament\s+used\s*\[mm\]\s*=\s*([\d.]+)', content, re.IGNORECASE)
            if mm_match:
                filament_used_mm = float(mm_match.group(1))

            # Format 2: ; filament used [g] = 12.34
            g_match = re.search(r';\s*filament\s+used\s*\[g\]\s*=\s*([\d.]+)', content, re.IGNORECASE)
            if g_match:
                filament_used_g = float(g_match.group(1))

            # Format 3: ; filament used [cm3] = 12.34
            cm3_match = re.search(r';\s*filament\s+used\s*\[cm3\]\s*=\s*([\d.]+)', content, re.IGNORECASE)
            if cm3_match:
                filament_used_cm3 = float(cm3_match.group(1))

            # Alternative format: ; filament_used_g = 12.34
            if filament_used_g is None:
                alt_g_match = re.search(r';\s*filament_used_g\s*=\s*([\d.]+)', content, re.IGNORECASE)
                if alt_g_match:
                    filament_used_g = float(alt_g_match.group(1))

            # Alternative format: ; filament_used_mm = 1234.56
            if filament_used_mm is None:
                alt_mm_match = re.search(r';\s*filament_used_mm\s*=\s*([\d.]+)', content, re.IGNORECASE)
                if alt_mm_match:
                    filament_used_mm = float(alt_mm_match.group(1))

            # Time parsing - multiple formats
            # Format 1: ; estimated printing time (normal mode) = 1h 23m 45s
            time_match = re.search(r';\s*estimated\s+printing\s+time.*?=\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
            if time_match:
                time_str = time_match.group(1).strip()

                hours = 0
                minutes = 0
                seconds = 0

                hour_match = re.search(r'(\d+)\s*h', time_str, re.IGNORECASE)
                if hour_match:
                    hours = int(hour_match.group(1))

                min_match = re.search(r'(\d+)\s*m(?:in)?', time_str, re.IGNORECASE)
                if min_match:
                    minutes = int(min_match.group(1))

                sec_match = re.search(r'(\d+)\s*s', time_str, re.IGNORECASE)
                if sec_match:
                    seconds = int(sec_match.group(1))

                estimated_time_seconds = hours * 3600 + minutes * 60 + seconds

        # Validate we got the essential data
        if filament_used_mm is None and filament_used_cm3 is None:
            # Try to estimate from G-code commands (fallback)
            filament_used_mm = estimate_filament_from_extrusion(gcode_path)

        if estimated_time_seconds is None or estimated_time_seconds == 0:
            estimated_time_seconds = 3600  # Default 1 hour if not found

        # Convert cm3 to mm if needed
        if filament_used_mm is None and filament_used_cm3 is not None:
            # Convert cm3 to length: volume = π * r² * length
            # r = 1.75/2 = 0.0875cm, length_cm = volume / (π * r²)
            filament_radius_cm = 0.175 / 2
            length_cm = filament_used_cm3 / (3.14159 * (filament_radius_cm ** 2))
            filament_used_mm = length_cm * 10  # cm to mm

        if filament_used_mm is None:
            filament_used_mm = 1000  # Default 1 meter

        # Calculate weight if not found
        if filament_used_g is None:
            if filament_used_cm3 is not None:
                # Use cm3 directly with PLA density
                filament_used_g = filament_used_cm3 * 1.24
            else:
                # Calculate from length
                # Volume = π * r² * length
                filament_radius_cm = 0.175 / 2  # 1.75mm diameter
                volume_cm3 = 3.14159 * (filament_radius_cm ** 2) * (filament_used_mm / 10)
                filament_used_g = volume_cm3 * 1.24  # PLA density

        return {
            'filament_length_mm': round(filament_used_mm, 2),
            'filament_weight_g': round(filament_used_g, 2),
            'estimated_time_seconds': estimated_time_seconds,
            'estimated_time_hours': round(estimated_time_seconds / 3600, 2)
        }

    except Exception as e:
        # Return default values instead of error
        return {
            'filament_length_mm': 1000,
            'filament_weight_g': 3.0,
            'estimated_time_seconds': 3600,
            'estimated_time_hours': 1.0,
            'warning': f'Using estimated values. Parse error: {str(e)}'
        }


def estimate_filament_from_extrusion(gcode_path):
    """
    Estimate filament length from E values in G-code (fallback method)
    """
    try:
        total_extrusion = 0
        with open(gcode_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if line.startswith('G1') and 'E' in line:
                    # Extract E value
                    e_match = re.search(r'E([\d.]+)', line)
                    if e_match:
                        e_val = float(e_match.group(1))
                        if e_val > total_extrusion:
                            total_extrusion = e_val
        return total_extrusion if total_extrusion > 0 else 1000
    except:
        return 1000
