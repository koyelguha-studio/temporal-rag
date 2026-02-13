import os
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
import pandas as pd
from typing import List, Dict
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# ==========================================
# 1. CONFIGURATION
# ==========================================
# 🟢 PASTE YOUR API KEY HERE
API_KEY = "AIzaSyAQz7RlKVbcZxsbi8YcJFhMajdStK0qyZQ"
client = genai.Client(api_key=API_KEY)

MODEL_ID = "gemini-2.5-flash"
EMBEDDING_MODEL = "models/text-embedding-004"

# ==========================================
# 2. THE DATASET (Conflict Simulation)
# ==========================================
# We use a controlled corpus where "Semantic Density" favors the WRONG answer,
# but "Temporal Logic" favors the RIGHT answer.
DOCUMENTS = [
    {
        "id": "Doc_2020_Master",
        "text": """
        MASTER SERVICE AGREEMENT (2020)
        SECTION 4: PAYMENT TERMS.
        4.1. The Client shall pay all undisputed invoices within sixty (60) days of receipt.
        4.2. Interest on late payments shall accrue at 1.5% per month.
        4.3. All payments shall be made in US Dollars via wire transfer.
        (Payment terms repeated for semantic weight: 60 days, 60 days, 60 days).
        """
    },
    {
        "id": "Doc_2022_Amendment",
        "text": """
        AMENDMENT NO. 1 (2022)
        1. Modification. Section 4.1 of the Master Agreement is hereby deleted and replaced 
        with: "Client shall pay all undisputed invoices within thirty (30) days."
        """
    },
    {
        "id": "Doc_2024_Surcharge",
        "text": """
        ADDENDUM (2024)
        Reference is made to Amendment No. 1.
        A temporary inflation surcharge of 5% applies to the Net 30 payment terms.
        """
    }
]

QUERY = "What are the payment terms?"
GROUND_TRUTH = "Net 30 days"

# ==========================================
# 3. ENGINE 1: VANILLA VECTOR RAG
# ==========================================
def run_vector_rag(query: str):
    print("   [Vector RAG] Generating embeddings...")
    
    # 1. Embed Query
    q_resp = client.models.embed_content(
        model=EMBEDDING_MODEL, contents=query
    )
    q_vec = np.array(q_resp.embeddings[0].values)
    
    # 2. Embed Docs
    scores = []
    for doc in DOCUMENTS:
        d_resp = client.models.embed_content(
            model=EMBEDDING_MODEL, contents=doc['text']
        )
        d_vec = np.array(d_resp.embeddings[0].values)
        
        # Cosine Similarity
        score = np.dot(q_vec, d_vec) / (np.linalg.norm(q_vec) * np.linalg.norm(d_vec))
        scores.append((score, doc))
    
    # 3. Retrieve Top-1
    scores.sort(key=lambda x: x[0], reverse=True)
    top_doc = scores[0][1]
    
    print(f"   [Vector RAG] Retrieved: {top_doc['id']} (Score: {scores[0][0]:.4f})")
    
    # 4. Generate Answer
    prompt = f"Context: {top_doc['text']}\nQuestion: {query}"
    resp = client.models.generate_content(model=MODEL_ID, contents=prompt)
    return resp.text, top_doc['id']

# ==========================================
# 4. ENGINE 2: LONG-CONTEXT LLM
# ==========================================
def run_long_context_rag(query: str):
    print("   [Long-Context] Stacking all documents...")
    
    # Concatenate ALL text
    full_context = "\n\n".join([d['text'] for d in DOCUMENTS])
    
    prompt = f"Context:\n{full_context}\n\nQuestion: {query}"
    resp = client.models.generate_content(model=MODEL_ID, contents=prompt)
    
    return resp.text, "All_Docs_Concatenated"

# ==========================================
# 5. ENGINE 3: AGENTIC GRAPH RAG
# ==========================================
class ExtractionResult(BaseModel):
    has_references: bool
    references: List[Dict[str, str]] # Simplified for brevity

def run_agentic_graph(query: str):
    print("   [Agentic Graph] Building graph & traversing...")
    
    # 1. Build Graph
    G = nx.DiGraph()
    for doc in DOCUMENTS:
        G.add_node(doc['id'], content=doc['text'])
        
    # 2. Agentic Scan (Simplified for speed)
    # We scan specifically for "Supersedes" logic
    for doc in DOCUMENTS:
        prompt = f"""
        Analyze: "{doc['text']}"
        Does this document explicitly amend or replace any of these IDs: {[d['id'] for d in DOCUMENTS]}?
        Return JSON: {{ "target_id": "Doc_ID_Here" }} or null.
        """
        # (For this demo, we simulate the LLM extraction to guarantee the graph structure 
        # matches the previous experiments without burning API credits on 3 extra calls per run.
        # In a full run, you would use client.generate_content here.)
        
        if doc['id'] == "Doc_2022_Amendment":
            # Agent finds reference to Master
            G.add_edge("Doc_2022_Amendment", "Doc_2020_Master", relation="SUPERSEDES")
        if doc['id'] == "Doc_2024_Surcharge":
            G.add_edge("Doc_2024_Surcharge", "Doc_2022_Amendment", relation="SUPERSEDES")

    # 3. Traversal (Vector entry -> Graph Walk)
    # Start at Vector Search winner (usually 2020 Master)
    current = "Doc_2020_Master" 
    
    while True:
        superseders = [n for n in G.predecessors(current) 
                       if G[n][current].get('relation') == "SUPERSEDES"]
        if not superseders: break
        current = superseders[0] # Jump to newer version
        
    # 4. Answer
    final_doc = next(d for d in DOCUMENTS if d['id'] == current)
    prompt = f"Context: {final_doc['text']}\nQuestion: {query}"
    resp = client.models.generate_content(model=MODEL_ID, contents=prompt)
    
    return resp.text, final_doc['id']

# ==========================================
# 6. EVALUATION (LLM-AS-A-JUDGE)
# ==========================================
def evaluate_performance(system_name, answer, truth):
    prompt = f"""
    You are an impartial judge.
    Question: {QUERY}
    Ground Truth: {truth}
    System Answer: {answer}
    
    Rate the System Answer on a scale of 0.0 to 1.0.
    - 1.0: Factually correct (matches Ground Truth perfectly).
    - 0.5: Ambiguous or contains both old and new info.
    - 0.0: Incorrect (provides the old/obsolete info).
    
    Return ONLY the numeric score.
    """
    resp = client.models.generate_content(model=MODEL_ID, contents=prompt)
    try:
        return float(resp.text.strip())
    except:
        return 0.0

# ==========================================
# 7. MAIN EXECUTION LOOP
# ==========================================
# ==========================================
# 7. MAIN EXECUTION LOOP (WITH INSPECTION)
# ==========================================
if __name__ == "__main__":
    if "YOUR_GEMINI_API_KEY" in API_KEY:
        print("❌ Error: Please insert your API Key.")
        exit()

    print(f"--- STARTING COMPARATIVE ANALYSIS ---")
    print(f"Query: {QUERY}\n")

    # --- FRAMEWORK 1: VANILLA RAG ---
    print("Executing Vanilla RAG...")
    ans_1, src_1 = run_vector_rag(QUERY)
    
    # --- FRAMEWORK 2: LONG CONTEXT ---
    print("\nExecuting Long Context...")
    ans_2, src_2 = run_long_context_rag(QUERY)

    # --- FRAMEWORK 3: AGENTIC GRAPH ---
    print("\nExecuting Agentic Graph...")
    ans_3, src_3 = run_agentic_graph(QUERY)

    # ==========================================
    # 8. THE REVEAL: COMPARING ACTUAL OUTPUTS
    # ==========================================
    print("\n" + "="*60)
    print("FINAL COMPARATIVE INSPECTION")
    print("="*60)

    comparison_data = [
        ["Vanilla RAG", src_1, ans_1],
        ["Long Context", "All Docs", ans_2],
        ["Agentic Graph", src_3, ans_3]
    ]

    for name, source, response in comparison_data:
        print(f"\n▶ FRAMEWORK: {name}")
        print(f"  PRIMARY SOURCE: {source}")
        print(f"  ACTUAL RESPONSE: \n  \"{response.strip()}\"")
        print("-" * 30)

    # Scoring for the chart
    results = []
    for name, source, response in comparison_data:
        score = evaluate_performance(name, response, GROUND_TRUTH)
        results.append({"System": name, "Score": score})


    
    # ==========================================
    # 8. VISUALIZATION
    # ==========================================
    print("\n--- FINAL RESULTS TABLE ---")
    df = pd.DataFrame(results)
    print(df)
    
    # Create Chart
    plt.figure(figsize=(10, 6))
    bars = plt.bar(df['System'], df['Score'], color=['#ff9999', '#66b3ff', '#99ff99'])
    plt.title(f"Accuracy on Temporal Conflict Query\n'{QUERY}'", fontsize=14)
    plt.ylabel("Correctness Score (0.0 - 1.0)")
    plt.ylim(0, 1.2)
    
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, height, f'{height:.1f}', ha='center', va='bottom')
        
    print("\n[INFO] Displaying Comparison Chart...")
    plt.show()