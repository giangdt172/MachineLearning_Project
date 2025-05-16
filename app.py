import gradio as gr
import os
import tempfile
import zipfile
import shutil
import json
from MachineLearning_Project.parse_repo import process_repo  # Import process_repo directly

# Define data folder paths
DATA_FOLDER = "data"
PROCESSED_REPO_PATH = os.path.join(DATA_FOLDER, "processed_repositories")

def process_uploaded_repository(repo_file):
    """Process an uploaded repository and save its structure"""
    if repo_file is None:
        return "Please upload a repository ZIP file first.", ""
    
    # Create data directories if they don't exist
    os.makedirs(DATA_FOLDER, exist_ok=True)
    os.makedirs(PROCESSED_REPO_PATH, exist_ok=True)
    
    # Extract the repository to a temporary directory
    temp_dir = tempfile.mkdtemp()
    repo_name = os.path.splitext(os.path.basename(repo_file.name))[0]
    
    try:
        with zipfile.ZipFile(repo_file.name, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Process the repository using process_repo
        processed_data = process_repo(temp_dir)
        
        if processed_data is None:
            return f"Repository {repo_name} does not meet processing criteria.", ""
        
        # Save the processed data to the data folder
        output_file = os.path.join(PROCESSED_REPO_PATH, f"{repo_name}.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(processed_data, f, ensure_ascii=False, indent=4)
        
        # Extract repository structure overview
        file_count = len(processed_data.keys())
        func_count = sum(len(f.get("functions", [])) for f in processed_data.values())
        class_count = sum(len(f.get("classes", [])) for f in processed_data.values())
        
        # Get import summary
        import_statements = set()
        for file_data in processed_data.values():
            if "import_statements" in file_data:
                for third_party in file_data["import_statements"]["third_party"]:
                    import_statements.add(third_party)
        
        summary = f"""
Repository '{repo_name}' successfully processed and saved to {output_file}

Structure Overview:
- {file_count} Python files processed
- {func_count} functions found
- {class_count} classes found
- {len(import_statements)} unique third-party imports
"""
        return "Processing complete!", summary
    
    except Exception as e:
        return f"Error processing repository: {str(e)}", ""
    finally:
        # Clean up
        shutil.rmtree(temp_dir)


# Build the Gradio interface
with gr.Blocks() as app:
    gr.Markdown("# Python Repository Processor")
    gr.Markdown("Upload a Python repository ZIP file to analyze and extract its structure.")
    
    with gr.Row():
        with gr.Column():
            # Step 1: Upload repository
            repo_file = gr.File(label="Upload Repository (ZIP file)")
            process_btn = gr.Button("Process Repository", variant="primary")
            
        with gr.Column():
            # Results area
            status_text = gr.Textbox(label="Status", placeholder="Upload a repository to begin...", interactive=False)
            repo_info = gr.Textbox(label="Repository Information", placeholder="Repository details will appear here...", 
                                  lines=10, interactive=False)
    
    # Event handler for processing repository
    process_btn.click(
        process_uploaded_repository, 
        inputs=repo_file, 
        outputs=[status_text, repo_info]
    )

# Launch the app
if __name__ == "__main__":
    app.launch()

if __name__ == "__main__":
    app.launch()
