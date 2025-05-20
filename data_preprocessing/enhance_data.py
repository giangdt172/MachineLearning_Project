import os
import json
import re
from .import_processing import build_entity_list_by_file, extract_from_path, get_all_classes, get_all_funcs
from .filter_error_repo import filter_repositories


def enhance_and_classify_outgoing_calls(json_file_path):

    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            repo_data = json.load(f)


        repo_data = filter_repositories(repo_data)

        
        
        file_entities, repo_data = build_entity_list_by_file(repo_data)

        with open('check2.json', 'w', encoding='utf-8') as f:
            json.dump(repo_data, f, indent=4)

        with open('check.json', 'w', encoding='utf-8') as f:
            json.dump(file_entities, f, indent=4)

        
        all_classes = get_all_classes(repo_data)

        
        
        functions_updated = 0
        methods_updated = 0
        
        for file_path, file_info in repo_data.items():
            
            if file_path not in file_entities:
                continue
                
            available_entities = file_entities[file_path]
            
            for func in file_info.get('functions', []):
                func_code = func.get('code', '')
                if not func_code:
                    continue
                
                
                new_outgoing_calls = {
                    'classes': [],
                    'functions': [],
                    'variable': []
                }
                
                
                clean_code = clean_code_for_analysis(func_code)
                
                
                identifiers = extract_identifiers(clean_code)
                
                
                referenced_entities = set()
                
                
                for identifier in identifiers:
                    
                    
                    for entity in available_entities['class_func']:
                        if '@' in entity:
                            entity_name = entity.split('@')[0]
                            if entity_name == identifier:
                                if entity in all_classes:
                                    if entity not in new_outgoing_calls['classes']:
                                        new_outgoing_calls['classes'].append(entity)
                                else:
                                    if entity not in new_outgoing_calls['functions']  or f" {entity_name}(" in clean_code or  f"({entity_name}(" in clean_code or f"{{{entity_name}(" in clean_code or f"@{entity_name}(" in clean_code:
                                        new_outgoing_calls['functions'].append(entity)
                                referenced_entities.add(entity)
                    
                    for var in available_entities['variable']:
                        
                        var_name = var.split('=')[0].strip() if '=' in var else var
                        if var_name == identifier or f" {var_name}." in func_code or f" ({var_name}." in clean_code or f"({var_name})" in clean_code:
                            if var not in new_outgoing_calls['variable']:
                                new_outgoing_calls['variable'].append(var)
                            referenced_entities.add(var)
                
                
                noise = {
                    'classes': [],
                    'functions': [],
                    'variable': []
                }
                
                
                for entity in available_entities['class_func']:
                    if entity not in referenced_entities:
                        if '@' in entity:
                            
                            if entity in all_classes:
                                noise['classes'].append(entity)
                            else:
                                noise['functions'].append(entity)
                
                
                for var in available_entities['variable']:
                    var_name = var.split('=')[0].strip() if '=' in var else var
                    var_is_used = False
                    for used_var in new_outgoing_calls['variable']:
                        used_var_name = used_var.split('=')[0].strip() if '=' in used_var else used_var
                        if var_name == used_var_name:
                            var_is_used = True
                            break
                    if not var_is_used:
                        noise['variable'].append(var)
                
                
                for category in new_outgoing_calls:
                    new_outgoing_calls[category] = sorted(list(set(new_outgoing_calls[category])))
                
                for category in noise:
                    noise[category] = sorted(list(set(noise[category])))
                
                
                func['outgoing_calls'] = new_outgoing_calls
                func['noise'] = noise
                functions_updated += 1

            for class_info in file_info.get('classes', []):
                class_name = class_info.get('name', '').split('@')[0] if '@' in class_info.get('name', '') else class_info.get('name', '')
                class_full_name = class_info.get('name', '')
                
                
                for method in class_info.get('methods', []):
                    method_code = method.get('code', '')
                    if not method_code:
                        continue
                    
                    
                    new_outgoing_calls = {
                        'classes': [],
                        'functions': [],
                        'variable': []
                    }
                    
                    
                    if class_full_name and class_full_name not in new_outgoing_calls['classes']:
                        new_outgoing_calls['classes'].append(class_full_name)
                    
                    
                    clean_code = clean_code_for_analysis(method_code)
                    
                    
                    identifiers = extract_identifiers(clean_code)
                    
                    
                    referenced_entities = set()
                    
                    
                    if class_full_name:
                        referenced_entities.add(class_full_name)
                    
                    
                    for identifier in identifiers:
                        

                        for entity in available_entities['class_func']:
                            if '@' in entity:
                                entity_name = entity.split('@')[0]
                                if entity_name == identifier:
                                    
                                    if entity in all_classes:
                                        if entity not in new_outgoing_calls['classes']:
                                            new_outgoing_calls['classes'].append(entity)
                                    else:
                                        if entity not in new_outgoing_calls['functions'] or f" {entity_name}(" in clean_code or  f"({entity_name}(" in clean_code or f"{{{entity_name}(" in clean_code or f"@{entity_name}(" in clean_code:
                                            new_outgoing_calls['functions'].append(entity)
                                    referenced_entities.add(entity)
                        
                        
                        for var in available_entities['variable']:
                            
                            var_name = var.split('=')[0].strip() if '=' in var else var
                            if var_name == identifier or f" {var_name}." in func_code or f" ({var_name}." in clean_code or f"({var_name})" in clean_code:
                                if var not in new_outgoing_calls['variable']:
                                    new_outgoing_calls['variable'].append(var)
                                referenced_entities.add(var)
                    
                    
                    noise = {
                        'classes': [],
                        'functions': [],
                        'variable': []
                    }
                    
                    
                    for entity in available_entities['class_func']:
                        if entity not in referenced_entities:
                            if '@' in entity:
                                
                                if entity in all_classes:
                                    noise['classes'].append(entity)
                                else:
                                    noise['functions'].append(entity)
                    
                    
                    for var in available_entities['variable']:
                        var_name = var.split('=')[0].strip() if '=' in var else var
                        var_is_used = False
                        for used_var in new_outgoing_calls['variable']:
                            used_var_name = used_var.split('=')[0].strip() if '=' in used_var else used_var
                            if var_name == used_var_name:
                                var_is_used = True
                                break
                        if not var_is_used:
                            noise['variable'].append(var)
                    
                    
                    for category in new_outgoing_calls:
                        new_outgoing_calls[category] = sorted(list(set(new_outgoing_calls[category])))
                    
                    for category in noise:
                        noise[category] = sorted(list(set(noise[category])))
                    
                    
                    method['outgoing_calls'] = new_outgoing_calls
                    method['noise'] = noise
                    methods_updated += 1
                    
        os.remove("check.json")
        os.remove("check2.json")

        print(f"Enhanced and classified outgoing_calls for {functions_updated} functions and {methods_updated} methods")
        return repo_data
        
    except Exception as e:
        print(f"Error enhancing outgoing calls: {e}")
        import traceback
        traceback.print_exc()
        return None


def clean_code_for_analysis(code):
    code = re.sub(r'"""[\s\S]*?"""', '', code)  
    code = re.sub(r"'''[\s\S]*?'''", '', code)  
    
    code = re.sub(r'"[^"]*"', '', code)        
    code = re.sub(r"'[^']*'", '', code)         
    
    code = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
    
    code = re.sub(r'def\s+[a-zA-Z_][a-zA-Z0-9_]*', '', code)
    
    return code


def extract_identifiers(code):
    identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code)
    
    python_keywords = {
        'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await', 'break', 
        'class', 'continue', 'def', 'del', 'elif', 'else', 'except', 'finally', 
        'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'nonlocal', 
        'not', 'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 'yield',
        'print', 'len', 'str', 'int', 'dict', 'list', 'set', 'tuple', 'self', 'cls'
    }
    
    return [ident for ident in identifiers if ident not in python_keywords]


def remove_same_func(data):
    functions_updated = 0
    methods_updated = 0
    
    for file_path, file_info in data.items():
    
        for func in file_info.get('functions', []):
            func_name = func.get('name', '')
            name = func_name.split('@')[0] if '@' in func_name else func_name
                
        
            if 'outgoing_calls' in func and 'functions' in func['outgoing_calls']:
                original_len = len(func['outgoing_calls']['functions'])
                func['outgoing_calls']['functions'] = [
                    call for call in func['outgoing_calls']['functions']
                    if call != func_name and not call.startswith(f"{name}.") and call not in (func.get("child_functions") or [])
                ]
                if len(func['outgoing_calls']['functions']) < original_len:
                    functions_updated += 1
        
        for class_info in file_info.get('classes', []):
            for method in class_info.get('methods', []):
                method_name = method.get('name', '')
                met_name = method_name.split('@')[0] if '@' in method_name else method_name
                
                if 'outgoing_calls' in method and 'functions' in method['outgoing_calls']:
                    original_len = len(method['outgoing_calls']['functions'])
                    method['outgoing_calls']['functions'] = [
                        call for call in method['outgoing_calls']['functions']
                        if call != method_name and not call.startswith(f"{met_name}.") and call not in (method.get("child_functions") or [])
                    ]
                    if len(method['outgoing_calls']['functions']) < original_len:
                        methods_updated += 1
    
    return data

def remove_overloaded_functions(data):

    functions_removed = 0
    methods_removed = 0
    
    for file_path, file_info in data.items():
 
        function_dict = {}
        
        for func in file_info.get('functions', []):
            full_name = func.get('name', '')
            if not full_name:
                continue
                
            lines = func.get('lines_of_code', 0)
            
            if full_name not in function_dict:
                function_dict[full_name] = (lines, func)
            else:
                existing_lines, _ = function_dict[full_name]
                if lines > existing_lines:
                    function_dict[full_name] = (lines, func)
                functions_removed += 1
        

        file_info['functions'] = [func for _, (_, func) in function_dict.items()]
        
        for class_info in file_info.get('classes', []):
            method_dict = {}
            
            for method in class_info.get('methods', []):
                full_name = method.get('name', '')
                if not full_name:
                    continue
                    
                lines = method.get('lines_of_code', 0)
                
                if full_name not in method_dict:
                    method_dict[full_name] = (lines, method)
                else:
                    existing_lines, _ = method_dict[full_name]
                    if lines > existing_lines:
                        method_dict[full_name] = (lines, method)
                    methods_removed += 1

            class_info['methods'] = [method for _, (_, method) in method_dict.items()]
    
    return data


def filter_same_name_different_file_calls(data):
    calls_modified = 0

    for file_path, file_info in data.items():
        for func in file_info.get('functions', []):
            if 'outgoing_calls' not in func or 'noise' not in func:
                continue
            
            calls_modified += filter_calls_for_entity(func, file_path)
        
        for class_info in file_info.get('classes', []):
            for method in class_info.get('methods', []):
                if 'outgoing_calls' not in method or 'noise' not in method:
                    continue
                
                calls_modified += filter_calls_for_entity(method, file_path)
    
    return data

def filter_calls_for_entity(entity, current_file_path):
    modified_count = 0
    
    categories = ['classes', 'functions']
    
    for category in categories:
        if category not in entity['outgoing_calls']:
            continue
        
 
        name_groups = {}
        for call in entity['outgoing_calls'][category]:
            if '@' in call:
                name, file_info = call.split('@', 1)
                if name not in name_groups:
                    name_groups[name] = []
                name_groups[name].append(call)
        
        for name, calls in name_groups.items():
            if len(calls) <= 1:
                continue  
            
            current_file_call = None
            other_calls = []
            
            for call in calls:
                _, file_path_in_call = call.split('@', 1)
                if file_path_in_call == current_file_path:
                    current_file_call = call
                else:
                    other_calls.append(call)
            
            if current_file_call:
                for call in other_calls:
                    if call in entity['outgoing_calls'][category]:
                        entity['outgoing_calls'][category].remove(call)
                        if call not in entity['noise'][category]:
                            entity['noise'][category].append(call)
                        modified_count += 1
    
    for category in categories:
        if category in entity['outgoing_calls']:
            entity['outgoing_calls'][category] = sorted(entity['outgoing_calls'][category])
        if category in entity['noise']:
            entity['noise'][category] = sorted(entity['noise'][category])
    
    return modified_count


def categorize_imports_correctly(data):
    moves_count = 0
    

    data_keys = set(data.keys())
    
    for file_path, file_info in data.items():
        if 'import_statements' not in file_info:
            continue
        
        imports_info = file_info['import_statements']
        
        if 'third_party' not in imports_info:
            continue
            

        project_imports = imports_info.get('project', [])
        third_party = imports_info['third_party'].copy()
        
        for import_statement in imports_info['third_party']:
            module_path = extract_from_path(import_statement)
            
            if module_path:
                for key in data_keys:
                    if f"/{module_path}" in key or key.startswith(module_path + ".py"):
                        if import_statement not in project_imports:
                            project_imports.append(import_statement)
                            third_party.remove(import_statement)
                            moves_count += 1
                            break
        
        imports_info['project'] = sorted(project_imports)
        imports_info['third_party'] = sorted(third_party)
        
    return data

def refine(json_file_path):
    enhanced_data = enhance_and_classify_outgoing_calls(json_file_path)
    enhanced_data = remove_same_func(enhanced_data)
    enhanced_data = remove_overloaded_functions(enhanced_data)
    enhanced_data = filter_same_name_different_file_calls(enhanced_data)
    enhanced_data = categorize_imports_correctly(enhanced_data)
    return enhanced_data


def save_enhanced_json(output_path, enhanced_data):
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(enhanced_data, f, indent=4)
    print(f"Enhanced data saved to {output_path}")

# Use relative paths instead of absolute paths
input_folder_path = "data/raw_json"
result_folder_path = "data/enhanced_json"
os.makedirs(result_folder_path, exist_ok=True)

if __name__ == "__main__":
    
    for filename in os.listdir(input_folder_path):
        if filename.endswith('.json'):
            filepath = os.path.join(input_folder_path, filename)
            
    
            enhanced_data = refine(filepath)

            output_file = os.path.join(result_folder_path, filename)
            save_enhanced_json(output_file, enhanced_data)

    # json_file_path = r"F:\năm hi\lab_fm\ReFunc\data\temp\processed_repositories\ESPixelStick.json"
    
    # enhanced_data = refine(json_file_path)

    # output_path = "repo_structure_enhanced.json"
    # save_enhanced_json(output_path, enhanced_data)