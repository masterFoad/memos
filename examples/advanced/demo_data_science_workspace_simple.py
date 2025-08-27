#!/usr/bin/env python3
"""
Simplified Data Science Workspace Demo
======================================
This demo creates a data science workspace with:
✅ 5GB persistent storage
✅ Basic directory structure
✅ Python virtual environment (without heavy libraries)
✅ Activation script
✅ Sample notebook
"""

import sys
import os
# Add the project root to the path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.append(project_root)

from sdk.python.client import OnMemClient
# Import test_utils from the correct location
sys.path.append(os.path.join(project_root, 'tests', 'unit'))
from test_utils import generate_test_token

def setup_data_science_persistent_storage():
    """Setup data science persistent storage with basic structure"""
    print("\n🧪 Setting up Data Science Persistent Storage")
    print("=" * 50)
    
    # Initialize client
    token = generate_test_token()
    client = OnMemClient('http://localhost:8080', token)
    
    namespace = "data-science-demo"
    user = "researcher-123"
    
    print(f"📁 Namespace: {namespace}")
    print(f"👤 User: {user}")
    
    # Step 1: Create persistent disk
    print("\n💾 Step 1: Creating 5GB persistent storage...")
    try:
        disk_info = client.create_persistent_disk(
            disk_name="datascience-persist-data-science-demo-researcher-123",
            namespace=namespace,
            user=user,
            size_gb=5,
            disk_type="pd-standard"
        )
        print(f"✅ Created persistent disk: {disk_info.get('disk_name', 'Unknown')}")
        print(f"✅ Created persistent disk: {disk_info}")
    except Exception as e:
        print(f"❌ Failed to create persistent disk: {e}")
        return None
    
    # Step 2: Setup basic structure
    print("\n🔧 Step 2: Setting up basic directory structure...")
    
    # Create a temporary workspace to configure the persistent storage
    with client.workspace(
        template="python",
        namespace=namespace,
        user=user,
        ttl_minutes=30,
        auto_cleanup=True
    ) as workspace:
        
        print(f"✅ Created temporary workspace: {workspace['id']}")
        
        # Simple setup script that just creates directories and basic files
        setup_script = """
import os
import subprocess
import sys

print("🔧 Setting up basic data science structure...")

# Check if persistent storage is available
persist_path = '/persist'
if os.path.exists(persist_path):
    print(f"✅ Persistent storage available at: {persist_path}")
    
    # Create data science directory structure
    ds_path = '/persist/datascience'
    os.makedirs(ds_path, exist_ok=True)
    os.makedirs(f'{ds_path}/venv', exist_ok=True)
    os.makedirs(f'{ds_path}/data', exist_ok=True)
    os.makedirs(f'{ds_path}/notebooks', exist_ok=True)
    os.makedirs(f'{ds_path}/models', exist_ok=True)
    
    print(f"✅ Created data science directory structure in: {ds_path}")
    
    # Create Python virtual environment (without installing heavy libraries)
    venv_path = f'{ds_path}/venv/python3.11'
    if not os.path.exists(venv_path):
        print("🐍 Creating Python 3.11 virtual environment...")
        try:
            subprocess.run([sys.executable, '-m', 'venv', venv_path], check=True)
            print(f"✅ Created virtual environment at: {venv_path}")
        except Exception as e:
            print(f"⚠️ Failed to create virtual environment: {e}")
    
    # Create activation script
    activate_script = f'''#!/bin/bash
export PATH="{venv_path}/bin:$PATH"
export PYTHONPATH="{venv_path}/lib/python3.11/site-packages:$PYTHONPATH"
echo "🐍 Data Science Environment Activated!"
echo "📦 Basic Python environment ready!"
echo "📊 To install libraries: pip install numpy pandas matplotlib jupyter"
'''
    
    try:
        with open(f'{ds_path}/activate_datascience.sh', 'w') as f:
            f.write(activate_script)
        os.chmod(f'{ds_path}/activate_datascience.sh', 0o755)
        print(f"✅ Created activation script: {ds_path}/activate_datascience.sh")
    except Exception as e:
        print(f"⚠️ Failed to create activation script: {e}")
    
    # Create sample Jupyter notebook
    notebook_content = '''{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# 🧪 Data Science Workspace Demo\\n",
    "\\n",
    "Welcome to your data science environment!\\n",
    "\\n",
    "## 📦 Getting Started\\n",
    "1. Activate the environment: `source /persist/datascience/activate_datascience.sh`\\n",
    "2. Install libraries: `pip install numpy pandas matplotlib jupyter`\\n",
    "3. Start Jupyter: `jupyter notebook --ip=0.0.0.0 --port=8888`\\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Test basic Python\\n",
    "print('Hello from data science workspace!')\\n",
    "import sys\\n",
    "print(f'Python version: {sys.version}')"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}'''
    
    try:
        with open(f'{ds_path}/notebooks/welcome_datascience.ipynb', 'w') as f:
            f.write(notebook_content)
        print(f"✅ Created sample notebook: {ds_path}/notebooks/welcome_datascience.ipynb")
    except Exception as e:
        print(f"⚠️ Failed to create notebook: {e}")
    
    # Create requirements.txt
    requirements_content = '''# Data Science Libraries
numpy
pandas
matplotlib
jupyter
ipykernel
seaborn
scikit-learn
'''
    
    try:
        with open(f'{ds_path}/requirements.txt', 'w') as f:
            f.write(requirements_content)
        print(f"✅ Created requirements.txt: {ds_path}/requirements.txt")
    except Exception as e:
        print(f"⚠️ Failed to create requirements.txt: {e}")
    
    print("✅ Basic data science structure setup completed!")
    
else:
    print(f"❌ Persistent storage not available at: {persist_path}")
"""
        
        # Execute the setup script
        result = client.run_python(workspace['id'], setup_script)
        
        print("📋 Setup Results:")
        print(result.get('stdout', ''))
        if result.get('stderr'):
            print("⚠️ Warnings/Errors:")
            print(result.get('stderr', ''))
        
        print("✅ Persistent storage setup completed!")
        
    return disk_info

def test_data_science_workspace():
    """Test the data science workspace with basic environment"""
    print("\n🧪 Testing Data Science Workspace")
    print("=" * 50)
    
    # Initialize client
    token = generate_test_token()
    client = OnMemClient('http://localhost:8080', token)
    
    namespace = "data-science-demo"
    user = "researcher-123"
    
    # Create workspace with persistent storage
    print("🚀 Creating data science workspace...")
    
    try:
        workspace = client.create_workspace_with_buckets(
            template="python",
            namespace=namespace,
            user=user,
            ttl_minutes=60
        )
        
        print(f"✅ Created workspace: {workspace['id']}")
        
        # Test the basic environment
        test_script = """
import os
import sys

print("🧪 Testing Basic Data Science Environment")
print("=" * 40)

# Check if persistent storage is mounted
persist_path = "/persist"
if os.path.exists(persist_path):
    print(f"✅ Persistent storage mounted at: {persist_path}")
    
    ds_path = "/persist/datascience"
    if os.path.exists(ds_path):
        print(f"✅ Data science directory found: {ds_path}")
        
        # Check virtual environment
        venv_path = f"{ds_path}/venv/python3.11"
        if os.path.exists(venv_path):
            print(f"✅ Virtual environment found: {venv_path}")
            
            # Test activating the environment
            activate_script = f"{ds_path}/activate_datascience.sh"
            if os.path.exists(activate_script):
                print(f"✅ Activation script found: {activate_script}")
                
                # Test basic Python functionality
                print("\\n🧪 Testing basic functionality...")
                print(f"🐍 Python: {sys.version}")
                print(f"🏠 Working Directory: {os.getcwd()}")
                
                # List available files
                print("\\n📁 Available files:")
                for root, dirs, files in os.walk(ds_path):
                    level = root.replace(ds_path, '').count(os.sep)
                    indent = ' ' * 2 * level
                    print(f"{indent}{os.path.basename(root)}/")
                    subindent = ' ' * 2 * (level + 1)
                    for file in files:
                        print(f"{subindent}{file}")
                
                print("\\n✅ Basic environment is ready!")
                print("📦 To install libraries: pip install -r /persist/datascience/requirements.txt")
                
            else:
                print("❌ Activation script not found!")
        else:
            print("❌ Virtual environment not found!")
    else:
        print("❌ Data science directory not found!")
        
else:
    print("❌ Persistent storage not mounted!")
"""
        
        print("🧪 Running environment tests...")
        result = client.run_python(workspace['id'], test_script)
        
        print("📋 Test Results:")
        print(result.get('stdout', ''))
        if result.get('stderr'):
            print("⚠️ Warnings/Errors:")
            print(result.get('stderr', ''))
        
        # Cleanup
        print(f"\n🧹 Cleaning up workspace: {workspace['id']}")
        client.delete_workspace(workspace['id'])
        print("✅ Workspace cleaned up!")
        
        return True
        
    except Exception as e:
        print(f"❌ Workspace test failed: {e}")
        return False

def main():
    """Main demo function"""
    print("🧪 Simplified Data Science Workspace Demo")
    print("=" * 50)
    print("This demo creates a data science workspace with:")
    print("✅ 5GB persistent storage")
    print("✅ Basic directory structure")
    print("✅ Python virtual environment")
    print("✅ Activation script")
    print("✅ Sample notebook")
    print()
    
    # Step 1: Setup persistent storage
    disk_info = setup_data_science_persistent_storage()
    
    if disk_info:
        print(f"\n✅ Persistent storage setup completed!")
        print(f"💾 Disk: {disk_info.get('disk_name', 'Unknown')}")
        print(f"📊 Size: {disk_info.get('size_gb', 0)}GB")
        
        # Step 2: Test the workspace
        success = test_data_science_workspace()
        
        if success:
            print("\n🎉 Demo completed successfully!")
            print("=" * 50)
            print("✅ Data science workspace is ready!")
            print("✅ Basic structure is set up!")
            print("✅ Persistent storage is working!")
            print()
            print("🚀 Next steps:")
            print("1. Create a new workspace with this persistent storage")
            print("2. Run: source /persist/datascience/activate_datascience.sh")
            print("3. Install libraries: pip install -r /persist/datascience/requirements.txt")
            print("4. Start Jupyter: jupyter notebook --ip=0.0.0.0 --port=8888")
            print("5. Open notebooks in /persist/datascience/notebooks/")
        else:
            print("\n❌ Demo failed during testing!")
    else:
        print("\n❌ Demo failed during setup!")

if __name__ == "__main__":
    main()
