import os
from sec_edgar_downloader import Downloader
from google.cloud import storage

GCS_BUCKET_NAME = "legal_raw_contracts_bucket"
LOCAL_DOWNLOAD_PATH = "./sec-edgar-filings"


dl = Downloader("MyCompany", "myemail@company.com", LOCAL_DOWNLOAD_PATH)
storage_client = storage.Client()

def upload_to_gcs(local_path, bucket_name):
    """Recursively uploads a local directory to GCS."""
    bucket = storage_client.bucket(bucket_name)
    
    for root, dirs, files in os.walk(local_path):
        for file in files:
            local_file = os.path.join(root, file)
            # Create a path for GCS that mirrors the local structure
            remote_path = os.path.relpath(local_file, local_path)
            blob = bucket.blob(f"raw_contracts/{remote_path}")
            
            print(f"📤 Uploading {file} to gs://{bucket_name}/raw_contracts/...")
            blob.upload_from_filename(local_file)

# 2. THE DOWNLOAD FLOW
tickers = ["TSLA", "RIVN", "LCID", "F", "GM"]

for ticker in tickers:
    print("************************")
    print(f"Processing {ticker}...")
    # A. 8-K (Current Reports): The source of Amendments
    # We only want the *text* of Exhibit 10s attached to 8-Ks
    
    # the limit is based on types of reports like current, yearly or quarterly. 
    dl.get("8-K", ticker, limit=50, include_amends=True)
    
    # B. 10-K (Annual Reports): The source of Base Agreements
    dl.get("10-K", ticker, limit=5, include_amends=True)

    # C. 10-Q (Quarterly): Often contains mid-year updates to credit lines
    dl.get("10-Q", ticker, limit=10)
print("✅ Download Complete. Now run the Refinery.")
print("************************")

# 3. SYNC TO CLOUD
if os.path.exists(LOCAL_DOWNLOAD_PATH):
    print("\n--- Syncing Local Files to GCP Storage ---")
    upload_to_gcs(LOCAL_DOWNLOAD_PATH, GCS_BUCKET_NAME)
    print("✅ Done. Your real SEC data is now in GCS.")
else:
    print("❌ Error: Download folder not found. Check SEC rate limits or ticker symbols.")
