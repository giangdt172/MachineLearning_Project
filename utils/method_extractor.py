import ast
import json
import os
import shutil # For cleanup in example
from models.model import CodeClassifier


def extract_methods_from_json_manifest(json_manifest_path, workspace_root):
    """
    Reads a JSON manifest file, and for each Python file path listed as a key,
    extracts methods/functions including their name, description, and code.

    Args:
        json_manifest_path (str): Path to the JSON manifest file.
        workspace_root (str): Absolute path to the workspace root.
                              Python file paths in the JSON are relative to this.

    Returns:
        list: A flat list of all extracted methods from all files.
    """
    all_extracted_methods = []
    
    if not os.path.isabs(workspace_root):
        print(f"Error: workspace_root must be an absolute path. Received: {workspace_root}")
        return all_extracted_methods

    if not os.path.exists(json_manifest_path):
        # If json_manifest_path is not absolute, try joining with workspace_root
        if not os.path.isabs(json_manifest_path):
            json_manifest_path = os.path.join(workspace_root, json_manifest_path)
        
        if not os.path.exists(json_manifest_path):
            print(f"Error: JSON manifest file not found at {json_manifest_path}")
            return all_extracted_methods

    try:
        with open(json_manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
    except Exception as e:
        print(f"Error reading or parsing JSON manifest {json_manifest_path}: {e}")
        return all_extracted_methods

    if not isinstance(manifest_data, dict):
        print(f"Error: JSON manifest {json_manifest_path} does not contain a top-level dictionary.")
        return all_extracted_methods

    print(f"Processing JSON manifest: {json_manifest_path}")
    print(f"Resolving Python file paths relative to workspace: {workspace_root}")

    for py_file_relative_path_from_json_key in manifest_data.keys():
        # Ensure the relative path from JSON key doesn't cause issues with os.path.join
        # For example, if workspace_root is C:\ and key is /module/file.py
        # os.path.join("C:\\", "/module/file.py") might become "C:\\module\\file.py" on Windows.
        # Normalizing the relative path first.
        normalized_relative_path = os.path.normpath(py_file_relative_path_from_json_key.lstrip('/\\\\'))
        py_file_absolute_path = os.path.join(workspace_root, normalized_relative_path)
        
        if not os.path.exists(py_file_absolute_path):
            print(f"Warning: Python file not found: {py_file_absolute_path} (from manifest key '{py_file_relative_path_from_json_key}'). Skipping.")
            continue
        
        if not py_file_absolute_path.endswith(".py"):
            print(f"Warning: Path is not a .py file: {py_file_absolute_path} (from manifest key '{py_file_relative_path_from_json_key}'). Skipping.")
            continue

        print(f"  Processing file: {py_file_absolute_path} (Manifest key: {py_file_relative_path_from_json_key})")
        try:
            with open(py_file_absolute_path, "r", encoding="utf-8") as pf:
                source_code = pf.read()
            
            # The display_path_override should be the relative path as it appears in the JSON key
            methods_in_file = extract_methods_from_single_py_file(
                py_file_absolute_path, 
                source_code, 
                display_path_override=py_file_relative_path_from_json_key 
            )
            all_extracted_methods.extend(methods_in_file)
        except Exception as e:
            print(f"Error processing Python file {py_file_absolute_path}: {e}")
            continue
            
    return all_extracted_methods

def extract_methods_from_enhanced_json(json_path):
    """
    Extracts method details from an enhanced JSON file.

    The JSON is expected to have a structure where top-level keys are file paths,
    each containing a 'classes' list. Each class has a 'methods' list,
    and each method has 'name', 'description', and 'code' fields.

    Args:
        json_path (str): Path to the enhanced JSON file.

    Returns:
        list: A list of dictionaries, where each dictionary contains:
              - "name" (str): The name of the method.
              - "description" (str): The description (docstring) of the method.
              - "code" (str): The source code of the method.
    """
    all_extracted_methods = []

    if not os.path.exists(json_path):
        print(f"Error: JSON file not found at {json_path}")
        return all_extracted_methods

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading or parsing JSON file {json_path}: {e}")
        return all_extracted_methods

    if not isinstance(data, dict):
        print(f"Error: JSON content from {json_path} is not a dictionary.")
        return all_extracted_methods

    for file_path_key, file_data in data.items():
        if not isinstance(file_data, dict):
            # print(f"Warning: Value for key '{file_path_key}' is not a dictionary. Skipping.")
            continue

        classes = file_data.get("classes")
        if not isinstance(classes, list):
            # print(f"Warning: No 'classes' list found or is not a list for '{file_path_key}'. Skipping.")
            continue

        for class_info in classes:
            if not isinstance(class_info, dict):
                # print(f"Warning: Item in 'classes' for '{file_path_key}' is not a dictionary. Skipping.")
                continue
            
            methods = class_info.get("methods")
            if not isinstance(methods, list):
                # print(f"Warning: No 'methods' list found or is not a list for class '{class_info.get('name', 'Unnamed Class')}' in '{file_path_key}'. Skipping.")
                continue

            for method_info in methods:
                if isinstance(method_info, dict):
                    name = method_info.get("name")
                    description = method_info.get("description")
                    code = method_info.get("code")

                    # Ensure all required fields are present, though they might be empty strings if so in JSON
                    if name is not None and description is not None and code is not None:
                        all_extracted_methods.append({
                            "name": name,
                            "description": description,
                            "code": code
                        })
                    # else:
                        # print(f"Warning: Method in class '{class_info.get('name')}' in '{file_path_key}' is missing one or more fields (name, description, code). Skipping method.")
                # else:
                    # print(f"Warning: Item in 'methods' for class '{class_info.get('name')}' in '{file_path_key}' is not a dictionary. Skipping method.")
    
    return all_extracted_methods

def extract_methods_for_specific_file_from_enhanced_json(json_path, target_file_key):
    """
    Extracts method details for a specific file key from an enhanced JSON file.

    Args:
        json_path (str): Path to the enhanced JSON file.
        target_file_key (str): The specific file path key to process (e.g., "pytorch-stable-diffusion-main/sd/clip.py").

    Returns:
        list: A list of dictionaries for methods found under the target_file_key,
              where each dictionary contains "name", "description", and "code".
              Returns an empty list if the key is not found or no methods are present.
    """
    methods_for_file = []

    if not os.path.exists(json_path):
        print(f"Error: JSON file not found at {json_path}")
        return methods_for_file

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading or parsing JSON file {json_path}: {e}")
        return methods_for_file

    if not isinstance(data, dict):
        print(f"Error: JSON content from {json_path} is not a dictionary.")
        return methods_for_file

    file_data = data.get(target_file_key)
    if not isinstance(file_data, dict):
        print(f"Warning: Key '{target_file_key}' not found in JSON or its value is not a dictionary.")
        return methods_for_file

    classes = file_data.get("classes")
    if not isinstance(classes, list):
        # print(f"Warning: No 'classes' list found or is not a list for '{target_file_key}'.")
        return methods_for_file

    for class_info in classes:
        if not isinstance(class_info, dict):
            # print(f"Warning: Item in 'classes' for '{target_file_key}' is not a dictionary.")
            continue
        
        methods = class_info.get("methods")
        if not isinstance(methods, list):
            # print(f"Warning: No 'methods' list found or is not a list for class '{class_info.get('name', 'Unnamed Class')}' in '{target_file_key}'.")
            continue

        for method_info in methods:
            if isinstance(method_info, dict):
                name = method_info.get("name")
                description = method_info.get("description")
                code = method_info.get("code")

                if name is not None and description is not None and code is not None:
                    methods_for_file.append({
                        "name": name,
                        "description": description,
                        "code": code
                    })
    return methods_for_file

if __name__ == "__main__":
   test = extract_methods_for_specific_file_from_enhanced_json("data/enhanced_json/pytorch-stable-diffusion-main.json", "pytorch-stable-diffusion-main/sd/decoder.py")
   checkpoint_dir = r"D:\HUST\2024.2\Machine Learning\ML_project\src\model\checkpoint-792"
   model_pt_path = r"D:\HUST\2024.2\Machine Learning\ML_project\src\model\checkpoint-792\model_epoch_4.pt"

   model = CodeClassifier(checkpoint_dir, model_pt_path)
   anchor = {"name": "calculate_sum",
    "signature": "def calculate_sum(a, b)",
    "docstring": "DOCSTRING"}
   for method in test:

       input_ref_ = f"{anchor}\n</s>\n{method}"
       pred_class, logits = model.predict_text(input_ref_)
       print(pred_class, method["name"])
       break