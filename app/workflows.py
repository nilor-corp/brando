"""
Workflow definitions for Brando app.
Each workflow defines the UI inputs and how to map them to ComfyUI workflow parameters.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import json


class WorkflowDefinition:
    """Base class for workflow definitions"""

    def __init__(self, name: str, description: str, workflow_file: str):
        self.name = name
        self.description = description
        self.workflow_file = workflow_file
        self.inputs = {}
        self.workflow_data = None

    def load_workflow(self) -> Dict[str, Any]:
        """Load the workflow JSON file"""
        if self.workflow_data is None:
            workflow_path = Path("workflows") / self.workflow_file
            if workflow_path.exists():
                with open(workflow_path, "r") as f:
                    self.workflow_data = json.load(f)
            else:
                # Return a placeholder workflow structure
                self.workflow_data = self._create_placeholder_workflow()
        return self.workflow_data

    def _create_placeholder_workflow(self) -> Dict[str, Any]:
        """Create a placeholder workflow structure"""
        return {"workflow_type": self.name, "nodes": {}, "connections": {}}

    def update_workflow(self, input_values: Dict[str, Any]) -> Dict[str, Any]:
        """Update workflow with input values"""
        workflow = self.load_workflow().copy()

        # Apply input mappings
        for input_name, value in input_values.items():
            if input_name in self.inputs:
                mapping = self.inputs[input_name]
                if mapping and value is not None:
                    self._apply_mapping(workflow, mapping, value)

        return workflow

    def _apply_mapping(self, workflow: Dict, mapping: Dict, value: Any):
        """Apply a parameter mapping to the workflow"""
        node_id = mapping.get("node_id")
        param_name = mapping.get("param_name")

        if node_id and param_name:
            if "nodes" not in workflow:
                workflow["nodes"] = {}
            if node_id not in workflow["nodes"]:
                workflow["nodes"][node_id] = {"inputs": {}}
            if "inputs" not in workflow["nodes"][node_id]:
                workflow["nodes"][node_id]["inputs"] = {}

            workflow["nodes"][node_id]["inputs"][param_name] = value


class LogoToVideoWorkflow(WorkflowDefinition):
    """Logo to Video workflow definition"""

    def __init__(self):
        super().__init__(
            name="logo_to_video",
            description="Generate a video from a logo with pixel map and reference images",
            workflow_file="logo-to-video.json",
        )

        # Define input mappings
        self.inputs = {
            "logo": {
                "type": "file",
                "label": "Logo",
                "mapping": {"node_id": "logo_loader", "param_name": "image"},
            },
            "pixel_map": {
                "type": "file",
                "label": "Pixel Map",
                "mapping": {"node_id": "pixel_map_loader", "param_name": "image"},
            },
            "reference_images": {
                "type": "files",
                "label": "Reference Images",
                "mapping": {"node_id": "reference_loader", "param_name": "images"},
            },
            "text_prompt": {
                "type": "text",
                "label": "Text Prompt",
                "value": "",
                "mapping": {"node_id": "text_prompt", "param_name": "text"},
            },
        }


class UpscaleWorkflow(WorkflowDefinition):
    """Upscale workflow definition"""

    def __init__(self):
        super().__init__(
            name="upscale",
            description="Upscale a video with AI",
            workflow_file="upscale-video.json",
        )

        # Define input mappings
        self.inputs = {
            "video": {
                "type": "file",
                "label": "Video to Upscale",
                "mapping": {"node_id": "video_loader", "param_name": "video"},
            },
            "upscale_factor": {
                "type": "dropdown",
                "label": "Upscale Factor",
                "choices": ["2x", "4x"],
                "value": "2x",
                "mapping": {"node_id": "upscaler", "param_name": "scale"},
            },
        }


# Workflow registry
WORKFLOWS = {"logo_to_video": LogoToVideoWorkflow(), "upscale": UpscaleWorkflow()}


def get_workflow(name: str) -> Optional[WorkflowDefinition]:
    """Get a workflow by name"""
    return WORKFLOWS.get(name)


def get_all_workflows() -> Dict[str, WorkflowDefinition]:
    """Get all available workflows"""
    return WORKFLOWS


def execute_workflow(
    workflow_name: str, input_values: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute a workflow with given input values"""
    workflow = get_workflow(workflow_name)
    if workflow:
        return workflow.update_workflow(input_values)
    else:
        raise ValueError(f"Unknown workflow: {workflow_name}")
