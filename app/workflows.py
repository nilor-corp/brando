"""
Workflow definitions for Brando app.
Each workflow defines the UI inputs and how to map them to ComfyUI workflow parameters.
"""

from typing import Dict, Any, Optional
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
        """Load the workflow JSON file."""
        if self.workflow_data is None:
            workflow_path = Path(__file__).parent / self.workflow_file
            if workflow_path.exists():
                with open(workflow_path, "r") as f:
                    self.workflow_data = json.load(f)
            else:
                self.workflow_data = self._create_placeholder_workflow()
        return self.workflow_data.copy()

    def _create_placeholder_workflow(self) -> Dict[str, Any]:
        return {}

    def update_workflow(self, input_values: Dict[str, Any], job_id: Optional[str] = None) -> Dict[str, Any]:
        """Update workflow with input values from the UI."""
        workflow = self.load_workflow()
        # Update from UI inputs
        for input_name, value in input_values.items():
            if input_name in self.inputs:
                mapping = self.inputs[input_name].get("mapping")
                if mapping and value is not None:
                    self._apply_mapping(workflow, mapping, value)

        # Inject job_id into any ImageStreamInput nodes
        if job_id:
            for node_id, node_data in workflow.items():
                if node_data.get("class_type") in ["ImageStreamInput", "ImageStreamOutput"]:
                    if "inputs" not in node_data:
                        node_data["inputs"] = {}
                    node_data["inputs"]["prompt_id"] = job_id
                    if node_data.get("class_type") == "ImageStreamOutput":
                        node_data["inputs"]["callback_url"] = "http://127.0.0.1:7861/receive_output"
        
        return workflow

    def _apply_mapping(self, workflow: Dict, mapping: Dict, value: Any):
        """Apply a parameter mapping to the workflow"""
        node_id = mapping.get("node_id")
        param_name = mapping.get("param_name")
        # The 'workflow' object is the dictionary of nodes in API format.
        if node_id and param_name and node_id in workflow:
            workflow[node_id]["inputs"][param_name] = value


class TestImageStreamWorkflow(WorkflowDefinition):
    def __init__(self):
        super().__init__(
            name="test_image_stream",
            description="Test the image stream functionality.",
            workflow_file="workflows/test-image-stream.json",
        )
        self.inputs = {}


# Workflow registry
WORKFLOWS = {
    "test_image_stream": TestImageStreamWorkflow(),
}


def get_workflow(name: str) -> Optional[WorkflowDefinition]:
    """Get a workflow by name"""
    return WORKFLOWS.get(name)


def get_all_workflows() -> Dict[str, WorkflowDefinition]:
    """Get all available workflows"""
    return WORKFLOWS

def execute_workflow(workflow_name: str, input_values: Dict[str, Any], job_id: Optional[str] = None) -> Dict[str, Any]:
    """Execute a workflow with given input values"""
    workflow = get_workflow(workflow_name)
    if workflow:
        return workflow.update_workflow(input_values, job_id=job_id)
    raise ValueError(f"Unknown workflow: {workflow_name}")
