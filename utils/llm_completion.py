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
        
        # Add top relevant methods to the prompt
        for i, method in enumerate(relevant_methods[:5]):  # Use top 5 most relevant methods
            if "code" in method:
                prompt += f"\n{'-'*50}\nRELATED FUNCTION {i+1} (Relevance: {method.get('relevance_score', 'N/A')}):\n```python\n{method['code']}\n```\n"
        
        prompt += "\nPlease implement the function body for the given signature and docstring, following the style of the related functions. Return ONLY the complete function code."
        
        return prompt

    def call_llm_api(self, prompt, model="gpt-4.1-nano"):
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
                    {"role": "system", "content": "You are an expert Python developer assistant."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,  # Lower temperature for more deterministic code generation
                "max_tokens": 1500
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
        prompt = self.generate_prompt(signature, docstring, relevant_methods)
        response = self.call_llm_api(prompt)
        
        if response.get("success", False):
            code = self.extract_code_block(response["code"])
            return {"success": True, "code": code}
        else:
            return {"success": False, "error": response.get("error", "Unknown error")} 