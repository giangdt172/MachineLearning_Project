import os
import json
import shutil  
import stat
from .parse_repo import process_repo  

# RAW_REPO_PATH = "../data/raw_repositories"
# PROCESSED_REPO_PATH = "../data/temp/processed_repositories"
# AGGREGATED_FILE = "../data/processed_repo.json"
RAW_REPO_PATH = "data/test-apps"
PROCESSED_REPO_PATH = "data/final/enhanced_data/test-apps"
AGGREGATED_FILE = "/data/processed_repo.json"

os.makedirs(PROCESSED_REPO_PATH, exist_ok=True)

def contains_py(dir_path):
    for root, dirs, files in os.walk(dir_path):
        for f in files:
            if f.lower().endswith('.py'):
                return True
    return False

def safe_remove(file_path):
    file_path = os.path.relpath(file_path).replace('\\', '/')
   
    try:
        os.remove(file_path)
    except PermissionError:
        os.chmod(file_path, stat.S_IWRITE)
        os.remove(file_path)

def safe_rmdir(dir_path):
    try:
        os.rmdir(dir_path)
    except PermissionError:
        os.chmod(dir_path, stat.S_IWRITE)
        os.rmdir(dir_path)

def safe_rmtree(dir_path):
    try:
        shutil.rmtree(dir_path)
    except PermissionError:
        os.chmod(dir_path, stat.S_IWRITE)
        shutil.rmtree(dir_path)

def clean_non_python_files(repo_path):
    for root, dirs, files in os.walk(repo_path, topdown=False):
        for f in files:
            if not f.lower().endswith(".py"):
                file_path = os.path.join(root, f)
                safe_remove(file_path)
        for d in dirs:
            d_path = os.path.join(root, d)
            if not os.listdir(d_path):
                safe_rmdir(d_path)
    
    for root, dirs, files in os.walk(repo_path, topdown=False):
        for d in dirs:
            d_path = os.path.join(root, d)
            if not contains_py(d_path):
                safe_rmtree(d_path)

def process_all_repositories():
    for repo_name in os.listdir(RAW_REPO_PATH):
        repo_path = os.path.join(RAW_REPO_PATH, repo_name)
        
        if os.path.isdir(repo_path):  
            print(f"Processing repository: {repo_name}...")
            clean_non_python_files(repo_path)
            try:
                processed_data = process_repo(repo_path)
                
                if processed_data is None or not processed_data:
                    print(f"No data processed for {repo_name}, skipping...")
                    safe_rmtree(repo_path)
                    print(f"Deleted repository folder: {repo_path}")
                    continue
                
                output_file = os.path.join(PROCESSED_REPO_PATH, f"{repo_name}.json")
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(processed_data, f, ensure_ascii=False, indent=4)
                print(f"Saved processed data to {output_file}")
                safe_rmtree(repo_path)
                print(f"Deleted repository folder: {repo_path}")
            except Exception as e:
                print(f"Error processing repository {repo_name}: {e}")
                print("Skipping deletion of repository folder.")

def merge_json_files():
    aggregated_data = {}
    for file_name in os.listdir(PROCESSED_REPO_PATH):
        if file_name.endswith(".json"):
            file_path = os.path.join(PROCESSED_REPO_PATH, file_name)
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if data is None or not data:
                print(f"Skipping empty data in {file_name}")
                continue
                
            repo_key = os.path.splitext(file_name)[0]
            aggregated_data[repo_key] = data

    with open(AGGREGATED_FILE, "w", encoding="utf-8") as f:
        json.dump(aggregated_data, f, ensure_ascii=False, indent=4)
    print(f"Aggregated JSON saved to {AGGREGATED_FILE}")

if __name__ == "__main__":
    try:
        process_all_repositories()
    except Exception as e:
        print(f"Error during processing repositories: {e}")
    # else:
    #     merge_json_files()
