import os
import json
import requests
import time
import uuid
import websocket
import threading
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
import gradio as gr
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define app directory at the top to be used in other functions
APP_DIR = Path(__file__).parent.resolve()

# Configuration
COMFY_IP = os.getenv("COMFY_IP", "127.0.0.1")
COMFY_PORT = os.getenv("COMFY_PORT", "8188")
COMFY_URL = f"http://{COMFY_IP}:{COMFY_PORT}"
WS_URL = f"ws://{COMFY_IP}:{COMFY_PORT}/ws"


# App state
class AppState:
    def __init__(self):
        self.client_id = str(uuid.uuid4())
        self.ws = None
        self.ws_connected = False
        self.current_progress = {}
        self.job_tracking = {}
        self.latest_output = None


app_state = AppState()


# WebSocket connection
def connect_websocket():
    """Connect to ComfyUI WebSocket for real-time updates"""
    try:
        app_state.ws = websocket.WebSocket()
        app_state.ws.connect(f"{WS_URL}?clientId={app_state.client_id}")
        app_state.ws_connected = True
        print(f"Connected to WebSocket: {WS_URL}")

        # Start listening thread
        def listen_websocket():
            while app_state.ws_connected:
                try:
                    message = app_state.ws.recv()
                    if message:
                        data = json.loads(message)
                        handle_websocket_message(data)
                except websocket.WebSocketConnectionClosedException:
                    print("WebSocket connection closed")
                    app_state.ws_connected = False
                    break
                except Exception as e:
                    print(f"WebSocket error: {e}")
                    time.sleep(1)

        thread = threading.Thread(target=listen_websocket, daemon=True)
        thread.start()
        return True
    except Exception as e:
        print(f"Failed to connect to WebSocket: {e}")
        return False


def handle_websocket_message(data):
    """Handle incoming WebSocket messages"""
    msg_type = data.get("type")
    msg_data = data.get("data", {})

    if msg_type == "executing":
        node_id = msg_data.get("node")
        if node_id:
            print(f"Executing node: {node_id}")
            app_state.current_progress = {"node": node_id, "status": "executing"}

    elif msg_type == "progress":
        app_state.current_progress.update(msg_data)
        print(f"Progress: {msg_data}")

    elif msg_type == "executed":
        node_id = msg_data.get("node")
        if node_id:
            print(f"Completed node: {node_id}")
            app_state.current_progress = {"node": node_id, "status": "completed"}


# ComfyUI API functions
def comfy_post(endpoint: str, data: Dict) -> Optional[Dict]:
    """Make POST request to ComfyUI API"""
    try:
        url = f"{COMFY_URL}/{endpoint}"
        response = requests.post(url, json=data)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"API error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Request error: {e}")
        return None


def comfy_get(endpoint: str) -> Optional[Dict]:
    """Make GET request to ComfyUI API"""
    try:
        url = f"{COMFY_URL}/{endpoint}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"API error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Request error: {e}")
        return None


def submit_workflow(workflow_data: Dict) -> Optional[str]:
    """Submit a workflow to ComfyUI"""
    prompt_data = {"prompt": workflow_data, "client_id": app_state.client_id}

    result = comfy_post("prompt", prompt_data)
    if result and "prompt_id" in result:
        prompt_id = result["prompt_id"]
        app_state.job_tracking[prompt_id] = {
            "status": "pending",
            "timestamp": time.time(),
            "workflow": workflow_data,
        }
        return prompt_id
    return None


def get_queue_status() -> Dict:
    """Get current queue status"""
    return comfy_get("queue") or {}


def interrupt_processing():
    """Interrupt current processing"""
    comfy_post("interrupt", {})


# File handling
def save_uploaded_file(file, subfolder: str = "") -> Optional[str]:
    """Save uploaded file and return the path"""
    if not file:
        return None

    try:
        # Create upload directory
        upload_dir = Path("uploads") / subfolder
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Save file
        filename = file.name
        filepath = upload_dir / filename

        with open(filepath, "wb") as f:
            f.write(file.read())

        return str(filepath)
    except Exception as e:
        print(f"Error saving file: {e}")
        return None


# Import workflow definitions
from workflows import get_workflow, execute_workflow


# Workflow execution functions
def execute_logo_to_video(logo, pixel_map, reference_images, text_prompt):
    """Execute the logo to video workflow"""
    print("Executing logo to video workflow")

    # Save uploaded files
    logo_path = save_uploaded_file(logo, "logos") if logo else None
    pixel_map_path = save_uploaded_file(pixel_map, "pixel_maps") if pixel_map else None

    # Prepare input values
    input_values = {
        "logo": logo_path,
        "pixel_map": pixel_map_path,
        "reference_images": reference_images,
        "text_prompt": text_prompt,
    }

    try:
        # Execute workflow using the new system
        workflow_data = execute_workflow("logo_to_video", input_values)
        prompt_id = submit_workflow(workflow_data)

        if prompt_id:
            return f"Workflow submitted! Prompt ID: {prompt_id}"
        else:
            return "Failed to submit workflow"
    except Exception as e:
        print(f"Error executing workflow: {e}")
        return f"Error: {str(e)}"


def execute_upscale(video, upscale_factor):
    """Execute the upscale workflow"""
    print("Executing upscale workflow")

    # Save uploaded file
    video_path = save_uploaded_file(video, "videos") if video else None

    # Prepare input values
    input_values = {"video": video_path, "upscale_factor": upscale_factor}

    try:
        # Execute workflow using the new system
        workflow_data = execute_workflow("upscale", input_values)
        prompt_id = submit_workflow(workflow_data)

        if prompt_id:
            return f"Workflow submitted! Prompt ID: {prompt_id}"
        else:
            return "Failed to submit workflow"
    except Exception as e:
        print(f"Error executing workflow: {e}")
        return f"Error: {str(e)}"


# Progress monitoring
def check_progress():
    """Check current progress and return status"""
    if app_state.current_progress:
        return f"Status: {app_state.current_progress.get('status', 'unknown')}"
    return "No active job"


def check_queue():
    """Check queue status"""
    queue_data = get_queue_status()
    running = len(queue_data.get("queue_running", []))
    pending = len(queue_data.get("queue_pending", []))
    return f"Running: {running}, Pending: {pending}"


# Load CSS from file
def load_css():
    """Load CSS from brando.css file"""
    try:
        # Use absolute path to be independent of CWD
        css_path = APP_DIR / "brando.css"
        with open(css_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: brando.css not found at {css_path}, using default styling")
        return ""


custom_css = load_css()


def create_background_css():
    """Create CSS with background image using direct URL."""
    return """
    .gradio-container {
        background: url(https://plus.unsplash.com/premium_photo-1749544311043-3a6a0c8d54af?q=80&w=2670&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D) !important;
        background-size: cover !important;
        background-position: center !important;
        background-repeat: no-repeat !important;
        background-attachment: fixed !important;
    }
    """


# Create the Gradio interface
def create_interface():
    """Create the main Gradio interface"""

    background_css = create_background_css()
    # Combine the main CSS with the background CSS
    final_css = custom_css + background_css

    with gr.Blocks(
        title="Brando",
        theme=gr.themes.Ocean(font=gr.themes.GoogleFont("DM Sans")),
        css=final_css,
    ) as demo:

        # Header
        gr.HTML(
            """
        <div class="app-header">
            <h1>BRANDO</h1>
        </div>
        """
        )

        # Main content panel
        with gr.Group(elem_classes="main-content-panel"):

            # Tab navigation
            with gr.Tabs() as tabs:

                # Logo to Video Tab
                with gr.TabItem("Logo to Video"):
                    with gr.Row(elem_classes="gradio-row"):
                        with gr.Column(elem_classes="gradio-column"):
                            with gr.Group(elem_classes="gradio-group"):
                                gr.Markdown("### Input Parameters")
                                with gr.Row(elem_classes="gradio-row"):
                                    logo_input = gr.File(
                                        label="Logo",
                                        file_types=["image"],
                                        elem_classes="file-upload-area",
                                    )

                                    pixel_map_input = gr.File(
                                        label="Pixel Map",
                                        file_types=["image"],
                                        elem_classes="file-upload-area",
                                    )

                                    reference_images_input = gr.File(
                                        label="Reference Images",
                                        file_count="multiple",
                                        file_types=["image"],
                                        elem_classes="file-upload-area",
                                    )

                                text_prompt_input = gr.Textbox(
                                    label="Text Prompt",
                                    placeholder="Enter your text prompt here...",
                                    lines=4,
                                )

                                generate_btn = gr.Button(
                                    "Generate Video",
                                    variant="primary",
                                    elem_classes="gradio-button",
                                )

                        with gr.Column(elem_classes="gradio-column"):
                            with gr.Group(elem_classes="gradio-group"):
                                gr.Markdown("### Output")
                                video_output = gr.Video(
                                    label="Generated Video",
                                    elem_classes="video-output",
                                    interactive=False,
                                )

                                status_output = gr.Textbox(
                                    label="Status",
                                    interactive=False,
                                    elem_classes="status-text",
                                )

                    # System status below output
                    with gr.Group(elem_classes="gradio-group system-status-group"):
                        gr.Markdown("### System Status")

                        with gr.Row(elem_classes="gradio-row"):
                            progress_status = gr.Textbox(
                                label="Progress",
                                interactive=False,
                                elem_classes="status-text",
                            )

                            queue_status = gr.Textbox(
                                label="Queue",
                                interactive=False,
                                elem_classes="status-text",
                            )

                        interrupt_btn = gr.Button(
                            "Interrupt", variant="stop", elem_classes="gradio-button"
                        )

                # Upscale Tab
                with gr.TabItem("Upscale"):
                    with gr.Row(elem_classes="gradio-row"):
                        with gr.Column(elem_classes="gradio-column"):
                            with gr.Group(elem_classes="gradio-group"):
                                gr.Markdown("### Input Parameters")

                                video_input = gr.File(
                                    label="Video to Upscale",
                                    file_types=["video"],
                                    elem_classes="file-upload-area",
                                )

                                upscale_factor = gr.Dropdown(
                                    label="Upscale Factor",
                                    choices=["2x", "4x"],
                                    value="2x",
                                )

                                upscale_btn = gr.Button(
                                    "Upscale Video",
                                    variant="primary",
                                    elem_classes="gradio-button",
                                )

                        with gr.Column(elem_classes="gradio-column"):
                            with gr.Group(elem_classes="gradio-group"):
                                gr.Markdown("### Output")
                                upscaled_video_output = gr.Video(
                                    label="Upscaled Video",
                                    elem_classes="video-output",
                                    interactive=False,
                                )

                                upscale_status = gr.Textbox(
                                    label="Status",
                                    interactive=False,
                                    elem_classes="status-text",
                                )

                    # System status below output for upscale tab
                    with gr.Group(elem_classes="gradio-group system-status-group"):
                        gr.Markdown("### System Status")

                        with gr.Row(elem_classes="gradio-row"):
                            progress_status_upscale = gr.Textbox(
                                label="Progress",
                                interactive=False,
                                elem_classes="status-text",
                            )

                            queue_status_upscale = gr.Textbox(
                                label="Queue",
                                interactive=False,
                                elem_classes="status-text",
                            )

                        interrupt_btn_upscale = gr.Button(
                            "Interrupt", variant="stop", elem_classes="gradio-button"
                        )

        # Event handlers
        generate_btn.click(
            fn=execute_logo_to_video,
            inputs=[
                logo_input,
                pixel_map_input,
                reference_images_input,
                text_prompt_input,
            ],
            outputs=status_output,
        )

        upscale_btn.click(
            fn=execute_upscale,
            inputs=[video_input, upscale_factor],
            outputs=upscale_status,
        )

        interrupt_btn.click(fn=interrupt_processing, outputs=None)
        interrupt_btn_upscale.click(fn=interrupt_processing, outputs=None)

        # Remove the timer and other JavaScript sources that might cause CSP issues
        # The background image should work with just CSS

    return demo


# Main execution
if __name__ == "__main__":
    demo = create_interface()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7861,
        share=False,
        inbrowser=True,
        show_error=True,
    )
