import ast
import json
import os
import shutil # For cleanup in example
from models.model import CodeClassifier



def extract_methods_from_enhanced_json(json_path):
    """
    Extracts method details from an enhanced JSON file.

    The JSON is expected to have a structure where top-level keys are file paths,
    each containing a 'classes' list and a 'functions' list. Each class has a 'methods' list,
    and both methods and functions have 'name', 'description', and 'code' fields.

    Args:
        json_path (str): Path to the enhanced JSON file.

    Returns:
        list: A list of dictionaries, where each dictionary contains:
              - "name" (str): The name of the method/function.
              - "description" (str): The description (docstring) of the method/function.
              - "code" (str): The source code of the method/function.
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

        # Extract standalone functions
        functions = file_data.get("functions", [])
        if isinstance(functions, list):
            for function_info in functions:
                if isinstance(function_info, dict):
                    name = function_info.get("name")
                    # Clean up name by removing file path if present
                    if name and "@" in name:
                        name = name.split("@")[0]
                    description = function_info.get("description")
                    code = function_info.get("code")

                    if name is not None and description is not None and code is not None:
                        all_extracted_methods.append({
                            "name": name,
                            "description": description,
                            "code": code
                        })
                    
        # Extract methods from classes (existing code)
        classes = file_data.get("classes", [])
        if isinstance(classes, list):
            for class_info in classes:
                if not isinstance(class_info, dict):
                    continue
                
                methods = class_info.get("methods", [])
                if not isinstance(methods, list):
                    continue

                for method_info in methods:
                    if isinstance(method_info, dict):
                        name = method_info.get("name")
                        # Clean up name by removing file path if present
                        if name and "@" in name:
                            name = name.split("@")[0]
                        description = method_info.get("description")
                        code = method_info.get("code")

                        if name is not None and description is not None and code is not None:
                            all_extracted_methods.append({
                                "name": name,
                                "description": description,
                                "code": code
                            })
    
    return all_extracted_methods

def extract_methods_for_specific_file_from_enhanced_json(json_path, target_file_key):
    """
    Extracts method and function details for a specific file key from an enhanced JSON file.

    Args:
        json_path (str): Path to the enhanced JSON file.
        target_file_key (str): The specific file path key to process (e.g., "pytorch-stable-diffusion-main/sd/clip.py").

    Returns:
        list: A list of dictionaries for methods and functions found under the target_file_key,
              where each dictionary contains "name", "description", "code", and optionally "outgoing_calls".
              Returns an empty list if the key is not found or no methods/functions are present.
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

    # Extract standalone functions
    functions = file_data.get("functions", [])
    if isinstance(functions, list):
        for function_info in functions:
            if isinstance(function_info, dict):
                name = function_info.get("name")
                # Clean up name by removing file path if present
                if name and "@" in name:
                    name = name.split("@")[0]
                description = function_info.get("description")
                code = function_info.get("code")
                # Extract outgoing calls
                outgoing_calls = function_info.get("outgoing_calls", {})

                if name is not None and description is not None and code is not None:
                    method_data = {
                        "name": name,
                        "description": description,
                        "code": code
                    }
                    # Add outgoing calls if present
                    if outgoing_calls:
                        method_data["outgoing_calls"] = outgoing_calls
                    
                    methods_for_file.append(method_data)

    # Extract methods from classes
    classes = file_data.get("classes", [])
    if not isinstance(classes, list):
        return methods_for_file

    for class_info in classes:
        if not isinstance(class_info, dict):
            continue
        
        methods = class_info.get("methods", [])
        if not isinstance(methods, list):
            continue

        for method_info in methods:
            if isinstance(method_info, dict):
                name = method_info.get("name")
                # Clean up name by removing file path if present
                if name and "@" in name:
                    name = name.split("@")[0]
                description = method_info.get("description")
                code = method_info.get("code")
                # Extract outgoing calls
                outgoing_calls = method_info.get("outgoing_calls", {})

                if name is not None and description is not None and code is not None:
                    method_data = {
                        "name": name,
                        "description": description,
                        "code": code
                    }
                    # Add outgoing calls if present
                    if outgoing_calls:
                        method_data["outgoing_calls"] = outgoing_calls
                    
                    methods_for_file.append(method_data)
    
    return methods_for_file

def build_method_call_tree(json_path, target_file_key, depth=2):
    """
    Builds a tree of method calls starting from methods in the target file.
    
    Args:
        json_path (str): Path to the enhanced JSON file.
        target_file_key (str): The specific file path key to start from.
        depth (int): How deep to follow the call chain (to prevent infinite recursion).
    
    Returns:
        list: A list of method dictionaries, each containing:
              - Basic method info (name, description, code)
              - "called_methods": List of method dictionaries that this method calls
    """
    # Storage for resolved methods (to avoid duplicate work and circular references)
    resolved_methods = {}
    
    # Load the entire JSON data once
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            all_data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return []
    
    def resolve_method_by_name(method_name):
        """Find method details by its full name (e.g., 'ClassName.method_name@file_path')"""
        # If we've already resolved this method, return the cached result
        if method_name in resolved_methods:
            return resolved_methods[method_name]
        
        # Parse method name to get file path if it contains '@'
        file_path = None
        if "@" in method_name:
            name_part, file_path = method_name.split("@", 1)
        else:
            name_part = method_name
            
        # Try to find the method in the data
        if file_path and file_path in all_data:
            file_data = all_data[file_path]
            
            # Check in functions
            for func in file_data.get("functions", []):
                if func.get("name") == method_name:
                    method_info = {
                        "name": name_part,
                        "description": func.get("description", ""),
                        "code": func.get("code", ""),
                        "file_path": file_path,
                        "outgoing_calls": func.get("outgoing_calls", {})  # Include outgoing calls for further resolution
                    }
                    resolved_methods[method_name] = method_info
                    return method_info
            
            # Check in class methods
            for cls in file_data.get("classes", []):
                for method in cls.get("methods", []):
                    if method.get("name") == method_name:
                        method_info = {
                            "name": name_part,
                            "description": method.get("description", ""),
                            "code": method.get("code", ""),
                            "file_path": file_path,
                            "outgoing_calls": method.get("outgoing_calls", {})  # Include outgoing calls for further resolution
                        }
                        resolved_methods[method_name] = method_info
                        return method_info
        
        # If we couldn't find detailed info, return a basic reference
        basic_info = {
            "name": name_part,
            "description": "",
            "code": "",
            "file_path": file_path or "unknown"
        }
        resolved_methods[method_name] = basic_info
        return basic_info
    
    def resolve_class_methods(class_name):
        """Find all methods of a class by its full name (e.g., 'ClassName@file_path')"""
        class_methods = []
        
        # Parse class name to get file path if it contains '@'
        file_path = None
        if "@" in class_name:
            name_part, file_path = class_name.split("@", 1)
        else:
            name_part = class_name
            
        # Try to find the class in the data
        if file_path and file_path in all_data:
            file_data = all_data[file_path]
            
            # Look for the class
            for cls in file_data.get("classes", []):
                if cls.get("name") == class_name:
                    # Extract all methods of this class
                    for method in cls.get("methods", []):
                        method_info = {
                            "name": method.get("name", "").split("@")[0] if "@" in method.get("name", "") else method.get("name", ""),
                            "description": method.get("description", ""),
                            "code": method.get("code", ""),
                            "file_path": file_path,
                            "method_type": "class_method",
                            "outgoing_calls": method.get("outgoing_calls", {})  # Include outgoing calls for further resolution
                        }
                        class_methods.append(method_info)
                    break
        
        return class_methods
    
    def resolve_function_details(function_name):
        """Find the complete details of a function by its full name"""
        # This is similar to resolve_method_by_name but optimized for functions
        if function_name in resolved_methods:
            return resolved_methods[function_name]
        
        file_path = None
        if "@" in function_name:
            name_part, file_path = function_name.split("@", 1)
        else:
            name_part = function_name
            
        if file_path and file_path in all_data:
            file_data = all_data[file_path]
            
            # Check in functions
            for func in file_data.get("functions", []):
                if func.get("name") == function_name:
                    function_info = {
                        "name": name_part,
                        "description": func.get("description", ""),
                        "code": func.get("code", ""),
                        "file_path": file_path,
                        "outgoing_calls": func.get("outgoing_calls", {})  # Include outgoing calls for further resolution
                    }
                    resolved_methods[function_name] = function_info
                    return function_info
        
        # If not found, return basic info
        basic_info = {
            "name": name_part,
            "description": "",
            "code": "",
            "file_path": file_path or "unknown"
        }
        resolved_methods[function_name] = basic_info
        return basic_info
    
    def build_call_tree_for_method(method_data, current_depth=0, visited=None):
        """Recursively build the call tree for a method"""
        if visited is None:
            visited = set()
            
        # Avoid circular references
        method_identifier = f"{method_data.get('name', '')}@{method_data.get('file_path', '')}"
        if method_identifier in visited or current_depth >= depth:
            return method_data
            
        visited.add(method_identifier)
        
        # Get outgoing calls
        outgoing_calls = method_data.get("outgoing_calls", {})
        called_methods = []
        
        # Process class method calls - get ALL methods of the class
        for class_method in outgoing_calls.get("classes", []):
            # Extract class name from the method name
            class_name = None
            if "@" in class_method:
                method_name, file_path = class_method.split("@", 1)
                if "." in method_name:
                    class_name, _ = method_name.split(".", 1)
                    class_name = f"{class_name}@{file_path}"
                else:
                    # If there's no dot, it might be the class name already
                    class_name = f"{method_name}@{file_path}"
            
            if class_name:
                # Get all methods of this class
                class_methods = resolve_class_methods(class_name)
                
                # Add a class reference first
                class_info = {
                    "name": class_name.split("@")[0] if "@" in class_name else class_name,
                    "description": "Class from " + (file_path if file_path else "unknown location"),
                    "code": "",
                    "file_path": file_path or "unknown",
                    "method_type": "class"
                }
                called_methods.append(class_info)
                
                # Then add all methods of this class
                for method in class_methods:
                    # Recursively build call tree for each method
                    if current_depth < depth - 1:
                        method = build_call_tree_for_method(
                            method, 
                            current_depth + 1,
                            visited.copy()
                        )
                    called_methods.append(method)
            else:
                # Fallback to old behavior if we couldn't extract class name
                resolved_method = resolve_method_by_name(class_method)
                if current_depth < depth - 1:
                    resolved_method = build_call_tree_for_method(
                        resolved_method, 
                        current_depth + 1,
                        visited.copy()
                    )
                called_methods.append(resolved_method)
        
        # Process function calls - get full function details
        for function in outgoing_calls.get("functions", []):
            function_details = resolve_function_details(function)
            # Recursively build call tree for this function
            if current_depth < depth - 1:
                function_details = build_call_tree_for_method(
                    function_details,
                    current_depth + 1,
                    visited.copy()
                )
            called_methods.append(function_details)
        
        # Add called methods to the result
        if called_methods:
            method_data["called_methods"] = called_methods
        
        return method_data
    
    # Start with methods in the target file
    base_methods = extract_methods_for_specific_file_from_enhanced_json(json_path, target_file_key)
    call_trees = []
    
    # Build call tree for each method
    for method in base_methods:
        call_tree = build_call_tree_for_method(method)
        call_trees.append(call_tree)
    
    return call_trees

def flatten_method_call_tree(call_tree, parent_names=None):
    """
    Flattens a nested method call tree into a list of lists structure.
    
    Args:
        call_tree (dict): A method dictionary containing "called_methods"
        parent_names (list): Chain of parent method names (for tracking call path)
    
    Returns:
        list: A list where each element is a list representing a call path
              [method1, method2, method3, ...] where method1 calls method2, etc.
    """
    if parent_names is None:
        parent_names = []
    
    # Create a copy of the current method without the "called_methods" field
    current_method = {k: v for k, v in call_tree.items() if k != "called_methods"}
    
    # If this method doesn't call any other methods, return a single path
    if "called_methods" not in call_tree or not call_tree["called_methods"]:
        return [[*parent_names, current_method]]
    
    # Initialize the result with the current method
    all_paths = []
    
    # For each called method, recursively get all paths
    for called_method in call_tree["called_methods"]:
        # Add the current method to parent_names for the next level
        new_parent_names = [*parent_names, current_method]
        
        # Get all paths from this called method
        paths_from_called = flatten_method_call_tree(called_method, new_parent_names)
        
        # Add these paths to the result
        all_paths.extend(paths_from_called)
    
    return all_paths

def find_method_across_files(json_path, method_name):
    """
    Find a method or function across all files in the JSON data.
    
    Args:
        json_path (str): Path to the enhanced JSON file.
        method_name (str): Name of the method/function to find (without file path).
        
    Returns:
        list: A list of dictionaries containing the method details from all matching files.
    """
    matching_methods = []
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading or parsing JSON file {json_path}: {e}")
        return matching_methods
    
    # Search across all files in the JSON
    for file_path, file_data in data.items():
        # Search in functions
        for func in file_data.get("functions", []):
            func_name = func.get("name", "").split("@")[0] if "@" in func.get("name", "") else func.get("name", "")
            if func_name == method_name:
                method_info = {
                    "name": func_name,
                    "description": func.get("description", ""),
                    "code": func.get("code", ""),
                    "file_path": file_path,
                    "outgoing_calls": func.get("outgoing_calls", {})
                }
                matching_methods.append(method_info)
        
        # Search in class methods
        for cls in file_data.get("classes", []):
            for method in cls.get("methods", []):
                method_name_part = method.get("name", "").split("@")[0] if "@" in method.get("name", "") else method.get("name", "")
                if method_name_part == method_name:
                    method_info = {
                        "name": method_name_part,
                        "description": method.get("description", ""),
                        "code": method.get("code", ""),
                        "file_path": file_path,
                        "outgoing_calls": method.get("outgoing_calls", {})
                    }
                    matching_methods.append(method_info)
    
    return matching_methods

def get_cross_file_dependencies(json_path, method_data):
    """
    Extract all cross-file dependencies for a method or function.
    
    Args:
        json_path (str): Path to the enhanced JSON file.
        method_data (dict): Dictionary containing the method details.
        
    Returns:
        dict: A dictionary containing lists of cross-file dependencies.
    """
    cross_file_deps = {
        "functions": [],
        "classes": []
    }
    
    current_file = method_data.get("file_path", "")
    outgoing_calls = method_data.get("outgoing_calls", {})
    
    # Extract cross-file function calls
    for func in outgoing_calls.get("functions", []):
        if "@" in func:
            _, file_path = func.split("@", 1)
            if file_path != current_file:
                cross_file_deps["functions"].append(func)
    
    # Extract cross-file class references
    for cls in outgoing_calls.get("classes", []):
        if "@" in cls:
            _, file_path = cls.split("@", 1)
            if file_path != current_file:
                cross_file_deps["classes"].append(cls)
    
    return cross_file_deps

def extract_methods_from_references(json_path, references, ref_type="outgoing_calls"):
    """
    Extract method details from function/class references in outgoing calls or noise fields.
    
    Args:
        json_path (str): Path to the enhanced JSON file.
        references (dict): Dictionary containing 'functions' and 'classes' lists with references.
        ref_type (str): Type of reference ('outgoing_calls' or 'noise').
        
    Returns:
        list: A list of dictionaries with extracted method details.
    """
    extracted_methods = []
    
    if not json_path or not references:
        return extracted_methods
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            all_data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return extracted_methods

    # Process function references
    for func_ref in references.get("functions", []):
        if "@" in func_ref:
            func_name, file_path = func_ref.split("@", 1)
            # Find the function in the data
            if file_path and file_path in all_data:
                file_data = all_data[file_path]
                for func in file_data.get("functions", []):
                    if func.get("name") == func_ref:
                        method_info = {
                            "name": func_name,
                            "description": func.get("description", ""),
                            "code": func.get("code", ""),
                            "file_path": file_path,
                            "ref_type": f"{ref_type}_function"
                        }
                        extracted_methods.append(method_info)
                        break
    
    # Process class references
    for class_ref in references.get("classes", []):
        if "@" in class_ref:
            class_name, file_path = class_ref.split("@", 1)
            # Find class methods in the data
            if file_path and file_path in all_data:
                file_data = all_data[file_path]
                for cls in file_data.get("classes", []):
                    if cls.get("name") == class_ref:
                        # Add all methods of this class
                        for method in cls.get("methods", []):
                            method_name = method.get("name", "").split("@")[0] if "@" in method.get("name", "") else method.get("name", "")
                            method_info = {
                                "name": method_name,
                                "description": method.get("description", ""),
                                "code": method.get("code", ""),
                                "file_path": file_path,
                                "class_name": class_name,
                                "ref_type": f"{ref_type}_class_method"
                            }
                            extracted_methods.append(method_info)
                        break
    
    return extracted_methods

def extract_all_related_methods(json_path, file_path):
    """
    Extract all methods related to a file including methods from outgoing calls and noise.
    
    Args:
        json_path (str): Path to the enhanced JSON file.
        file_path (str): Path to the source file.
        
    Returns:
        dict: A dictionary with keys 'file_methods', 'outgoing_calls', and 'noise',
              each containing a list of method dictionaries.
    """
    all_methods = {
        'file_methods': [],
        'outgoing_calls_methods': [],
        'noise_methods': []
    }
    
    try:
        # Get methods from the file itself
        file_methods = extract_methods_for_specific_file_from_enhanced_json(json_path, file_path)
        all_methods['file_methods'] = file_methods
        
        # Load the JSON file to access raw data
        with open(json_path, "r", encoding="utf-8") as f:
            all_data = json.load(f)
            
        # Get file data
        file_data = all_data.get(file_path, {})
        
        # Process each method to extract outgoing calls and noise
        for method in file_methods:
            # Extract methods from outgoing calls
            if 'outgoing_calls' in method:
                outgoing_methods = extract_methods_from_references(
                    json_path, method['outgoing_calls'], "outgoing_calls"
                )
                all_methods['outgoing_calls_methods'].extend(outgoing_methods)
        
        # Process functions in the file
        for func in file_data.get("functions", []):
            # Extract noise references
            if "noise" in func:
                noise_methods = extract_methods_from_references(
                    json_path, func["noise"], "noise"
                )
                all_methods['noise_methods'].extend(noise_methods)
        
        # Process classes in the file
        for cls in file_data.get("classes", []):
            for method in cls.get("methods", []):
                # Extract noise references from class methods
                if "noise" in method:
                    noise_methods = extract_methods_from_references(
                        json_path, method["noise"], "noise"
                    )
                    all_methods['noise_methods'].extend(noise_methods)
    
    except Exception as e:
        print(f"Error extracting related methods: {e}")
        import traceback
        traceback.print_exc()
    
    return all_methods

if __name__ == "__main__":
    # Example usage
    json_path = "data/enhanced_json/pydep-main.json"
    target_file = "pydep-main/src/pydepcall/Node.py"
    
    print("Testing basic method extraction...")
    methods = extract_methods_for_specific_file_from_enhanced_json(json_path, target_file)
    print(f"Found {len(methods)} methods/functions in {target_file}")
    
    print("\nTesting method call tree construction...")
    call_trees = build_method_call_tree(json_path, target_file, depth=2)
    print(f"Built call trees for {len(call_trees)} methods/functions")
    
    # Display all call trees with detailed information
    if call_trees:
        for method_index, example in enumerate(call_trees, 1):
            print(f"\n=================================================================")
            print(f"CALL TREE #{method_index}: {example['name']}")
            print(f"=================================================================")
            print(f"Description: {example['description']}")
            print(f"Code snippet: {example['code'][:100]}..." if len(example['code']) > 100 else f"Code: {example['code']}")
            
            if "called_methods" in example and example['called_methods']:
                print(f"\nCALLED METHODS ({len(example['called_methods'])}):")
                
                # Group by file path for better organization
                methods_by_file = {}
                for called in example['called_methods']:
                    file_path = called.get('file_path', 'unknown')
                    if file_path not in methods_by_file:
                        methods_by_file[file_path] = []
                    methods_by_file[file_path].append(called)
                
                # Print methods grouped by file
                for file_path, methods_list in methods_by_file.items():
                    print(f"\n  From {file_path} ({len(methods_list)} methods):")
                    for i, called in enumerate(methods_list, 1):
                        method_type = called.get('method_type', '')
                        if method_type == 'class':
                            print(f"    {i}. {called['name']} (Class)")
                            print(f"       {called['description']}")
                        else:
                            print(f"    {i}. {called['name']}")
                            print(f"       Description: {called['description'][:50]}..." if called['description'] and len(called['description']) > 50 else f"       Description: {called['description']}" if called['description'] else "       No description")
                            print(f"       Code snippet: {called['code'][:50]}..." if called['code'] and len(called['code']) > 50 else f"       Code: {called['code']}" if called['code'] else "       No code")
                        
                        # Show nested calls if any
                        if "called_methods" in called and called['called_methods']:
                            print(f"       Makes {len(called['called_methods'])} further calls")
                
                # Convert to flattened paths
                flat_paths = flatten_method_call_tree(example)
                print(f"\n  FLATTENED CALL PATHS:")
                print(f"  Found {len(flat_paths)} distinct call paths")
                for i, path in enumerate(flat_paths[:3], 1):  # Show first 3 paths
                    print(f"  Path {i}: {' -> '.join(m['name'] for m in path)}")
            else:
                print("\nThis method doesn't call any other methods.")
            
        # Show complete detailed examples for class methods
        print(f"\n=================================================================")
        print(f"DETAILED CLASS METHOD EXAMPLES:")
        print(f"=================================================================")
        
        shown_methods = set()
        for tree in call_trees:
            if "called_methods" in tree and tree['called_methods']:
                for called in tree['called_methods']:
                    if called.get('method_type') == 'class':
                        class_name = called['name']
                        # Find methods belonging to this class
                        for method in tree['called_methods']:
                            method_name = method.get('name', '')
                            # Check if it's a method of this class and hasn't been shown yet
                            if method.get('method_type') == 'class_method' and method_name.startswith(class_name) and method_name not in shown_methods:
                                print(f"\n--- {method_name} ---")
                                print(f"Description: {method['description']}")
                                print(f"Full code:\n{method['code']}")
                                shown_methods.add(method_name)
    
    #print(call_trees)
    
    
    print("\nTesting relevance with CodeClassifier...")
    checkpoint_dir = r"D:\HUST\2024.2\Machine Learning\ML_project\src\model\checkpoint-792"
    model_pt_path = r"D:\HUST\2024.2\Machine Learning\ML_project\src\model\checkpoint-792\model_epoch_4.pt"
    model = CodeClassifier(checkpoint_dir, model_pt_path)
    anchor = {"name": "__init__",
        "signature": " def __init__(self, eps: float)",
        "docstring": "Implement RMSNorm init method"}
    
    # Function to evaluate relevance for a method
    def evaluate_method_relevance(method, anchor, model, depth=0):
        """Evaluate the relevance of a method against an anchor using the model."""
        indent = "  " * depth
        
        # Check if method has all the required fields
        if all(field in method for field in ["name", "description", "code"]):
            # Create input for the model
            method_data = {
                "name": method["name"],
                "description": method["description"],
                "code": method["code"]
            }
            
            # Create input reference
            input_ref = f"{anchor['name']}\n{anchor['signature']}\n{anchor['docstring']}\n</s>\n{method_data['name']}\n{method_data['code']}\n{method_data['description']}"
            
            # Predict using the model
            try:
                pred_class, logits = model.predict_text(input_ref)
                relevance = "Relevant" if pred_class == 1 else "Not relevant"
                print(f"{indent}{method['name']}: {relevance} (Score: {logits})")
                return pred_class == 1
            except Exception as e:
                print(f"{indent}Error evaluating {method['name']}: {e}")
                return False
        return False
    
    # Function to process a call tree recursively
    def process_call_tree(tree, anchor, model, depth=0):
        """Process a call tree and its called methods recursively."""
        indent = "  " * depth
        
        # Evaluate the tree itself
        print(f"\n{indent}Evaluating call tree: {tree['name']}")
        is_relevant = evaluate_method_relevance(tree, anchor, model, depth)
        
        # Process called methods if they exist
        if "called_methods" in tree and tree["called_methods"]:
            print(f"{indent}Processing {len(tree['called_methods'])} called methods for {tree['name']}:")
            
            # Track relevance statistics
            relevant_methods = 0
            total_methods = 0
            
            # Process each called method
            for called_method in tree["called_methods"]:
                # Increment count only for methods with required fields
                if all(field in called_method for field in ["name", "description", "code"]):
                    total_methods += 1
                    if evaluate_method_relevance(called_method, anchor, model, depth + 1):
                        relevant_methods += 1
                
                # Recursively process nested call trees
                if "called_methods" in called_method and called_method["called_methods"]:
                    process_call_tree(called_method, anchor, model, depth + 1)
            
            # Print relevance summary for this level
            if total_methods > 0:
                relevance_percentage = (relevant_methods / total_methods) * 100
                print(f"{indent}Summary for {tree['name']}: {relevant_methods}/{total_methods} methods relevant ({relevance_percentage:.1f}%)")
    
    # Process each call tree
    print("\nEvaluating relevance across all call trees...")
    for tree_index, tree in enumerate(call_trees, 1):
        print(f"\n{'='*50}")
        print(f"CALL TREE #{tree_index}: {tree['name']} - RELEVANCE ANALYSIS")
        print(f"{'='*50}")
        process_call_tree(tree, anchor, model)
    
    


