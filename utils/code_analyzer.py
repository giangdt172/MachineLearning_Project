"""
Code analyzer functions for extracting function signatures and docstrings.
"""

import ast
import re

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

def get_function_options(file_content):
    """Get dropdown options for functions in the current file"""
    functions = extract_signatures_and_docstrings(file_content)
    return {f"{func['name']}": func for func in functions}

def set_function_inputs(function_selection, function_data):
    """Set signature and docstring inputs when a function is selected"""
    if not function_selection or not function_data:
        return "", ""
    
    selected_func = function_data.get(function_selection, {})
    return (
        selected_func.get("signature", ""),
        selected_func.get("docstring", "")
    )

def analyze_file_functions(file_content):
    """Analyze the current file and extract functions"""
    import gradio as gr
    
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