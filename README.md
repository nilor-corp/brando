# Brando

A beautiful glass-morphism themed Gradio interface for ComfyUI workflows, with a GitHub Pages showcase site.

## 🎨 **GitHub Pages Site**

The main repository contains a showcase website at the root level:

- **`index.html`** - Main showcase page
- **`style.css`** - Website styling
- **`script.js`** - Website functionality
- **`mockup.html`** - Design mockup

Visit the site at: [https://nilor-corp.github.io/brando](https://nilor-corp.github.io/brando)

## 🤖 **Python Application**

The actual Gradio app is located in the `/app/` directory:

### Features

- **Simple Interface**: Clean, focused UI for specific workflows
- **Real-time Progress**: WebSocket connection to ComfyUI for live updates
- **File Upload**: Direct file handling without path dependencies
- **Beautiful Theme**: Glass-morphism styling inspired by the Brando design

## Workflows

Currently supports:

- **Logo to Video**: Generate videos from logos with pixel maps and reference images
- **Upscale**: AI-powered video upscaling

## 🚀 **Quick Start**

### For the Python App:

1. **Navigate to app directory**:

   ```bash
   cd app
   ```

2. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:

   ```bash
   cp env.example .env
   # Edit .env with your ComfyUI settings
   ```

4. **Test Setup** (optional):

   ```bash
   python test_setup.py
   ```

5. **Run the App**:
   ```bash
   python app.py
   ```

### For the Website:

The GitHub Pages site is automatically deployed from the root directory. No additional setup required.

## ⚙️ **Configuration**

Edit `app/.env` file to configure:

- `COMFY_IP`: ComfyUI server IP (default: 127.0.0.1)
- `COMFY_PORT`: ComfyUI server port (default: 8188)
- `BRANDO_PORT`: Brando app port (default: 7860)
- `BRANDO_HOST`: Brando app host (default: 0.0.0.0)

## Usage

1. Open the app in your browser (usually http://localhost:7860)
2. Select a workflow tab
3. Upload required files and enter parameters
4. Click the generate button
5. Monitor progress in real-time
6. View results in the output panel

## 📁 **Project Structure**

```
brando/
├── app/                    # Python Application
│   ├── app.py             # Main Gradio app
│   ├── brando.css         # Theme styling
│   ├── workflows.py       # Workflow definitions
│   ├── requirements.txt   # Python dependencies
│   ├── env.example       # Configuration template
│   ├── test_setup.py     # Setup verification
│   └── workflows/        # JSON workflow files
├── index.html             # GitHub Pages site
├── style.css              # Website styling
├── script.js              # Website functionality
├── mockup.html            # Design mockup
└── README.md              # This file
```

## 🏗️ **Architecture**

- **app.py**: Main Gradio application
- **brando.css**: Theme styling (glass-morphism design)
- **workflows.py**: Modular workflow definitions
- **WebSocket Connection**: Real-time communication with ComfyUI
- **File Handling**: Secure upload and storage
- **Workflow Management**: JSON-based workflow definitions

## 🔧 **Development**

To add new workflows:

1. Define the workflow in `app/workflows.py`
2. Create an execution function
3. Add UI components in `create_interface()`
4. Connect event handlers

## License

Part of the Brando project by Nilor Corp.
