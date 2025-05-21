"""
LLM API handler for code completion functionality.
"""

import os
import requests
import json
from dotenv import load_dotenv

class LLMCompletionHandler:
    def __init__(self):
        # Load API key from .env file
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.api_url = "https://api.openai.com/v1/chat/completions"
        
        # Validate API key on initialization
        if not self.validate_api_key():
            print("Warning: Invalid or missing OpenAI API key in .env file")
    
    def validate_api_key(self):
        """Validate that the API key is set and correctly formatted."""
        if not self.api_key:
            return False
        if not self.api_key.startswith("sk-"):
            return False
        return True

    def generate_prompt(self, signature, docstring, relevant_methods):
        """Generate a prompt for the LLM using the signature, docstring, and relevant methods."""
        prompt = f"""You are an expert Python developer. Complete the following function based on its signature and docstring.
Also use the provided related functions as a reference for coding style and API usage.

FUNCTION TO COMPLETE:
```python
{signature}
{docstring}
    # Your implementation here
```

RELATED FUNCTIONS AND METHODS (ordered by relevance):
"""
        
        # Add top relevant methods to the prompt, grouped by type
        if relevant_methods:
            # Get top 10 most relevant methods
            top_methods = sorted(relevant_methods[:10], key=lambda m: m.get('relevance_score', 0), reverse=True)
            
            # Group methods by their type for better organization
            method_groups = {
                "In-file Method": [],
                "Outgoing Call": [],
                "Dependency": []
            }
            
            # Categorize methods
            for method in top_methods:
                ref_type = method.get("ref_type", "")
                if "file_method" in ref_type:
                    method_groups["In-file Method"].append(method)
                elif "outgoing_call" in ref_type:
                    method_groups["Outgoing Call"].append(method)
                elif "noise" in ref_type:
                    method_groups["Dependency"].append(method)
            
            # Add methods from each group
            for group_name, methods in method_groups.items():
                if methods:
                    prompt += f"\n{'-'*50}\n{group_name.upper()} REFERENCES:\n"
                    for i, method in enumerate(methods):
                        if "code" in method:
                            method_name = method.get('name', '').split(' (')[0]  # Get clean method name
                            file_path = method.get('file_path', 'unknown')
                            prompt += f"\n{'-'*30}\n{group_name} {i+1}: {method_name} (from {file_path}) - Relevance: {method.get('relevance_score', 'N/A'):.4f}\n```python\n{method['code']}\n```\n"
        else:
            prompt += "\nNo relevant methods found for reference. Please implement based on the signature and docstring only.\n"
        
        prompt += "\nPlease implement the function body for the given signature and docstring, following the style of the related functions. Your code should be compatible with the existing codebase as shown in the references."
        prompt += "\nReturn ONLY the complete function code without explanations. The function should include proper error handling and follow best practices."
        
        return prompt

    def call_llm_api(self, prompt, model="gpt-4-turbo"):
        """Call the LLM API to generate code completion."""
        if not self.validate_api_key():
            return {"success": False, "error": "OpenAI API key is invalid or missing in .env file. Please add OPENAI_API_KEY=your_key to your .env file."}
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are an expert Python developer assistant specialized in code completion. Focus on generating high-quality, maintainable code that matches the style of the provided examples."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,  # Lower temperature for more deterministic code generation
                "max_tokens": 2000
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                code = result["choices"][0]["message"]["content"]
                return {"success": True, "code": code}
            else:
                error_info = response.json() if response.content else {"error": f"Status code: {response.status_code}"}
                return {"success": False, "error": error_info}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def extract_code_block(self, text):
        """Extract the code block from the LLM response."""
        if "```python" in text:
            start = text.find("```python") + 9
            end = text.find("```", start)
            if start > 0 and end > start:
                return text[start:end].strip()
        
        # If no python code block, try finding any code block
        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if start > 0 and end > start:
                return text[start:end].strip()
            
        # Return the whole text if no code block markers found
        return text.strip()
    
    def complete_function(self, signature, docstring, relevant_methods):
        """Complete a function based on signature, docstring and relevant methods."""
        # Ensure we have valid input
        if not signature or not signature.strip():
            return {"success": False, "error": "Function signature is empty"}

        try:
            # Count methods by type for analytics
            method_counts = {
                "in_file": 0,
                "outgoing_calls": 0,
                "dependencies": 0
            }
            
            if relevant_methods:
                for method in relevant_methods:
                    ref_type = method.get("ref_type", "")
                    if "file_method" in ref_type:
                        method_counts["in_file"] += 1
                    elif "outgoing_call" in ref_type:
                        method_counts["outgoing_calls"] += 1
                    elif "noise" in ref_type:
                        method_counts["dependencies"] += 1
            
            # Generate prompt with enhanced context
            prompt = self.generate_prompt(signature, docstring, relevant_methods)
            
            # Call LLM API with contextual information
            response = self.call_llm_api(prompt)
            
            if response.get("success", False):
                code = self.extract_code_block(response["code"])
                
                # Extract function name from signature for validation
                func_name = ""
                if "def " in signature:
                    func_name = signature.split("def ")[1].split("(")[0].strip()
                
                # Basic validation that the code returned includes the function definition
                if func_name and (f"def {func_name}" not in code):
                    # Try to fix the code by adding function signature
                    code = f"{signature}\n{code}" if not code.startswith(signature) else code
                
                result = {
                    "success": True, 
                    "code": code,
                    "context": {
                        "in_file_methods": method_counts["in_file"],
                        "outgoing_calls": method_counts["outgoing_calls"],
                        "dependencies": method_counts["dependencies"]
                    }
                }
                
                return result
            else:
                error_msg = response.get("error", "Unknown error")
                if isinstance(error_msg, dict) and "error" in error_msg:
                    error_msg = error_msg["error"].get("message", str(error_msg))
                    
                return {
                    "success": False, 
                    "error": f"Failed to generate code: {error_msg}",
                    "context": method_counts
                }
                
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            return {
                "success": False, 
                "error": f"Exception during code generation: {str(e)}",
                "traceback": error_trace
            } 