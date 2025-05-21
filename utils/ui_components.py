"""
UI components for the repository analysis app.
"""

import gradio as gr
import os
import json
from pathlib import Path
import re

from .repo_processor import process_uploaded_repository
from .file_utils import (
    cleanup_temp_dir, 
    display_file_content, 
    extract_py_files,
    save_model_input
)
from .code_analyzer import (
    analyze_file_functions,
    extract_signatures_and_docstrings
)
from .method_extractor import extract_methods_for_specific_file_from_enhanced_json
from models.model import CodeClassifier

# Initialize CodeClassifier model (paths will be updated when the app runs)
code_classifier = None

def initialize_code_classifier(checkpoint_dir, model_pt_path):
    """Initialize the code classifier model."""
    global code_classifier
    try:
        code_classifier = CodeClassifier(checkpoint_dir, model_pt_path)
        return True
    except Exception as e:
        print(f"Error initializing CodeClassifier: {e}")
        return False

def render_file_tree(file_structure, selected_path=""):
    """Convert file structure to Gradio components"""
    if file_structure is None:
        return gr.Markdown("No repository loaded")
    
    def build_tree_html(node, path=[]):
        current_path = path + [node["name"]]
        path_str = "/".join(current_path[1:])
        
        if node["type"] == "directory":
            if not node["children"]:
                return ""
            children_html = "".join([build_tree_html(child, current_path) for child in node["children"]])
            is_selected = path_str == selected_path
            selected_class = "selected" if is_selected else ""
            if len(path) == 0:
                return f"""<div class="file-tree-root">{children_html}</div>"""
            return f"""
            <details open>
                <summary class="directory {selected_class}" data-path="{path_str}" onclick="selectItem(this, '{path_str}')" title="Click to select folder">📁 {node["name"]}</summary>
                <div class="directory-content">{children_html}</div>
            </details>
            """
        else:
            is_selected = path_str == selected_path
            selected_class = "selected" if is_selected else ""
            file_icon = "🐍" if node["name"].endswith('.py') else "📄"
            # Add draggable attribute and drag events for files
            return f"""<div class="file {selected_class}" data-path="{path_str}" onclick="selectItem(this, '{path_str}')" draggable="true" ondragstart="dragStart(event, '{path_str}')" title="Drag to Selected Path or click to select">{file_icon} {node["name"]}</div>"""
    
    html_content = build_tree_html(file_structure)
    
    css = """
    <style>
        .file-tree-root {
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 10px;
            max-height: 500px;
            overflow: auto;
            background-color: #f9f9f9;
        }
        .directory-content {
            padding-left: 20px;
        }
        .file, .directory summary {
            padding: 4px 8px;
            margin: 2px 0;
            cursor: pointer;
            border-radius: 4px;
        }
        .file:hover, .directory summary:hover {
            background-color: #f0f0f0;
        }
        .selected {
            background-color: #e1f5fe;
            font-weight: bold;
        }
        details > summary {
            list-style: none;
        }
        details > summary::-webkit-details-marker {
            display: none;
        }
        .file {
            cursor: grab;
        }
        .file.dragging {
            opacity: 0.5;
        }
        .dropzone {
            border: 2px dashed #ccc;
            border-radius: 4px;
            padding: 10px;
            text-align: center;
            background-color: #f9f9f9;
            min-height: 80px;
            margin-bottom: 10px;
            transition: all 0.3s ease;
        }
        .dropzone.drag-over {
            background-color: #e3f2fd;
            border-color: #2196F3;
            transform: scale(1.02);
        }
    </style>
    """
    
    js = """
    <script>
        // Add these functions once the page is loaded
        function setupDragAndDrop() {
            // Setup drop zone
            const dropZone = document.createElement('div');
            dropZone.className = 'dropzone';
            dropZone.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%;"><div>📄 Drop Python files here</div></div>';
            dropZone.addEventListener('dragover', function(e) {
                e.preventDefault();
                this.classList.add('drag-over');
            });
            dropZone.addEventListener('dragleave', function() {
                this.classList.remove('drag-over');
            });
            dropZone.addEventListener('drop', function(e) {
                e.preventDefault();
                this.classList.remove('drag-over');
                const path = e.dataTransfer.getData('text');
                const pathInput = document.getElementById('selected-path-input');
                if (pathInput && path) {
                    pathInput.value = path;
                    pathInput.dispatchEvent(new Event('input', { bubbles: true }));
                    pathInput.dispatchEvent(new Event('change', { bubbles: true }));
                    // Also update visual selection in the file tree
                    document.querySelectorAll('.selected').forEach(sel => {
                        sel.classList.remove('selected');
                    });
                    const fileEl = document.querySelector(`.file[data-path="${path}"]`);
                    if (fileEl) {
                        fileEl.classList.add('selected');
                    }
                }
            });
            
            // Insert the drop zone before the path input
            const pathInput = document.getElementById('selected-path-input');
            if (pathInput) {
                const container = pathInput.closest('.gradio-container, .block');
                if (container) {
                    container.insertBefore(dropZone, pathInput);
                } else {
                    // If we can't find the container, try to insert before the input itself
                    const inputContainer = pathInput.parentElement;
                    if (inputContainer) {
                        inputContainer.insertBefore(dropZone, pathInput);
                    }
                }
            }
        }
        
        function dragStart(event, path) {
            event.dataTransfer.setData('text', path);
            // Add a visual effect
            event.target.classList.add('dragging');
            setTimeout(() => event.target.classList.remove('dragging'), 100);
        }
        
        function selectItem(element, path) {
            if (element.tagName === 'SUMMARY') {
                event.preventDefault();
            }
            document.querySelectorAll('.selected').forEach(sel => {
                sel.classList.remove('selected');
            });
            element.classList.add('selected');
            const pathInput = document.getElementById('selected-path-input');
            if (pathInput) {
                pathInput.value = path;
                // Dispatch both input and change events to ensure Gradio detects the change
                pathInput.dispatchEvent(new Event('input', { bubbles: true }));
                pathInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
        
        // Set up drag and drop when the DOM is loaded
        document.addEventListener('DOMContentLoaded', setupDragAndDrop);
        // Also try immediately in case DOM is already loaded
        if (document.readyState === 'complete' || document.readyState === 'interactive') {
            setTimeout(setupDragAndDrop, 100);
        }
        // Add a resize observer to handle Gradio's layout changes
        setTimeout(() => {
            const observer = new MutationObserver(function(mutations) {
                // If the dropzone doesn't exist, set it up
                if (!document.querySelector('.dropzone')) {
                    setupDragAndDrop();
                }
            });
            
            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        }, 1000);
    </script>
    """
    
    return gr.HTML(css + html_content + js)

def create_application():
    """Create the complete application with UI and event handlers"""
    with gr.Blocks() as app:
        gr.Markdown("# Python Repository Processor")
        gr.Markdown("Upload a Python repository ZIP file to analyze and extract its structure.")
        
        # Store paths for CodeClassifier
        checkpoint_dir_state = gr.State("")
        model_pt_path_state = gr.State("")
        json_path_state = gr.State("")
        relevance_info_state = gr.State([])
        
        with gr.Row():
            with gr.Column(scale=1):
                repo_file = gr.File(label="Upload Repository (ZIP file)")
                process_btn = gr.Button("Process Repository", variant="primary")
                status_text = gr.Textbox(label="Status", placeholder="Upload a repository to begin...", interactive=False)
                
            with gr.Column(scale=2):
                repo_info = gr.Textbox(label="Repository Information", placeholder="Repository details will appear here...", 
                                      lines=8, interactive=False)
        
        with gr.Row(visible=False) as file_explorer_row:
            with gr.Column(scale=1):
                gr.Markdown("### Repository Structure")
                gr.Markdown("*Drag files to the drop zone on the right →*")
                file_tree_html = gr.HTML("No repository loaded")
                
            with gr.Column(scale=2):
                gr.Markdown("### File Explorer")
                
                # Add a dropdown for file selection
                file_dropdown = gr.Dropdown(label="Select a Python file", choices=[], elem_id="file-dropdown")
                
                selected_path = gr.Textbox(label="Selected Path", placeholder="Drag a Python file here or click on a file in the tree", 
                                          interactive=True, elem_id="selected-path-input")
                file_content = gr.Code(label="File Content", language="python", lines=20, interactive=False)
                
                # Add Signature and Docstring fields
                gr.Markdown("### Model Input")
                gr.Markdown("*Enter function signature and docstring below*")
                
                signature_input = gr.Textbox(label="Signature", placeholder="Enter function/method signature here...", 
                                           lines=2, interactive=True)
                docstring_input = gr.Textbox(label="Docstring", placeholder="Enter docstring here...", 
                                           lines=4, interactive=True)
                
                # Add relevance indicator
                relevance_status = gr.Markdown("", elem_id="relevance-indicator")
                
                # Add button to save/export the data
                with gr.Row():
                    export_btn = gr.Button("Save Model Input", variant="primary")
                    extract_btn = gr.Button("Analyze File", variant="secondary")
                    check_relevance_btn = gr.Button("Check Relevance", variant="secondary")
                    export_status = gr.Textbox(label="Status", visible=False)
                
                # Add area to display relevant methods
                relevant_methods_md = gr.Markdown("### Relevant Methods", visible=False)
                relevant_methods_box = gr.Dataframe(
                    headers=["Method Name", "Similarity"],
                    datatype=["str", "str"],
                    visible=False
                )
        
        # Store file structure and temp_dir
        file_structure_state = gr.State(None)
        temp_dir_state = gr.State(None)
        python_files_state = gr.State([])
        function_data_state = gr.State({})
        
        # First clean up previous temp dir, then process the new repository
        process_btn.click(
            lambda temp_dir: cleanup_temp_dir(temp_dir),
            inputs=temp_dir_state,
            outputs=temp_dir_state,
            show_progress=False
        ).then(
            process_uploaded_repository, 
            inputs=repo_file, 
            outputs=[status_text, repo_info, file_structure_state, temp_dir_state]
        ).then(
            lambda x: gr.update(visible=True) if x is not None else gr.update(visible=False),
            inputs=file_structure_state,
            outputs=file_explorer_row,
            show_progress=False
        ).then(
            render_file_tree,
            inputs=file_structure_state,
            outputs=file_tree_html,
            show_progress=False
        ).then(
            extract_py_files,
            inputs=file_structure_state,
            outputs=python_files_state,
            show_progress=False
        ).then(
            lambda files: gr.update(choices=files),
            inputs=python_files_state,
            outputs=file_dropdown,
            show_progress=False
        ).then(
            lambda repo_file, temp_dir: update_json_path_and_model_paths(repo_file, temp_dir),
            inputs=[repo_file, temp_dir_state],
            outputs=[json_path_state, checkpoint_dir_state, model_pt_path_state],
            show_progress=False
        )
        
        # Connect the dropdown to select files
        file_dropdown.change(
            lambda x: x,
            inputs=file_dropdown,
            outputs=selected_path,
            show_progress=False
        )
        
        # Connect file content display + auto-analysis
        selected_path.change(
            lambda p, fs, td: display_file_content(p, fs, td),
            inputs=[selected_path, file_structure_state, temp_dir_state],
            outputs=file_content,
            show_progress=False
        ).then(
            lambda content: analyze_file_functions(content)[1:],
            inputs=file_content,
            outputs=[function_data_state, export_status]
        ).then(
            # Clear relevance indicator when a new file is selected
            lambda: gr.update(value=""),
            inputs=[],
            outputs=relevance_status
        ).then(
            # Reset relevance methods display
            lambda: [gr.update(visible=False), gr.update(visible=False, value=[])],
            inputs=[],
            outputs=[relevant_methods_md, relevant_methods_box]
        )
        
        # Connect the analyze button
        extract_btn.click(
            lambda content: analyze_file_functions(content)[1:],
            inputs=file_content,
            outputs=[function_data_state, export_status]
        )
        
        # Connect the export button
        export_btn.click(
            lambda p, name, sig, doc: save_model_input(p, extract_function_name(sig), sig, doc),
            inputs=[selected_path, signature_input, signature_input, docstring_input],
            outputs=export_status
        )
        
        # Connect the check relevance button
        check_relevance_btn.click(
            check_function_relevance_to_file,
            inputs=[
                selected_path,
                signature_input,
                docstring_input,
                json_path_state,
                checkpoint_dir_state,
                model_pt_path_state
            ],
            outputs=[
                relevance_status,
                relevance_info_state,
                relevant_methods_md,
                relevant_methods_box
            ]
        )
        
    return app

def extract_function_name(signature):
    """Extract function name from signature."""
    if not signature:
        return ""
    signature = signature.strip()
    if signature.startswith("def "):
        # Extract name between "def " and first "("
        name_end = signature.find("(")
        if name_end > 4:  # "def " is 4 characters
            return signature[4:name_end].strip()
    return ""

def update_json_path_and_model_paths(repo_file, temp_dir):
    """Update the JSON path based on the repo file and setup model paths."""
    json_path = ""
    try:
        if repo_file and temp_dir:
            # Get the base name of the repository ZIP file
            repo_filename = os.path.basename(repo_file.name)
            repo_name = os.path.splitext(repo_filename)[0]
            
            # Construct the path to the enhanced JSON file
            json_path = os.path.join("data", "enhanced_json", f"{repo_name}.json")
            
            # Check if the JSON file exists
            if not os.path.exists(json_path):
                print(f"Warning: Enhanced JSON file not found at {json_path}")
            else:
                print(f"Found JSON file at {json_path}")
    except Exception as e:
        print(f"Error determining JSON path: {e}")
    
    # Set up model paths - these would be configured based on your environment
    checkpoint_dir = r"D:\HUST\2024.2\Machine Learning\ML_project\src\model\checkpoint-792"
    model_pt_path = r"D:\HUST\2024.2\Machine Learning\ML_project\src\model\checkpoint-792\model_epoch_4.pt"
    
    return json_path, checkpoint_dir, model_pt_path

def check_function_relevance_to_file(selected_path, signature, docstring, json_path, checkpoint_dir, model_pt_path):
    """Check if the given function is relevant to the selected file."""
    if not selected_path or not json_path:
        return (
            gr.update(value="<div style='color: red;'>No file selected or JSON not available</div>"),
            [],
            gr.update(visible=False),
            gr.update(visible=False, value=[])
        )
    
    # Extract the function name from signature
    func_name = extract_function_name(signature)
    
    # Create the anchor with the entered function details
    anchor = {
        "name": func_name,
        "signature": signature,
        "docstring": docstring if docstring else "DOCSTRING"
    }
    
    try:
        # Initialize the model if not already done
        global code_classifier
        if code_classifier is None:
            if not initialize_code_classifier(checkpoint_dir, model_pt_path):
                return (
                    gr.update(value="<div style='color: red;'>Failed to initialize code classifier model</div>"),
                    [],
                    gr.update(visible=False),
                    gr.update(visible=False, value=[])
                )
        
        # Extract methods from the selected file's JSON entry
        methods = extract_methods_for_specific_file_from_enhanced_json(json_path, selected_path)
        
        if not methods:
            return (
                gr.update(value="<div style='color: orange;'>No methods found in the selected file</div>"),
                [],
                gr.update(visible=False),
                gr.update(visible=False, value=[])
            )
        
        # Check relevance of each method
        relevant_methods = []
        relevant_count = 0
        
        for method in methods:
            input_ref_ = f"{anchor}\n</s>\n{method}"
            pred_class, logits = code_classifier.predict_text(input_ref_)
            
            # Convert logits to probabilities if needed
            if hasattr(logits, 'tolist'):
                logits = logits.tolist()
            
            # Store method name and relevance score
            method_relevance = {
                "name": method["name"],
                "relevance_score": logits[0][1] if isinstance(logits[0], list) else logits[1],
                "is_relevant": pred_class == 1
            }
            relevant_methods.append(method_relevance)
            
            if pred_class == 1:
                relevant_count += 1
        
        # Sort methods by relevance score in descending order
        relevant_methods.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        # Prepare data for display
        display_data = []
        for method in relevant_methods[:10]:  # Show top 10 methods
            display_data.append([
                method["name"],
                f"{method['relevance_score']:.4f}" if isinstance(method['relevance_score'], (int, float)) else str(method['relevance_score'])
            ])
        
        # Determine if there are enough relevant methods
        relevance_threshold = 0.3  # 30% of methods should be relevant
        has_enough_relevant = relevant_count >= len(methods) * relevance_threshold
        
        # Create the relevance message
        if has_enough_relevant:
            color = "green"
            message = f"✅ Relevant! Found {relevant_count} out of {len(methods)} relevant methods"
        else:
            color = "red"
            message = f"❌ Not relevant! Only found {relevant_count} out of {len(methods)} relevant methods"
        
        relevance_html = f"<div style='color: {color}; font-weight: bold;'>{message}</div>"
        
        return (
            gr.update(value=relevance_html),
            relevant_methods,
            gr.update(visible=True),
            gr.update(visible=True, value=display_data)
        )
        
    except Exception as e:
        error_message = f"Error checking relevance: {str(e)}"
        print(error_message)
        return (
            gr.update(value=f"<div style='color: red;'>{error_message}</div>"),
            [],
            gr.update(visible=False),
            gr.update(visible=False, value=[])
        ) 