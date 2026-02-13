import os
import pickle
import networkx as nx
from google.cloud import storage

# --- CONFIGURATION ---
# UPDATE THESE IF YOUR BUCKET NAME IS DIFFERENT
BUCKET_NAME = "legal_clean_contracts_bucket" 
OUTPUT_FILE = "full_legal_context.txt"

# The folders containing your text files
FOLDERS = ["F/", "GM/", "LCID/", "RIVN/", "TSLA/"]

# The file containing your graph structure
GRAPH_FILE = "legal_knowledge_graph.pickle"

def consolidate():
    """
    Reads the graph pickle and all text files from GCS,
    consolidating them into a single text file for evaluation generation.
    """
    print(f"🚀 Starting consolidation from bucket: {BUCKET_NAME}")
    
    try:
        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)
    except Exception as e:
        print(f"❌ Error connecting to GCS: {e}")
        return

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        
        # --- PART 1: THE KNOWLEDGE GRAPH (The Map) ---
        print("📉 Extracting Knowledge Graph Structure...")
        blob = bucket.blob(GRAPH_FILE)
        
        if blob.exists():
            try:
                # Download and unpickle the graph
                graph_bytes = blob.download_as_bytes()
                G = pickle.loads(graph_bytes)
                
                # Write a clear header for the LLM
                f.write("="*80 + "\n")
                f.write("SECTION 1: KNOWLEDGE GRAPH EDGES (Ground Truth for Reasoning)\n")
                f.write("NOTE: Use these edges to identify multi-hop chains (e.g., A -> AMENDS -> B).\n")
                f.write("="*80 + "\n\n")
                
                if len(G.edges) == 0:
                    f.write("(No edges found in graph)\n")
                else:
                    count = 0
                    for u, v, data in G.edges(data=True):
                        # Format: NODE_A --[RELATION]--> NODE_B
                        relation = data.get('relation', 'RELATES_TO').upper()
                        f.write(f"EDGE: {u} --[{relation}]--> {v}\n")
                        count += 1
                    print(f"   ✅ Wrote {count} graph edges.")
                
                f.write("\n\n")
            except Exception as e:
                print(f"   ❌ Error reading pickle file: {e}")
                f.write(f"(Error reading graph file: {e})\n")
        else:
            print(f"   ⚠️ Graph file '{GRAPH_FILE}' not found in bucket.")
            f.write("(Graph file not found)\n")

        # --- PART 2: THE RAW TEXT (The Content) ---
        print("📄 Extracting Legal Text Documents...")
        
        total_files = 0
        for folder in FOLDERS:
            print(f"   📂 Scanning folder: {folder}...")
            blobs = bucket.list_blobs(prefix=folder)
            
            folder_count = 0
            for blob in blobs:
                # We only want text files, not the folder itself or other binaries
                if blob.name.endswith(".txt"):
                    try:
                        content = blob.download_as_text()
                        
                        # Write a distinct separator and ID for each document
                        f.write("="*80 + "\n")
                        f.write(f"DOCUMENT_ID: {blob.name}\n")
                        f.write("TYPE: Raw Legal Text\n")
                        f.write("="*80 + "\n")
                        
                        f.write(content)
                        f.write(f"\n\n--- END OF DOCUMENT: {blob.name} ---\n\n")
                        
                        folder_count += 1
                        total_files += 1
                    except Exception as e:
                        print(f"      ⚠️ Skipped {blob.name}: {e}")
            
            print(f"      -> Processed {folder_count} files.")

    print(f"\n🎉 DONE! Full context saved to: {OUTPUT_FILE}")
    print(f"   Total Files Processed: {total_files}")
    print(f"   Now upload '{OUTPUT_FILE}' to your LLM to generate evaluation questions.")

if __name__ == "__main__":
    consolidate()