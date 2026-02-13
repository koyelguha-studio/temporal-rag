import functions_framework
import pickle
import networkx as nx
import os
import re
from google.cloud import storage
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List
from dateutil import parser 

# --- CONFIGURATION ---
GRAPH_FILE_NAME = "legal_knowledge_graph.pickle"
storage_client = storage.Client()

# --- SCHEMA ---
class Reference(BaseModel):
    target_date: str = Field(..., description="The EXACT Effective Date (YYYY-MM-DD) of the PRIOR agreement being amended.")
    relationship: str = Field(..., description="AMENDS, SUPERSEDES, or REPLACES")
    evidence: str = Field(..., description="Brief quote proving the link.")

class LegalDocMetadata(BaseModel):
    doc_date: str = Field(..., description="Effective date of THIS document (YYYY-MM-DD).")
    doc_type: str = Field(..., description="Type of document (e.g. Credit Agreement).")
    references: List[Reference]

# --- ID LOGIC (The "Glue") ---
def generate_stable_id(ticker, date_str):
    """
    Creates a UNIVERSAL ID to guarantee connectivity.
    Format: TICKER_YYYY-MM-DD_CONTRACT
    """
    if not date_str or date_str.lower() == "null":
        return None
    
    try:
        # Standardize 'Feb 22, 2021' -> '2021-02-22'
        dt = parser.parse(date_str)
        clean_date = dt.strftime("%Y-%m-%d")
    except Exception:
        # Fallback cleanup
        clean_date = re.sub(r'[^0-9-]', '', date_str.replace(" ", "-").replace("/", "-"))
    
    # We force '_CONTRACT' suffix to ensure Node A matches Node B's search.
    return f"{ticker.upper()}_{clean_date}_CONTRACT"

# --- GRAPH OPS ---
def load_or_create_graph(bucket_name):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(GRAPH_FILE_NAME)
    if blob.exists():
        return pickle.loads(blob.download_as_bytes())
    return nx.DiGraph()

def save_graph(bucket_name, G):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(GRAPH_FILE_NAME)
    blob.upload_from_string(pickle.dumps(G))

# --- CLOUD FUNCTION ---
@functions_framework.cloud_event
def build_knowledge_graph(cloud_event):
    data = cloud_event.data
    bucket_name = data["bucket"]
    file_name = data["name"]

    if file_name == GRAPH_FILE_NAME or not file_name.endswith(".txt"):
        return

    print(f"🚀 Analyzing: {file_name}")

    # 1. Ticker Extraction (Folder Safe)
    try:
        if "/" in file_name:
            ticker = file_name.split("/")[0].upper() # Handle 'LCID/8-K/...'
        else:
            ticker = file_name.split("_")[0].upper() # Handle flat files
    except:
        ticker = "UNKNOWN"

    # 2. Download Text
    bucket = storage_client.bucket(bucket_name)
    try:
        text = bucket.blob(file_name).download_as_text()
    except Exception as e:
        print(f"❌ Read Error: {e}")
        return

    # 3. Gemini Extraction
    client = genai.Client(
        vertexai=True, 
        project=os.environ.get("PROJECT_ID"), 
        location="us-central1"
    )

    prompt = f"""
    Analyze this legal document to build a graph node.
    1. Extract the Effective Date (YYYY-MM-DD).
    2. Identify PRIOR documents this one AMENDS.
    
    Current Ticker: {ticker}
    
    TEXT START:
    {text}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LegalDocMetadata
            )
        )
        meta = response.parsed
    except Exception as e:
        print(f"❌ Gemini Error: {e}")
        return

    # 4. Build Graph
    G = load_or_create_graph(bucket_name)

    # Node Creation
    current_node_id = generate_stable_id(ticker, meta.doc_date)
    
    if not current_node_id:
        print(f"⚠️ Skipping: Missing Date for {file_name}")
        return

    G.add_node(
        current_node_id,
        date=meta.doc_date,
        type=meta.doc_type,
        original_file=file_name
    )
    print(f"  + Node: {current_node_id}")

    # Edge Creation
    for ref in meta.references:
        target_id = generate_stable_id(ticker, ref.target_date)
        
        if not target_id: continue

        # --- GUARDRAILS ---
        if target_id == current_node_id: continue # No Self-Loops
        if ref.target_date >= meta.doc_date: continue # No Time-Travel

        G.add_edge(
            current_node_id,
            target_id,
            relation=ref.relationship,
            evidence=ref.evidence
        )
        print(f"  🔗 Link: {current_node_id} -> {target_id}")

    save_graph(bucket_name, G)