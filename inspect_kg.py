# inspect_kg.py
import pickle, argparse, os
from collections import Counter
from google.cloud import storage

def download_gcs(gs_uri, out):
    assert gs_uri.startswith("gs://")
    parts = gs_uri[5:].split("/",1)
    bucket = parts[0]; blob = parts[1]
    client = storage.Client()
    b = client.bucket(bucket)
    b.blob(blob).download_to_filename(out)
    return out

def load_kg(path):
    with open(path,'rb') as f:
        return pickle.load(f)

def main():
    import networkx as nx
    p = argparse.ArgumentParser()
    p.add_argument("--gcs-uri", type=str, default=None)
    p.add_argument("--local-kg", type=str, default=None)
    p.add_argument("--out", type=str, default="kg_inspect.pkl")
    args = p.parse_args()
    if args.gcs_uri:
        local = args.out
        print("Downloading", args.gcs_uri, "->", local)
        download_gcs(args.gcs_uri, local)
        path = local
    elif args.local_kg:
        path = args.local_kg
    else:
        raise SystemExit("Provide --gcs-uri or --local-kg")
    G = load_kg(path)
    print("Graph type:", type(G), "nodes:", G.number_of_nodes(), "edges:", G.number_of_edges())
    # sample nodes and attr keys
    sample = list(G.nodes(data=True))[:10]
    print("Sample nodes (first 10):")
    for n, d in sample:
        print("NODE:", n, "ATTRS:", list(d.keys()))
    # aggregate attribute keys
    attr_keys = Counter()
    for _, d in G.nodes(data=True):
        for k in d.keys():
            attr_keys[k]+=1
    print("Top node attribute keys and counts:", attr_keys.most_common()[:30])
    # try to find company-like keys and most common values
    possible_keys = ['company','ticker','cik','org','entity','issuer']
    found = {}
    for k in possible_keys:
        vals = [d.get(k) for _,d in G.nodes(data=True) if d.get(k) is not None]
        if vals:
            c = Counter(vals)
            found[k] = c.most_common(10)
    print("Detected candidate identifier keys (top values):")
    for k,v in found.items():
        print("==",k,"==\n",v)
    # any node with TSLA?
    tsla_matches = [(n,d) for n,d in G.nodes(data=True) if any((str(v).upper()=="TSLA") for v in d.values())]
    print("Nodes containing 'TSLA' in any attr:", len(tsla_matches))
    if tsla_matches:
        print(tsla_matches[:5])
    # list top companies by heuristic keys
    heur = None
    for k in ['company','ticker','cik','org','entity','issuer']:
        vals = [d.get(k) for _,d in G.nodes(data=True) if d.get(k)]
        if vals:
            print(f"Example values for key {k}: {Counter(vals).most_common(5)}")
    print("Done.")

if __name__ == '__main__':
    main()
