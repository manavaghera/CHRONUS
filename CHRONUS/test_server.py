import sys
sys.path.insert(0, r"C:\Users\manav\OneDrive\Desktop\CHRONUS DB\CHRONUS")
print("1: importing api_server...", flush=True)
try:
    import api_server
    print("2: api_server OK", flush=True)
except Exception as e:
    print(f"ERROR: {e}", flush=True)
    import traceback
    traceback.print_exc()
