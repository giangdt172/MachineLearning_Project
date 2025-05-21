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
from .method_extractor import (
    extract_methods_for_specific_file_from_enhanced_json,
    build_method_call_tree,
    flatten_method_call_tree
)
from models.model import CodeClassifier
from .llm_completion import LLMCompletionHandler

# Initialize CodeClassifier model and LLM handler
code_classifier = None
llm_handler = LLMCompletionHandler()

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
        call_tree_state = gr.State([])
        
        # Main application UI
        with gr.Row():
            with gr.Column(scale=1):
                repo_file = gr.File(label="Upload Repository (ZIP file)")
                process_btn = gr.Button("Process Repository", variant="primary")
                status_text = gr.Textbox(label="Status", placeholder="Upload a repository to begin...", interactive=False)
                
            with gr.Column(scale=2):
                repo_info = gr.Textbox(label="Repository Information", placeholder="Repository details will appear here...", 
                                      lines=8, interactive=False)
        
        # File explorer section (initially hidden)
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
                
                # Function Input Section
                gr.Markdown("### Function Input")
                gr.Markdown("*Enter function signature and docstring below*")
                
                signature_input = gr.Textbox(label="Signature", placeholder="Enter function/method signature here...", 
                                          lines=2, interactive=True)
                docstring_input = gr.Textbox(label="Docstring", placeholder="Enter docstring here...", 
                                          lines=4, interactive=True)
                
                # Buttons for analysis and generation
                with gr.Row():
                    check_relevance_btn = gr.Button("Check Relevance", variant="primary")
                    complete_function_btn = gr.Button("Complete Function", variant="primary")
                    export_status = gr.Textbox(label="Status", visible=False)
                
                # Relevance Status
                relevance_status = gr.Markdown("", elem_id="relevance-indicator")
                
                # Results Tabs - All in one tabbed interface
                with gr.Tabs() as results_tabs:
                    # Relevant Methods Tab
                    with gr.Tab("Relevant Methods"):
                        relevant_methods_md = gr.Markdown("### Relevant Methods")
                        relevant_methods_box = gr.Dataframe(
                            headers=["Method Name", "Relevance Score"],
                            datatype=["str", "str"]
                        )
                    
                    # Code Completion Tab
                    with gr.Tab("Code Completion"):
                        code_completion_md = gr.Markdown("### Generated Code")
                        code_completion_output = gr.Code(label="Generated Code", language="python", lines=15, interactive=False)
                    
                    # Call Tree Analysis Tab
                    with gr.Tab("Call Tree Analysis"):
                        call_tree_md = gr.Markdown("### Call Tree Analysis")
                        with gr.Tabs() as call_tree_tabs:
                            with gr.Tab("Call Tree Summary"):
                                call_tree_summary = gr.Markdown("")
                            with gr.Tab("Method Relevance"):
                                call_tree_relevance = gr.Dataframe(
                                    headers=["Method", "Relevance", "Score"],
                                    datatype=["str", "str", "str"]
                                )
                            with gr.Tab("Call Paths"):
                                call_paths = gr.Markdown("")

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
                relevant_methods_box,
                call_tree_summary,
                call_tree_relevance,
                call_paths
            ]
        ).then(
            # Switch to the Relevant Methods tab after checking relevance
            lambda: 0,  # Return tab index 0 (Relevant Methods tab)
            inputs=None,
            outputs=results_tabs
        )
        
        # Event handler for function completion
        complete_function_btn.click(
            complete_function,
            inputs=[
                signature_input,
                docstring_input,
                relevance_info_state,
            ],
            outputs=[
                code_completion_output,
                export_status
            ]
        ).then(
            # Switch to the Code Completion tab after generating code
            lambda: 1,  # Return tab index 1 (Code Completion tab)
            inputs=None,
            outputs=results_tabs
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
    """Check if the given function is relevant to the selected file and analyze call trees."""
    if not selected_path or not json_path:
        return (
            gr.update(value="<div style='color: red;'>No file selected or JSON not available</div>"),
            [],  # relevant_methods will be empty
            [],  # empty dataframe
            "",  # empty call tree summary
            [],  # empty call tree relevance
            ""   # empty call paths
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
                    [],  # relevant_methods will be empty
                    [],  # empty dataframe
                    "",  # empty call tree summary
                    [],  # empty call tree relevance
                    ""   # empty call paths
                )
        
        # Extract methods from the selected file's JSON entry
        methods = extract_methods_for_specific_file_from_enhanced_json(json_path, selected_path)
        
        if not methods:
            return (
                gr.update(value="<div style='color: orange;'>No methods found in the selected file</div>"),
                [],  # relevant_methods will be empty
                [],  # empty dataframe
                "",  # empty call tree summary
                [],  # empty call tree relevance
                ""   # empty call paths
            )
        
        # Check relevance of each method
        relevant_methods = []
        relevant_count = 0
        
        for method in methods:
            input_ref_ = f"{anchor}\n</s>\n{method}"
            pred_class, logits = code_classifier.predict_text(input_ref_)
            
            # Convert logits to probabilities if needed
            logits_value = logits[0, 1].item()
            
            # Store method name and relevance score
            method_relevance = {
                "name": method["name"],
                "relevance_score": logits_value,
                "is_relevant": pred_class == 1,
                "code": method.get("code", ""),
                "description": method.get("description", "")
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
        
        # Build call tree for the most relevant method
        call_tree_data = []
        call_tree_relevance_data = []
        call_paths_html = ""
        
        if relevant_methods and relevant_count > 0:
            # Get the most relevant method
            most_relevant = relevant_methods[0]["name"]
            most_relevant_method = next((m for m in methods if m["name"] == most_relevant), None)
            
            if most_relevant_method:
                # Build call tree with depth 2
                call_trees = build_method_call_tree(json_path, selected_path, depth=2)
                
                if call_trees:
                    # Find the call tree for the most relevant method
                    target_tree = next((tree for tree in call_trees if tree["name"] == most_relevant), call_trees[0])
                    
                    # Generate summary
                    call_tree_summary_html = f"<h4>Call Tree for {target_tree['name']}</h4>"
                    if "called_methods" in target_tree and target_tree["called_methods"]:
                        # Group by file path
                        methods_by_file = {}
                        for called in target_tree["called_methods"]:
                            file_path = called.get("file_path", "unknown")
                            if file_path not in methods_by_file:
                                methods_by_file[file_path] = []
                            methods_by_file[file_path].append(called)
                        
                        # Build summary HTML
                        for file_path, methods_list in methods_by_file.items():
                            call_tree_summary_html += f"<p><strong>From {file_path} ({len(methods_list)} methods):</strong></p><ul>"
                            for method in methods_list:
                                method_type = method.get("method_type", "")
                                if method_type == "class":
                                    call_tree_summary_html += f"<li>{method['name']} (Class)</li>"
                                else:
                                    call_tree_summary_html += f"<li>{method['name']}</li>"
                            call_tree_summary_html += "</ul>"
                    else:
                        call_tree_summary_html += "<p>No method calls found.</p>"
                    
                    # Evaluate relevance for each method in the call tree
                    def evaluate_method_relevance(method, anchor, model):
                        """Evaluate the relevance of a method against an anchor using the model."""
                        # Check if method has all the required fields
                        if all(field in method for field in ["name", "description", "code"]):
                            # Create input reference using the same format as the initial relevance check
                            input_ref = f"{anchor}\n</s>\n{method}"
                            
                            # Predict using the model
                            try:
                                pred_class, logits = model.predict_text(input_ref)
        
                                
                                relevance_score = logits[0, 1].item()
                                relevance = "Relevant" if pred_class == 1 else "Not relevant"
                                
                                return {
                                    "method": method["name"],
                                    "relevance": relevance,
                                    "score": relevance_score
                                }
                            except Exception as e:
                                return {
                                    "method": method["name"],
                                    "relevance": "Error",
                                    "score": str(e)
                                }
                        return None
                    
                    # Process all methods in the call tree
                    methods_to_process = [target_tree]
                    all_relevance_results = []
                    
                    if "called_methods" in target_tree:
                        methods_to_process.extend(target_tree["called_methods"])
                    
                    for method in methods_to_process:
                        result = evaluate_method_relevance(method, anchor, code_classifier)
                        if result:
                            all_relevance_results.append(result)
                    
                    # Sort by score in descending order
                    all_relevance_results.sort(key=lambda x: x["score"] if isinstance(x["score"], (int, float)) else 0, reverse=True)
                    
                    # Prepare for display
                    for result in all_relevance_results:
                        call_tree_relevance_data.append([
                            result["method"],
                            result["relevance"],
                            f"{result['score']:.4f}" if isinstance(result["score"], (int, float)) else str(result["score"])
                        ])
                    
                    # Generate call paths visualization
                    flat_paths = flatten_method_call_tree(target_tree)
                    call_paths_html = f"<h4>Call Paths for {target_tree['name']}</h4>"
                    if flat_paths:
                        call_paths_html += "<ul>"
                        for i, path in enumerate(flat_paths, 1):
                            path_str = " → ".join(m["name"] for m in path)
                            call_paths_html += f"<li>Path {i}: {path_str}</li>"
                        call_paths_html += "</ul>"
                    else:
                        call_paths_html += "<p>No call paths found.</p>"
                    
                    call_tree_data = call_trees
        
        # Return the data for the UI components - no visibility updates needed
        return (
            gr.update(value=relevance_html),
            relevant_methods,
            display_data,
            call_tree_summary_html if 'call_tree_summary_html' in locals() else "",
            call_tree_relevance_data,
            call_paths_html
        )
        
    except Exception as e:
        error_message = f"Error checking relevance: {str(e)}"
        print(error_message)
        import traceback
        traceback.print_exc()
        return (
            gr.update(value=f"<div style='color: red;'>{error_message}</div>"),
            [],  # relevant_methods will be empty
            [],  # empty dataframe
            "",  # empty call tree summary
            [],  # empty call tree relevance
            ""   # empty call paths
        )

def complete_function(signature, docstring, relevant_methods):
    """Use LLM to complete the function based on the signature, docstring and relevant methods."""
    global llm_handler
    
    if not signature:
        return (
            "```\n# Error: Function signature is empty\n```", 
            "Signature required"
        )
    
    try:
        result = llm_handler.complete_function(signature, docstring, relevant_methods)
        
        if result.get("success", False):
            return (
                result["code"],
                "Code generation successful"
            )
        else:
            error_msg = result.get("error", "Unknown error")
            return (
                f"```\n# Error: {error_msg}\n```",
                f"Failed to generate code: {error_msg}"
            )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return (
            f"```\n# Exception occurred: {str(e)}\n```",
            f"Exception: {str(e)}"
        ) 