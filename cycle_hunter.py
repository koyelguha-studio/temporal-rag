import networkx as nx
import pickle
from google.cloud import storage

# --- CONFIGURATION ---
BUCKET_NAME = "legal_clean_contracts_bucket"
GRAPH_FILE = "legal_knowledge_graph.pickle"

def find_loops():
    print(f"🕵️ Downloading Graph...")
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(GRAPH_FILE)
    
    if not blob.exists():
        print("❌ Graph file not found!")
        return
        
    G = pickle.loads(blob.download_as_bytes())

    try:
        # Fixed: Unpacking (u, v, direction) instead of just (u, v)
        cycle = nx.find_cycle(G, orientation="original")
        print("\n⚠️ CYCLIC ERROR DETECTED:")
        for edge in cycle:
            # We use *edge to catch any number of values (u, v, [direction])
            u, v, *rest = edge
            print(f"  🔴 {u} --> {v}")
            # Try to print relationship if it exists
            rel = G.edges[u, v].get('relation', 'unknown')
            print(f"     (Relation: {rel})")
            
        print("\n💡 Diagnosis: These documents claim to amend each other.")
        print("Likely Cause: One document is an 'Amended and Restated' version,")
        print("but the Builder extracted the wrong date for the Target.")
        
    except nx.NetworkXNoCycle:
        print("\n✅ No cycles found! The graph is a valid DAG (Directed Acyclic Graph).")

if __name__ == "__main__":
    find_loops()