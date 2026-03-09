import re
import os
from google.cloud import storage
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
RAW_BUCKET_NAME = "legal_raw_contracts_bucket" 
RAW_PREFIX = "raw_cfr_2001/" # Root folder containing 2000, 2001, etc.
CLEAN_BUCKET_NAME = "legal_clean_contracts_bucket"
# CLEAN_BUCKET_NAME = "infinity_learn_poc"

storage_client = storage.Client()

def extract_structured_markdown(xml_content):
    """
    Parses XML into hierarchical Markdown to preserve Section/Part context.
    """
    soup = BeautifulSoup(xml_content, 'xml')
    lines = []
    
    # 1. Statutory Authority (For USC -> CFR Hops)
    for auth in soup.find_all('AUTH'):
        lines.append(f"STATUTORY_AUTHORITY: {auth.get_text().strip()}")

    # 2. Extract Body Hierarchy
    for element in soup.find_all(['TITLE', 'CHAPTER', 'PART', 'SECTION', 'P', 'THISTITL', 'REVISED', 'SUBJECT', 'CONTAINS', 'DATE']):
        if element.name == 'TITLE':
            lines.append(f"\n# {element.get_text().strip()}")
        elif element.name == 'CHAPTER':
            lines.append(f"\n## CHAPTER {element.get_text().strip()}")
        elif element.name == 'PART':
            num = element.find('EAR').get_text().strip() if element.find('EAR') else "N/A"
            lines.append(f"\n### PART {num}")
        elif element.name == 'SECTION':
            num = element.find('SECTNO').get_text().strip() if element.find('SECTNO') else "N/A"
            lines.append(f"\n#### SECTION {num}")
        elif element.name == 'THISTITL':
            lines.append(f"\n##### THISTITL {element.get_text().strip()}")
        elif element.name == 'REVISED':
            lines.append(f"\n###### REVISED {element.get_text().strip()}")
        elif element.name == 'SUBJECT':
            lines.append(f"\n####### SUBJECT {element.get_text().strip()}")
        elif element.name == 'CONTAINS':
            lines.append(f"\n######## CONTAINS {element.get_text().strip()}")
        elif element.name == 'DATE':
            lines.append(f"\n######### DATE {element.get_text().strip()}")
        elif element.name == 'P':
            text = element.get_text().strip()
            if text: lines.append(text)

    # 3. Temporal Change Log (The "Lineage Instructions")
    lsa_entries = [e.get_text().strip() for e in soup.find_all('ENTRY')]
    if lsa_entries:
        lines.append("\n=== TEMPORAL CHANGE LOG (LSA) ===")
        lines.extend([f"LSA_CHANGE: {entry}" for entry in lsa_entries])

    return "\n".join(lines)

def run_bulk_import():
    source_bucket = storage_client.bucket(RAW_BUCKET_NAME)
    clean_bucket = storage_client.bucket(CLEAN_BUCKET_NAME)
    
    # Iterate through all files in 'raw_cfr/'
    blobs = source_bucket.list_blobs(prefix=RAW_PREFIX)

    for blob in blobs:
        if not blob.name.endswith(".xml") or "title-12" not in blob.name.lower():
            continue

        print(f"⚙️ Processing: {blob.name}")
        
        # 1. Extract Year from Path
        year_match = re.search(r'/(\d{4})/', blob.name)
        year = year_match.group(1) if year_match else "UnknownYear"
        year = "2001" # Pre-processed for years 2001, 2002, 2003, 2004 and 2005 by changing it. 
        
        # 2. Guarantee Uniqueness by using the original filename
        original_filename = os.path.basename(blob.name).replace(".xml", "")
        
        try:
            raw_xml = blob.download_as_text()
            markdown_content = extract_structured_markdown(raw_xml)
            
            # 3. ORGANIZED PATH LOGIC
            # This creates folders: CFR/2000/, CFR/2001/, etc.
            # Filename example: CFR/2000/Y2000_CFR-2000-title12-vol1.txt
            clean_blob_name = f"CFR_sample/{year}/Y{year}_{original_filename}.txt"

            header = (
                f"IDENTITY: Title 12\n"
                f"YEAR: {year}\n"
                f"ORIGINAL_FILE: {original_filename}\n"
                f"{'='*40}\n\n"
            )
            
            clean_blob = clean_bucket.blob(clean_blob_name)
            clean_blob.upload_from_string(header + markdown_content)
            print(f"  ✅ Saved to Folder: {clean_blob_name}")

        except Exception as e:
            print(f"  ❌ Error: {e}")

if __name__ == "__main__":
    run_bulk_import()