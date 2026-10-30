"""python3 -I run_all.py <model.fbx>  (run inside this folder; needs numpy, scipy, Pillow)
Extracts textures + skeleton/animations from the FBX, then builds out/axolotl.axm"""
import sys, io, os, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fbxparse, axextract
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
os.makedirs('tex', exist_ok=True); os.makedirs('out', exist_ok=True)
_, root = fbxparse.parse(sys.argv[1])
for c in root.first('Objects').children:
    if c.name == 'Video':
        open('tex/' + c.props[1].split('\x00')[0], 'wb').write(c.first('Content').props[0])
pickle.dump(axextract.extract(sys.argv[1]), open('extract.pkl', 'wb'))
sys.argv = ['build_model.py']
exec(open('build_model.py').read())
