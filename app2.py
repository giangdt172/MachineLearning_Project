import gradio as gr
import os
import tempfile
import zipfile
import shutil
import json
from parse_repo import process_repo

# Define data folder paths
DATA_FOLDER = "data"
PROCESSED_REPO_PATH = os.path.join(DATA_FOLDER, "processed_repositories")

def process_uploaded_repository(repo_file):
    """Process an uploaded repository and save its structure"""
    if repo_file is None:
        return "Please upload a repository ZIP file first.", "", None
    
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
            return f"Repository {repo_name} does not meet processing criteria.", "", None
        
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
        return "Processing complete!", summary, file_structure
    
    except Exception as e:
        return f"Error processing repository: {str(e)}", "", None
    finally:
        # Clean up
        shutil.rmtree(temp_dir)

def build_file_structure(root_dir):
    """Build a dictionary representing the repository's file structure, showing only Python files"""
    file_tree = {"name": os.path.basename(root_dir), "type": "directory", "children": []}
    
    def add_to_tree(parent_dict, path, is_dir):
        parts = path.split(os.sep)
        current = parent_dict
        
        # Navigate to the correct position in the tree
        for i, part in enumerate(parts[:-1]):
            # Look for the directory in children
            found = False
            for child in current["children"]:
                if child["name"] == part:
                    current = child
                    found = True
                    break
            
            if not found:
                # Create new directory node
                new_dir = {"name": part, "type": "directory", "children": []}
                current["children"].append(new_dir)
                current = new_dir
        
        # Add the final item (file or directory)
        if is_dir:
            for child in current["children"]:
                if child["name"] == parts[-1]:
                    return  # Directory already exists
            current["children"].append({"name": parts[-1], "type": "directory", "children": []})
        else:
            current["children"].append({"name": parts[-1], "type": "file"})
    
    # Process all files and directories
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Get relative path from root
        rel_path = os.path.relpath(dirpath, root_dir)
        if rel_path != ".":
            add_to_tree(file_tree, rel_path, True)
        
        # Add only Python files
        for filename in filenames:
            if filename.endswith('.py'):  # Only include Python files
                file_rel_path = os.path.join(rel_path, filename)
                if file_rel_path.startswith(".\\") or file_rel_path.startswith("./"):
                    file_rel_path = file_rel_path[2:]
                add_to_tree(file_tree, file_rel_path, False)
    
    # Clean up empty directories
    def clean_empty_dirs(node):
        if node["type"] == "directory":
            # First, recursively clean children
            node["children"] = [clean_empty_dirs(child) for child in node["children"]]
            # Filter out None values (deleted empty directories)
            node["children"] = [child for child in node["children"] if child is not None]
            # If this directory has no children, return None to remove it
            if not node["children"] and node["name"] != os.path.basename(root_dir):  # Keep root even if empty
                return None
        return node
    
    clean_empty_dirs(file_tree)
    
    # Sort the file tree alphabetically
    def sort_tree(node):
        if "children" in node:
            # Sort directories first, then files, both alphabetically
            node["children"].sort(key=lambda x: (0 if x["type"] == "file" else 1, x["name"].lower()))
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
        path_str = "/".join(current_path[1:])  # Skip the first level
        
        if node["type"] == "directory":
            # Create expandable section for directory
            if not node["children"]:
                # Empty directory, don't display
                return ""
                
            children_html = "".join([build_tree_html(child, current_path) for child in node["children"]])
            is_selected = path_str == selected_path
            
            # Special case for root level
            if len(path) == 0:
                return f"""<div class="file-tree-root">{children_html}</div>"""
            
            selected_class = "selected" if is_selected else ""
            return f"""
            <details open>
                <summary class="directory {selected_class}" data-path="{path_str}" onclick="selectItem(this, '{path_str}')" title="Click to select folder">📁 {node["name"]}</summary>
                <div class="directory-content">{children_html}</div>
            </details>
            """
        else:
            # Create leaf node for file (should be Python file only)
            is_selected = path_str == selected_path
            selected_class = "selected" if is_selected else ""
            file_icon = "🐍" if node["name"].endswith('.py') else "📄"
            return f"""<div class="file {selected_class}" data-path="{path_str}" onclick="selectItem(this, '{path_str}')" title="Click to select file">{file_icon} {node["name"]}</div>"""
    
    html_content = build_tree_html(file_structure)
    
    # Add CSS styling
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
    </style>
    """
    
    # Add improved JavaScript for selection
    js = """
    <script>
        function selectItem(element, path) {
            // Prevent the details from toggling when clicking on summary
            if (element.tagName === 'SUMMARY') {
                event.preventDefault();
            }
            
            // Clear all previous selections
            document.querySelectorAll('.selected').forEach(sel => {
                sel.classList.remove('selected');
            });
            
            // Add selection to clicked element
            element.classList.add('selected');
            
            // Get selected path input element
            const pathInput = document.getElementById('selected-path-input');
            if (pathInput) {
                pathInput.value = path;
                // Trigger input event for Gradio
                pathInput.dispatchEvent(new Event('input', { bubbles: true }));
                
                // Also trigger submit button click to save selection
                const saveButton = document.getElementById('save-selection-button');
                if (saveButton) {
                    saveButton.click();
                }
            }
        }
        
        // Initialize after DOM is fully loaded
        document.addEventListener('DOMContentLoaded', function() {
            // Set up a mutation observer to detect when the tree is added to the DOM
            const observer = new MutationObserver((mutations) => {
                for (const mutation of mutations) {
                    if (mutation.addedNodes.length) {
                        const fileTree = document.querySelector('.file-tree-root');
                        if (fileTree) {
                            // If there's a selected path in the input, highlight it
                            const pathInput = document.getElementById('selected-path-input');
                            if (pathInput && pathInput.value) {
                                const path = pathInput.value;
                                const element = document.querySelector(`[data-path="${path}"]`);
                                if (element) {
                                    element.classList.add('selected');
                                }
                            }
                            observer.disconnect();
                        }
                    }
                }
            });
            
            // Start observing
            observer.observe(document.body, { childList: true, subtree: true });
        });
    </script>
    """
    
    return gr.HTML(css + html_content + js)
    
    # Add JavaScript for selection
    js = """
    <script>
        function initializeTree() {
            const files = document.querySelectorAll('.file, .directory summary');
            files.forEach(elem => {
                elem.addEventListener('click', (e) => {
                    e.preventDefault();
                    // Clear previous selection
                    document.querySelectorAll('.selected').forEach(sel => {
                        sel.classList.remove('selected');
                    });
                    // Add selection to clicked element
                    elem.classList.add('selected');
                    // Get the path
                    const path = elem.getAttribute('data-path');
                    // Update path textbox via Gradio
                    if (typeof gradioApp !== 'undefined') {
                        const pathInput = gradioApp().querySelector('#selected-path-textbox textarea');
                        if (pathInput) {
                            pathInput.value = path;
                            pathInput.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                    }
                });
            });
        }
        
        // Wait for elements to be rendered
        if (window.gradio_loaded) {
            setTimeout(initializeTree, 100);
        } else {
            document.addEventListener('DOMContentLoaded', function() {
                setTimeout(initializeTree, 100);
            });
        }
    </script>
    """
    
    return gr.HTML(css + html_content + js)

# Build the Gradio interface
with gr.Blocks() as app:
    gr.Markdown("# Python Repository Processor")
    gr.Markdown("Upload a Python repository ZIP file to analyze and extract its structure.")
    
    with gr.Row():
        with gr.Column(scale=1):
            # Step 1: Upload repository
            repo_file = gr.File(label="Upload Repository (ZIP file)")
            process_btn = gr.Button("Process Repository", variant="primary")
            status_text = gr.Textbox(label="Status", placeholder="Upload a repository to begin...", interactive=False)
            
        with gr.Column(scale=2):
            # Results area
            repo_info = gr.Textbox(label="Repository Information", placeholder="Repository details will appear here...", 
                                  lines=8, interactive=False)
    
    with gr.Row(visible=False) as file_explorer_row:
        with gr.Column(scale=1):
            # File tree explorer
            gr.Markdown("### Repository Structure")
            file_tree_html = gr.HTML("No repository loaded")
            
        with gr.Column(scale=2):
            # Selected path and save button
            selected_path = gr.Textbox(label="Selected Path", placeholder="Click on a file or directory to select it", 
                                      interactive=True, elem_id="selected-path-input")
            save_btn = gr.Button("Save Selection", elem_id="save-selection-button")
            selection_status = gr.Textbox(label="Selection Status", placeholder="No selection saved yet", interactive=False)
    
    # Store file structure for use in callbacks
    file_structure_state = gr.State(None)
    
    # Event handler for processing repository
    process_result = process_btn.click(
        process_uploaded_repository, 
        inputs=repo_file, 
        outputs=[status_text, repo_info, file_structure_state]
    )
    
    # Update file tree when processing is complete
    process_result.then(
        lambda x: gr.update(visible=True) if x is not None else gr.update(visible=False),
        inputs=file_structure_state,
        outputs=file_explorer_row,
        show_progress=False
    )
    
    process_result.then(
        render_file_tree,
        inputs=file_structure_state,
        outputs=file_tree_html,
        show_progress=False
    )
    
    # Event handler for saving selection
    save_btn.click(
        lambda path: f"Selection saved: {path}" if path else "No path selected",
        inputs=selected_path,
        outputs=selection_status,
        show_progress=False
    )

def display_file_content(path, file_structure):
    """Return the content of the selected Python file"""
    if not path or not file_structure:
        return "No file selected"
    
    # Only show content for Python files
    if not path.endswith('.py'):
        return "Only Python (.py) files can be displayed"
    
    try:
        # The path in the repository structure uses forward slashes
        # Need to convert to system path separators for file reading
        path_parts = path.split('/')
        
        # Recursively find file in the structure
        def find_file_node(node, parts, current_index=0):
            if current_index >= len(parts):
                return None
                
            current_part = parts[current_index]
            
            if current_index == len(parts) - 1:  # Last part, looking for the file
                for child in node.get("children", []):
                    if child["name"] == current_part and child["type"] == "file":
                        return True
                return None
            else:  # Looking for a directory
                for child in node.get("children", []):
                    if child["name"] == current_part and child["type"] == "directory":
                        return find_file_node(child, parts, current_index + 1)
                return None
        
        file_exists = find_file_node(file_structure, path_parts)
        
        if file_exists:
            # Return a message for the demo
            return f"Content of {path} would be displayed here.\n\nIn a complete implementation, this would read the file content from disk or from the processed repository data."
        else:
            return f"File not found: {path}"
            
    except Exception as e:
        return f"Error reading file: {str(e)}"

# Launch the app
if __name__ == "__main__":
    app.launch()