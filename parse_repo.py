import os
import ast
import json
import sys
import pkgutil
import networkx as nx
import re

globalvar = dict()

def get_builtin_functions():
    return set(dir(__builtins__))

def get_methods():
    return set([
        'append', 'extend', 'insert', 'remove', 'pop', 'clear', 'index', 'count',
        'sort', 'reverse', 'copy', 'get', 'items', 'keys', 'values', 'update',
        'strip', 'split', 'join', 'replace', 'format', 'startswith', 'endswith',
        'read', 'write', 'close', 'find', 'lower', 'upper', 'isalpha', 'isdigit'
    ])

def get_available_modules():
    std_modules = set(sys.builtin_module_names)
    installed_modules = {mod[1] for mod in pkgutil.iter_modules()}
    common_modules = set(['os', 'sys', 're', 'json', 'datetime', 'math', 'random',
                          'requests', 'csv', 'time', 'collections', 'pathlib', 'logging','numpy'])
    return std_modules.union(installed_modules).union(common_modules)

def parse_python_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()

    relative_path = os.path.basename(file_path)
    tree = ast.parse(code)

    structure = {
        "functions": [],
        "classes": [],
        "variables": [],
        "import_statements": {
            "project": [],
            "third_party": []
        },
        "other": []
    }
    
    builtins = get_builtin_functions()
    common_methods = get_methods()
    common_modules = get_available_modules()
    
    imported_names = {}    
    
    for node in tree.body:
        if isinstance(node, ast.Import):
            for name in node.names:
                mod_name = name.name.split('.')[0]
                if mod_name in common_modules:
                    structure["import_statements"]["third_party"].append(f"import {name.name}")
                else:
                    structure["import_statements"]["project"].append(f"import {name.name}")
                    
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level > 0:
                module = "." * node.level + module
            mod_processed = module.lstrip('.')
            
            for name in node.names:
                imported_names[name.name] = module
                stmt = f"from {module} import {name.name}"
                if node.level > 0 or mod_processed not in common_modules:
                    structure["import_statements"]["project"].append(stmt)
                else:
                    structure["import_statements"]["third_party"].append(stmt)
    
    def extract_dependencies(node):
        dependencies = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    func_name = child.func.id
                    if func_name not in builtins:
                        if func_name in imported_names:
                            module = imported_names[func_name]
                            dependencies.append(f"{module}.{func_name}")
                        else:
                            dependencies.append(func_name)
                elif isinstance(child.func, ast.Attribute):
                    if isinstance(child.func.value, ast.Name):
                        module = child.func.value.id
                        method = child.func.attr
                        if module not in common_modules and method not in common_methods:
                            dependencies.append(f"{module}.{method}")
        return list(set(dependencies))
    
    def calculate_complexity(node):
        complexity = 1  
        for child in ast.walk(node):
            if isinstance(child, ast.If):
                complexity += 1
            elif isinstance(child, (ast.For, ast.While)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, ast.IfExp):
                complexity += 1
            elif isinstance(child, (ast.ListComp, ast.DictComp, ast.SetComp)):
                for generator in child.generators:
                    if generator.ifs:
                        complexity += len(generator.ifs)
        return complexity

    def process_function(node):
        func_name = node.name  
        loc = node.end_lineno - node.lineno + 1
        dependencies = extract_dependencies(node)
        
        params = {}
        param_list = []
        for arg in node.args.args:
            param_name = arg.arg
            param_type = "unknown"
            if param_name == "str":
                param_type = "string"
            elif arg.annotation:
                if isinstance(arg.annotation, ast.Name):
                    param_type = arg.annotation.id
                elif isinstance(arg.annotation, ast.Constant):
                    param_type = str(arg.annotation.value)
            params[param_name] = {
                "type": param_type
            }
            param_list.append(param_name)
        
        docstring_obj = ast.get_docstring(node)
        has_docstring = docstring_obj is not None
        docstring = docstring_obj or "DOCSTRING"
        
        complexity = calculate_complexity(node)
        source_segment = ast.get_source_segment(code, node)
        
        structure["functions"].append({
            "name": func_name,  
            "file_path": relative_path,
            "description": docstring,
            "code": source_segment,
            "parameters": params,
            "lines_of_code": loc,
            "dependencies": dependencies,
            "has_docstring": has_docstring,
            "complexity": complexity,
            "outgoing_calls": [],
            "incoming_calls": []
        })
    
    def process_class(cls_node):
        cls_name = cls_node.name
        cls_docstring = ast.get_docstring(cls_node) or "DOCSTRING"
        bases = []
        for base in cls_node.bases:
            try:
                bases.append(ast.unparse(base))
            except AttributeError:
                bases.append(getattr(base, 'id', repr(base)))
        
        methods = []
        
        # Process all methods including __init__
        for child in cls_node.body:
            if isinstance(child, ast.FunctionDef):
                method_name = f"{cls_name}.{child.name}"
                loc = child.end_lineno - child.lineno + 1
                dependencies = extract_dependencies(child)
                params = {}
                param_list = []
                for arg in child.args.args:
                    param_name = arg.arg
                    param_type = "unknown"
                    if param_name == "str":
                        param_type = "string"
                    elif arg.annotation:
                        if isinstance(arg.annotation, ast.Name):
                            param_type = arg.annotation.id
                        elif isinstance(arg.annotation, ast.Constant):
                            param_type = str(arg.annotation.value)
                    params[param_name] = {"type": param_type}
                    param_list.append(param_name)
                docstring_obj = ast.get_docstring(child)
                has_docstring = docstring_obj is not None
                docstring = docstring_obj or "DOCSTRING"
                comp = calculate_complexity(child)
                source_segment = ast.get_source_segment(code, child)
                
                methods.append({
                    "name": method_name,
                    "file_path": relative_path,
                    "description": docstring,
                    "code": source_segment,
                    "parameters": params,
                    "lines_of_code": loc,
                    "dependencies": dependencies,
                    "has_docstring": has_docstring,
                    "complexity": comp,
                    "outgoing_calls": [],
                    "incoming_calls": []
                })
        
        structure["classes"].append({
            "name": cls_name,
            "file_path": relative_path,
            "description": cls_docstring,
            "base_classes": bases,
            "methods": methods
        })
    
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            process_function(node)
        elif isinstance(node, ast.ClassDef):
            process_class(node)
    
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Assign, ast.Import, ast.ImportFrom)):
            other_segment = ast.get_source_segment(code, node)
            if other_segment:
                structure["other"].append(other_segment)
    
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    var_name = target.id
                    var_value = ""
                    if isinstance(node.value, ast.Constant):
                        if isinstance(node.value.value, str):
                            var_value = f'"{node.value.value}"'
                        else:
                            var_value = repr(node.value.value)
                    elif isinstance(node.value, ast.Str):
                        var_value = f'"{node.value.s}"'
                    else:
                        try:
                            var_value = ast.get_source_segment(code, node.value)
                        except:
                            var_value = "..."
                    structure["variables"].append(f'{var_name} = {var_value}')
                    globalvar[var_name] = f'{var_name} = {var_value}'
                    
    return structure
'''
def compute_centralities(repo_structure):
    G = nx.DiGraph()
    for file_structure in repo_structure.values():
        func_method = file_structure.get("functions", []) + [
            m for cls in file_structure.get("classes", []) for m in cls.get("methods", [])
        ]
        for function in func_method:
            func_key = function["name"]
            G.add_node(func_key)

    for file_structure in repo_structure.values():
        func_method = file_structure.get("functions", []) + [
            m for cls in file_structure.get("classes", []) for m in cls.get("methods", [])
        ]
        for function in func_method:
            caller = function["name"]
            for callee in function["outgoing_calls"]:
                if callee in G.nodes:
                    G.add_edge(caller, callee)

    degree_centrality = nx.degree_centrality(G)
    deg_in = dict(G.in_degree())
    deg_out = dict(G.out_degree())
    betweenness = nx.betweenness_centrality(G, normalized=True)
    closeness = nx.closeness_centrality(G)
    try:
        eigenvector = nx.eigenvector_centrality(G, max_iter=1000)
    except nx.NetworkXException:
        eigenvector = {node: 0 for node in G.nodes()}

    for file_structure in repo_structure.values():
        func_method = file_structure.get("functions", []) + [
            m for cls in file_structure.get("classes", []) for m in cls.get("methods", [])
        ]
        for function in func_method:
            k = function["name"]
            function["degree_in"] = deg_in.get(k, 0)
            function["degree_out"] = deg_out.get(k, 0)
            function["degree_centrality"] = degree_centrality.get(k, 0)
            function["betweenness"] = betweenness.get(k, 0)
            function["closeness"] = closeness.get(k, 0)
            function["eigenvector"] = eigenvector.get(k, 0)
'''

def extract_repo_structure(repo_path):
    repo_structure = {}

    for root, _, files in os.walk(repo_path):
        for file in files:
            if not file.endswith(".py"):
                continue
                
            full_path = os.path.join(root, file)
            relative_path = os.path.relpath(full_path, repo_path).replace('\\', '/')
            
            try:
                repo_structure[relative_path] = parse_python_file(full_path)
            except Exception as e:
                repo_structure[relative_path] = {
                    "functions": [],
                    "variables": [],
                    "import_statements": {
                        "project": [],
                        "third_party": [f"Error: {str(e)}"]
                    },
                    "classes": []
                }


    function_refs = {}
    class_refs = {}
    candidate_map = {}
    
    for file_path, file_structure in repo_structure.items():
        for i, function in enumerate(file_structure.get("functions", [])):
            function.setdefault("incoming_calls", [])
            function.setdefault("outgoing_calls", [])

            new_name = f"{function['name']}@{file_path}" if "@" not in function["name"] else function["name"]
            function["name"] = new_name
            function["file_path"] = file_path
            
            function_refs[new_name] = ("function", file_path, i)
            base_name = new_name.split('@')[0]
            candidate_map.setdefault(base_name, []).append(new_name)
        
        for ci, cls in enumerate(file_structure.get("classes", [])):
            new_name = f"{cls['name']}@{file_path}" if "@" not in cls["name"] else cls["name"]
            cls["name"] = new_name
            cls["file_path"] = file_path
            class_refs[new_name] = ("class", file_path, ci)
            
            for mi, method in enumerate(cls.get("methods", [])):
                method.setdefault("incoming_calls", [])
                method.setdefault("outgoing_calls", [])
                
                method_new_name = f"{method['name']}@{file_path}" if "@" not in method["name"] else method["name"]
                method["name"] = method_new_name
                method["file_path"] = file_path
                
                function_refs[method_new_name] = ("method", file_path, ci, mi)
                base_method_name = method_new_name.split('@')[0]
                candidate_map.setdefault(base_method_name, []).append(method_new_name)

    def resolve_dependencies(caller_key, deps, outgoing_calls):
        for dep in deps:
            callee_fn = dep.split(".")[-1] if "." in dep else dep
            for candidate in candidate_map.get(callee_fn, []):
                if candidate not in outgoing_calls:
                    outgoing_calls.append(candidate)
                
                ref = function_refs.get(candidate)
                if not ref:
                    continue
                    
                if ref[0] == "function":
                    f_file, f_index = ref[1], ref[2]
                    repo_structure[f_file]["functions"][f_index]["incoming_calls"].append(caller_key)
                else: 
                    f_file, cls_index, method_index = ref[1], ref[2], ref[3]
                    repo_structure[f_file]["classes"][cls_index]["methods"][method_index]["incoming_calls"].append(caller_key)
        return outgoing_calls

    for file_path, file_structure in repo_structure.items():
        for func in file_structure.get("functions", []):
            deps = func.pop("dependencies", []) if "dependencies" in func else []
            func["outgoing_calls"] = resolve_dependencies(func["name"], deps, func["outgoing_calls"])
        
        for cls in file_structure.get("classes", []):
            for method in cls.get("methods", []):
                deps = method.pop("dependencies", []) if "dependencies" in method else []
                method["outgoing_calls"] = resolve_dependencies(method["name"], deps, method["outgoing_calls"])

    return repo_structure

'''
def change_structure(data, requirement):

    file_txt = open(requirement, "r")
    requirements = file_txt.read().split('\n')
    for value in data.values():
        import_state = value["import_statements"]
        for project in import_state["project"]:
            for library in requirements:
                if library != '':
                    library = library.split('==')
                    library[0] = library[0].replace("-","_")
                    
                    if library[0] in project:
                        import_state["third_party"].append(project)
                        break
                    
        for project in import_state["third_party"]:
            if project in import_state["project"]:
                import_state["project"].remove(project)
    return data
'''

def add_globalvar_calls(data, globalvar):
    for file_structure in data.values():
        for function in file_structure.get("functions", []):
            code = function.get("code", "")
            for var, var_def in globalvar.items():
                pattern_usage = r'\b' + re.escape(var) + r'\b'
                pattern_assignment = r'\b' + re.escape(var) + r'\s*='
                if re.search(pattern_usage, code) and not re.search(pattern_assignment, code):
                    if var_def not in function.get("outgoing_calls", []):
                        function.setdefault("outgoing_calls", []).append(var_def)
    return data


def filter_outgoing_calls_by_proximity(data):
    for file_structure in data.values():
        for function in file_structure.get("functions", []):
            current_file = function.get("file_path", "")  
            calls = function.get("outgoing_calls", [])
            call_groups = {}
            for call in calls:
                if "@" in call:
                    base_name, target_file = call.split("@", 1)
                    call_groups.setdefault(base_name, []).append((call, target_file))
                else:
                    call_groups.setdefault(call, []).append((call, ""))
            filtered_calls = []
            for base, group in call_groups.items():
                candidate = None
                for full_call, target in group:
                    if target.endswith(current_file):
                        candidate = full_call
                        break
                if candidate is None:
                    candidate = group[0][0]
                filtered_calls.append(candidate)
            function["outgoing_calls"] = filtered_calls

        for cls in file_structure.get("classes", []):
            for method in cls.get("methods", []):
                current_file = method.get("file_path", "")
                calls = method.get("outgoing_calls", [])
                call_groups = {}
                for call in calls:
                    if "@" in call:
                        base_name, target_file = call.split("@", 1)
                        call_groups.setdefault(base_name, []).append((call, target_file))
                    else:
                        call_groups.setdefault(call, []).append((call, ""))
                filtered_calls = []
                for base, group in call_groups.items():
                    candidate = None
                    for full_call, target in group:
                        if target.endswith(current_file):
                            candidate = full_call
                            break
                    if candidate is None:
                        candidate = group[0][0]
                    filtered_calls.append(candidate)
                method["outgoing_calls"] = filtered_calls
    return data

def validate_imports(data):
    repo_files = data
    
    project_modules = set()
    directories = set()
    
    for file_path in repo_files.keys():
        base = os.path.splitext(os.path.basename(file_path))[0]
        project_modules.add(base)
        
        dir_path = os.path.dirname(file_path)
        parts = dir_path.split(os.sep)
        for part in parts:
            if part:  
                directories.add(part)
    
    project_modules.update(directories)
    
    for file_structure in repo_files.values():
        project_imports = file_structure.get("import_statements", {}).get("project", [])
        third_party_imports = file_structure.get("import_statements", {}).get("third_party", [])
        
        if not project_imports:
            continue 
        
        valid_imports = []
        for imp in project_imports:
            imported_mod = None
            if imp.startswith("import "):
                mod = imp.split()[1]
                imported_mod = mod.lstrip('.').split('.')[0]
            elif imp.startswith("from "):
                mod = imp.split()[1]
                imported_mod = mod.lstrip('.').split('.')[0]
            
            if imported_mod and imported_mod in project_modules:
                valid_imports.append(imp)
            else:
                third_party_imports.append(imp)
        
        file_structure["import_statements"]["project"] = valid_imports
        file_structure["import_statements"]["third_party"] = third_party_imports
    
    return data


def filter_valid_repo(data):
    valid_files = {}
    for file_path, content in data.items():
        if "import_statements" not in content:
            continue 
        
        project_imports = content["import_statements"].get("project", [])
        third_party_imports = content["import_statements"].get("third_party", [])
        overall_imports = project_imports + third_party_imports
        
        if len(overall_imports) >= 0 and len(project_imports) >= 0:
            valid_files[file_path] = content

    if len(valid_files) < 1:
        return False
    return True


def process_repo(repo_path):
    structure = extract_repo_structure(repo_path)
    status = filter_valid_repo(structure)
    if status:
        #requirements_files = structure.pop("lib_requirement", None)
        #requirements_files = os.path.join(repo_path, requirements_files) if requirements_files else None
        #structure = change_structure(structure["repo_files"], requirements_files)
        structure = add_globalvar_calls(structure, globalvar)
        structure = filter_outgoing_calls_by_proximity(structure)
        structure = validate_imports(structure)
        #structure = filter_valid_repo(structure)
        return structure
    else:
        print(f"Repository {repo_path} does not meet the criteria.")
        return None



if __name__ == "__main__":
    repo_path = r"E:\Career\Research\[BKAI] - AI4Code\ReFunc\data\raw_repositories\Megatron-DeepSpeed"
    #repo_path = r"E:\Career\Research\[BKAI] - AI4Code\ReFunc\data\pydep"
    structure = process_repo(repo_path)
    with open('repo_structure.json', 'w', encoding='utf-8') as f:
        json.dump(structure, f, indent=4)


