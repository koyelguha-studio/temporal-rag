import pickle
import networkx as nx
import random
import json
import re
from google import genai

# --- CONFIGURATION ---
PICKLE_PATH = "local_cfr_graph.pickle"
PROJECT_ID = "playground-koyel"
NUM_QUESTIONS = 10  

# Initialize Gemini Client
client = genai.Client(vertexai=True, project=PROJECT_ID, location="us-central1")

def load_and_audit_graph():
    """Loads the graph and verifies your specific data structure."""
    if not os.path.exists(PICKLE_PATH):
        raise FileNotFoundError(f"❌ {PICKLE_PATH} not found.")
    
    with open(PICKLE_PATH, "rb") as f:
        G = pickle.load(f)
    
    # Audit: Count how many nodes have 'content' vs 'summary'
    has_content = sum(1 for n, d in G.nodes(data=True) if 'content' in d)
    has_year = sum(1 for n, d in G.nodes(data=True) if 'year' in d)
    
    print(f"📊 Graph Loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges.")
    print(f"🔍 Audit: {has_content} nodes have 'content', {has_year} have 'year' labels.")
    
    if has_content == 0:
        print("⚠️ WARNING: No nodes contain 'content'. Check your graph extraction logic.")
    
    return G

def generate_golden_set(G):
    golden_dataset = []

    # 1. Group Sections by Name to find Temporal Chains (2001 -> 2002 -> 2003)
    # This specifically looks for sections that exist in at least 2 different years
    temporal_groups = {}
    for node_id, data in G.nodes(data=True):
        # We clean the ID to get the base section (e.g., SEC_303.0_2001 -> 303.0)
        base_id = re.sub(r'SEC_|_(\d{4})', '', node_id)
        if base_id not in temporal_groups:
            temporal_groups[base_id] = []
        temporal_groups[base_id].append(node_id)

    # Filter for groups that have a 25-year potential (at least 2 entries)
    evolutionary_targets = [v for k, v in temporal_groups.items() if len(v) > 1]
    
    # 2. Identify Citation "Hubs" for Structural Multi-Hop
    # These are sections that cite at least 3 other sections
    citation_hubs = [n for n in G.nodes() if G.out_degree(n) >= 3]

    print(f"🧬 Identified {len(evolutionary_targets)} Temporal Chains and {len(citation_hubs)} Structural Hubs.")

    for i in range(NUM_QUESTIONS):
        # Alternate between testing Temporal Drift and Structural Dependency
        category = "TEMPORAL_DRIFT" if i % 2 == 0 else "STRUCTURAL_MULTI_HOP"
        
        context_nodes = []
        if category == "TEMPORAL_DRIFT" and evolutionary_targets:
            # Pick a random section and sort its IDs by year
            context_nodes = sorted(random.choice(evolutionary_targets), key=lambda x: G.nodes[x].get('year', '0'))
        elif category == "STRUCTURAL_MULTI_HOP" and citation_hubs:
            root = random.choice(citation_hubs)
            # Get the root and its first 3 neighbors (the sections it cites)
            context_nodes = [root] + list(G.neighbors(root))[:3]
        
        if not context_nodes:
            continue

        # Build the context string using the 'content' field you verified
        context_text = ""
        for nid in context_nodes:
            data = G.nodes[nid]
            text = data.get('content', '[Content Missing]')
            year = data.get('year', 'N/A')
            context_text += f"--- NODE: {nid} (Year: {year}) ---\n{text[:3000]}\n\n"

        # Ask Gemini to generate a "Tough" question
        prompt = f"""
        You are a Legal Engineering Auditor. I am testing a Graph RAG system for Banking Regulations (CFR Title 12).
        
        Using the provided context of multiple related sections/years, generate a 'Golden Test Case'.
        
        CATEGORY: {category}
        CONTEXT:
        {context_text}

        TASK:
        1. Write a COMPLEX QUESTION. 
           - If TEMPORAL: Ask how a specific rule changed or was replaced over the years.
           - If STRUCTURAL: Ask how a rule in the root section is constrained by definitions in the cited sections.
        2. Write a GOLDEN ANSWER. Use the 'content' provided to be 100% accurate.
        3. Explain WHY GRAPH RAG is better than VECTOR RAG here. (e.g. "Vector RAG would only find the latest year, missing the amendment history").

        RETURN JSON ONLY:
        {{
            "question": "...",
            "golden_answer": "...",
            "graph_advantage": "...",
            "involved_nodes": {json.dumps(context_nodes)},
            "category": "{category}"
        }}
        """

        try:
            print(f"🧠 Generating Golden Pair {i+1}...")
            response = client.models.generate_content(model="gemini-2.5-pro", contents=prompt)
            clean_json = response.text.replace("```json", "").replace("```", "").strip()
            golden_item = json.loads(clean_json)
            golden_dataset.append(golden_item)
        except Exception as e:
            print(f"❌ Error on pair {i+1}: {e}")

    return golden_dataset

if __name__ == "__main__":
    import os
    
    # 1. Audit and Load
    graph = load_and_audit_graph()
    
    # 2. Generate Dataset
    final_set = generate_golden_set(graph)
    
    # 3. Save to Disk
    output_file = "cfr_golden_dataset.json"
    with open(output_file, "w") as f:
        json.dump(final_set, f, indent=4)
        
    print(f"\n✨ DONE! Generated {len(final_set)} golden questions.")
    print(f"📂 Saved to: {output_file}")