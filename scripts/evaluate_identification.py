"""Execute catalog-backed plot-identification evaluation; never call provider APIs."""
import argparse
import json
import sys
import math
import random
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.config import ROOT
from src.data_loader import load_active_catalogs
from src.schemas import ConversationState
from src.conversation import StoryScoutEngine
from src.retrieval import RetrievalIndex
from src.identification import identify


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['tfidf','semantic','hybrid'],default='hybrid')
    parser.add_argument('--output',default=None)
    args=parser.parse_args()
    dataset=json.loads((ROOT/'data/identification_queries.json').read_text())
    focal=json.loads((ROOT/'data/passage_evaluation.json').read_text())
    queries=[{**row,'category':row.get('category','broad_plot')} for row in dataset['queries']]
    queries += [{**row,'category':'focal_detail'} for row in focal['queries']]
    catalogs=load_active_catalogs()
    ids={item.id for items in catalogs.values() for item in items}
    missing=sorted({item_id for row in queries for item_id in row['relevant_ids']} - ids)
    if missing:
        raise SystemExit('Evaluation targets absent from active catalog: '+', '.join(missing))
    indexes={m:RetrievalIndex(rows,args.mode) for m,rows in catalogs.items()}
    engine=StoryScoutEngine(catalogs,indexes,args.mode)
    rows=[]
    for query in queries:
        _,results,_=identify(engine,query['query'],ConversationState(media_selection=query['media']))
        ranked=sorted([rec for group in results.values() for rec in group],key=lambda r:(-r.score,r.item.id))[:5]
        returned_ids=[r.item.id for r in ranked]
        relevant=set(query['relevant_ids'])
        positions=[i+1 for i,item_id in enumerate(returned_ids) if item_id in relevant]
        dcg=sum(1/math.log2(rank+1) for rank,item_id in enumerate(returned_ids,1) if item_id in relevant)
        ideal=sum(1/math.log2(rank+1) for rank in range(1,min(len(relevant),len(returned_ids))+1))
        rows.append({**query,'returned_ids':returned_ids,'top1_correct':bool(returned_ids and returned_ids[0] in relevant),
                     'hit_at_3':bool(any(rank<=3 for rank in positions)),
                     'reciprocal_rank_at_5':1/min(positions) if positions else 0,
                     'recall_at_5':sum(item_id in relevant for item_id in returned_ids)/len(relevant),
                     'ndcg_at_5':dcg/ideal if ideal else 0.0,
                     'target_count':len(relevant),'target_coverage':sum(item_id in ids for item_id in relevant)/len(relevant)})
    rng=random.Random(20261031)
    def interval(key):
        if len(rows)<2:return None
        samples=sorted(sum(rows[rng.randrange(len(rows))][key] for _ in rows)/len(rows) for _ in range(2000))
        return [round(samples[int((len(samples)-1)*.025)],4),round(samples[int((len(samples)-1)*.975)],4)]
    def summarize(values):
        if not values:return {'queries':0}
        return {'queries':len(values),'top1_accuracy':round(sum(r['top1_correct'] for r in values)/len(values),4),
                'hit_at_3':round(sum(r['hit_at_3'] for r in values)/len(values),4),
                'mrr_at_5':round(sum(r['reciprocal_rank_at_5'] for r in values)/len(values),4),
                'recall_at_5':round(sum(r['recall_at_5'] for r in values)/len(values),4),
                'ndcg_at_5':round(sum(r['ndcg_at_5'] for r in values)/len(values),4)}
    categories=sorted({row.get('category','uncategorized') for row in rows})
    result={'executed_at':datetime.now(timezone.utc).isoformat(),'requested_mode':args.mode,
            'active_modes':{m:i.active_mode for m,i in indexes.items()},'model_assistance':False,
            'catalog_profile':__import__('os').getenv('STORYSCOUT_CATALOG_PROFILE','full'),
            'catalog_size':{m:len(items) for m,items in catalogs.items()},'query_count':len(rows),
            'category_counts':{c:sum(row.get('category','uncategorized')==c for row in rows) for c in categories},
            'judgment_method':dataset['judgment_method']+' '+focal['judgment_method'],
            'limitations':dataset['limitations']+' '+focal['limitations'],
            'target_coverage':round(sum(row['target_coverage'] for row in rows)/len(rows),4),
            'overall':summarize(rows),'by_category':{c:summarize([r for r in rows if r.get('category','uncategorized')==c]) for c in categories},
            'bootstrap_95_percent_ci':{metric:interval(metric) for metric in ['top1_correct','hit_at_3','reciprocal_rank_at_5','recall_at_5','ndcg_at_5']},
            'bootstrap_note':'Percentile bootstrap over query cases (2,000 resamples; fixed seed); interval describes this curated query set only.',
            'rows':rows}
    out=Path(args.output) if args.output else ROOT/'artifacts/identification'/f'{args.mode}.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))

if __name__=='__main__':main()
