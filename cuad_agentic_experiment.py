import os
import networkx as nx
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from datasets import load_dataset
from google import genai
from google.genai import types

# ==========================================
# 1. CONFIGURATION & CLIENT SETUP
# ==========================================
API_KEY = "AIzaSyAQz7RlKVbcZxsbi8YcJFhMajdStK0qyZQ"
client = genai.Client(api_key=API_KEY)
MODEL_ID = "gemini-2.5-flash"


# ==========================================
# 2. DATA: The "Gold Standard" Simulation
# ==========================================
# Since the external dataset is flaky, we inject real legal patterns here.
REAL_WORLD_SAMPLES = [
    {
        "id": "Master_Service_Agreement_2020",
        "text": """
        SECTION 4: PAYMENT TERMS.
        4.1 Standard Terms. Client shall pay all undisputed invoices within sixty (60) days 
        of receipt. Late payments shall incur interest at a rate of 1.5% per month.
        4.2 Currency. All payments shall be made in USD.
        """
    },
    {
        "id": "Amendment_01_2022",
        "text": """
        AMENDMENT NO. 1 TO MASTER SERVICE AGREEMENT
        This Amendment is entered into effective as of Jan 1, 2022.
        
        1. Modification of Payment Terms.
        Section 4.1 of the Master Service Agreement is hereby deleted in its entirety 
        and replaced with the following: 
        "Client shall pay all undisputed invoices within thirty (30) days of receipt."
        
        2. All other terms remain unchanged.
        """
    },
    {
        "id": "Emergency_Addendum_2024",
        "text": """
        SUPPLY CHAIN SURCHARGE ADDENDUM (2024)
        Reference is made to Amendment No. 1.
        
        Due to global inflation, a temporary surcharge of 5% applies to all invoices.
        This Addendum supersedes any conflicting terms in the Amendment regarding fixed pricing.
        """
    }
]

# ==========================================
# 3. SCHEMA DEFINITIONS
# ==========================================
class ClauseReference(BaseModel):
    target_doc_id: str = Field(..., description="The ID/Name of the document being changed or referenced.")
    relation_type: str = Field(..., description="Type: SUPERSEDES, AMENDS, or REFERS_TO")
    reasoning: str = Field(..., description="Quote the specific text that indicates this change.")

class ExtractionResult(BaseModel):
    has_references: bool
    references: List[ClauseReference]

# ==========================================
# 4. KNOWLEDGE GRAPH ENGINE
# ==========================================
class LegalKnowledgeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_document(self, doc_id: str, content: str):
        self.graph.add_node(doc_id, content=content, valid=True)
        return doc_id

    def add_link(self, source: str, target: str, relation: str):
        # We model the dependency: Source (Newer) -> Target (Older)
        self.graph.add_edge(source, target, relation=relation)

    def get_valid_context(self, start_doc_id: str):
        """
        Traverses the graph to see if the requested doc is the final truth.
        If it finds a node that SUPERSEDES the current one, it jumps to it.
        """
        # Note: In a real graph, we'd search 'successors' if edges point Older->Newer.
        # Here we check if any *other* node points to us claiming to SUPERSEDE us.
        
        current = start_doc_id
        path_log = [current]
        
        # Simple traversal: Find the newest node in the chain
        # We look for nodes that point TO 'current' with 'SUPERSEDES'
        while True:
            superseders = [n for n in self.graph.predecessors(current) 
                           if self.graph[n][current].get('relation') == 'SUPERSEDES']
            
            if not superseders:
                break
            
            # Jump to the update
            current = superseders[0]
            path_log.append(current)
            
        return self.graph.nodes[current]['content'], path_log

# ==========================================
# 5. EXECUTION PIPELINE
# ==========================================
def run_demo():
    print("--- Phase 1: Ingesting Legal Corpus ---")
    kg = LegalKnowledgeGraph()
    
    for sample in REAL_WORLD_SAMPLES:
        kg.add_document(sample["id"], sample["text"])
        print(f"✅ Ingested: {sample['id']}")

    print("\n--- Phase 2: Agentic Scanning (Gemini 2.0) ---")
    # The Agent reads every doc to find connections
    for doc_id in kg.graph.nodes:
        content = kg.graph.nodes[doc_id]['content']
        print(f"🧐 Agent analyzing {doc_id}...")
        
        prompt = f"""
        Analyze this legal text. Does it amend, replace, or supersede another document?
        Text: "{content}"
        
        Known Document IDs in system: {[s['id'] for s in REAL_WORLD_SAMPLES]}
        (Match the 'target_doc_id' to one of these if possible)
        """
        
        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ExtractionResult
                )
            )
            
            extraction = response.parsed
            if extraction.has_references:
                for ref in extraction.references:
                    print(f"   🔗 Link Found: {doc_id} --{ref.relation_type}--> {ref.target_doc_id}")
                    print(f"      Reasoning: {ref.reasoning}")
                    
                    # Update the Graph Topology
                    if ref.relation_type in ["SUPERSEDES", "AMENDS", "REPLACES"]:
                        # We normalize "AMENDS" to "SUPERSEDES" for this logic
                        kg.add_link(doc_id, ref.target_doc_id, "SUPERSEDES")
            else:
                print("   No references found.")

        except Exception as e:
            print(f"   ⚠️ API Error: {e}")

    print("\n--- Phase 3: The 'Time-Travel' Query ---")
    # SCENARIO: User finds the old 2020 contract via Vector Search and asks "What are the payment terms?"
    # Standard RAG would just read the 2020 doc (Net 60).
    # Our Agentic Graph will correct it.
    
    start_node = "Master_Service_Agreement_2020"
    print(f"User Query: 'What are the payment terms in {start_node}?'")
    
    final_content, path = kg.get_valid_context(start_node)
    
    print("\n[RESULT]")
    print(f"Graph Path Traversed: {' ➔ '.join(path)}")
    print("-" * 40)
    print(f"VALID ANSWER SOURCE:\n{final_content.strip()}")
    print("-" * 40)

if __name__ == "__main__":
    run_demo()