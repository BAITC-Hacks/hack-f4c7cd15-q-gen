"""Validate the hackathon output contract against source node identifiers."""
import csv
import math
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.packages'))
import duckdb

ROLES = {'consolidator','transit','distributor','terminal','coordinator','peripheral'}
FIELDS = {
    'nodes_roles':{'gid','role','role_score','cluster_id','priority_score','evidence'},
    'clusters':{'cluster_id','n_nodes','n_seed','sum_kzt_internal','top_gids','hypothesis'},
    'top_nodes':{'rank','gid','role','priority_score','why'},
}


def validate(data,out):
    db=duckdb.connect()
    expected={r[0] for r in db.execute('SELECT gid FROM read_parquet(?)',[str(data/'nodes.parquet')]).fetchall()}
    db.close()
    tables={}
    for name,required in FIELDS.items():
        with (out/(name+'.csv')).open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            if not required.issubset(reader.fieldnames or []):
                raise ValueError(f'{name}: missing columns')
            tables[name]=list(reader)
        for row in tables[name]:
            if any(row[k] is None or not row[k].strip() for k in required):
                raise ValueError(f'{name}: empty required values')
    nodes=tables['nodes_roles']
    if len(nodes)!=len(expected) or {int(r['gid']) for r in nodes}!=expected:
        raise ValueError('Missing or duplicate nodes')
    for r in nodes:
        if r['role'] not in ROLES or len(r['evidence'])>200:
            raise ValueError('Invalid role or evidence')
        for field in ('role_score','priority_score'):
            if not math.isfinite(float(r[field])) or not 0<=float(r[field])<=1:
                raise ValueError(f'Invalid {field}')
    clusters=tables['clusters']
    membership={int(r['cluster_id']) for r in clusters}
    if len(membership)!=len(clusters):
        raise ValueError('Duplicate cluster ids')
    if {int(r['cluster_id']) for r in nodes}!=membership:
        raise ValueError('Cluster membership mismatch')
    for c in clusters:
        members=[n for n in nodes if n['cluster_id']==c['cluster_id']]
        if len(members)!=int(c['n_nodes']):
            raise ValueError('Cluster size mismatch')
    top=tables['top_nodes']
    if len(top)<min(20,len(expected)) or len({r['gid'] for r in top})!=len(top):
        raise ValueError('Insufficient or duplicate top nodes')
    scores=[float(r['priority_score']) for r in top]
    if scores!=sorted(scores,reverse=True):
        raise ValueError('Top list not ranked')
    lookup={r['gid']:r for r in nodes}
    for i,r in enumerate(top,1):
        n=lookup.get(r['gid'])
        if n is None or int(r['rank'])!=i or r['role']!=n['role'] or r['priority_score']!=n['priority_score']:
            raise ValueError('Top record inconsistent with node record')
    return {'nodes':len(nodes),'clusters':len(clusters),'top_nodes':len(top),'schema':'OK'}


if __name__=='__main__':
    print(validate(ROOT/'data',ROOT/'out'))

