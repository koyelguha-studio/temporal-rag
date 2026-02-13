import functions_framework
import re
from bs4 import BeautifulSoup
from google.cloud import storage
from dateutil import parser

# Initialize GCS client
storage_client = storage.Client()
CLEAN_BUCKET_NAME = "legal_clean_contracts_bucket"

# --- 1. ROBUST REGEX PATTERNS ---
# Matches <TYPE>EX-10.1, EX-10.2 but EXCLUDES EX-101 (XBRL)
# The \b ensures '10' is a whole word, followed by a dot.
EXHIBIT_PATTERN = re.compile(
    r'<DOCUMENT>\s*<TYPE>EX-10\.[0-9]+\b.*?\n(.*?)</DOCUMENT>', 
    re.DOTALL | re.IGNORECASE
)

DATE_PATTERNS = [
    re.compile(r"dated as of\s+([A-B][a-y]{2,8}\s+\d{1,2},\s+\d{4})", re.IGNORECASE),
    re.compile(r"entered into on\s+([A-B][a-y]{2,8}\s+\d{1,2},\s+\d{4})", re.IGNORECASE),
    re.compile(r"effective\s+([A-B][a-y]{2,8}\s+\d{1,2},\s+\d{4})", re.IGNORECASE),
]

# --- 2. HELPER FUNCTIONS ---

def extract_exhibit_from_submission(raw_content):
    """
    Slices the EX-10 document out of the giant full-submission.txt
    while ignoring EX-101 (XBRL) files.
    """
    # If it's a standalone text file (no SGML tags), return as is
    if "<DOCUMENT>" not in raw_content:
        return raw_content

    print("    -> Detected Full Submission. extracting specific Exhibit 10...")
    
    matches = EXHIBIT_PATTERN.findall(raw_content)
    
    if not matches:
        return None  # No valid Exhibit 10 found
    
    # Filter out any accidental XBRL/XML snippets
    valid_contracts = [m for m in matches if "xmlns:xbrli" not in m.lower()]
    
    if not valid_contracts:
        return None

    # Heuristic: The longest Exhibit 10 is usually the actual contract text
    # (Shorter ones are often certifications or schedules)
    longest_match = max(valid_contracts, key=len)
    
    # Extract text between <TEXT> tags if present
    text_match = re.search(r'<TEXT>(.*?)</TEXT>', longest_match, re.DOTALL | re.IGNORECASE)
    return text_match.group(1) if text_match else longest_match

def extract_date(text):
    """Finds the effective date of the contract for the Graph Node ID."""
    header = text[:5000]
    for pattern in DATE_PATTERNS:
        match = pattern.search(header)
        if match:
            try:
                date_str = match.group(1)
                dt = parser.parse(date_str, fuzzy=True)
                return dt.strftime("%Y-%m-%d")
            except:
                continue
    return None

def is_valid_contract(text):
    """Filters out noise (cover pages, empty exhibits)."""
    text_lower = text.lower()[:5000]
    
    # 1. Must contain contract keywords
    keywords = ["credit agreement", "amended and restated", "loan agreement", 
                "guarantee agreement", "pledge agreement", "indenture"]
    if not any(k in text_lower for k in keywords):
        return False
        
    # 2. Must have legal structure (Density Check)
    # A real contract has multiple Sections/Articles
    if text_lower.count("section") < 5 and text_lower.count("article") < 2:
        return False
        
    return True

# --- 3. CLOUD FUNCTION HANDLER ---

@functions_framework.cloud_event
def process_sec_submission(cloud_event):
    data = cloud_event.data
    bucket_name = data["bucket"]
    file_name = data["name"] # e.g. "sec-edgar-filings/TSLA/8-K/.../full-submission.txt"

    print(f"⚙️ Processing file: {file_name}")

    # A. Download raw file
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    
    try:
        raw_content = blob.download_as_text(encoding="utf-8")
    except Exception as e:
        print(f"❌ Error downloading {file_name}: {e}")
        return

    # B. Extract only the Material Contract (Ignore XBRL/101)
    content_to_process = extract_exhibit_from_submission(raw_content)
    
    if not content_to_process:
        print(f"⏭️ Skipping {file_name}: No valid Exhibit 10 found.")
        return

    # C. Clean HTML tags
    soup = BeautifulSoup(content_to_process, 'html.parser')
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()
    
    clean_text = soup.get_text(separator='\n\n')
    
    # D. Validation & Date Extraction
    if not is_valid_contract(clean_text):
        print(f"⏭️ Skipping {file_name}: Content does not look like a significant contract.")
        return

    eff_date = extract_date(clean_text)
    if not eff_date:
        print(f"⚠️ Warning: Could not find date in {file_name}. Skipping to maintain Graph integrity.")
        return

    # E. Construct Smart Filename for Graph Metadata
    # Attempt to extract Ticker from folder path: "sec-edgar-filings/TSLA/..."
    parts = file_name.split('/')
    ticker = parts[1] if len(parts) > 1 else "UNK"
    
    # Generate unique, descriptive name: TSLA_2023-01-05_Contract_ORIGINALNAME.txt
    # This helps the Graph Builder know exactly what node this is.
    safe_original_name = os.path.basename(file_name).replace(".txt", "").replace(".htm", "")
    new_blob_name = f"{ticker}_{eff_date}_Contract_{safe_original_name}.txt"

    # F. Upload to Clean Bucket
    clean_bucket = storage_client.bucket(CLEAN_BUCKET_NAME)
    clean_blob = clean_bucket.blob(new_blob_name)
    clean_blob.upload_from_string(clean_text)

    print(f"✅ Success: Refined and saved as {new_blob_name}")