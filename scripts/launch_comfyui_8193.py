# Launch a dedicated ComfyUI instance on port 8193 for the H3 replica pipeline.
# Adjust TORCH / COMFY / OUT / IN to your machine before use.
import sys, os, runpy

TORCH = r'G:/path/to/torch-overlay'   # torch cu130 overlay dir (must contain torch/)
COMFY = r'G:/comfyui'                  # ComfyUI >= 0.44.0 checkout
OUT   = r'G:/path/to/gen/output'       # generation outputs
IN    = r'G:/path/to/gen/input'        # segment windows + P3 reference crops

sys.path.insert(0, TORCH)
sys.path.insert(0, COMFY)
os.chdir(COMFY)
sys.argv = [
    COMFY + '/main.py',
    '--listen', '127.0.0.1', '--port', '8193',
    '--disable-auto-launch',
    '--disable-mmap',             # avoids 0xC0000005 when loading the qwen3vl encoder with CUDA active
    '--reserve-vram', '11',
    '--disable-cuda-malloc',
    '--use-pytorch-cross-attention',
    '--output-directory', OUT,
    '--input-directory', IN,
]
runpy.run_path(COMFY + '/main.py', run_name='__main__')
