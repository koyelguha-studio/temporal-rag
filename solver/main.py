import pickle
import networkx as nx
import os
import re
from google import genai
from google.cloud import storage

# --- CONFIGURATION ---
LOCAL_PICKLE = "local_cfr_graph.pickle"
PROJECT_ID = "playground-koyel"
# Change this to your ACTUAL clean bucket name where the .txt files are stored
CLEAN_BUCKET_NAME = "legal_clean_contracts_bucket" 

# Initialize Clients
storage_client = storage.Client()
client = genai.Client(vertexai=True, project=PROJECT_ID, location="us-central1")
bucket = storage_client.bucket(CLEAN_BUCKET_NAME)

def load_graph_local():
    with open(LOCAL_PICKLE, "rb") as f:
        return pickle.load(f)

def get_relevant_nodes_for_cfr(G, user_question):
    id_hints = re.findall(r'(?:Section|Part|SEC|PT|§)\s*([\d\.]+)', user_question, re.I)
    candidates = []
    for node_id, data in G.nodes(data=True):
        if any(hint in node_id for hint in id_hints):
            candidates.append(f"ID: {node_id} | Year: {data.get('year')}")
    
    if not candidates:
        candidates = [f"ID: {n} | Year: {G.nodes[n].get('year')}" for n in list(G.nodes())[:50]]

    prompt = f"User: {user_question}\nCandidates:\n{candidates[:50]}\nReturn relevant IDs only (comma separated)."
    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    found_ids = re.findall(r'SEC_[\d\.]+_\d{4}', response.text)
    return [rid for rid in found_ids if rid in G]

def resolve_cfr_lineage(G, root_ids, max_hops=1): # Capped at 1 hop for local testing
    all_nodes = set(root_ids)
    for root in root_ids:
        path_edges = list(nx.bfs_edges(G, source=root, depth_limit=max_hops))
        for u, v in path_edges:
            all_nodes.add(v)
    return list(all_nodes)

def get_high_fidelity_context(G, node_ids):
    """
    Extracts text directly from the 'content' field stored in the Knowledge Graph nodes.
    Falls back to 'summary' if content is missing.
    """
    full_context = ""
    for node_id in node_ids:
        data = G.nodes[node_id]
        
        # 1. Grab the 'content' field you found during debugging
        # We also grab 'name' (the Subject) to give Gemini better headings
        section_text = data.get("content", data.get("summary", "[No content available]"))
        section_name = data.get("name", "Unnamed Section")
        year = data.get("year", "N/A")
        
        # 2. Build the structured context block
        full_context += f"\n\n--- SOURCE: {node_id} ---\n"
        full_context += f"HEADING: {section_name}\n"
        full_context += f"YEAR: {year}\n"
        full_context += f"CONTENT:\n{section_text}\n"
        full_context += f"{'-'*40}\n"
    
    return full_context

def run_local_solver(question):
    print(f"📥 Loading Graph...")
    G = load_graph_local()
    
    # 1. Find the 2001, 2002, 2003 versions
    root_ids = get_relevant_nodes_for_cfr(G, question)
    print(f"🎯 Nodes Identified: {root_ids}")

    # 2. Get high-fidelity context from the 'content' field
    # Note: We skip neighbors for this specific 'Scope' question to keep it clean
    context = get_high_fidelity_context(G, root_ids)

    # 3. Ask Gemini to analyze the actual text
    final_prompt = f"""
    You are a Banking Law Expert. Answer the question using ONLY the provided context.
    If multiple years are provided, explain if the scope changed or stayed the same.
    
    QUESTION: {question}
    
    CONTEXT:
    {context}
    """
    
    print("🧠 Analyzing text...")
    response = client.models.generate_content(model="gemini-2.0-flash", contents=final_prompt)

    print("\n🤖 ANSWER:")
    print("-" * 30)
    print(response.text)
    print("-" * 30)

if __name__ == "__main__":
    run_local_solver("what is the scope for section 303.0 ?")

