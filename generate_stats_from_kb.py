import networkx as nx
import pickle
from google.cloud import storage

# --- CONFIGURATION ---
BUCKET_NAME = "legal_clean_contracts_bucket"  # Your bucket name
GRAPH_FILE = "legal_knowledge_graph.pickle"

def analyze_graph():
    # 1. Load the Graph
    print(f"📥 Downloading {GRAPH_FILE} from {BUCKET_NAME}...")
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(GRAPH_FILE)
    
    if not blob.exists():
        print("❌ Graph file not found!")
        return

    G = pickle.loads(blob.download_as_bytes())
    
    # 2. Basic Metrics
    num_nodes = G.number_of_nodes()
    num_edges = G.number_of_edges()
    density = nx.density(G)
    
    print("\n--- 📊 KNOWLEDGE GRAPH TOPOLOGY ---")
    print(f"Total Documents (Nodes): {num_nodes}")
    print(f"Total Relationships (Edges): {num_edges}")
    print(f"Graph Density: {density:.4f}")

    # 3. Advanced Metrics (For the Paper)
    # A. Company Clusters (Weakly Connected Components)
    # This tells you how many distinct "Islands" of legal reality exist (e.g., Tesla vs Ford)
    undirected = G.to_undirected()
    components = list(nx.connected_components(undirected))
    print(f"Distinct Company Clusters: {len(components)}")
    
    # B. The "Deepest Chain" (Max Hops)
    # We find the longest path in the graph. This proves your system can handle complex histories.
    try:
        longest_path = nx.dag_longest_path(G)
        print(f"Max Hop Depth: {len(longest_path) - 1}")
        print(f"Longest Chain Sample: {longest_path}")
    except nx.NetworkXUnfeasible:
        print("⚠️ Graph has cycles (loops). Max depth calculation skipped.")

    # C. "Leaf" Analysis (Current Truths)
    # Nodes with in-degree 0 (nothing amends them) are the "Latest Versions".
    current_truths = [n for n in G.nodes() if G.in_degree(n) == 0]
    print(f"Active 'Current Truth' Documents: {len(current_truths)}")

if __name__ == "__main__":
    analyze_graph()