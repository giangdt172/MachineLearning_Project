import gradio as gr
import os
import tempfile
import zipfile
import shutil
import json
import time
import re
import ast
from parse_repo import process_repo  # Assuming this is your custom module

# Define data folder paths
DATA_FOLDER = "data"
PROCESSED_REPO_PATH = os.path.join(DATA_FOLDER, "processed_repositories")

def process_uploaded_repository(repo_file):
    """Process an uploaded repository and save its structure"""
    if repo_file is None:
        return "Please upload a repository ZIP file first.", "", None, None
    
    # Create data directories if they don't exist
    os.makedirs(DATA_FOLDER, exist_ok=True)
    os.makedirs(PROCESSED_REPO_PATH, exist_ok=True)
    
    # Extract the repository to a temporary directory
    temp_dir = tempfile.mkdtemp()
    repo_name = os.path.splitext(os.path.basename(repo_file.name))[0]
    
    try:
        with zipfile.ZipFile(repo_file.name, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Build folder/file structure
        file_structure = build_file_structure(temp_dir)
        
        # Process the repository using process_repo
        processed_data = process_repo(temp_dir)
        
        if processed_data is None:
            return f"Repository {repo_name} does not meet processing criteria.", "", None, None
        
        # Save the processed data to the data folder
        output_file = os.path.join(PROCESSED_REPO_PATH, f"{repo_name}.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(processed_data, f, ensure_ascii=False, indent=4)
        
        # Count Python files
        py_files = []
        def count_py_files(node):
            if node["type"] == "file" and node["name"].endswith(".py"):
                py_files.append(node["name"])
            elif node["type"] == "directory":
                for child in node["children"]:
                    count_py_files(child)
        
        count_py_files(file_structure)
        
        # Extract repository structure overview
        file_count = len(processed_data.keys())
        func_count = sum(len(f.get("functions", [])) for f in processed_data.values())
        class_count = sum(len(f.get("classes", [])) for f in processed_data.values())
        
        # Get import summary
        import_statements = set()
        for file_data in processed_data.values():
            if "import_statements" in file_data:
                for third_party in file_data["import_statements"]["third_party"]:
                    import_statements.add(third_party)
        
        summary = f"""
Repository '{repo_name}' successfully processed and saved to {output_file}

Structure Overview:
- {len(py_files)} Python files found
- {file_count} Python files processed
- {func_count} functions found
- {class_count} classes found
- {len(import_statements)} unique third-party imports
"""
        return "Processing complete!", summary, file_structure, temp_dir  # Return temp_dir for file access
    
    except Exception as e:
        return f"Error processing repository: {str(e)}", "", None, None
    # Note: Don't delete temp_dir here; we'll clean it up later

def build_file_structure(root_dir):
    """Build a dictionary representing the repository's file structure, showing only Python files"""
    root_name = os.path.basename(root_dir)
    file_tree = {"name": root_name, "type": "directory", "children": []}
    
    def add_to_tree(parent_dict, rel_path, is_dir):
        # Handle path separator differences in OS
        rel_path = rel_path.replace(os.sep, '/')
        parts = rel_path.split('/')
        
        current = parent_dict
        
        for i, part in enumerate(parts[:-1]):
            if not part:  # Skip empty parts
                continue
                
            found = False
            for child in current["children"]:
                if child["name"] == part:
                    current = child
                    found = True
                    break
            
            if not found:
                new_dir = {"name": part, "type": "directory", "children": []}
                current["children"].append(new_dir)
                current = new_dir
        
        last_part = parts[-1]
        if not last_part:  # Skip empty last part
            return
            
        if is_dir:
            # Check if this directory already exists
            for child in current["children"]:
                if child["name"] == last_part:
                    return
            current["children"].append({"name": last_part, "type": "directory", "children": []})
        else:
            # Check if this file already exists
            for child in current["children"]:
                if child["name"] == last_part:
                    return
            current["children"].append({"name": last_part, "type": "file"})
    
    # Walk through the directory structure
    for dirpath, dirnames, filenames in os.walk(root_dir):
        rel_path = os.path.relpath(dirpath, root_dir)
        if rel_path != ".":
            add_to_tree(file_tree, rel_path, True)
        
        for filename in filenames:
            if filename.endswith('.py'):
                file_rel_path = os.path.join(rel_path, filename)
                if file_rel_path.startswith(".\\") or file_rel_path.startswith("./"):
                    file_rel_path = file_rel_path[2:]
                add_to_tree(file_tree, file_rel_path, False)
    
    def clean_empty_dirs(node):
        if node["type"] == "directory":
            node["children"] = [clean_empty_dirs(child) for child in node["children"]]
            node["children"] = [child for child in node["children"] if child is not None]
            if not node["children"] and node["name"] != root_name:
                return None
        return node
    
    clean_empty_dirs(file_tree)
    
    def sort_tree(node):
        if "children" in node:
            node["children"].sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"].lower()))
            for child in node["children"]:
                if child["type"] == "directory":
                    sort_tree(child)
    
    sort_tree(file_tree)
    return file_tree

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

def display_file_content(path, file_structure, temp_dir):
    """Return the content of the selected Python file"""
    if not path or not file_structure or not temp_dir:
        return f"No file selected or repository not loaded. Path: {path}, Temp dir exists: {temp_dir is not None}"
    
    if not path.endswith('.py'):
        return "Only Python (.py) files can be displayed"
    
    try:
        # Convert path to system path (replace '/' with os.sep)
        file_path = os.path.normpath(os.path.join(temp_dir, path))
        
        # Log paths to help diagnose issues
        debug_info = f"Looking for file:\nRequested path: {path}\nFull path: {file_path}\nTemp dir: {temp_dir}\n"
        
        # First try a direct file access
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        
        # If that didn't work, try to find the file in the file structure
        # Verify the file exists in the structure
        path_parts = path.split('/')
        
        # Check if the first part might be the repository root folder
        # If path doesn't start with the repo root directory, adjust path_parts
        root_name = os.path.basename(temp_dir)
        root_dir_contents = os.listdir(temp_dir)
        debug_info += f"Root directory name: {root_name}\nRoot directory contents: {root_dir_contents}\n"
        
        # Try alternative path constructions
        alternative_paths = [
            # Try with temp_dir as base
            os.path.join(temp_dir, *path_parts),
            # Try finding the file directly under temp_dir
            os.path.join(temp_dir, os.path.basename(path)),
            # Try with each subdirectory
            *[os.path.join(temp_dir, subdir, *path_parts) for subdir in root_dir_contents 
              if os.path.isdir(os.path.join(temp_dir, subdir))]
        ]
        
        debug_info += "Trying alternative paths:\n"
        for alt_path in alternative_paths:
            debug_info += f"- {alt_path} (exists: {os.path.exists(alt_path)})\n"
            if os.path.exists(alt_path) and os.path.isfile(alt_path):
                with open(alt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return content
        
        # If we got here, we couldn't find the file
        return f"File not found: {path}\n\nDebug information:\n{debug_info}"
            
    except Exception as e:
        return f"Error reading file: {str(e)}\nPath: {path}\nTemp dir: {temp_dir}"

# Build the Gradio interface
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
            
            # Add dropdown for functions in the current file
            function_dropdown = gr.Dropdown(label="Select a function/method", choices=[], elem_id="function-dropdown")
            
            signature_input = gr.Textbox(label="Signature", placeholder="Enter function/method signature here...", 
                                       lines=2, interactive=True)
            docstring_input = gr.Textbox(label="Docstring", placeholder="Enter docstring here...", 
                                       lines=4, interactive=True)
            
            # Add button to save/export the data
            with gr.Row():
                export_btn = gr.Button("Save Model Input", variant="primary")
                extract_btn = gr.Button("Analyze File", variant="secondary")
                export_all_btn = gr.Button("Export All Functions", variant="secondary")
                export_status = gr.Textbox(label="Status", visible=False)
    
    # Store file structure and temp_dir
    file_structure_state = gr.State(None)
    temp_dir_state = gr.State(None)
    python_files_state = gr.State([])
    function_data_state = gr.State({})
    
    # Clean up temp_dir when app closes or new repo is processed
    def cleanup_temp_dir(old_temp_dir, new_temp_dir=None):
        if old_temp_dir and os.path.exists(old_temp_dir) and old_temp_dir != new_temp_dir:
            shutil.rmtree(old_temp_dir)
        return new_temp_dir
    
    # Helper function to extract Python files for dropdown
    def extract_py_files(file_structure):
        if not file_structure:
            return []
        
        files = []
        
        def traverse(node, path=""):
            current_path = path + "/" + node["name"] if path else node["name"]
            if node["type"] == "file" and node["name"].endswith(".py"):
                # Skip the root directory name in the path
                display_path = current_path.split("/", 1)[1] if "/" in current_path else current_path
                files.append(display_path)
            elif node["type"] == "directory":
                for child in node["children"]:
                    traverse(child, current_path)
        
        traverse(file_structure)
        return sorted(files)
    
    # Event handlers - defined here after all UI components
    # but still inside the Blocks context
    
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
    
    # The rest of the event handlers that reference functions
    # defined later in the file now use lambda functions
    
    # Connect file content display + auto-analysis
    selected_path.change(
        lambda p, fs, td: display_file_content(p, fs, td),
        inputs=[selected_path, file_structure_state, temp_dir_state],
        outputs=file_content,
        show_progress=False
    ).then(
        lambda content: analyze_file_functions(content),
        inputs=file_content,
        outputs=[function_dropdown, function_data_state, export_status]
    )
    
    # Connect the analyze button
    extract_btn.click(
        lambda content: analyze_file_functions(content),
        inputs=file_content,
        outputs=[function_dropdown, function_data_state, export_status]
    )
    
    # Connect the export button
    export_btn.click(
        lambda p, sig, doc: save_model_input(p, sig, doc),
        inputs=[selected_path, signature_input, docstring_input],
        outputs=export_status
    )
    
    # Connect the export all button
    export_all_btn.click(
        lambda p, fd: export_all_functions(p, fd),
        inputs=[selected_path, function_data_state],
        outputs=export_status
    )
    
    # Connect the function dropdown
    function_dropdown.change(
        lambda fs, fd: set_function_inputs(fs, fd),
        inputs=[function_dropdown, function_data_state],
        outputs=[signature_input, docstring_input]
    )

# Function to analyze the current file and extract functions
def analyze_file_functions(file_content):
    if not file_content:
        return (gr.update(choices=[], value=None), 
               {}, 
               gr.update(value="No file content to analyze", visible=True))
    
    try:
        functions = extract_signatures_and_docstrings(file_content)
        function_names = [func["name"] for func in functions]
        function_data = {func["name"]: func for func in functions}
        
        if not functions:
            return (gr.update(choices=[], value=None), 
                   {}, 
                   gr.update(value="No functions or methods found in this file", visible=True))
        
        return (gr.update(choices=function_names, value=function_names[0] if function_names else None), 
               function_data, 
               gr.update(value=f"Found {len(functions)} functions/methods", visible=True))
    
    except Exception as e:
        return (gr.update(choices=[], value=None), 
               {}, 
               gr.update(value=f"Error analyzing file: {str(e)}", visible=True))

# Function to save model input data
def save_model_input(file_path, signature, docstring):
    if not file_path:
        return gr.update(value="Error: No file selected", visible=True)
    
    try:
        # Create a directory for saved inputs if it doesn't exist
        os.makedirs("model_inputs", exist_ok=True)
        
        # Create a filename based on the selected file
        base_filename = os.path.basename(file_path)
        output_filename = f"model_inputs/{os.path.splitext(base_filename)[0]}_input.json"
        
        # Save the data as JSON
        data = {
            "file_path": file_path,
            "signature": signature,
            "docstring": docstring,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        
        return gr.update(value=f"Saved to {output_filename}", visible=True)
    
    except Exception as e:
        return gr.update(value=f"Error saving data: {str(e)}", visible=True)

# Function to export all functions from the current file
def export_all_functions(file_path, function_data):
    if not file_path:
        return gr.update(value="Error: No file selected", visible=True)
    
    if not function_data:
        return gr.update(value="Error: No functions found in file", visible=True)
    
    try:
        # Create a directory for saved inputs if it doesn't exist
        os.makedirs("model_inputs", exist_ok=True)
        
        # Create a base filename from the selected file
        base_filename = os.path.basename(file_path)
        base_name = os.path.splitext(base_filename)[0]
        
        # Create a directory for this file's functions
        file_dir = f"model_inputs/{base_name}"
        os.makedirs(file_dir, exist_ok=True)
        
        # Save each function as a separate JSON file
        for func_name, func_data in function_data.items():
            # Create a sanitized filename
            safe_name = re.sub(r'[^\w]', '_', func_name)
            output_filename = f"{file_dir}/{safe_name}.json"
            
            # Save the data as JSON
            export_data = {
                "file_path": file_path,
                "function_name": func_name,
                "signature": func_data.get("signature", ""),
                "docstring": func_data.get("docstring", ""),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            with open(output_filename, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=4)
        
        # Also save a summary file with all functions
        summary_filename = f"model_inputs/{base_name}_all.json"
        all_functions = []
        for func_name, func_data in function_data.items():
            all_functions.append({
                "function_name": func_name,
                "signature": func_data.get("signature", ""),
                "docstring": func_data.get("docstring", "")
            })
        
        summary_data = {
            "file_path": file_path,
            "functions": all_functions,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        with open(summary_filename, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=4)
        
        return gr.update(
            value=f"Exported {len(function_data)} functions to {file_dir} and summary to {summary_filename}", 
            visible=True
        )
    
    except Exception as e:
        return gr.update(value=f"Error exporting functions: {str(e)}", visible=True)

# Function to extract signatures and docstrings from Python code
def extract_signatures_and_docstrings(code):
    """Extract function/method signatures and docstrings from Python code"""
    if not code:
        return []
    
    results = []
    
    try:
        # Parse the code into an AST
        tree = ast.parse(code)
        
        # Function to extract from a function node
        def process_function_node(node, class_name=None):
            # Get function name with class prefix if this is a method
            name = f"{class_name}.{node.name}" if class_name else node.name
            
            # Build the signature
            args = []
            for arg in node.args.args:
                if hasattr(arg, 'annotation') and arg.annotation is not None:
                    arg_type = ast.unparse(arg.annotation).strip()
                    args.append(f"{arg.arg}: {arg_type}")
                else:
                    args.append(arg.arg)
            
            # Handle varargs
            if node.args.vararg:
                args.append(f"*{node.args.vararg.arg}")
            
            # Handle keyword args
            if node.args.kwarg:
                args.append(f"**{node.args.kwarg.arg}")
            
            # Build the return type if available
            returns = ""
            if node.returns:
                returns = f" -> {ast.unparse(node.returns).strip()}"
            
            # Build the full signature
            signature = f"def {name}({', '.join(args)}){returns}:"
            
            # Get the docstring if available
            docstring = ast.get_docstring(node) or ""
            
            # Skip dunder methods
            if not name.startswith("__"):
                results.append({
                    "name": name,
                    "signature": signature,
                    "docstring": docstring
                })
        
        # Process all functions and methods
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if this is a method in a class
                parent_class = None
                for parent in ast.walk(tree):
                    if isinstance(parent, ast.ClassDef) and any(
                        isinstance(child, ast.FunctionDef) and child.name == node.name 
                        for child in parent.body
                    ):
                        parent_class = parent.name
                        break
                
                # Skip if it's a method and will be processed with the class
                if parent_class is None:
                    process_function_node(node)
            
            elif isinstance(node, ast.ClassDef):
                # Process all methods in the class
                for child in node.body:
                    if isinstance(child, ast.FunctionDef):
                        process_function_node(child, node.name)
    
    except SyntaxError:
        # If there's a syntax error, fall back to regex-based extraction
        # Function pattern
        func_pattern = r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)(?:\s*->\s*([^:]+))?\s*:"
        # Docstring pattern (both triple quotes variants)
        docstring_pattern = r'"""(.*?)"""|\'\'\' ?(.*?)\'\'\'|"(.*?)"|\' ?(.*?)\''
        
        # Find all functions
        for match in re.finditer(func_pattern, code, re.DOTALL):
            func_name = match.group(1)
            signature = match.group(0)
            
            # Find the docstring (naive approach, but works for simple cases)
            func_end = match.end()
            next_50_chars = code[func_end:func_end+300]
            docstring = ""
            docstring_match = re.search(docstring_pattern, next_50_chars.strip(), re.DOTALL)
            if docstring_match:
                docstring = next((group for group in docstring_match.groups() if group is not None), "")
            
            results.append({
                "name": func_name,
                "signature": signature,
                "docstring": docstring.strip()
            })
    
    return results

# Function to get dropdown options for functions in the current file
def get_function_options(file_content):
    functions = extract_signatures_and_docstrings(file_content)
    return {f"{func['name']}": func for func in functions}

# Function to set signature and docstring inputs when a function is selected
def set_function_inputs(function_selection, function_data):
    if not function_selection or not function_data:
        return "", ""
    
    selected_func = function_data.get(function_selection, {})
    return (
        selected_func.get("signature", ""),
        selected_func.get("docstring", "")
    )

if __name__ == "__main__":
    app.launch(share = True)