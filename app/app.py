import os
import json
import requests
import time
import uuid
import websocket
import threading
import asyncio
import httpx # Add httpx for async requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
import gradio as gr
from dotenv import load_dotenv
import shutil # Add shutil for file copying
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

# Load environment variables
load_dotenv()

# Define app directory at the top to be used in other functions
APP_DIR = Path(__file__).parent.resolve()

# Configuration
COMFY_IP = os.getenv("COMFY_IP", "127.0.0.1")
COMFY_PORT = os.getenv("COMFY_PORT", "8188")
COMFY_URL = f"http://{COMFY_IP}:{COMFY_PORT}"
STREAM_IP = os.getenv("IMAGE_STREAM_HOST", "127.0.0.1")
STREAM_PORT = os.getenv("IMAGE_STREAM_PORT", "8189")
STREAM_URL = f"http://{STREAM_IP}:{STREAM_PORT}"
WS_URL = f"ws://{COMFY_IP}:{COMFY_PORT}/ws"


# App state
class AppState:
    """Simple class to hold application state"""

    def __init__(self):
        self.client_id = str(uuid.uuid4())
        self.ws_connected = False
        self.job_tracking: Dict[str, Dict] = {}
        self.current_progress: Dict[str, Any] = {}
        self.last_submitted_job_id: Optional[str] = None
        self.job_is_running: bool = False
        self.uploaded_files: Dict[str, list[str]] = {}
        self.ws_app: Optional[websocket.WebSocketApp] = None


app_state = AppState()

# --- WebSocket Logic (Daemon Thread) ---
def connect_websocket():
    """Establish and manage the WebSocket connection in a daemon thread."""

    def on_message(ws, message):
        """Handle incoming messages."""
        try:
            data = json.loads(message)
            handle_websocket_message(data)
        except json.JSONDecodeError:
            print(f"WebSocket: Received non-JSON message: {message}")

    def on_error(ws, error):
        """Log WebSocket errors."""
        print(f"WebSocket Error: {error}")
        app_state.ws_connected = False

    def on_close(ws, close_status_code, close_msg):
        """Log when the connection is closed."""
        print(f"WebSocket Connection Closed. Code: {close_status_code}, Msg: {close_msg}")
        app_state.ws_connected = False

    def on_open(ws):
        """Log when the connection is successfully opened."""
        print("WebSocket Connection Opened.")
        app_state.ws_connected = True

    def connection_thread():
        """The main thread that runs the WebSocket connection loop."""
        ws_url = f"{WS_URL}?clientId={app_state.client_id}"
        app_state.ws_app = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        app_state.ws_app.run_forever()

    # The daemon=True flag is the critical fix for the shutdown hang.
    thread = threading.Thread(target=connection_thread, daemon=True)
    thread.start()


def handle_websocket_message(data):
    """
    Handles incoming WebSocket messages. This version robustly tracks multiple
    queued jobs and handles conditional workflows.
    """
    msg_type = data.get("type")
    
    if msg_type == "progress_state":
        msg_data = data.get("data", {})
        job_id = msg_data.get("prompt_id")

        if not job_id or job_id not in app_state.job_tracking:
            return
            
        job_info = app_state.job_tracking[job_id]
        if job_info["status"] == "completed":
            return

        nodes_data = msg_data.get("nodes", {})
        
        # Dynamically discover all nodes that are part of this job's execution path.
        # The 'nodes' object in the message contains all nodes that have ever been part of the path.
        job_info["nodes_in_path"].update(nodes_data.keys())

        # Track all nodes that have finished.
        for node_id, node_info in nodes_data.items():
            if node_info.get("state") == "finished":
                job_info["completed_nodes"].add(node_id)
        
        # Check for completion: the job is done when the set of completed nodes
        # is the same as the set of all nodes that we've seen for this job.
        if job_info["nodes_in_path"] and job_info["completed_nodes"].issuperset(job_info["nodes_in_path"]):
            job_info["status"] = "completed"
            print(f"🎉 Job {job_id} fully completed!")

            # Clean up uploaded files associated with this job
            if job_id in app_state.uploaded_files:
                for filepath in app_state.uploaded_files[job_id]:
                    try:
                        os.remove(filepath)
                        print(f"Deleted uploaded file: {filepath}")
                    except OSError as e:
                        print(f"Error deleting file {filepath}: {e}")
                del app_state.uploaded_files[job_id] # Clean up the tracking entry
        else:
            # Provide running progress
            progress = len(job_info["completed_nodes"])
            total = len(job_info["nodes_in_path"]) if job_info["nodes_in_path"] else "?"
            print(f"Job {job_id} progress: {progress}/{total} nodes completed.")


# --- ComfyUI & File Handling ---
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


def submit_workflow(workflow_data: Dict, job_id: str, timeouts: Optional[Dict[str, int]] = None) -> Optional[str]:
    """Submit a workflow to ComfyUI with a specific job_id and per-node timeouts."""
    prompt_data = {
        "prompt": workflow_data,
        "client_id": app_state.client_id,
        "prompt_id": job_id,
        "extra_data": {
            "job_id": job_id,
            "prompt_id": job_id,
            "timeouts": timeouts or {},
        },
    }

    result = comfy_post("prompt", prompt_data)
    if result and "number" in result:
        app_state.job_tracking[job_id] = {
            "status": "pending",
            "timestamp": time.time(),
            "workflow": workflow_data,
            "nodes_in_path": set(),
            "completed_nodes": set(),
            "output_queue": asyncio.Queue(),
            "output_files": [],
        }
        return job_id
    elif result and "error" in result:
        print(f"Error submitting workflow: {result['error']}")
        return None
    return None


async def send_image_async(client, job_id: str, node_id: str, file_path: str, filename: str):
    """Sends a single image to the stream server."""
    url = f"{STREAM_URL}/upload_image/{job_id}/{node_id}"
    api_key = os.getenv("IMAGE_STREAM_API_KEY", "your-super-secret-key")
    headers = {"Authorization": f"Bearer {api_key}"}
    
    with open(file_path, "rb") as f:
        image_bytes = f.read()

    files = {'image_file': (filename, image_bytes, 'image/png')} # Assuming PNG, adjust if needed
    
    try:
        response = await client.post(url, files=files, headers=headers)
        response.raise_for_status()
        print(f"Successfully uploaded image for {job_id} -> {node_id}")
    except httpx.HTTPStatusError as e:
        print(f"FATAL: An image upload failed for {job_id} -> {node_id}: {e}")
        # Re-raise to be caught by the orchestrator
        raise

# File handling
def save_uploaded_file(file_obj, subfolder: str = "") -> Optional[str]:
    """Save uploaded file object and return its path."""
    if not file_obj:
        return None

    try:
        # Create upload directory
        upload_dir = Path("uploads") / subfolder
        upload_dir.mkdir(parents=True, exist_ok=True)

        # The Gradio File component returns a path-like object with a .name attribute for the full path
        original_path = Path(file_obj.name)
        filename = original_path.name
        filepath = upload_dir / filename

        # Copy the file from the temp location to our upload directory
        shutil.copy(original_path, filepath)

        return str(filepath)
    except Exception as e:
        print(f"Error saving file: {e}")
        return None


def track_uploaded_file(job_id: str, filepath: str):
    """Tracks an uploaded file against a job_id for later cleanup."""
    if job_id not in app_state.uploaded_files:
        app_state.uploaded_files[job_id] = []
    app_state.uploaded_files[job_id].append(filepath)


# Import workflow definitions
from workflows import get_workflow, execute_workflow


# Workflow execution functions
async def execute_test_image_stream(image_files):
    """
    Execute the test image stream workflow. This function is a generator
    that yields status updates and file paths for the output gallery.
    """
    if not image_files:
        yield "Error: At least one image file is required.", []
        return

    # 1. Save all uploaded files locally
    image_paths = []
    for image_file in image_files:
        path = save_uploaded_file(image_file, "test_stream")
        if path:
            image_paths.append(path)

    if not image_paths:
        yield "Error: Failed to save uploaded images.", []
        return

    try:
        # 2. Generate a unique job_id and submit the workflow
        job_id = str(uuid.uuid4())
        for image_path in image_paths:
            track_uploaded_file(job_id, image_path)
        workflow_data = execute_workflow("test_image_stream", {}, job_id=job_id)
        
        timeouts = {"input_1": 120}
        if not submit_workflow(workflow_data, job_id, timeouts=timeouts):
            yield "Failed to submit test workflow to ComfyUI.", []
            return

        yield f"Workflow submitted (Job ID: {job_id}). Uploading {len(image_paths)} image(s)...", []

        # 3. Upload all images and then trigger the workflow
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                # Create a list of upload tasks
                upload_tasks = []
                for image_path in image_paths:
                    filename_for_upload = Path(image_path).name
                    upload_tasks.append(
                        send_image_async(client, job_id, "input_1", image_path, filename_for_upload)
                    )
                # Run all uploads concurrently
                await asyncio.gather(*upload_tasks)
            except httpx.HTTPStatusError:
                yield f"Error: Failed to upload one or more images for job {job_id}.", []
                return

            api_key = os.getenv("IMAGE_STREAM_API_KEY", "your-super-secret-key")
            headers = {"Authorization": f"Bearer {api_key}"}
            trigger_url = f"{STREAM_URL}/trigger_workflow/{job_id}"
            await client.post(trigger_url, headers=headers)

        yield f"Job {job_id} triggered. Waiting for output...", []

        # 4. Listen for outputs from the queue
        queue = app_state.job_tracking[job_id]["output_queue"]
        while app_state.job_tracking[job_id]["status"] != "completed":
            try:
                updated_files = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield f"Job {job_id} running... Received {len(updated_files)} output(s).", updated_files
            except asyncio.TimeoutError:
                # If the queue is empty, just continue the loop to re-check the job status
                continue
        
        # Final update
        final_files = app_state.job_tracking[job_id].get("output_files", [])
        yield f"Job {job_id} completed.", final_files
        print(f"--- Stream for Job ID {job_id} has finished. ---")

    except Exception as e:
        print(f"Error executing test workflow: {e}")
        yield f"An unexpected error occurred: {str(e)}", []


def load_css():
    """Load CSS from brando.css file"""
    try:
        css_path = APP_DIR / "brando.css"
        with open(css_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: brando.css not found at {css_path}, using default styling")
        return ""

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

# --- Gradio UI & FastAPI App ---
def create_interface():
    """Create the main Gradio interface"""
    custom_css = load_css()
    background_css = create_background_css()
    final_css = custom_css + background_css
    with gr.Blocks(
        title="Brando",
        theme=gr.themes.Default(font=gr.themes.GoogleFont("DM Sans")),
        css=final_css,
    ) as demo:
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

                # Test Image Stream Tab
                with gr.TabItem("Test Image Stream"):
                    # gr.Markdown("### Test Tab")
                    with gr.Row(elem_classes="gradio-row"):
                        with gr.Column(elem_classes="gradio-column"):
                            with gr.Group(elem_classes="gradio-group"):
                                gr.Markdown("### Input Image")
                                test_image_input = gr.File(
                                    label="Image",
                                    file_types=["image"],
                                    file_count="multiple",
                                    elem_classes="file-upload-area",
                                )
                                test_stream_btn = gr.Button(
                                    "Run Test Stream",
                                    variant="primary",
                                    elem_classes="gradio-button",
                                )
                        with gr.Column(elem_classes="gradio-column"):
                             with gr.Group(elem_classes="gradio-group"):
                                gr.Markdown("### Status")
                                test_stream_status_output = gr.Textbox(
                                    label="Status",
                                    interactive=False,
                                    elem_classes="status-text",
                                )
                                gr.Markdown("### Output Image")
                                test_stream_output_gallery = gr.Gallery(
                                    label="Output",
                                    show_label=False,
                                    elem_id="gallery",
                                    columns=2, 
                                    object_fit="contain"
                                )

                # # Logo to Video Tab - Commented out for now
                # with gr.TabItem("Logo to Video"):
                #     with gr.Row(elem_classes="gradio-row"):
                #         with gr.Column(elem_classes="gradio-column"):
                #             with gr.Group(elem_classes="gradio-group"):
                #                 gr.Markdown("### Input Parameters")
                #                 with gr.Row(elem_classes="gradio-row"):
                #                     logo_input = gr.File(
                #                         label="Logo",
                #                         file_types=["image"],
                #                         elem_classes="file-upload-area",
                #                     )

                #                     pixel_map_input = gr.File(
                #                         label="Pixel Map",
                #                         file_types=["image"],
                #                         elem_classes="file-upload-area",
                #                     )

                #                     reference_images_input = gr.File(
                #                         label="Reference Images",
                #                         file_count="multiple",
                #                         file_types=["image"],
                #                         elem_classes="file-upload-area",
                #                     )

                #                 text_prompt_input = gr.Textbox(
                #                     label="Text Prompt",
                #                     placeholder="Enter your text prompt here...",
                #                     lines=4,
                #                 )

                #                 generate_btn = gr.Button(
                #                     "Generate Video",
                #                     variant="primary",
                #                     elem_classes="gradio-button",
                #                 )

                #         with gr.Column(elem_classes="gradio-column"):
                #             with gr.Group(elem_classes="gradio-group"):
                #                 gr.Markdown("### Output")
                #                 video_output = gr.Video(
                #                     label="Generated Video",
                #                     elem_classes="video-output",
                #                     interactive=False,
                #                 )

                #                 status_output = gr.Textbox(
                #                     label="Status",
                #                     interactive=False,
                #                     elem_classes="status-text",
                #                 )

                #     # System status below output
                #     with gr.Group(elem_classes="gradio-group system-status-group"):
                #         gr.Markdown("### System Status")

                #         with gr.Row(elem_classes="gradio-row"):
                #             progress_status = gr.Textbox(
                #                 label="Progress",
                #                 interactive=False,
                #                 elem_classes="status-text",
                #             )

                #             queue_status = gr.Textbox(
                #                 label="Queue",
                #                 interactive=False,
                #                 elem_classes="status-text",
                #             )

                #         interrupt_btn = gr.Button(
                #             "Interrupt", variant="stop", elem_classes="gradio-button"
                #         )

                # Upscale Tab - Commented out for now
                # with gr.TabItem("Upscale"):
                #     with gr.Row(elem_classes="gradio-row"):
                #         with gr.Column(elem_classes="gradio-column"):
                #             with gr.Group(elem_classes="gradio-group"):
                #                 gr.Markdown("### Input Parameters")

                #                 video_input = gr.File(
                #                     label="Video to Upscale",
                #                     file_types=["video"],
                #                     elem_classes="file-upload-area",
                #                 )

                #                 upscale_factor = gr.Dropdown(
                #                     label="Upscale Factor",
                #                     choices=["2x", "4x"],
                #                     value="2x",
                #                 )

                #                 upscale_btn = gr.Button(
                #                     "Upscale Video",
                #                     variant="primary",
                #                     elem_classes="gradio-button",
                #                 )

                #         with gr.Column(elem_classes="gradio-column"):
                #             with gr.Group(elem_classes="gradio-group"):
                #                 gr.Markdown("### Output")
                #                 upscaled_video_output = gr.Video(
                #                     label="Upscaled Video",
                #                     elem_classes="video-output",
                #                     interactive=False,
                #                 )

                #                 upscale_status = gr.Textbox(
                #                     label="Status",
                #                     interactive=False,
                #                     elem_classes="status-text",
                #                 )

                #     # System status below output for upscale tab
                #     with gr.Group(elem_classes="gradio-group system-status-group"):
                #         gr.Markdown("### System Status")

                #         with gr.Row(elem_classes="gradio-row"):
                #             progress_status_upscale = gr.Textbox(
                #                 label="Progress",
                #                 interactive=False,
                #                 elem_classes="status-text",
                #             )

                #             queue_status_upscale = gr.Textbox(
                #                 label="Queue",
                #                 interactive=False,
                #                 elem_classes="status-text",
                #             )

                #         interrupt_btn_upscale = gr.Button(
                #             "Interrupt", variant="stop", elem_classes="gradio-button"
                #         )

        # State for tracking the current job
        current_job_id = gr.State(None)

        # Event handlers
        test_stream_btn.click(
            fn=execute_test_image_stream,
            inputs=[test_image_input],
            outputs=[test_stream_status_output, test_stream_output_gallery],
        )
    return demo


# Create the FastAPI app and mount the Gradio interface
app = FastAPI()
demo = create_interface()

@app.post("/receive_output")
async def receive_output(request: Request):
    """Receives an image from the ComfyUI ImageStreamOutput node and saves it."""
    try:
        form_data = await request.form()
        prompt_id = form_data.get("prompt_id")
        node_id = form_data.get("node_id")
        output_file = form_data.get("output_file")

        if not all([prompt_id, node_id, output_file]):
            return JSONResponse({"status": "error", "message": "Missing required form fields."}, status_code=400)

        output_dir = APP_DIR / "outputs" / prompt_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Sanitize filename
        filename = "".join(c for c in output_file.filename if c.isalnum() or c in ('_', '-', '.'))
        file_path = output_dir / filename
        
        # Save file content
        content = await output_file.read()
        with open(file_path, "wb") as f:
            f.write(content)
            
        print(f"Received and saved output to {file_path}")

        # Track the output file and notify the listener queue
        if prompt_id in app_state.job_tracking:
            job_data = app_state.job_tracking[prompt_id]
            
            # Use the list from the job tracking state
            if "output_files" not in job_data:
                job_data["output_files"] = []
            job_data["output_files"].append(str(file_path))
            
            # Put the complete, updated list into the queue
            if "output_queue" in job_data:
                await job_data["output_queue"].put(job_data["output_files"])
            
        return JSONResponse({"status": "success", "path": str(file_path)})

    except Exception as e:
        print(f"Error in /receive_output: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

app = gr.mount_gradio_app(app, demo, path="/")

def main():
    """Main function to launch the Gradio interface."""
    connect_websocket()
    uvicorn.run(app, host="0.0.0.0", port=7861)

if __name__ == "__main__":
    main()
