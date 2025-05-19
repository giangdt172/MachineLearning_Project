import json


def filter_repositories(data):

    error_files = []
    filtered_data = data.copy()
    
    for file_path, file_info in data.items():
        third_party_info = file_info["import_statements"].get("third_party", [])
        if third_party_info and third_party_info[0].startswith("Error: "):
            error_files.append(file_path)
            filtered_data.pop(file_path)
    
    files_to_remove = set()
    
    for file_path, file_info in filtered_data.items():
        for func in file_info["functions"]:
            if any(out.split("@")[-1] in error_files for out in func["outgoing_calls"]):
                files_to_remove.add(file_path)
                break
        
        if file_path not in files_to_remove:
            for cls in file_info["classes"]:
                if any(out.split("@")[-1] in error_files for method in cls["methods"] 
                       for out in method["outgoing_calls"]):
                    files_to_remove.add(file_path)
                    break
    

    return {file_path: filtered_data[file_path] for file_path in filtered_data if file_path not in files_to_remove}




        