# Builds porterino.zip, the file you pick in Blender's "Install from Disk".   python make_zip.py
import os
import zipfile

here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, "porterino.zip")
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for name in sorted(os.listdir(os.path.join(here, "porterino"))):
        if name.endswith(".py"):
            z.write(os.path.join(here, "porterino", name), "porterino/" + name)
print("wrote", out)
