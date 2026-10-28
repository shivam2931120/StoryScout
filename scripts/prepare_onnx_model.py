"""Cache the official Apache-2.0 MiniLM quantized export at a pinned revision."""
from pathlib import Path
import hashlib,json,sys,urllib.request
ROOT=Path(__file__).resolve().parents[1]
REVISION='1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
DIRECTORY=ROOT/'artifacts/.cache/onnx_minilm'

def prepare():
    DIRECTORY.mkdir(parents=True,exist_ok=True)
    files={'model.onnx':'onnx/model_quint8_avx2.onnx','tokenizer.json':'tokenizer.json'}
    manifest={'model':'sentence-transformers/all-MiniLM-L6-v2','revision':REVISION,'quantization':'official quint8 AVX2 ONNX export','license':'Apache-2.0','files':{}}
    for target,source in files.items():
        path=DIRECTORY/target
        if not path.exists():
            url=f'https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/{REVISION}/{source}'
            temporary=path.with_suffix('.tmp')
            urllib.request.urlretrieve(url,temporary)
            temporary.replace(path)
        manifest['files'][target]={'source_path':source,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (DIRECTORY/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('Quantized MiniLM cached locally:',DIRECTORY,flush=True)

if __name__=='__main__':prepare()
