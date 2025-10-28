import io, os, zipfile

def zip_bytes(dir_path, skip=None):
    skip=set(skip or [])
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
        for r,_,fs in os.walk(dir_path):
            for f in fs:
                p=os.path.join(r,f); rel=os.path.relpath(p,dir_path)
                if any(rel.startswith(s) for s in skip): continue
                z.write(p, rel)
    b.seek(0); return b.read()
