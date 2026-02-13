import pandas as pd
import requests
import time
from time import perf_counter as perf_counter
import json
import os
from google.cloud import discoveryengine_v1 as discoveryengine
from google.auth.transport.requests import Request
from google.oauth2 import id_token
import subprocess

# --- CONFIGURATION ---
PROJECT_ID = "playground-koyel"
LOCATION = "global"
# For Vertex AI Agent Builder (Search Engine)
DATA_STORE_ID = "knowledge-hub-ds_1770736679016" 
# For your Custom GraphRAG
GRAPHRAG_URL = "https://query-legal-graph-35744769544.us-central1.run.app"

INPUT_EXCEL = "questions.xlsx"
OUTPUT_EXCEL = "evaluation_results_comparison.xlsx"

# --- HELPER: AUTHENTICATION ---
def get_gcloud_identity_token():
    """
    Equivalent to $(gcloud auth print-identity-token)
    This is the most reliable way to authenticate from a local machine
    where you have already run 'gcloud auth login'.
    """
    try:
        result = subprocess.run(
            ['gcloud', 'auth', 'print-identity-token'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"❌ Auth Error: Could not get token from gcloud. Error: {e}")
        return None

# --- METHOD 1: YOUR AGENTIC GRAPHRAG ---
def call_graph_rag(question):
    token = get_gcloud_identity_token()
    if not token:
        return {"answer": "AUTH_ERROR", "latency": 0, "total_hops": 0, "max_depth": 0, "branches": 0, "detailed_lineage": "N/A"}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    start_time = perf_counter()
    try:
        resp = requests.post(
            GRAPHRAG_URL, 
            headers=headers, 
            json={"question": question}, 
            timeout=180 
        )
        latency = perf_counter() - start_time
        
        # 1. Check if the status is not 200
        if resp.status_code != 200:
            print(f"❌ Server returned error {resp.status_code}: {resp.text[:200]}")
            return {"answer": f"HTTP Error {resp.status_code}", "latency": latency, "total_hops": 0, "max_depth": 0, "branches": 0, "detailed_lineage": "N/A"}

        # 2. Safety check: Is it actually JSON?
        try:
            data = resp.json()
        except ValueError:
            print(f"❌ Response was not JSON! Received: {resp.text[:500]}")
            return {"answer": "INVALID_JSON_RESPONSE", "latency": latency, "total_hops": 0, "max_depth": 0, "branches": 0, "detailed_lineage": "N/A"}

        # 3. Process the JSON as normal
        metrics = data.get("metrics", {})
        lineage_map = data.get("lineage_details", {})
        
        lineage_str = ""
        for root, details in lineage_map.items():
            path_str = " -> ".join(details.get("path", []))
            lineage_str += f"[{root} (Hops: {details.get('hops')})]: {path_str} | "

        return {
            "answer": data.get("answer"),
            "latency": latency,
            "total_hops": metrics.get("total_aggregate_hops", 0),
            "max_depth": metrics.get("max_traversal_depth", 0),
            "branches": metrics.get("branches_explored", 0),
            "detailed_lineage": lineage_str
        }
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        return {"answer": "REQUEST_FAILED", "latency": 0, "total_hops": 0, "max_depth": 0, "branches": 0, "detailed_lineage": "N/A"}
      
# --- METHOD 2: VERTEX AI AGENT BUILDER (Baseline) ---
def call_agent_builder(question):
    client = discoveryengine.SearchServiceClient()
    serving_config = client.serving_config_path(
        project=PROJECT_ID, location=LOCATION, data_store=DATA_STORE_ID, serving_config="default_search"
    )
    
    start_time = perf_counter()
    request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query=question,
        content_search_spec={
            "summary_spec": {
                "summary_result_count": 5, 
                "include_citations": True
            }
        }
    )
    
    try:
        response = client.search(request)
        latency = perf_counter() - start_time
        
        # 1. Extract the answer
        summary_text = "No summary generated"
        if response.summary:
            summary_text = response.summary.summary_text
        
        # 2. Robust Citation Extraction (handles different SDK versions)
        citation_links = []
        try:
            # Try the most recent schema
            if hasattr(response.summary, 'summary_with_metadata'):
                meta = response.summary.summary_with_metadata
                # If 'citations' field is missing, it might be 'references'
                citations = getattr(meta, 'citations', [])
                citation_links = [getattr(c, 'uri', 'N/A') for c in citations]
        except Exception:
            # Fallback: Just mark as 'Available in response' if we can't parse easily
            citation_links = ["See Vertex Console"]

        return {
            "answer": summary_text,
            "latency": latency,
            "citations": ", ".join(citation_links)
        }
    except Exception as e:
        print(f"❌ Agent Builder Error: {e}")
        return {"answer": f"Search Error: {e}", "latency": 0, "citations": "N/A"}
    
def run_benchmark():
    df = pd.read_excel(INPUT_EXCEL)
    # df = df.head(2)
    results = []

    for index, row in df.iterrows():
        question = row['Question']
        print(f"🚀 Question {index+1}: {question[:60]}...")

        # 1. Run your Custom GraphRAG
        g_data = call_graph_rag(question)
        
        # 2. Run Baseline Agent Builder
        a_data = call_agent_builder(question) # Uncomment when ready

        results.append({
            "Question": question,
            "GraphRAG_Answer": g_data['answer'],
            "GraphRAG_Latency": g_data['latency'],
            "GraphRAG_TotalHops": g_data['total_hops'],
            "GraphRAG_MaxDepth": g_data['max_depth'],
            "GraphRAG_Branches": g_data['branches'],
            "GraphRAG_FullLineage": g_data['detailed_lineage'],
            "AgentBuilder_Answer": a_data['answer'],
            "AgentBuilder_Citations": a_data['citations'],
            "AgentBuilder_Latency": a_data['latency']
        })

        time.sleep(5) # Quota protection

    pd.DataFrame(results).to_excel(OUTPUT_EXCEL, index=False)
    print(f"🎉 Benchmark complete. Data saved to {OUTPUT_EXCEL}")

if __name__ == "__main__":
    run_benchmark()