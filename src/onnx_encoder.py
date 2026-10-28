"""Low-memory CPU inference for the original MiniLM sentence encoder.

The official quantized ONNX export uses the original tokenizer, masked mean
pooling and L2 normalization. No external inference API or PyTorch import.
"""
from pathlib import Path
import numpy as np
from .config import ARTIFACT_DIR


class QuantizedMiniLM:
    def __init__(self, directory: Path | None = None):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        directory=directory or ARTIFACT_DIR/'.cache/onnx_minilm'
        options=ort.SessionOptions()
        options.intra_op_num_threads=1
        options.inter_op_num_threads=1
        options.enable_cpu_mem_arena=False
        options.enable_mem_pattern=False
        self.session=ort.InferenceSession(str(directory/'model.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
        self.tokenizer=Tokenizer.from_file(str(directory/'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=256)
        self.tokenizer.enable_padding(pad_id=0,pad_token='[PAD]')
        self.inputs={x.name for x in self.session.get_inputs()}

    def encode(self,texts,batch_size=8,normalize_embeddings=True,**kwargs):
        vectors=[]
        for start in range(0,len(texts),min(batch_size,8)):
            encoded=self.tokenizer.encode_batch(list(texts[start:start+min(batch_size,8)]))
            mask=np.asarray([x.attention_mask for x in encoded],dtype=np.int64)
            feeds={'input_ids':np.asarray([x.ids for x in encoded],dtype=np.int64),'attention_mask':mask,
                   'token_type_ids':np.asarray([x.type_ids for x in encoded],dtype=np.int64)}
            tokens=self.session.run(None,{k:v for k,v in feeds.items() if k in self.inputs})[0]
            weights=mask.astype(np.float32)
            pooled=(tokens*weights[:,:,None]).sum(axis=1)/np.maximum(weights.sum(axis=1,keepdims=True),1)
            if normalize_embeddings:pooled/=np.maximum(np.linalg.norm(pooled,axis=1,keepdims=True),1e-9)
            vectors.append(pooled.astype(np.float32))
        return np.concatenate(vectors) if vectors else np.empty((0,384),dtype=np.float32)
