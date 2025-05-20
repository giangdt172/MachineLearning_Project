"""
UI components for the repository analysis app.
"""

import gradio as gr
from .repo_processor import process_uploaded_repository
from .file_utils import (
    cleanup_temp_dir, 
    display_file_content, 
    extract_py_files,
    save_model_input,
    export_all_functions
)
from .code_analyzer import (
    analyze_file_functions,
    extract_signatures_and_docstrings,
    set_function_inputs
)

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
                gr.Markdown("*Select a function from the dropdown or enter details manually*")
                
                signature_input = gr.Textbox(label="Signature", placeholder="Enter function/method signature here...", 
                                           lines=2, interactive=True)
                docstring_input = gr.Textbox(label="Docstring", placeholder="Enter docstring here...", 
                                           lines=4, interactive=True)
                
                # Add button to save/export the data
                with gr.Row():
                    export_btn = gr.Button("Save Model Input", variant="primary")
                    extract_btn = gr.Button("Analyze File", variant="secondary")
                    export_status = gr.Textbox(label="Status", visible=False)
        
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
        )
        
        # Connect the analyze button
        extract_btn.click(
            lambda content: analyze_file_functions(content)[1:],
            inputs=file_content,
            outputs=[function_data_state, export_status]
        )
        
        # Connect the export button
        export_btn.click(
            lambda p, sig, doc: save_model_input(p, extract_function_name(sig), sig, doc),
            inputs=[selected_path, signature_input, docstring_input],
            outputs=export_status
        )
        
    return app 

def create_model_input_form():
    with gr.Blocks() as form:
        gr.subheader("Model Input")
        gr.write("Select a function from the dropdown or enter details manually")
        
        # Remove the function/method dropdown field
        # st.selectbox("Select a function/method", options=[], key="function_dropdown")
        
        signature = gr.text_area("Signature", placeholder="Enter function/method signature here...", key="signature")
        docstring = gr.text_area("Docstring", placeholder="Enter docstring here...", key="docstring")
        
        col1, col2 = gr.columns(2)
        with col1:
            save_button = gr.form_submit_button("Save Model Input")
        with col2:
            analyze_button = gr.form_submit_button("Analyze File")
        # Remove Export All Functions button
        # with col3:
        #     export_button = gr.form_submit_button("Export All Functions")
        
        if save_button:
            # Extract function name from signature
            function_name = extract_function_name(signature)
            model_input = {
                "name": function_name,
                "signature": signature,
                "docstring": docstring
            }
            gr.session_state.model_input = model_input
            gr.success(f"Saved model input for function: {function_name}")

# Add new function to extract function name
def extract_function_name(signature):
    if not signature:
        return ""
    signature = signature.strip()
    if signature.startswith("def "):
        # Extract name between "def " and first "("
        name_end = signature.find("(")
        if name_end > 4:  # "def " is 4 characters
            return signature[4:name_end].strip()
    return "" 