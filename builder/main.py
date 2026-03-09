import re, pickle, time, os, unicodedata
import networkx as nx
from google.cloud import storage
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional

# --- CONFIGURATION ---
PROJECT_ID = "playground-koyel"
CLEAN_BUCKET = "legal_clean_contracts_bucket"
LOCAL_GRAPH_FILE = "local_cfr_graph.pickle"
LOCATION = "us-central1"
FAILED_LOG_DIR = "failed_extractions"

# Ensure log directory exists
os.makedirs(FAILED_LOG_DIR, exist_ok=True)

storage_client = storage.Client()

class ClauseReference(BaseModel):
    target_id: str 
    relationship: str 
    evidence: str

class SectionSkeleton(BaseModel):
    node_id: str 
    name: str
    references: List[ClauseReference] = Field(default_factory=list)

class SubGraphBatch(BaseModel):
    part_id: str 
    part_name: str
    sections: List[SectionSkeleton]

def sanitize_text(text: str) -> str:
    """Removes mojibake, control characters, and the § symbol."""
    # Normalize unicode (turns fancy quotes into straight quotes, etc.)
    text = unicodedata.normalize('NFKC', text)
    
    # Explicitly remove the section symbol §
    text = text.replace('§', '')
    
    # Remove non-printable control characters
    return "".join(ch for ch in text if unicodedata.category(ch)[0] != "C").strip()

def extract_composite_header(header_text: str, tags: list) -> str:
    """
    Scans the header for a list of custom tags and combines their values.
    Example tags: ['#####DATE', '#####REVISED', '#####TITLE', '#####AGENCY']
    """
    clean_header = sanitize_text(header_text)
    captured_metadata = []

    for tag in tags:
        # Regex Logic:
        # rf"{tag}" -> Start at your tag (e.g., ##### THISTITL)
        # \s* -> Eat any whitespace after the tag
        # (.*?) -> Capture everything non-greedily
        # (?=#|$) -> STOP as soon as you see a '#' OR the end of the string
        pattern = rf"{tag}\s*(.*?)(?=#|$)"
        
        match = re.search(pattern, clean_header, re.DOTALL | re.IGNORECASE)
        
        if match:
            content = match.group(1).strip()
            if content:
                label = tag.replace('#', '').strip()
                captured_metadata.append(f"[{label}]: {content}")

    return "\n\n".join(captured_metadata)

class CFRAgenticAtomicOrchestrator:
    def __init__(self):
        self.client = genai.Client(vertexai=True)
        self.G = self.init_graph()

    def init_graph(self):
        if os.path.exists(LOCAL_GRAPH_FILE):
            print(f"💾 Resuming from local graph: {LOCAL_GRAPH_FILE}")
            with open(LOCAL_GRAPH_FILE, "rb") as f: return pickle.load(f)
        return nx.DiGraph()

    # def process_archive(self):
    #     blobs = list(storage_client.list_blobs(CLEAN_BUCKET, prefix="CFR_sample/"))
    #     blobs.sort(key=lambda x: x.name)

    #     for blob in blobs:
    #         if not blob.name.endswith(".txt"): continue
            
    #         print(f"\n🚀 Volume: {blob.name}")
    #         year = re.search(r'(\d{4})', blob.name).group(1) if re.search(r'(\d{4})', blob.name) else "2001"
            
    #         full_text = blob.download_as_text()
    #         parts = re.split(r'(?=#### SECTION)', full_text)
            
    #         # Use broader header context to ensure Topic Hubs are accurate
    #         header_context = sanitize_text(parts[0]) 
    #         sections = parts[1:]
            
    #         print(f"✅ {len(sections)} sections found. Processing without truncation...")

    #         for idx, sec_raw in enumerate(sections):
    #             # NO TRUNCATION: Send the full section. 
    #             # Flash 2.5 can handle 1M tokens; 8000 chars was a fraction of its power.
    #             clean_sec = sanitize_text(sec_raw)
                
    #             # Dynamic Instruction: Forces Gemini to be exhaustive
    #             prompt_directive = (
    #                 f"You are a specialized Legal Knowledge Graph Extractor for the CFR Year {year}. "
    #                 "Analyze the provided TEXT and its CONTEXT. "
    #                 "1. Identify the Parent PART/SUBPART. "
    #                 "2. Extract EVERY SINGLE cross-reference, citation, or superseding mention. "
    #                 "3. Do not summarize. Do not skip references in long lists."
    #             )
                
    #             input_payload = f"{prompt_directive}\n\nCONTEXT:\n{header_context}\n\nTEXT:\n{clean_sec}"
                
    #             print(f"   ∟ {idx+1}/{len(sections)} ({len(input_payload)} chars)...", end="", flush=True)

    #             success = False
    #             for attempt in range(3):
    #                 try:
    #                     # Adaptive Timeout: Longer for bigger sections
    #                     timeout_val = 120.0 if len(input_payload) < 50000 else 400.0
                        
    #                     # Refresh client/config to apply dynamic timeout
    #                     config = types.GenerateContentConfig(
    #                         response_mime_type="application/json",
    #                         response_schema=SubGraphBatch,
    #                         temperature=0.0
    #                     )

    #                     time.sleep(1.0 + (attempt * 2)) 
    #                     contents = [
    #                         types.Content(
    #                         role="user",
    #                         parts=[
    #                             types.Part.from_text(text=f"""{input_payload}""")
    #                         ]
    #                         ),
    #                     ]
    #                     response = self.client.models.generate_content(
    #                         model="gemini-2.5-flash",
    #                         contents=contents,
    #                         config=config
    #                     )
                        
    #                     if response.parsed:
    #                         # CRITICAL: We pass 'sec_raw' (the original UNTOUCHED text)
    #                         # to the graph, ensuring 100% data fidelity.
    #                         self.stitch(response.parsed, sec_raw, year)
    #                         print(" ✅", end="")
    #                         success = True
    #                         break

    #                 except Exception as e:
    #                     if "429" in str(e):
    #                         time.sleep(30)
    #                     else:
    #                         print(f" ⚠️ {str(e)}...", end="")

    #             if idx % 10 == 0:
    #                 with open(LOCAL_GRAPH_FILE, "wb") as f: pickle.dump(self.G, f)
            
    #         print("\n🏁 Volume Complete.")

    # def process_archive(self):
    #     blobs = list(storage_client.list_blobs(CLEAN_BUCKET, prefix="CFR_sample/"))
    #     blobs.sort(key=lambda x: x.name)

    #     for blob in blobs:
    #         if not blob.name.endswith(".txt"): continue
            
    #         print(f"\n🚀 Volume: {blob.name}")
    #         year = re.search(r'(\d{4})', blob.name).group(1) if re.search(r'(\d{4})', blob.name) else "2001"
            
    #         full_text = blob.download_as_text()
    #         parts = re.split(r'(?=#### SECTION)', full_text)
    #         header_context = sanitize_text(parts[0]) 
    #         sections = parts[1:]
            
    #         print(f"✅ {len(sections)} sections found. Adaptive Processing Enabled.")

    #         for idx, sec_raw in enumerate(sections):
    #             # 1. TOKEN SAFETY CHECK (Approx 1 token ~= 4 chars)
    #             # If section > 3.5M chars, it's definitely over the 1M token limit.
    #             print(f"Section length:", len(sec_raw))
    #             if len(sec_raw) > 3500000:
    #                 print(f"   ∟ {idx+1}/{len(sections)} 🧩 MONSTER SECTION ({len(sec_raw)} chars). Chunking...")
    #                 self.process_monster_section(sec_raw, header_context, year)
    #             else:
    #                 # Normal processing for standard sections
    #                 self.execute_extraction(sec_raw, header_context, year, idx, len(sections))

    # def process_monster_section(self, sec_raw, header, year):
    #     """Splits a massive section into 3MB chunks with 5k char overlap."""
    #     chunk_size = 3000000  # ~750k tokens
    #     overlap = 5000
        
    #     # Extract the specific section title to keep context high
    #     title_match = re.search(r'#### SECTION\s+.*?\n(.*?)\n', sec_raw)
    #     sec_title = title_match.group(1) if title_match else "Unknown Section"

    #     start = 0
    #     chunk_idx = 1
    #     while start < len(sec_raw):
    #         end = start + chunk_size
    #         chunk_text = sec_raw[start:end]
            
    #         # Label the chunk so Gemini knows it's a partial view
    #         chunk_context = f"{header}\nSECTION TITLE: {sec_title}\n(Part {chunk_idx} of this section)"
            
    #         print(f"      ∟ Sub-chunk {chunk_idx}...", end="", flush=True)
    #         self.execute_extraction(chunk_text, chunk_context, year, f"{chunk_idx}(M)", "Sub")
            
    #         start += (chunk_size - overlap)
    #         chunk_idx += 1

    # def execute_extraction(self, text, context, year, idx, total):
    #     """Standard API call logic moved to a reusable method."""
    #     clean_sec = sanitize_text(text)
    #     prompt_directive = (
    #         f"You are a specialized Legal Knowledge Graph Extractor for the CFR Year {year}. "
    #         "Extract EVERY cross-reference. If this text is a continuation, focus on links found here."
    #     )
    #     input_payload = f"{prompt_directive}\n\nCONTEXT:\n{context}\n\nTEXT:\n{clean_sec}"
        
    #     # Adaptive Timeout based on payload size
    #     timeout = 40.0 if len(text) > 1000000 else 10.0
        
    #     success = False
    #     for attempt in range(3):
    #         try:
    #             time.sleep(1.0 + (attempt * 2))
    #             contents = [
    #                         types.Content(
    #                         role="user",
    #                         parts=[
    #                             types.Part.from_text(text=f"""{input_payload}""")
    #                         ]
    #                         ),
    #                     ]
    #             response = self.client.models.generate_content(
    #                 model="gemini-2.5-flash",
    #                 contents=contents,
    #                 config=types.GenerateContentConfig(
    #                     response_mime_type="application/json",
    #                     response_schema=SubGraphBatch,
    #                     temperature=0.0
    #                 )
    #             )
    #             if response.parsed:
    #                 # Stitching into the SAME graph node (the ID remains the same)
    #                 # so citations from Chunk 1 and Chunk 2 merge naturally.
    #                 self.stitch(response.parsed, text, year)
    #                 print(" ✅", end="", flush=True)
    #                 success = True
    #                 break
    #         except Exception as e:
    #             print(f" ⚠️ {str(e)[:40]}", end="")
        
    #     if not success: print(" ❌", end="")

    def log_failure(self, text, year, idx, chunk_id=None):
        """Saves problematic text to disk for manual review."""
        filename = f"fail_{year}_sec_{idx}_chunk_{chunk_id}.txt" if chunk_id else f"fail_{year}_sec_{idx}.txt"
        path = os.path.join(FAILED_LOG_DIR, filename)
        with open(path, "w") as f:
            f.write(text)
        print(f" 📂 Saved failed text to {path}")

    def process_archive(self):
        target_tags = ['##### THISTITL', '###### REVISED', '######### DATE']
        storage_client = storage.Client()
        blobs = list(storage_client.list_blobs(CLEAN_BUCKET, prefix="CFR_sample/"))
        blobs.sort(key=lambda x: x.name)

        for blob in blobs:
            if not blob.name.endswith(".txt"): continue
            
            print(f"\n🚀 Volume: {blob.name}")
            year = re.search(r'(\d{4})', blob.name).group(1) if re.search(r'(\d{4})', blob.name) else "2002"
            
            # Catch GCS download errors
            try:
                full_text = blob.download_as_text()
            except Exception as e:
                print(f"❌ Failed to download {blob.name}: {e}")
                continue
            parts = re.split(r'(?=#### SECTION)', full_text)

            # Instead of the whole header, take only the 'tail' of it (the context)
            header_raw = sanitize_text(parts[0])
            # header_context = header_full[-10000:] if len(header_full) > 10000 else header_full
            header_context = extract_composite_header(header_raw, target_tags)
            print(f"HEADER: {header_context}")


            sections = parts[1:]
            
            print(f"✅ {len(sections)} sections found. Context slimmed to {len(header_context)} chars.")

            for idx, sec_raw in enumerate(sections):
                # Adaptive Threshold: > 3M chars (~750k tokens) triggers chunking
                try:
                    if len(sec_raw) > 3000000:
                        print(f"   ∟ {idx+1}/{len(sections)} 🧩 MONSTER DETECTED ({len(sec_raw)} chars)")
                        self.process_monster_section(sec_raw, header_context, year, idx+1)
                    else:
                        print(f"   ∟ {idx+1}/{len(sections)} ({len(sec_raw)} chars)... ", end="", flush=True)
                        success, error_msg = self.execute_extraction(sec_raw, header_context, year)
                        if success:
                            print("✅")
                        else:
                            print(f"❌ ERROR: {error_msg}")
                            self.log_failure(sec_raw, year, idx+1, error_msg=error_msg)
                except Exception as e:
                    # Catch unexpected logical crashes in the loop
                    print(f"💥 CRITICAL LOOP ERROR on Sec {idx+1}: {str(e)}")

                # Save the graph every 10 sections
                if idx % 10 == 0:
                    with open(LOCAL_GRAPH_FILE, "wb") as f: pickle.dump(self.G, f)
            
            # Final save after volume completion
            with open(LOCAL_GRAPH_FILE, "wb") as f: pickle.dump(self.G, f)

    def process_monster_section(self, sec_raw, header, year, sec_idx):
        """Splits massive sections into chunks to stay under 1M token limit."""
        chunk_size = 2500000 # Conservative 600k tokens to ensure response room
        overlap = 10000      # 10k overlap to catch split citations
        
        start = 0
        chunk_idx = 1
        while start < len(sec_raw):
            end = start + chunk_size
            chunk_text = sec_raw[start:end]
            
            sub_context = f"{header}\n(This is part {chunk_idx} of a very large section)"
            print(f"      ∟ Chunk {chunk_idx}... ", end="", flush=True)
            
            success = self.execute_extraction(chunk_text, sub_context, year)
            if success:
                print("✅")
            else:
                print("❌")
                self.log_failure(chunk_text, year, sec_idx, chunk_idx)
            
            start += (chunk_size - overlap)
            chunk_idx += 1

    def execute_extraction(self, text, context, year) -> bool:
        clean_sec = sanitize_text(text)
        prompt = (
            f"As a legal graph analyst, extract metadata for year {year}.\n"
            f"CONTEXT:\n{context}\n\nTEXT:\n{clean_sec}"
        )
        contents = [
                    types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=f"""{prompt}""")
                    ]
                    ),
                ]
        for attempt in range(3):
            try:
                # Add jitter sleep to avoid rate limiting
                time.sleep(2 * attempt)
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash", # Best speed/reliability
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=SubGraphBatch,
                        temperature=0.0
                    )
                )
                if response.parsed:
                    self.stitch(response.parsed, text, year)
                    return True, ""
            except Exception as e:
                last_error = str(e)
                # Catch 429 specifically for longer cooldown
                if "429" in last_error: time.sleep(30)
                continue
        return False, last_error

    def canonical_part_id(self, raw_id: str) -> str:
        """
        Standardizes Part IDs to a 'PART_X' format.
        Handles 'Pt. 1', 'Part 1', 'PT 1', and '1'.
        """
        if not raw_id:
            return "PART_UNKNOWN"
        
        # 1. Standardize string: uppercase and remove punctuation
        clean = raw_id.upper().replace(".", "").replace("PT", "PART").replace(" ", "")
        
        # 2. Extract digits only to rebuild canonical string
        match = re.search(r'(\d+)', clean)
        if match:
            return f"PART_{match.group(1)}"
        
        # Fallback to a sanitized version of the string if no digits found
        return f"PART_{re.sub(r'[^A-Z0-9]', '_', clean)}"

    def stitch(self, data: SubGraphBatch, raw_text: str, year: str):
        """
        Stitches extracted data into the global NetworkX graph with 
        canonical hub normalization and temporal sectioning.
        """
        # 1. Canonical Identity Hub (The Yellow Topic Node)
        p_id = self.canonical_part_id(data.part_id)
        p_name = data.part_name.strip().upper()
        
        if not self.G.has_node(p_id):
            self.G.add_node(p_id, name=p_name, level="Identity", type="Topic")
        else:
            # Update name if the incoming one is more descriptive/longer
            existing_name = self.G.nodes[p_id].get('name', '')
            if len(p_name) > len(existing_name):
                self.G.nodes[p_id]['name'] = p_name

        # 2. Process Sections (The Blue State Nodes)
        for sec in data.sections:
            # Extract clean numeric section ID (e.g., '24.1')
            s_num_match = re.search(r'(\d+\.\d+)', sec.node_id)
            s_num = s_num_match.group(1) if s_num_match else sec.node_id.upper().replace(" ", "_")
            
            # Temporal ID ensures SEC_24.1_2001 is distinct from SEC_24.1_2002
            s_id = f"SEC_{s_num}_{year}"
            
            self.G.add_node(
                s_id,
                name=sec.name,
                content=raw_text, # Full raw text preserved here
                year=year,
                level="State",
                type="Section"
            )
            
            # Hierarchical Link: Part -> Section
            self.G.add_edge(p_id, s_id, relation="CONTAINS")

            # 3. Agentic Edges (The Citations)
            for ref in sec.references:
                # Check if the reference target is a Part or a Section
                # We apply the same canonical logic to the target to ensure matching
                if "PART" in ref.target_id.upper() or "PT" in ref.target_id.upper():
                    t_id = self.canonical_part_id(ref.target_id)
                else:
                    t_id = ref.target_id.upper().replace(" ", "_").strip()
                
                # If target doesn't exist, create it as a 'Ghost' (Identity node)
                if not self.G.has_node(t_id):
                    self.G.add_node(t_id, level="Identity", type="Ghost", name="Pending Ingestion")
                
                # Add the relationship edge with evidence
                self.G.add_edge(s_id, t_id, relation=ref.relationship, evidence=ref.evidence)

if __name__ == "__main__":
    builder = CFRAgenticAtomicOrchestrator()
    builder.process_archive()