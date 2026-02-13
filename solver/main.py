# # # # import os
# # # # import pickle
# # # # import functions_framework
# # # # import networkx as nx
# # # # from google.cloud import storage
# # # # from google import genai

# # # # storage_client = storage.Client()
# # # # GRAPH_FILE_NAME = "legal_knowledge_graph.pickle"

# # # # def get_best_starting_node(G, user_question):
# # # #     """Uses Gemini to pick the correct starting node from the graph."""
# # # #     node_ids = list(G.nodes())
# # # #     # client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
# # # #     client = genai.Client(
# # # #     vertexai=True, 
# # # #     project=os.environ.get("PROJECT_ID"), # Automatically set in Cloud Functions
# # # #     location="us-central1" # Or your preferred region
# # # #     )

    
# # # #     prompt = f"""
# # # #     The user is asking a question about a legal document. 
# # # #     Below is a list of Document IDs available in our Knowledge Graph.
# # # #     Pick the SINGLE most relevant Document ID that should be the starting point.
# # # #     If you cannot find a match, return 'NONE'.
    
# # # #     User Question: {user_question}
# # # #     Available IDs: {node_ids}
    
# # # #     Return ONLY the ID.
# # # #     """
    
# # # #     response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
# # # #     return response.text.strip()

# # # # @functions_framework.http
# # # # def query_legal_graph(request):
# # # #     CLEAN_BUCKET = os.environ.get("CLEAN_BUCKET_NAME")
# # # #     request_json = request.get_json(silent=True)
    
# # # #     # We now accept 'question' instead of 'doc_id'
# # # #     user_question = request_json.get('question')
# # # #     if not user_question:
# # # #         return {"error": "Please provide a 'question'"}, 400

# # # #     # 1. Load Graph
# # # #     bucket = storage_client.bucket(CLEAN_BUCKET)
# # # #     G = pickle.loads(bucket.blob(GRAPH_FILE_NAME).download_as_bytes())

# # # #     # 2. STEP 1: Identification (NL -> ID)
# # # #     target_id = get_best_starting_node(G, user_question)
    
# # # #     if target_id == "NONE" or target_id not in G:
# # # #         return {"error": f"Could not find a relevant document for: {user_question}"}, 404

# # # #     # 3. STEP 2: Traversal (Your Logic)

# # # #     def resolve_current_truth(G: nx.DiGraph, start_doc_id: str):
# # # #         """
# # # #         Traverses 'SUPERSEDES' edges backwards to find the latest valid document.
# # # #         """
# # # #         current_node = start_doc_id
# # # #         path_taken = [current_node]
# # # #         visited = {current_node}  # Safety: Prevent infinite loops if graph has cycles

# # # #         while True:
# # # #             # 1. Find candidates: Nodes that point TO the current node
# # # #             # Logic: If Node B says "I supersede Node A", the edge is B -> A.
# # # #             # So we look at predecessors of A to find B.
# # # #             predecessors = list(G.predecessors(current_node))
            
# # # #             # 2. Filter: Only follow 'SUPERSEDES', 'AMENDS', or 'REPLACES' edges
# # # #             valid_superseders = []
# # # #             for pred in predecessors:
# # # #                 edge_data = G.get_edge_data(pred, current_node)
# # # #                 relation = edge_data.get("relation", "").upper()
# # # #                 if relation in ["SUPERSEDES", "AMENDS", "REPLACES"]:
# # # #                     valid_superseders.append(pred)
            
# # # #             # 3. Stop if we hit a dead end (no newer documents found)
# # # #             if not valid_superseders:
# # # #                 break

# # # #             # 4. Conflict Resolution: If multiple docs amend this one, pick the NEWEST
# # # #             # We assume nodes have a 'date' attribute (ISO format YYYY-MM-DD)
# # # #             valid_superseders.sort(
# # # #                 key=lambda n: G.nodes[n].get("date", "0000-00-00"), 
# # # #                 reverse=True
# # # #             )
# # # #             winner = valid_superseders[0]

# # # #             # 5. Loop Safety Check
# # # #             if winner in visited:
# # # #                 break
                
# # # #             # 6. Make the Jump
# # # #             current_node = winner
# # # #             path_taken.append(current_node)
# # # #             visited.add(current_node)

# # # #         # 7. Package the Result
# # # #         final_node_data = G.nodes[current_node]
# # # #         return {
# # # #             "final_doc_id": current_node,
# # # #             "final_summary": final_node_data.get("summary", "No summary available."),
# # # #             "final_date": final_node_data.get("date"),
# # # #             "path_taken": path_taken,
# # # #             "hops": len(path_taken) - 1
# # # #         }

# # # #     result = resolve_current_truth(G, target_id)
    
# # # #     # 4. STEP 3: Final Answer Generation
# # # #     # client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
# # # #     client = genai.Client(
# # # #     vertexai=True, 
# # # #     project=os.environ.get("PROJECT_ID"), # Automatically set in Cloud Functions
# # # #     location="us-central1" # Or your preferred region
# # # #     )

# # # #     final_prompt = f"""
# # # #     Based on the following data from the latest document version, answer the user's question.
# # # #     Document ID: {result['final_doc_id']}
# # # #     Summary: {result['final_summary']}
    
# # # #     Question: {user_question}
# # # #     """
# # # #     answer = client.models.generate_content(model="gemini-2.0-flash", contents=final_prompt)
    
# # # #     return {
# # # #         "answer": answer.text,
# # # #         "source_lineage": result['path_taken'],
# # # #         "hops": result['hops']
# # # #     }

# # # import functions_framework
# # # import pickle
# # # import networkx as nx
# # # import os
# # # from google.cloud import storage
# # # from google import genai

# # # # --- GLOBAL INITIALIZATION (Performance Fix) ---
# # # # Loading the graph globally ensures it caches between requests (Cold Start optimization)
# # # storage_client = storage.Client()
# # # GRAPH_FILE_NAME = "legal_knowledge_graph.pickle"
# # # CLEAN_BUCKET = os.environ.get("CLEAN_BUCKET_NAME", "legal_clean_contracts_bucket")

# # # try:
# # #     print("📥 Loading Graph into Memory...")
# # #     bucket = storage_client.bucket(CLEAN_BUCKET)
# # #     blob = bucket.blob(GRAPH_FILE_NAME)
# # #     G_GLOBAL = pickle.loads(blob.download_as_bytes())
# # #     print(f"✅ Graph Loaded: {len(G_GLOBAL.nodes())} nodes.")
# # # except Exception as e:
# # #     print(f"⚠️ Graph Load Failed: {e}")
# # #     G_GLOBAL = nx.DiGraph()

# # # # --- HELPER: START NODE SELECTOR ---
# # # def get_best_starting_node(G, user_question):
# # #     # 1. Pre-Filter: Only show nodes that match Tickers mentioned in the question
# # #     # This prevents sending 1000 unrelated nodes to the LLM
# # #     all_nodes = list(G.nodes())
# # #     candidates = []
    
# # #     # Simple heuristic: If "Tesla" or "TSLA" in question, only show TSLA nodes
# # #     question_upper = user_question.upper()
# # #     relevant_tickers = []
# # #     if "TESLA" in question_upper or "TSLA" in question_upper: relevant_tickers.append("TSLA")
# # #     if "LUCID" in question_upper or "LCID" in question_upper: relevant_tickers.append("LCID")
# # #     if "RIVIAN" in question_upper or "RIVN" in question_upper: relevant_tickers.append("RIVN")
    
# # #     if relevant_tickers:
# # #         candidates = [n for n in all_nodes if any(t in n for t in relevant_tickers)]
# # #     else:
# # #         # Fallback: Send top 50 nodes if no entity detected (Risk mitigation)
# # #         candidates = all_nodes[:50]

# # #     client = genai.Client(
# # #         vertexai=True, 
# # #         project=os.environ.get("PROJECT_ID"), 
# # #         location="us-central1"
# # #     )

# # #     # 2. The "Originalist" Prompt
# # #     # We force it to pick the OLDEST matching doc to ensure traversal happens
# # #     prompt = f"""
# # #     You are a Legal Graph Librarian.
# # #     The user is asking a question about a contract chain.
# # #     Identify the ROOT / ORIGINAL Agreement that starts the chain relevant to the question.
    
# # #     Do NOT pick the latest amendment. Pick the BASE agreement (e.g., 2021 instead of 2025).
# # #     If no match found, return 'NONE'.

# # #     User Question: {user_question}
# # #     Candidate Documents: {candidates}
    
# # #     Return ONLY the Document ID.
# # #     """
    
# # #     response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
# # #     return response.text.strip()

# # # # --- MAIN CLOUD FUNCTION ---
# # # @functions_framework.http
# # # def query_legal_graph(request):
# # #     request_json = request.get_json(silent=True)
# # #     user_question = request_json.get('question')
    
# # #     if not user_question:
# # #         return {"error": "Missing 'question'"}, 400

# # #     # Use Global Graph
# # #     G = G_GLOBAL
    
# # #     # STEP 1: Identification
# # #     target_id = get_best_starting_node(G, user_question)
# # #     print(f"📍 Start Node Selected: {target_id}")

# # #     if target_id == "NONE" or target_id not in G:
# # #         return {"error": "No relevant document found."}, 404

# # #     # STEP 2: Traversal (The "Current Truth" Logic)
# # #     path_taken = [target_id]
# # #     current_node = target_id
    
# # #     while True:
# # #         # Find predecessors (Documents that point TO the current one)
# # #         # Edge Direction: New -> Old. So Predecessors = Newer Docs.
# # #         predecessors = list(G.predecessors(current_node))
        
# # #         # Filter for valid modifications
# # #         valid_updates = []
# # #         for pred in predecessors:
# # #             relation = G.edges[pred, current_node].get("relation", "").upper()
# # #             if relation in ["AMENDS", "SUPERSEDES", "REPLACES"]:
# # #                 valid_updates.append(pred)
        
# # #         if not valid_updates:
# # #             break # Reached the "Leaf" (Newest version)
            
# # #         # Greedy Sort: Pick the one with the latest date in ID (LCID_2025 > LCID_2024)
# # #         # We assume ID format: TICKER_YYYY-MM-DD_...
# # #         valid_updates.sort(reverse=True) 
# # #         next_node = valid_updates[0]
        
# # #         path_taken.append(next_node)
# # #         current_node = next_node

# # #     # STEP 3: Content Retrieval (The "Empty Summary" Fix)
# # #     final_node_data = G.nodes[current_node]
# # #     summary = final_node_data.get("summary", "")
    
# # #     # If summary is weak, DOWNLOAD THE FULL TEXT
# # #     context_text = summary
# # #     if len(summary) < 50 or "No summary" in summary:
# # #         print(f"📥 Fetching full text for {current_node}...")
# # #         try:
# # #             # We need the original filename to download
# # #             original_file = final_node_data.get("original_file")
# # #             bucket = storage_client.bucket(CLEAN_BUCKET)
# # #             blob = bucket.blob(original_file)
# # #             full_text = blob.download_as_text()
# # #             context_text = full_text[:30000] # Cap at 30k chars for LLM safety
# # #         except Exception as e:
# # #             print(f"⚠️ Failed to download text: {e}")
# # #             context_text = "Full text unavailable. Relying on graph metadata."

# # #     # STEP 4: Answer Generation
# # #     client = genai.Client(
# # #         vertexai=True, 
# # #         project=os.environ.get("PROJECT_ID"), 
# # #         location="us-central1"
# # #     )

# # #     final_prompt = f"""
# # #     You are a Legal Expert Agent.
# # #     Answer the user's question based strictly on the provided 'Current Truth' document.
    
# # #     The system started at an older document and traversed the legal graph to find this latest version.
    
# # #     User Question: {user_question}
    
# # #     --- CURRENT TRUTH DOCUMENT ({current_node}) ---
# # #     {context_text}
# # #     -----------------------------------------------
    
# # #     If the text contains the answer, provide it with specific numbers/dates.
# # #     If not, state that the document does not contain the specific details.
# # #     """
    
# # #     answer = client.models.generate_content(model="gemini-2.0-flash", contents=final_prompt)
    
# # #     return {
# # #         "answer": answer.text,
# # #         "source_lineage": path_taken,
# # #         "hops": len(path_taken) - 1,
# # #         "final_doc_used": current_node
# # #     }

# # import functions_framework
# # import pickle
# # import networkx as nx
# # import os
# # from google.cloud import storage
# # from google import genai

# # storage_client = storage.Client()
# # GRAPH_FILE_NAME = "legal_knowledge_graph.pickle"
# # CLEAN_BUCKET = os.environ.get("CLEAN_BUCKET_NAME", "legal_clean_contracts_bucket")

# # # --- 1. ROOT SELECTOR ---
# # def get_root_node(G, user_question):
# #     client = genai.Client(vertexai=True, project=os.environ.get("PROJECT_ID"), location="us-central1")
# #     q_upper = user_question.upper()
# #     ticker = next((t for t in ["LCID", "TSLA", "RIVN", "F", "GM"] if t in q_upper), "LCID")
    
# #     # We find all possible starting points for this company
# #     candidates = [n for n in G.nodes() if n.startswith(ticker)]
# #     candidates.sort() # Oldest first

# #     prompt = f"Question: {user_question}\nPick the ID of the OLDEST original agreement for this topic: {candidates}. Return ONLY the ID."
# #     response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
# #     return response.text.strip()

# # # --- 2. SEMANTIC TRAVERSAL (The "Better Way") ---
# # def agentic_traversal(G, bucket, root_id, user_question):
# #     """
# #     Examines every branch of history to find the 'Story' that matches the question.
# #     """
# #     client = genai.Client(vertexai=True, project=os.environ.get("PROJECT_ID"), location="us-central1")
# #     path = [root_id]
# #     curr = root_id

# #     while True:
# #         # Find all amendments/predecessors
# #         preds = list(G.predecessors(curr))
# #         valid_options = [p for p in preds if G.edges[p, curr].get("relation") in ["AMENDS", "SUPERSEDES"]]
        
# #         if not valid_options:
# #             break

# #         # If there's a choice, we look at the content of each option
# #         if len(valid_options) > 1:
# #             option_details = []
# #             for opt in valid_options:
# #                 snippet = bucket.blob(G.nodes[opt].get("original_file")).download_as_text()[:1000]
# #                 option_details.append(f"ID: {opt}\nContent: {snippet}\n---")
            
# #             prompt = f"Query: {user_question}\n\nCurrently at: {curr}\nWhich of these next steps matches the TOPIC?:\n{option_details}\nReturn ONLY the ID."
# #             resp = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
# #             curr = resp.text.strip()
# #         else:
# #             curr = valid_options[0]
            
# #         path.append(curr)
# #     return path

# # # --- 3. MAIN FUNCTION ---
# # @functions_framework.http
# # def query_legal_graph(request):
# #     req = request.get_json(silent=True)
# #     question = req.get('question')
# #     bucket = storage_client.bucket(CLEAN_BUCKET)
# #     G = pickle.loads(bucket.blob(GRAPH_FILE_NAME).download_as_bytes())

# #     # Step 1: Find the Root
# #     root_id = get_root_node(G, question)
    
# #     # Step 2: Follow the correct 'Story' (Pathfinding)
# #     lineage = agentic_traversal(G, bucket, root_id, question)

# #     # Step 3: Accumulate full text from the correct lineage
# #     # context = ""
# #     # for node in lineage:
# #     #     text = bucket.blob(G.nodes[node].get("original_file")).download_as_text()
# #     #     context += f"\n--- VERSION: {node} ---\n{text[:20000]}"
# #     # --- ACCUMULATIVE CONTEXT (Hardened) ---
# #     full_context = ""
# #     for node_id in lineage:
# #         node_data = G.nodes[node_id]
# #         file_path = node_data.get("original_file")
        
# #         # 1. Check if the node is a 'Ghost Node' (No file path)
# #         if file_path is None:
# #             print(f"⚠️ Skipping download for Ghost Node: {node_id}")
# #             # Fallback: Just provide the ID so the LLM knows it exists in history
# #             full_context += f"\n\n--- DOCUMENT VERSION: {node_id} ---\n[Full text not yet ingested. This document exists as a reference in the legal chain.]\n"
# #             continue

# #         # 2. If file_path exists, try to download
# #         try:
# #             print(f"📥 Fetching text for: {node_id}")
# #             raw_text = bucket.blob(file_path).download_as_text()
            
# #             # Use the first 20k characters to stay within context limits
# #             full_context += f"\n\n--- DOCUMENT VERSION: {node_id} ---\n"
# #             full_context += raw_text[:20000] 
# #         except Exception as e:
# #             print(f"❌ Failed to download {file_path}: {e}")
# #             full_context += f"\n[Error loading text for {node_id}]"


# #     # Step 4: Final Synthesis
# #     client = genai.Client(vertexai=True, project=os.environ.get("PROJECT_ID"), location="us-central1")
# #     ans = client.models.generate_content(model="gemini-2.0-flash", contents=f"Question: {question}\nContext:\n{full_context}")
    
# #     return {"answer": ans.text, "hops": len(lineage)-1, "lineage": lineage}

# import functions_framework
# import pickle
# import networkx as nx
# import os
# import re
# from google.cloud import storage
# from google import genai

# # --- GLOBAL CONFIGURATION ---
# storage_client = storage.Client()
# GRAPH_FILE_NAME = "legal_knowledge_graph.pickle"
# CLEAN_BUCKET = os.environ.get("CLEAN_BUCKET_NAME", "legal_clean_contracts_bucket")

# def load_graph():
#     bucket = storage_client.bucket(CLEAN_BUCKET)
#     blob = bucket.blob(GRAPH_FILE_NAME)
#     return pickle.loads(blob.download_as_bytes())

# # --- 1. THE "ROOT-SEEKER" WITH TOPIC DISAMBIGUATION ---
# def get_best_starting_node(G, user_question):
#     """
#     Identifies the single ROOT document ID. 
#     Uses a regex to ensure a string is returned, preventing NetworkXErrors.
#     """
#     client = genai.Client(vertexai=True, project=os.environ.get("PROJECT_ID"), location="us-central1")
    
#     # Identify Ticker to narrow search
#     q_upper = user_question.upper()
#     ticker = next((t for t in ["LCID", "TSLA", "RIVN", "F", "GM"] if t in q_upper), "LCID")
    
#     # Get all candidate nodes + their summaries for the LLM to judge topic
#     candidates = []
#     for node_id in G.nodes():
#         if node_id.startswith(ticker):
#             summary = G.nodes[node_id].get("summary", "No summary available")
#             candidates.append(f"ID: {node_id} | TOPIC: {summary[:150]}")
    
#     candidates.sort() # Put oldest at the top

#     prompt = f"""
#     You are a Legal Librarian. The user asked: '{user_question}'
    
#     We have multiple legal 'chains' (e.g., Investment vs. Employment Plans).
#     Pick the ID of the ORIGINAL/ROOT document that matches the TOPIC.
    
#     - For 'Shares' or 'Ayar', pick the oldest Investment/Subscription agreement.
#     - For 'Options' or 'Incentive Plan', pick the oldest Plan.
    
#     Candidate Documents:
#     {candidates}
    
#     Return ONLY the single Document ID (e.g., {ticker}_2021-01-01_CONTRACT).
#     """
    
#     response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
#     raw_output = response.text.strip()
    
#     # REGEX FIX: Extract the ID string even if the LLM returns a list or markdown
#     match = re.search(r'[A-Z]+_\d{4}-\d{2}-\d{2}_CONTRACT', raw_output)
#     if match:
#         return match.group(0)
#     return "NONE"

# # --- 2. TRAVERSAL ENGINE ---
# def resolve_lineage(G, start_node):
#     path = [start_node]
#     curr = start_node
#     while True:
#         preds = list(G.predecessors(curr))
#         # Find newer docs pointing back to current (AMENDS relationship)
#         valid_updates = [p for p in preds if G.edges[p, curr].get("relation") in ["AMENDS", "SUPERSEDES", "REPLACES"]]
#         if not valid_updates:
#             break
#         valid_updates.sort() # Follow chronological order
#         curr = valid_updates[0]
#         path.append(curr)
#     return path

# # --- 3. MAIN SOLVER FUNCTION ---
# @functions_framework.http
# def query_legal_graph(request):
#     req_json = request.get_json(silent=True)
#     user_question = req_json.get('question', '')
    
#     G = load_graph()
#     bucket = storage_client.bucket(CLEAN_BUCKET)

#     # STEP A: Identify Start Node
#     root_id = get_best_starting_node(G, user_question)
    
#     # STEP B: Check for broad "Discovery Mode" or Errors
#     # If the question is broad or no root is found, return all company nodes
#     if root_id == "NONE" or root_id not in G:
#         ticker = next((t for t in ["LCID", "TSLA", "RIVN", "F", "GM"] if t in user_question.upper()), "LCID")
#         all_related = sorted([n for n in G.nodes() if n.startswith(ticker)])
#         print(f"📡 Discovery Mode Active. All nodes for {ticker}: {all_related}")
        
#         return {
#             "answer": f"I couldn't identify a single chain. Here are all chronological documents for {ticker} found in the graph.",
#             "hops": 0,
#             "source_lineage": all_related,
#             "mode": "discovery"
#         }

#     # STEP C: Traverse the specific chain (Precision Mode)
#     lineage_path = resolve_lineage(G, root_id)
#     print(f"🛤️ Path Traversed: {' -> '.join(lineage_path)}")

#     # STEP D: Accumulate Context (with Ghost Node Safety)
#     full_context = ""
#     for node_id in lineage_path:
#         node_data = G.nodes[node_id]
#         file_path = node_data.get("original_file")
        
#         if file_path:
#             try:
#                 raw_text = bucket.blob(file_path).download_as_text()
#                 full_context += f"\n\n--- DOCUMENT: {node_id} ---\n{raw_text[:20000]}"
#             except Exception:
#                 full_context += f"\n[Error loading text for {node_id}]"
#         else:
#             # Handle Ghost Nodes (Reference exists, but file doesn't)
#             full_context += f"\n\n--- DOCUMENT: {node_id} ---\n[Summary Only]: {node_data.get('summary', 'No summary available.')}"

#     # STEP E: Synthesis
#     client = genai.Client(vertexai=True, project=os.environ.get("PROJECT_ID"), location="us-central1")
#     final_prompt = f"""
#     Answer the user's question using the provided chronological document lineage.
#     Newer documents (bottom) override older ones (top).
    
#     Question: {user_question}
#     Lineage Path: {' -> '.join(lineage_path)}
    
#     Context:
#     {full_context}
#     """
    
#     response = client.models.generate_content(model="gemini-2.0-flash", contents=final_prompt)
    
#     return {
#         "answer": response.text,
#         "hops": len(lineage_path) - 1,
#         "source_lineage": lineage_path,
#         "mode": "precision"
#     }

import functions_framework
import pickle
import networkx as nx
import os
import re
from google.cloud import storage
from google import genai

# --- GLOBAL CONFIGURATION ---
storage_client = storage.Client()
GRAPH_FILE_NAME = "legal_knowledge_graph.pickle"
CLEAN_BUCKET = os.environ.get("CLEAN_BUCKET_NAME", "legal_clean_contracts_bucket")

def load_graph():
    bucket = storage_client.bucket(CLEAN_BUCKET)
    blob = bucket.blob(GRAPH_FILE_NAME)
    return pickle.loads(blob.download_as_bytes())

# --- 1. THE HYBRID SELECTOR (Handles Chains & Siblings) ---
def get_relevant_nodes_for_topic(G, user_question):
    """
    Identifies all relevant ROOT nodes. 
    Handles 'Compare' queries by returning multiple roots if necessary.
    """
    client = genai.Client(vertexai=True, project=os.environ.get("PROJECT_ID"), location="us-central1")
    
    # Identify Ticker
    q_upper = user_question.upper()
    ticker = next((t for t in ["LCID", "TSLA", "RIVN", "F", "GM"] if t in q_upper), None)
    
    if not ticker:
        return []

    # Gather candidates for the specific company
    candidates = []
    for node_id in G.nodes():
        if node_id.startswith(ticker):
            summary = G.nodes[node_id].get("summary", "Legal agreement or annual metric exhibit")
            candidates.append(f"ID: {node_id} | ABOUT: {summary[:150]}")
    
    candidates.sort()

    prompt = f"""
    You are a Legal Graph Scout. User Question: '{user_question}'
    
    TASK:
    1. If the question asks to COMPARE multiple years, list ALL sections, or asks about a broad topic, 
       return a COMMA-SEPARATED list of all relevant Root IDs.
    2. If it is a specific data question, return just the single oldest ROOT ID for that specific chain.
    
    Candidates:
    {candidates}
    
    Return IDs ONLY (e.g., ID1, ID2). Do not include extra text.
    """
    
    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    raw_output = response.text.strip()
    
    # Regex to extract valid IDs from the potentially messy LLM output
    found_ids = re.findall(r'[A-Z0-9]+_\d{4}-\d{2}-\d{2}_CONTRACT', raw_output)
    return [rid for rid in found_ids if rid in G]

# --- 2. MULTI-BRANCH TRAVERSAL ENGINE ---
def resolve_multi_lineage(G, root_ids):
    """
    Follows every root to its latest amendment, tracking hops per branch.
    """
    lineage_map = {}
    all_unique_nodes = []
    
    for root in root_ids:
        path = [root]
        curr = root
        branch_hops = 0
        
        while True:
            preds = list(G.predecessors(curr))
            # Follow 'AMENDS', 'SUPERSEDES', or 'REPLACES' relations
            valid_updates = [p for p in preds if G.edges[p, curr].get("relation") in ["AMENDS", "SUPERSEDES", "REPLACES"]]
            
            if not valid_updates:
                break
            
            valid_updates.sort() # Forward chronological order
            curr = valid_updates[0]
            path.append(curr)
            branch_hops += 1
            
        lineage_map[root] = {"path": path, "hops": branch_hops}
        all_unique_nodes.extend(path)

    # Flatten nodes while preserving unique order
    flat_path = list(dict.fromkeys(all_unique_nodes))
    total_aggregate_hops = sum(item["hops"] for item in lineage_map.values())
    max_depth = max(item["hops"] for item in lineage_map.values()) if lineage_map else 0

    return lineage_map, flat_path, total_aggregate_hops, max_depth

# --- 3. MAIN CLOUD FUNCTION ---
@functions_framework.http
def query_legal_graph(request):
    req_json = request.get_json(silent=True)
    user_question = req_json.get('question', '')
    
    G = load_graph()
    bucket = storage_client.bucket(CLEAN_BUCKET)

    # 1. Selection
    root_ids = get_relevant_nodes_for_topic(G, user_question)
    if not root_ids:
        return {"error": "No relevant documents found."}, 404

    # 2. Multi-Path Traversal
    lineage_map, flat_path, total_hops, max_depth = resolve_multi_lineage(G, root_ids)

    # 3. Context Accumulation
    full_context = ""
    for node_id in flat_path:
        node_data = G.nodes[node_id]
        file_path = node_data.get("original_file")
        if file_path:
            try:
                raw_text = bucket.blob(file_path).download_as_text()
                full_context += f"\n\n--- DOCUMENT: {node_id} ---\n{raw_text[:20000]}"
            except Exception:
                full_context += f"\n[Document {node_id} text load error]"
        else:
            full_context += f"\n\n--- DOCUMENT: {node_id} (Ref) ---\n{node_data.get('summary', '')}"

    # 4. Final Answer Generation
    client = genai.Client(vertexai=True, project=os.environ.get("PROJECT_ID"), location="us-central1")
    response = client.models.generate_content(
        model="gemini-2.0-flash", 
        contents=f"User Question: {user_question}\n\nLegal History Context:\n{full_context}"
    )

    return {
        "answer": response.text,
        "metrics": {
            "total_aggregate_hops": total_hops,
            "max_traversal_depth": max_depth,
            "branches_explored": len(root_ids)
        },
        "lineage_details": lineage_map,
        "processed_nodes": flat_path
    }