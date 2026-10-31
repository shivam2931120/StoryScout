"""Execute a small offline identification benchmark; never call provider APIs."""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.config import ROOT, DEMO_FILES
from src.data_loader import load_catalog
from src.schemas import ConversationState
from src.conversation import StoryScoutEngine
from src.retrieval import RetrievalIndex
from src.identification import identify


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['tfidf','hybrid'],default='tfidf')
    args=parser.parse_args()
    dataset=json.loads((ROOT/'data/identification_queries.json').read_text())
    catalogs={m:load_catalog(DEMO_FILES[m],m) for m in ['book','movie']}
    indexes={m:RetrievalIndex(rows,args.mode) for m,rows in catalogs.items()}
    engine=StoryScoutEngine(catalogs,indexes,args.mode)
    rows=[]
    for query in dataset['queries']:
        _,results,_=identify(engine,query['query'],ConversationState(media_selection=query['media']))
        ranked=sorted([rec for group in results.values() for rec in group],key=lambda r:(-r.score,r.item.id))[:3]
        ids=[r.item.id for r in ranked]
        positions=[i+1 for i,item_id in enumerate(ids) if item_id in query['relevant_ids']]
        rows.append({**query,'returned_ids':ids,'top1_correct':bool(ids and ids[0] in query['relevant_ids']),'hit_at_3':bool(positions),'reciprocal_rank_at_3':1/min(positions) if positions else 0})
    result={'executed_at':datetime.now(timezone.utc).isoformat(),'requested_mode':args.mode,'active_modes':{m:i.active_mode for m,i in indexes.items()},'model_assistance':False,'query_count':len(rows),'judgment_method':dataset['judgment_method'],'limitations':dataset['limitations'],'top1_accuracy':sum(r['top1_correct'] for r in rows)/len(rows),'hit_at_3':sum(r['hit_at_3'] for r in rows)/len(rows),'mrr_at_3':sum(r['reciprocal_rank_at_3'] for r in rows)/len(rows),'rows':rows}
    out=ROOT/'artifacts/identification';out.mkdir(exist_ok=True)
    (out/f'{args.mode}.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))

if __name__=='__main__':main()
