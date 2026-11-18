"""
KiranaCopilot - Launch Script
Runs FastAPI backend serving the single-page React frontend.
Open http://127.0.0.1:8000 in your browser.
"""
import uvicorn
import os
import sys

if __name__ == "__main__":
    # Ensure project root is in sys.path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    print("\n" + "="*60)
    print("  🚀 Starting KiranaCopilot: StoreyStores")
    print("  🌐 Open in browser: http://127.0.0.1:8000")
    print("  🛠️  Live Agent Console active in right pane")
    print("="*60 + "\n")
    
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
