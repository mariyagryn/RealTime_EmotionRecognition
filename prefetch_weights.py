import os, shutil, glob
import numpy as np
from deepface import DeepFace

_ = DeepFace.analyze(np.zeros((224,224,3), dtype=np.uint8), actions=['emotion'],
                     enforce_detection=False, detector_backend='opencv', silent=True)

cache = os.path.expanduser("~/.deepface/weights")
print("DeepFace weights cache:", cache)
files = glob.glob(os.path.join(cache, "*"))
for f in files:
    print(" -", os.path.basename(f))

dst = "models/weights"
os.makedirs(dst, exist_ok=True)
for f in files:
    shutil.copy2(f, os.path.join(dst, os.path.basename(f)))
print("\nCopied weights to:", dst, "(add 'models/' to .gitignore to avoid committing)")
