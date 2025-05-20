import json
import re
import os
from pathlib import Path
from collections import defaultdict


def get_all_classes(repo_data):
    all_classes = set()
    for file_path, file_info in repo_data.items():
        for class_info in file_info.get('classes', []):
            class_name = class_info.get('name', '')
            if class_name:  
                all_classes.add(class_name)
    return all_classes

def get_all_funcs(repo_data):
    all_funcs = set()
    for file_path, file_info in repo_data.items():
        for func_info in file_info.get('functions', []):
            func_name = func_info.get('name', '')
            if func_name:  
                all_funcs.add(func_name)
    return all_funcs



def build_entity_list_by_file(data):
    error_file = list()
    try:
 
      
        entities_info = collect_project_entities(data)
        
     
        file_entities = {}


   
        for file_path, file_info in data.items():
   
            file_entities[file_path] = {
                'class_func': [],
                'variable': []
            }
            
     
            imported_entities = {
                'class_func': [],
                'variable': []
            }
            

            import_stmts = file_info.get('import_statements', {})
            all_imports = import_stmts.get('project', []) + import_stmts.get('third_party', [])
            for import_stmt in all_imports:                
                process_import_statement(
                    import_stmt, 
                    file_path, 
                    imported_entities, 
                    entities_info,
                    data
                    )

            

            file_entities[file_path]['class_func'].extend(imported_entities['class_func'])
            file_entities[file_path]['variable'].extend(imported_entities['variable'])

            for class_info in file_info.get('classes', []):
                class_full_name = class_info.get('name', '')
                if not class_full_name:
                    continue
                    
                if '@' not in class_full_name:
                    class_full_name = f"{class_full_name}@{file_path}"
                
                if class_full_name not in file_entities[file_path]['class_func']:
                    file_entities[file_path]['class_func'].append(class_full_name)
            
     
            for func_info in file_info.get('functions', []):
                func_full_name = func_info.get('name', '')
                if not func_full_name:
                    continue
                    
                if '@' not in func_full_name:
                    func_full_name = f"{func_full_name}@{file_path}"
                
                if func_full_name not in file_entities[file_path]['class_func']:
                    file_entities[file_path]['class_func'].append(func_full_name)
            
    
            for var_expr in file_info.get('variables', []):
                if isinstance(var_expr, str) and var_expr:
                    if var_expr not in file_entities[file_path]['variable']:
                        file_entities[file_path]['variable'].append(var_expr)
            
     
            file_entities[file_path]['class_func'] = sorted(list(set(file_entities[file_path]['class_func'])))
            #file_entities[file_path]['variable'] = sorted(list(set(file_entities[file_path]['variable'])))
        
        return file_entities, data
    
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}

def collect_project_entities(data):
 
    entities = {
        'class_func': defaultdict(list),  # Store lists of class/function entities
        'variable': defaultdict(list)     # Store lists of variable entities
    }
    
    for file_path, file_info in data.items():
   
        for class_info in file_info.get('classes', []):
            class_full_name = class_info.get('name', '')
            if '@' in class_full_name:
                class_name = class_full_name.split('@')[0]
            else:
                class_name = class_full_name
                class_full_name = f"{class_name}@{file_path}"
            
            entities['class_func'][class_name].append(class_full_name)
        
  
        for func_info in file_info.get('functions', []):
            func_full_name = func_info.get('name', '')
            if '@' in func_full_name:
                func_name = func_full_name.split('@')[0]
            else:
                func_name = func_full_name
                func_full_name = f"{func_name}@{file_path}"
            
            entities['class_func'][func_name].append(func_full_name)
        
      
        for var_expr in file_info.get('variables', []):
            if isinstance(var_expr, str):
                if '=' in var_expr:
                    var_name = var_expr.split('=')[0].strip()
                else:
                    var_name = var_expr.strip()
                    
                entities['variable'][var_name].append(var_expr)
        with open ('check1.json', 'w', encoding='utf-8') as f:
            json.dump(entities, f, ensure_ascii=False, indent=4)
    
    os.remove("check1.json")

    return entities


def process_import_statement(import_stmt, current_file_path, imported_entities, entities_info, full_data, init = False):
    if current_file_path not in full_data:
        print(current_file_path)
        return None
    try: 
        if import_stmt.startswith("import "):
            handle_regular_import(
                import_stmt, 
                current_file_path,
                imported_entities,
                entities_info,
                full_data
            )
        

        elif import_stmt.startswith("from ") and " import " in import_stmt:
            handle_from_import(
                import_stmt,
                current_file_path, 
                imported_entities,
                entities_info,
                full_data
            )


    except Exception as e:
        print(f"Lỗi khi xử lý import statement '{import_stmt}' ở file {current_file_path}: {str(e)}")


def handle_regular_import(import_stmt, current_file_path, imported_entities, entities_info, full_data):
    import_part = import_stmt[7:]

    entities = [m.strip() for m in import_part.split(',')]
    
    for entity in entities:
        if not entity:
            continue
        
        original_entity = entity
        alias = None
        
     
        if " as " in entity:
            original_entity, alias = [x.strip() for x in entity.split(" as ", 1)]
        
   
        if "." in original_entity:
            parts = original_entity.split(".")
            last_part = parts[-1]
            module_path = ".".join(parts[:-1])
            
            classify_and_add_entity(
                import_stmt,
                last_part, 
                module_path, 
                imported_entities, 
                entities_info,
                current_file_path,
                full_data,
                original_entity  
            )
            
        
def extract_from_path(import_statement: str) -> str:
    import_statement = import_statement.strip()
    
    if import_statement.startswith('from'):
        match = re.match(r'from\s+([.\w]+)\s+import\s+[\w.,\s]+(?:\s+as\s+\w+)?', import_statement)
        if not match:
            return None
        module_path = match.group(1).lstrip('.')
        return module_path.replace('.', '/')

    elif import_statement.startswith('import'):
        match = re.match(r'import\s+([.\w]+)(?:\s+as\s+\w+)?', import_statement)
        if not match:
            return None
        module_path = match.group(1).lstrip('.')
        return module_path.replace('.', '/')
    
    return None

def handle_from_import(import_stmt, current_file_path, imported_entities, entities_info, full_data):
  
    parts = import_stmt.split(" import ", 1)
    if len(parts) != 2:
        return
    
    module_part = parts[0][5:].strip()  
    entities_part = parts[1].strip()
    

    resolved_path = resolve_module_path(module_part, current_file_path)
    
  
    if entities_part == "*":
        handle_wildcard_import(
            resolved_path, 
            current_file_path, 
            imported_entities, 
            entities_info, 
            full_data
        )
        return None
   
    entities = [e.strip() for e in entities_part.split(',')]
    
    for entity in entities:
        if not entity:
            continue
            
        original_entity = entity
        alias = None
        
   
        if " as " in entity:
            original_entity, alias = [x.strip() for x in entity.split(" as ", 1)]
            
        possible_module_paths = [
            f"{resolved_path}/{original_entity}.py",  
            f"{resolved_path}/{original_entity}/__init__.py",
        ]
            
        module_file = None
        for path in possible_module_paths:
            if path in full_data:
                module_file = path
                break
             
        single_class_func = []
        single_var = []
        for f in full_data.keys():
            for c in full_data[f].get('classes', []):
                if c.get('name', '').startswith(f"{original_entity}@"):
                    single_class_func.append(c.get('name', ''))
                else:
                    continue
            for c in full_data[f].get('functions', []):
                if c.get('name', '').startswith(f"{original_entity}@"):
                    single_class_func.append(c.get('name', ''))
                else:
                    continue
            for c in full_data[f].get('variables', []):
                if isinstance(c, str) and c.startswith(f"{original_entity} =") or c.startswith(f"{original_entity}="):
                    single_var.append(c)
                else:
                    continue
        if len(single_class_func) + len(single_var) == 1:
            if len(single_class_func) == 1:
                imported_entities['class_func'].append(single_class_func[0])
            if len(single_var) == 1:
                imported_entities['variable'].append(single_var[0])
                 
        if not module_file:
            for file_path in full_data.keys():
                if file_path.startswith(f"{resolved_path}/{original_entity}"):
                    module_file = file_path
                    break

        if not module_file:
            file_paths = list(full_data.keys())
            extracted_path = extract_from_path(import_stmt)
            if extracted_path:  
                for file_path in file_paths:
                    if extracted_path + '/' + entity in file_path:
                        module_file = file_path
                        break
        

        if f"{resolved_path}/__init__.py" in full_data:
            m_f = f"{resolved_path}/__init__.py"
            file_info = full_data.get(m_f, {})
            candidate = f"{original_entity}@{resolved_path}/__init__.py"
            for class_info in file_info.get('classes', []):
                class_full_name = class_info.get('name', '')
                if class_full_name and candidate in class_full_name:
                    imported_entities['class_func'].append(class_full_name)
                    break
            for func_info in file_info.get('functions', []):
                func_full_name = func_info.get('name', '')
                if func_full_name and candidate in func_full_name:
                    imported_entities['class_func'].append(func_full_name)
                    break
            for var in file_info.get('variables', []):
                if isinstance(var, str) and var.startswith(original_entity):
                    imported_entities['variable'].append(var)
                    break
                
        if not module_file:
            a = f"{resolved_path}.py"
            if a in full_data:
                m_f = f"{resolved_path}.py"
                file_info = full_data.get(m_f, {})
                candidate = f"{original_entity}@{resolved_path}.py"
                for class_info in file_info.get('classes', []):
                    class_full_name = class_info.get('name', '')
                    if class_full_name and candidate in class_full_name:
                        imported_entities['class_func'].append(class_full_name)
                        break
                for func_info in file_info.get('functions', []):
                    func_full_name = func_info.get('name', '')
                    if func_full_name and candidate in func_full_name:
                        imported_entities['class_func'].append(func_full_name)
                        break
                for var in file_info.get('variables', []):
                    if isinstance(var, str) and var.startswith(original_entity):
                        imported_entities['variable'].append(var)
                        break
                imprt_statement = file_info.get('import_statements', {})
                all_imports = imprt_statement.get('project', []) + imprt_statement.get('third_party', [])
                for imp in all_imports:
                    if original_entity in imp:
                        path = resolve_module_path(imp, a)
                        ca = f"{original_entity}@{path}"
                        if path in full_data:
                            f_info = full_data.get(path,{})
                            for class_info in f_info.get('classes', []):
                                class_full_name = class_info.get('name', '')
                                if class_full_name and ca in class_full_name:
                                    imported_entities['class_func'].append(class_full_name)
                                    break
                            for func_info in f_info.get('functions', []):
                                func_full_name = func_info.get('name', '')
                                if func_full_name and ca in func_full_name:
                                    imported_entities['class_func'].append(func_full_name)
                                    break
                            for var in f_info.get('variables', []):
                                if isinstance(var, str) and var.startswith(original_entity):
                                    imported_entities['variable'].append(var)
                                    break
        
        if module_file:
            file_info = full_data.get(module_file, {})
            
            for class_info in file_info.get('classes', []):
                class_full_name = class_info.get('name', '')
                if class_full_name and class_full_name not in imported_entities['class_func']:
                    imported_entities['class_func'].append(class_full_name)
            
            for func_info in file_info.get('functions', []):
                func_full_name = func_info.get('name', '')
                if func_full_name and func_full_name not in imported_entities['class_func']:
                    imported_entities['class_func'].append(func_full_name)
            
            for var in file_info.get('variables', []):
                if isinstance(var, str) and var not in imported_entities['variable']:
                    imported_entities['variable'].append(var)
            return True
        
        else:
            classify_and_add_entity(
                import_stmt,
                original_entity, 
                resolved_path, 
                imported_entities, 
                entities_info,
                current_file_path,  
                full_data, 
                original_entity
            )
            


def handle_wildcard_import(module_path, current_file_path, imported_entities, entities_info, full_data):

    target_file = find_module_file(module_path, current_file_path, full_data)
    
    if not target_file:
        return
    
 
    file_info = full_data.get(target_file, {})
    

    for class_info in file_info.get('classes', []):
        class_full_name = class_info.get('name', '')
        if class_full_name and class_full_name not in imported_entities['class_func']:
            imported_entities['class_func'].append(class_full_name)
    

    for func_info in file_info.get('functions', []):
        func_full_name = func_info.get('name', '')
        if func_full_name and func_full_name not in imported_entities['class_func']:
            imported_entities['class_func'].append(func_full_name)
    

    for var_expr in file_info.get('variables', []):
        if isinstance(var_expr, str) and var_expr not in imported_entities['variable']:
            imported_entities['variable'].append(var_expr)

def find_module_file(module_path, current_file_path, full_data):

    path_parts = module_path.replace('.', '/')
     
    exact_path = f"{path_parts}.py"
    if exact_path in full_data:
        return exact_path
    

    for file_path in full_data.keys():
        if file_path.startswith(f"{path_parts}/__init__.py"):
            return file_path
    

    candidates = []
    for file_path in full_data.keys():

        if path_parts in file_path:
            candidates.append(file_path)
    

    if candidates:
        return min(candidates, key=len)
    
    return None

def classify_and_add_entity(import_stmt, entity_name, module_path, imported_entities, entities_info, current_file_path, full_data, original_entity,init = False):
    possible_module_paths = [
        f"{module_path}/{entity_name}.py",              
        f"{module_path}/{entity_name}/__init__.py" ,
        f"{entity_name}.py"   
    ]

    module_file = None
    for path in possible_module_paths:
        if path in full_data:
            module_file = path
            break

    
    if not module_file:
        entity_path_prefix = f"{module_path}/{entity_name}"
        for file_path in full_data:
            if file_path.startswith(entity_path_prefix):
                module_file = file_path
                break
   

    all_funcs = get_all_funcs(full_data)
    all_classes = get_all_classes(full_data)
    all_func_classes = all_funcs.union(all_classes)
    

    if not module_file:
        entity_func_class = entity_name + '@' + module_path + '.py'
        if entity_func_class in all_funcs or entity_func_class in all_classes:
            imported_entities['class_func'].append(entity_func_class)
            return
        
    if not module_file:
        entity_func_class = entity_name + '@' + module_path
        for c_f in all_func_classes:
            if entity_func_class in c_f:
                imported_entities['class_func'].append(c_f)
                return
            
    if not module_file:
        path = module_path + '.py'
        a = full_data.keys()
        if path in full_data:
            var = full_data[path].get("variables", [])
            for v in var:
                if v.startswith(entity_name + ' ') or v.startswith(entity_name + '='):
                    imported_entities["variable"].append(v)
                    return
        for i in a:
            if i.endswith(path):
                var = full_data[i].get("variables", [])
                for v in var:
                    if v.startswith(entity_name + ' ') or v.startswith(entity_name + '='):
                        imported_entities["variable"].append(v)
                        return
    
    key = full_data.keys()
             
    if module_file:
        file_info = full_data.get(module_file, {})
        
        for class_info in file_info.get('classes', []):
            class_full_name = class_info.get('name', '')
            if class_full_name and class_full_name not in imported_entities['class_func']:
                imported_entities['class_func'].append(class_full_name)
        
        for func_info in file_info.get('functions', []):
            func_full_name = func_info.get('name', '')
            if func_full_name and func_full_name not in imported_entities['class_func']:
                imported_entities['class_func'].append(func_full_name)
        
        for var in file_info.get('variables', []):
            if isinstance(var, str) and var not in imported_entities['variable']:
                imported_entities['variable'].append(var)
        return True
    
    if init == False:
        init_file_path = extract_from_path(import_stmt) + '/__init__.py'
        entity_path = extract_from_path(import_stmt) + '/' + original_entity

        
        if any(key.endswith(init_file_path) for key in full_data) and not any(path.startswith(entity_path) for path in full_data):
            for key in full_data:
                if key.endswith(init_file_path):
                    module_file = key
                    break
            
            init_file_info = full_data.get(module_file, {})
            entity_found = False
            
            for class_info in init_file_info.get('classes', []):
                class_name = class_info.get('name', '').split('@')[0] if '@' in class_info.get('name', '') else class_info.get('name', '')
                if class_name == original_entity:
                    imported_entities['class_func'].append(class_info.get('name', ''))
                    entity_found = True
            
            for func_info in init_file_info.get('functions', []):
                func_name = func_info.get('name', '').split('@')[0] if '@' in func_info.get('name', '') else func_info.get('name', '')
                if func_name == original_entity:
                    imported_entities['class_func'].append(func_info.get('name', ''))
                    entity_found = True
            
            for var in init_file_info.get('variables', []):
                if isinstance(var, str):
                    var_name = var.split('=')[0].strip() if '=' in var else var.strip()
                    if var_name == original_entity or var_name == f"__all__" and original_entity in var:
                        imported_entities['variable'].append(var)
                        entity_found = True
            
            if not entity_found:
                import_stmts = init_file_info.get('import_statements', {})
                all_imports = import_stmts.get('project', []) + import_stmts.get('third_party', [])
                
                for import_stmt in all_imports:
                    if original_entity in import_stmt:
                        temp_imported_entities = {'class_func': [], 'variable': []}
                        
                        init_file_path = extract_from_path(import_stmt) + '/' + extract_from_path(import_stmt) + '.py'
                        entity_path = extract_from_path(import_stmt) + '/' + original_entity
                        
                        if any(key.endswith(init_file_path) for key in full_data) and not any(path.startswith(entity_path) for path in full_data):
                            try:
                                process_import_statement(
                                    import_stmt,
                                    init_file_path,
                                    temp_imported_entities,
                                    entities_info,
                                    full_data,
                                    init = True
                                    )
                            except:
                                return
                        
                        imported_entities['class_func'].extend(temp_imported_entities['class_func'])
                        imported_entities['variable'].extend(temp_imported_entities['variable'])
                        entity_found = True
                        
            return entity_found
    else:
        init_file_path = extract_from_path(import_stmt) + '/' + extract_from_path(import_stmt) + '.py'
        entity_path = extract_from_path(import_stmt) + '/' + original_entity
        
        if any(key.endswith(init_file_path) for key in full_data) and not any(path.startswith(entity_path) for path in full_data):
            for key in full_data:
                if key.endswith(init_file_path):
                    module_file = key
                    break
            
            init_file_info = full_data.get(module_file, {})
            entity_found = False
            
            for class_info in init_file_info.get('classes', []):
                class_name = class_info.get('name', '').split('@')[0] if '@' in class_info.get('name', '') else class_info.get('name', '')
                if class_name == original_entity:
                    imported_entities['class_func'].append(class_info.get('name', ''))
                    entity_found = True
            
            for func_info in init_file_info.get('functions', []):
                func_name = func_info.get('name', '').split('@')[0] if '@' in func_info.get('name', '') else func_info.get('name', '')
                if func_name == original_entity:
                    imported_entities['class_func'].append(func_info.get('name', ''))
                    entity_found = True
            
            for var in init_file_info.get('variables', []):
                if isinstance(var, str):
                    var_name = var.split('=')[0].strip() if '=' in var else var.strip()
                    if var_name == original_entity or var_name == f"__all__" and original_entity in var:
                        imported_entities['variable'].append(var)
                        entity_found = True
            
            if not entity_found:
                import_stmts = init_file_info.get('import_statements', {})
                all_imports = import_stmts.get('project', []) + import_stmts.get('third_party', [])
                
                for import_stmt in all_imports:
                    if original_entity in import_stmt:
                        temp_imported_entities = {'class_func': [], 'variable': []}
                        process_import_statement(
                            import_stmt,
                            init_file_path,
                            temp_imported_entities,
                            entities_info,
                            full_data,
                            init = True
                        )
                    
                        imported_entities['class_func'].extend(temp_imported_entities['class_func'])
                        imported_entities['variable'].extend(temp_imported_entities['variable'])
                        entity_found = True
                        
            return entity_found







def resolve_module_path(module_path, current_file_path):
    if module_path.startswith('.'):
        dots_count = 0
        while dots_count < len(module_path) and module_path[dots_count] == '.':
            dots_count += 1

        module_path = module_path[dots_count:]

        path_parts = current_file_path.split('/')
        path_parts = path_parts[:-dots_count]

        base_path = '/'.join(path_parts)
        if module_path:
            return f"{base_path}/{module_path.replace('.', '/')}"
        else:
            return base_path

    else:
        return module_path.replace('.', '/')