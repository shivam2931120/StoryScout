"""Executed ablation: same catalog/model/filters, whole-document vs passages.

Includes the existing broad benchmark plus source-checked focal-detail queries.
No independent human judgments or universal accuracy claims.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.evaluate import evaluate_mode
from src.data_loader import load_active_catalogs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',default='artifacts/passages')
    args=parser.parse_args()
    catalogs=load_active_catalogs()
    focal=json.loads((ROOT/'data/passage_evaluation.json').read_text())
    broad=json.loads((ROOT/'data/evaluation_queries.json').read_text())
    available={item.id for group in catalogs.values() for item in group}
    if any(item_id not in available for row in focal['queries'] for item_id in row['relevant_ids']):
        raise ValueError('A focal query target is not in the active catalog')
    output={'executed_at':datetime.now(timezone.utc).isoformat(),'catalog':{key:len(items) for key,items in catalogs.items()},
            'method':'Within-run ablation; identical data, encoder, query-cache reset and hard filters. Only passage_matching differs.',
            'judgment_method':focal['judgment_method'],'limitations':focal['limitations'],
            'broad_query_count':len(broad),'focal_query_count':len(focal['queries']),'results':{}}
    previous=os.environ.get('STORYSCOUT_PASSAGE_MATCHING')
    try:
        for enabled in [False,True]:
            os.environ['STORYSCOUT_PASSAGE_MATCHING']='true' if enabled else 'false'
            name='passages' if enabled else 'whole_document'
            output['results'][name]={}
            for mode in ['tfidf','semantic','hybrid']:
                metrics,rows=evaluate_mode(mode,catalogs,broad+focal['queries'])
                # Recompute domain means by benchmark, using the returned per-query data.
                from scripts.evaluate import aggregate_rows
                broad_rows=rows[:sum(2 if row['media']=='both' else 1 for row in broad)]
                focal_rows=rows[len(broad_rows):]
                split={}
                for benchmark,details in [('broad',broad_rows),('focal',focal_rows)]:
                    split[benchmark]={domain:aggregate_rows([row for row in details if row['domain']==domain]) for domain in ['book','movie'] if any(row['domain']==domain for row in details)}
                output['results'][name][mode]={'run':metrics,'by_benchmark':split,'queries':rows}
                print(name,mode,split,flush=True)
    finally:
        if previous is None:os.environ.pop('STORYSCOUT_PASSAGE_MATCHING',None)
        else:os.environ['STORYSCOUT_PASSAGE_MATCHING']=previous
    directory=ROOT/args.output_dir;directory.mkdir(parents=True,exist_ok=True)
    (directory/'comparison.json').write_text(json.dumps(output,indent=2)+'\n')
    lines=['# Passage retrieval ablation','',output['method'],'',output['judgment_method'],'',output['limitations'],'',
           '| Method | Passages | Benchmark/domain | P@5 | Recall@5 | MRR@5 | Returned precision | Hard compliance |','|---|---|---|---:|---:|---:|---:|---:|']
    for name,modes in output['results'].items():
        for mode,data in modes.items():
            for benchmark,domains in data['by_benchmark'].items():
                for domain,m in domains.items():
                    lines.append(f"| {mode} | {name} | {benchmark}/{domain} | {m['precision_at_5']} | {m['recall_at_5']} | {m['mrr_at_5']} | {m['precision_when_returned']} | {m['hard_constraint_compliance']} |")
    (directory/'summary.md').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':main()
