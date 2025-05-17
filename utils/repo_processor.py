"""
Repository processing utilities.
"""

import os
import tempfile
import zipfile
import json
import shutil
from .file_utils import build_file_structure

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
        
        # Process the repository using process_repo if it's available
        try:
            from parse_repo import process_repo
            processed_data = process_repo(temp_dir)
            
            if processed_data is None:
                return f"Repository {repo_name} does not meet processing criteria.", "", file_structure, temp_dir
            
            # Save the processed data to the data folder
            output_file = os.path.join(PROCESSED_REPO_PATH, f"{repo_name}.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(processed_data, f, ensure_ascii=False, indent=4)
        except (ImportError, ModuleNotFoundError):
            # If process_repo is not available, continue without it
            processed_data = {"info": "parse_repo module not found, basic processing only"}
        
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
        try:
            file_count = len(processed_data.keys())
            func_count = sum(len(f.get("functions", [])) for f in processed_data.values())
            class_count = sum(len(f.get("classes", [])) for f in processed_data.values())
            
            # Get import summary
            import_statements = set()
            for file_data in processed_data.values():
                if "import_statements" in file_data:
                    for third_party in file_data["import_statements"]["third_party"]:
                        import_statements.add(third_party)
        except (AttributeError, TypeError):
            file_count = len(py_files)
            func_count = 0
            class_count = 0
            import_statements = set()
        
        summary = f"""
Repository '{repo_name}' successfully processed

Structure Overview:
- {len(py_files)} Python files found
- {file_count} Python files processed
- {func_count} functions found
- {class_count} classes found
- {len(import_statements)} unique third-party imports
"""
        return "Processing complete!", summary, file_structure, temp_dir
    
    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return f"Error processing repository: {str(e)}", "", None, None 