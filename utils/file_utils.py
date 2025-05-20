"""
File utility functions for handling file operations.
"""

import os
import tempfile
import zipfile
import shutil
import json
import time
import re

def cleanup_temp_dir(old_temp_dir, new_temp_dir=None):
    """Clean up temporary directory when app closes or new repo is processed"""
    if old_temp_dir and os.path.exists(old_temp_dir) and old_temp_dir != new_temp_dir:
        shutil.rmtree(old_temp_dir)
    return new_temp_dir

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

def extract_py_files(file_structure):
    """Extract list of Python files from the file structure tree"""
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

def save_model_input(file_path: str, name: str, signature: str, docstring: str):
    """Save the model input data to a JSON file"""
    if not file_path:
        return f"Error: No file selected"
    
    try:
        # Create a directory for saved inputs if it doesn't exist
        os.makedirs("model_inputs", exist_ok=True)
        
        # Create a filename based on the selected file and function name
        base_filename = os.path.basename(file_path)
        base_name_part = os.path.splitext(base_filename)[0]
        
        function_name_part_for_file = ""
        if name: # If a name was extracted
            # Sanitize: replace non-alphanumeric/hyphen with a single underscore
            s = re.sub(r'[^\\w-]+', '_', name) 
            # Collapse multiple underscores to one
            s = re.sub(r'_+', '_', s)
            # Remove leading/trailing underscores
            s = s.strip('_')
            if s: # If something remains after sanitization
                function_name_part_for_file = f"_{s}"
        
        output_filename = f"model_inputs/{base_name_part}{function_name_part_for_file}_input.json"
        
        # Save the data as JSON
        data = {
            "file_path": file_path,
            "name": name,
            "signature": signature,
            "docstring": "DOCSTRING" if docstring == "" else docstring,
        }
        
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        
        return f"Saved to {output_filename}"
    
    except Exception as e:
        return f"Error saving data: {str(e)}"

def export_all_functions(file_path, function_data):
    """Export all functions from the current file to JSON"""
    if not file_path:
        return f"Error: No file selected"
    
    if not function_data:
        return f"Error: No functions found in file"
    
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
        
        return f"Exported {len(function_data)} functions to {file_dir} and summary to {summary_filename}"
    
    except Exception as e:
        return f"Error exporting functions: {str(e)}" 