import os
import sys
import glob

current_dir = os.path.dirname(__file__)
module_files = glob.glob(os.path.join(current_dir, "*.py"))
module_names = [os.path.basename(f)[:-3] for f in module_files if not f.endswith("__init__.py")]
for module_name in module_names:
    module = __import__(f"{__name__}.{module_name}", fromlist=["*"])
    classes = [getattr(module, x) for x in dir(module) if isinstance(getattr(module, x), type)]
    for cls in classes:
        setattr(sys.modules[__name__], cls.__name__, cls)