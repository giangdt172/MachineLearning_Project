"""
Python Repository Processing Application.
This app allows you to analyze Python repositories and extract function signatures and docstrings.
"""

# Import from our modules
from utils.ui_components import create_application

# Create and launch the app
if __name__ == "__main__":
    app = create_application()
    app.launch(share=True) 