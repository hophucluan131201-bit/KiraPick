"""Offline, read-only hardware diagnostic for KiraPick on Windows.
No network access, no file modifications. Uses optional torch / onnxruntime.
"""
import sys
import platform
import subprocess
import importlib.util

print('KiraPick | Offline GPU diagnostics')
print('OS:', platform.platform())
print('Python:', sys.version.split()[0])

try:
    res = subprocess.run(
        ['nvidia-smi', '--query-gpu=name,memory.total,memory.free,driver_version,temperature.gpu',
         '--format=csv,noheader'],
        capture_output=True, text=True, timeout=10, check=False,
    )
    print('NVIDIA GPU (name, total/free memory, driver, temperature):')
    print(res.stdout.strip() or res.stderr.strip() or 'Not available')
except (OSError, subprocess.TimeoutExpired) as exc:
    print('NVIDIA-SMI: unavailable -', exc)

if importlib.util.find_spec('torch'):
    try:
        import torch
        print('PyTorch:', torch.__version__)
        print('PyTorch CUDA runtime:', torch.version.cuda)
        print('CUDA available:', torch.cuda.is_available())
        if torch.cuda.is_available():
            print('GPU name:', torch.cuda.get_device_name(0))
            print('Compute capability:', torch.cuda.get_device_capability(0))
            free, total = torch.cuda.mem_get_info(0)
            print('GPU free/total (MiB):', round(free/1048576), '/', round(total/1048576))
    except Exception as exc:
        print('PyTorch CUDA probe failed:', type(exc).__name__, str(exc))
else:
    print('PyTorch not installed (optional).')

if importlib.util.find_spec('onnxruntime'):
    try:
        import onnxruntime as ort
        print('ONNX Runtime:', ort.__version__)
        print('Providers:', ', '.join(ort.get_available_providers()))
        print('Note: Provider listed does not prove model inference works.')
    except Exception as exc:
        print('ONNX Runtime probe failed:', type(exc).__name__, str(exc))
else:
    print('ONNX Runtime not installed (optional).')
