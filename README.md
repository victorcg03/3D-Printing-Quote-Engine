# Machine Shop Suite

**Open Source 3D Printing Quote Engine**

A production-ready web application for calculating accurate 3D printing quotes. Upload multiple STL files, configure print parameters, and get instant cost breakdowns with detailed pricing analysis. Perfect for 3D printing businesses, makerspaces, and service bureaus.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-green.svg)
![Flask](https://img.shields.io/badge/flask-3.0.0-lightgrey.svg)

**Created by [Burst Neuron](https://burstneuron.com) • Powered by [PrusaSlicer](https://www.prusa3d.com/page/prusaslicer_424/)**

---

## ✨ Features

### Core Functionality
- **📁 Multi-File Upload** - Upload and process multiple STL files at once with batch quoting
- **🎨 3D Preview** - Interactive Three.js viewer with multi-file support
- **💰 Accurate Quote Calculation** - Real-time pricing with detailed cost breakdown
- **⚡ Sequential Processing** - Queue-based processing to prevent server overload
- **📊 Detailed Breakdown** - Material, electricity, depreciation, markup, and operational costs

### Materials & Quality
- **🎨 Multiple Materials** - Support for PLA, ABS, PETG, TPU, and Nylon (fully customizable)
- **🎯 Quality Presets** - Draft (0.3mm), Standard (0.2mm), Fine (0.15mm), Ultra Fine (0.1mm)
- **🔧 Material Management** - Add/remove materials with custom pricing and properties

### Pricing & Configuration
- **💵 Printer-Specific Markup** - Configure profit margins per printer (e.g., 30% markup for premium printers)
- **🛠️ Post-Processing Options** - Customizable services (sanding, painting, polishing, threading)
- **🖨️ Multi-Printer Support** - Manage multiple printers with individual bed sizes, speeds, and markup multipliers
- **⚙️ Web-Based Admin Panel** - Configure pricing, materials, printers, and post-processing via UI
- **🌍 Multi-Currency Support** - Configure your preferred currency and tax rates

### Technical Features
- **🐳 Docker Ready** - One-command deployment with Docker Compose
- **🔒 Production Grade** - Logging, error handling, input validation, and security best practices
- **📱 Responsive Design** - Works seamlessly on desktop, tablet, and mobile devices
- **🎨 Modern UI** - Clean Tailwind CSS interface with intuitive navigation

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** or **Docker**
- **PrusaSlicer** installed and accessible in PATH

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/Machine-Shop-Suite/3D-Printing-Quote-Engine.git
cd 3D-Printing-Quote-Engine

# Start the application
docker-compose up -d

# Access the application
open http://localhost:5000
```

### Option 2: Manual Installation

```bash
# Clone the repository
git clone https://github.com/Machine-Shop-Suite/3D-Printing-Quote-Engine.git
cd 3D-Printing-Quote-Engine

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and set PRUSA_SLICER_PATH

# Run the application
python app.py
```

---

## 📖 Usage

### Getting a Quote

1. **Upload STL File** - Click "Upload STL" and select your 3D model
2. **Configure Settings**:
   - Choose material (PLA, ABS, PETG, TPU, Nylon)
   - Select print quality (Draft, Standard, Fine, Ultra Fine)
   - Set infill percentage (5-100%)
   - Enable supports if needed
3. **Set Quantity** - Specify how many copies you need
4. **Get Quote** - View detailed cost breakdown including:
   - Material cost
   - Electricity cost
   - Machine depreciation
   - Operational costs
   - Tax calculation
   - **Total price**

### Configuring Settings

Access the admin panel at `/settings` to configure:

- **Material Prices** - Set price per kg for each material
- **Material Properties** - Configure density, temperatures, and speeds
- **Pricing Parameters** - Base costs, electricity rates, depreciation
- **Tax Rates** - GST/VAT configuration
- **Printer Settings** - Bed size, nozzle diameter, speeds
- **Currency** - Set your preferred currency symbol

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file from `.env.example`:

```bash
# PrusaSlicer Configuration
PRUSA_SLICER_PATH=prusa-slicer  # or full path to executable

# Application Settings
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=your-secret-key-here
```

### Configuration File

The application uses `config.json` for all pricing and material settings. On first run, default values are created. Modify via:

- Web interface at `/settings`
- Direct editing of `config.json`
- API at `/api/settings`

Example `config.json` structure:

```json
{
  "materials": {
    "pla": {
      "name": "PLA (Polylactic Acid)",
      "price_per_kg": 800,
      "density_g_cm3": 1.24,
      "bed_temp": 55,
      "extruder_temp": 215,
      "colors": ["White", "Black", "Red", "Blue"]
    }
  },
  "pricing": {
    "base_cost": 150,
    "electricity_rate_per_kwh": 7,
    "printer_power_watts": 1000,
    "depreciation_per_hour": 50,
    "gst_rate": 0.18
  }
}
```

---

## 🏗️ Architecture

```
machine shop-suite/
├── app.py              # Main Flask application
├── config.py           # Configuration management
├── utils.py            # STL processing utilities
├── requirements.txt    # Python dependencies
├── Dockerfile          # Docker container definition
├── docker-compose.yml  # Docker orchestration
├── .env.example        # Environment template
├── config.json         # Runtime configuration (auto-generated)
├── templates/          # HTML templates
│   ├── index.html      # Quote engine UI
│   └── settings.html   # Admin configuration UI
├── static/             # CSS, JS, images
└── logs/               # Application logs
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main quote engine interface |
| `/settings` | GET | Admin configuration panel |
| `/api/config` | GET | Get current configuration |
| `/api/materials` | GET | List all available materials |
| `/api/slice` | POST | Analyze STL file (returns filament usage) |
| `/api/calculate-quote` | POST | Calculate quote with pricing breakdown |
| `/api/settings` | GET/POST | Get or update application settings |

---

## 🐳 Docker Deployment

### Build and Run

```bash
# Build the image
docker build -t machineshop-suite .

# Run the container
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/config.json:/app/config.json \
  -v $(pwd)/logs:/app/logs \
  --name machineshop \
  machineshop-suite
```

### Docker Compose (Recommended)

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild after changes
docker-compose up -d --build
```

---

## 🔧 Development

### Running Locally

```bash
# Install development dependencies
pip install -r requirements.txt

# Run in debug mode
FLASK_DEBUG=True python app.py

# Access at http://localhost:5000
```

### Project Structure

- **app.py** - Main application, routes, and API endpoints
- **config.py** - Configuration management with JSON persistence
- **utils.py** - STL slicing and G-code parsing utilities
- **templates/** - Jinja2 HTML templates
- **static/** - Frontend assets (CSS, JS, images)

### Adding New Materials

Edit `config.json` or use the `/settings` interface:

```json
{
  "materials": {
    "new_material": {
      "name": "New Material Name",
      "description": "Material description",
      "density_g_cm3": 1.25,
      "price_per_kg": 1200,
      "bed_temp": 60,
      "extruder_temp": 220,
      "perimeter_speed": 60,
      "infill_speed": 100,
      "solid_infill_speed": 80,
      "colors": ["Color1", "Color2"]
    }
  }
}
```

---

## 🛠️ Troubleshooting

### PrusaSlicer Not Found

**Error**: `PrusaSlicer not found at: prusa-slicer`

**Solution**:
1. Install PrusaSlicer from https://www.prusa3d.com/page/prusaslicer_424/
2. Set `PRUSA_SLICER_PATH` in `.env` to the correct path:
   - **Linux/Mac**: `/usr/bin/prusa-slicer` or `/usr/local/bin/prusa-slicer`
   - **Windows**: `C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe`
3. Verify installation: `prusa-slicer --version`

### Docker Container Issues

**Error**: Container fails to start

**Solution**:
```bash
# Check logs
docker-compose logs web

# Rebuild image
docker-compose build --no-cache

# Restart services
docker-compose restart
```

### File Upload Errors

**Error**: `File too large` or upload fails

**Solution**:
- Check file size (default limit: 100MB)
- Ensure STL file is valid
- Check disk space in upload directory

---

## 📝 Configuration Examples

### For Service Bureau

```json
{
  "pricing": {
    "base_cost": 200,
    "electricity_rate_per_kwh": 10,
    "depreciation_per_hour": 75,
    "gst_rate": 0.18
  }
}
```

### For Educational Institution

```json
{
  "pricing": {
    "base_cost": 50,
    "electricity_rate_per_kwh": 5,
    "depreciation_per_hour": 25,
    "gst_rate": 0.0
  }
}
```

### For Hobby/Maker Space

```json
{
  "pricing": {
    "base_cost": 100,
    "electricity_rate_per_kwh": 7,
    "depreciation_per_hour": 30,
    "gst_rate": 0.10
  }
}
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style

- Follow PEP 8 for Python code
- Use meaningful variable names
- Add docstrings to functions
- Comment complex logic

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **[Burst Neuron](https://burstneuron.com)** - Creator and maintainer of Machine Shop Suite
- **[PrusaSlicer](https://www.prusa3d.com/page/prusaslicer_424/)** - Excellent open-source slicing engine
- **[Flask](https://flask.palletsprojects.com/)** - Lightweight web framework
- **[Three.js](https://threejs.org/)** - 3D model visualization
- **[Tailwind CSS](https://tailwindcss.com/)** - Modern UI framework

---

## 📞 Support

### Community Support
- **Issues**: [GitHub Issues](https://github.com/Machine-Shop-Suite/3D-Printing-Quote-Engine/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Machine-Shop-Suite/3D-Printing-Quote-Engine/discussions)
- **Documentation**: [Wiki](https://github.com/Machine-Shop-Suite/3D-Printing-Quote-Engine/wiki)

### Professional Consultancy

Need help deploying or customizing Machine Shop Suite for your business?

**[Burst Neuron](https://burstneuron.com)** offers professional consultancy services for:
- 🚀 Production deployment and setup
- ⚙️ Custom feature development
- 🔧 Integration with existing systems
- 📊 Pricing strategy optimization
- 🎓 Training and onboarding
- 🛠️ Ongoing maintenance and support

**Contact**: [burstneuron1729@gmail.com](mailto:burstneuron1729@gmail.com?subject=Machine%20Shop%20Suite%20Consultation)

**Website**: [https://burstneuron.com](https://burstneuron.com)

---

## 🗺️ Roadmap

- [ ] Multi-printer support
- [ ] Batch quote calculation
- [ ] Quote history and export (CSV/PDF)
- [ ] REST API authentication
- [ ] Multi-language support
- [ ] Mobile-responsive UI improvements
- [ ] Support for SLA printing
- [ ] Integration with online payment gateways
- [ ] Customer portal for quote requests

---

**Made with ❤️ for the maker community**
