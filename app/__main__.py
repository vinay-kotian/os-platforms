"""
Entry point for running the app package as a module: python3 -m app
This redirects to the main app.py file in the parent directory
"""
import sys
import os
import runpy

if __name__ == '__main__':
    # Get the parent directory (where app.py is located)
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app_py_path = os.path.join(parent_dir, 'app.py')
    
    if not os.path.exists(app_py_path):
        print("Error: app.py not found in parent directory")
        print(f"Expected at: {app_py_path}")
        sys.exit(1)
    
    # Change to parent directory and run app.py
    original_dir = os.getcwd()
    try:
        os.chdir(parent_dir)
        # Execute app.py as a script
        runpy.run_path('app.py', run_name='__main__')
    finally:
        os.chdir(original_dir)

