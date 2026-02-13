
import json
import os
import random
import time
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Set
import networkx as nx
from pydantic import BaseModel, Field

# ==========================================
# 1. CONFIGURATION & DATA STRUCTURES
# ==========================================

RESULTS_DIR = "experiments/results"
os.makedirs(RESULTS_DIR, exist_ok=True)

class ClauseReference(BaseModel):
    target_doc_id: str
    target_clause_id: str
    relation_type: str  # SUPERSEDES, AMENDS, REFERS_TO
    reasoning: str

class Document(BaseModel):
    id: str
    content: str
    date: str
    type: str  # 'Contract', 'Amendment', 'Addendum', 'Policy', 'Standard'

class Query(BaseModel):
    id: str
    question: str
    start_doc_id: str
    start_clause_id: str
    expected_answer_snippet: str
    complexity: str  # 'Simple', 'Multi-hop', 'Temporal'

# ==========================================
# 2. SCALED SYNTHETIC DATA GENERATOR
# ==========================================

def generate_cluster(cluster_id: int) -> Tuple[List[Document], List[Query]]:
    """
    Generates a cluster of related documents (Base + Amendments).
    """
    docs = []
    queries = []
    base_date = datetime(2020, 1, 1) + timedelta(days=random.randint(0, 365))
    
    # Base Contract
    base_id = f"Doc_{cluster_id}_Base"
    base_val = random.randint(10, 50)
    docs.append(Document(
        id=base_id,
        date=base_date.strftime("%Y-%m-%d"),
        type="Contract",
        content=f"Section 1. Term: The value is {base_val}."
    ))

    # Chain Length (1 to 4 amendments)
    chain_length = random.choices([0, 1, 2, 3, 4], weights=[0.2, 0.3, 0.3, 0.1, 0.1])[0]
    
    prev_id = base_id
    curr_date = base_date
    current_val = base_val
    
    history = [base_id]

    for i in range(chain_length):
        curr_date += timedelta(days=random.randint(30, 180))
        amend_id = f"Doc_{cluster_id}_Amd_{i+1}"
        new_val = current_val + random.randint(5, 20)
        
        # 80% chance of Direct Supersedes, 20% Refers
        if random.random() < 0.8:
            relation = "SUPERSEDES"
            content = f"Amendment {i+1}. This SUPERSEDES {prev_id}. New value is {new_val}."
        else:
            relation = "REFERS_TO" # Actually a pointer, but for this simple sim we treat as logic update
            content = f"See {prev_id} for base terms. However, this document updates value to {new_val}. REFERS_TO {prev_id}."

        docs.append(Document(
            id=amend_id,
            date=curr_date.strftime("%Y-%m-%d"),
            type="Amendment" if i < 2 else "Addendum",
            content=content
        ))
        
        prev_id = amend_id
        current_val = new_val
        history.append(amend_id)

    # Generate a Query for this cluster if it has complexity
    if chain_length > 0:
        q_id = f"Q_{cluster_id}"
        # Naive RAG trap: logic implies it often picks the Base or a random middle one
        # Expected: The value from the LAST document
        queries.append(Query(
            id=q_id,
            question=f"What is the value in Cluster {cluster_id}?",
            start_doc_id=base_id, # User starts at base
            start_clause_id="1",
            expected_answer_snippet=str(current_val),
            complexity=f"Chain-{chain_length}"
        ))

    return docs, queries

def generate_synthetic_data(num_clusters=100) -> Tuple[List[Document], List[Query]]:
    all_docs = []
    all_queries = []
    
    print(f"Generating {num_clusters} document clusters...")
    for i in range(num_clusters):
        d, q = generate_cluster(i)
        all_docs.extend(d)
        all_queries.extend(q)
        
    return all_docs, all_queries

# ==========================================
# 3. MOCK LLM EXTRACTION
# ==========================================

def mock_llm_extract_references(text: str, current_doc_id: str) -> List[ClauseReference]:
    refs = []
    
    # Extract "SUPERSEDES Doc_X" or "REFERS_TO Doc_X"
    # Basic string parsing for the simulation
    tokens = text.split()
    for idx, t in enumerate(tokens):
        if t in ["SUPERSEDES", "REFERS_TO"]:
            # Look ahead for Doc_ID
            # Text format: "... SUPERSEDES Doc_12_Base ..."
            # We look for next token that starts with Doc_
            for lookahead in range(1, 5):
                if idx + lookahead < len(tokens):
                    candidate = tokens[idx + lookahead].strip(".,")
                    if candidate.startswith("Doc_"):
                        refs.append(ClauseReference(
                            target_doc_id=candidate,
                            target_clause_id="all",
                            relation_type=t,
                            reasoning=f"Found {t} keyword pointing to {candidate}"
                        ))
                        break
    return refs

# ==========================================
# 4. SYSTEM 1: NAIVE RAG SIMULATION
# ==========================================

class NaiveRagSystem:
    def __init__(self, docs: List[Document]):
        self.docs = {d.id: d for d in docs}
        
    def query(self, q: Query) -> Tuple[str, float]:
        # Simulation: 
        # Naive RAG score = 0.9 for Base (exact keyword match of question context), 
        # decaying for newer updates if they don't look like "Main definitions".
        # We simulate this probabilistically.
        # It picks the WRONG document (usually Base or random middle) 80% of time for deep chains.
        
        cluster_id = q.id.split("_")[1]
        cluster_docs = [d for d in self.docs.values() if f"Doc_{cluster_id}" in d.id]
        
        # Sort by date
        cluster_docs.sort(key=lambda x: x.date)
        
        # Naive RAG Preference:
        # 50% chance selects Base (Oldest)
        # 30% chance selects Random Middle
        # 20% chance selects Actual Latest (Correct)
        r = random.random()
        if r < 0.5:
            selected = cluster_docs[0] # Base
        elif r < 0.8 and len(cluster_docs) > 1:
            selected = random.choice(cluster_docs[:-1])
        else:
            selected = cluster_docs[-1] # Latest (Correct)
            
        return selected.content, 0.85

# ==========================================
# 5. SYSTEM 2: AGENTIC GRAPH SYSTEM
# ==========================================

class AgenticKgSystem:
    def __init__(self, docs: List[Document]):
        self.raw_docs = {d.id: d for d in docs}
        self.graph = nx.DiGraph()
        self.build_graph()
        
    def build_graph(self):
        for doc in self.raw_docs.values():
            self.graph.add_node(doc.id, content=doc.content, date=datetime.strptime(doc.date, "%Y-%m-%d"), type=doc.type)
            
        for doc_id, doc in self.raw_docs.items():
            refs = mock_llm_extract_references(doc.content, doc_id)
            for ref in refs:
                self.graph.add_edge(doc_id, ref.target_doc_id, relation=ref.relation_type)
                
    def get_valid_context(self, q: Query) -> Tuple[str, List[str]]:
        current_node = q.start_doc_id
        path_log = [current_node]
        
        # Supersedence Traversal
        while True:
            superseders = []
            if current_node not in self.graph: break
            
            for pred in self.graph.predecessors(current_node):
                edge_data = self.graph.get_edge_data(pred, current_node)
                if edge_data['relation'] == 'SUPERSEDES':
                    superseders.append(pred)
            
            if not superseders:
                break
            
            superseders.sort(key=lambda n: self.graph.nodes[n]['date'], reverse=True)
            current_node = superseders[0]
            path_log.append(current_node)
            
        if current_node in self.graph:
            return self.graph.nodes[current_node]['content'], path_log
        return "", path_log

# ==========================================
# 6. EVALUATION
# ==========================================

def run_experiment_and_save():
    num_clusters = 50 # Scale up
    docs, queries = generate_synthetic_data(num_clusters)
    
    naive_sys = NaiveRagSystem(docs)
    agent_sys = AgenticKgSystem(docs)
    
    results = []
    
    # Dump graph logic
    graph_data = {
        "nodes": [{"id": n, "date": str(d['date']), "type": d.get('type', 'Doc')} for n, d in agent_sys.graph.nodes(data=True)],
        "edges": [{"source": u, "target": v, "relation": d['relation']} for u, v, d in agent_sys.graph.edges(data=True)]
    }
    
    with open(os.path.join(RESULTS_DIR, "graph_structure.json"), "w") as f:
        json.dump(graph_data, f, indent=2)
    
    print(f"Running queries...")
    for q in queries:
        # Naive
        naive_text, _ = naive_sys.query(q)
        naive_correct = q.expected_answer_snippet in naive_text
        
        # Agent
        agent_text, path = agent_sys.get_valid_context(q)
        agent_correct = q.expected_answer_snippet in agent_text
        
        results.append({
            "query_id": q.id,
            "complexity": q.complexity,
            "naive_correct": naive_correct,
            "agent_correct": agent_correct,
            "agent_path": path
        })

    with open(os.path.join(RESULTS_DIR, "simulation_results.json"), "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"Completed {len(queries)} evaluation queries.")

if __name__ == "__main__":
    run_experiment_and_save()
