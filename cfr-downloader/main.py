import re
import requests
import xml.etree.ElementTree as ET
from google.cloud import storage

GCS_BUCKET_NAME = "legal_raw_contracts_bucket"
LOCAL_DOWNLOAD_PATH = "./cfr-raw-data"
SITEMAP_INDEX_URL = "https://www.govinfo.gov/sitemap/CFR_sitemap_index.xml"

storage_client = storage.Client()

def get_xml_urls_from_sitemaps(target_years, target_titles):
    """
    Crawls the sitemap index to find specific CFR XML links matching our target years and titles.
    """
    print(f"Fetching sitemap index from {SITEMAP_INDEX_URL}...")
    try:
        response = requests.get(SITEMAP_INDEX_URL, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error fetching sitemap index: {e}")
        return []

    # Parse sitemap index
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as e:
        print(f"❌ XML Parse Error in sitemap index: {e}")
        return []

    # Map XML namespace for parsing
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    
    yearly_sitemaps = []
    # e.g., <loc>https://www.govinfo.gov/sitemap/CFR_2024_sitemap.xml</loc>
    for sitemap in root.findall('sm:sitemap/sm:loc', ns):
        url = sitemap.text
        match = re.search(r'CFR_(\d{4})_sitemap\.xml', url)
        if match:
            year = match.group(1)
            if year in target_years:
                yearly_sitemaps.append(url)
                
    xml_download_urls = []
    
    for sitemap_url in yearly_sitemaps:
        print(f"Checking sitemap: {sitemap_url}")
        try:
            resp = requests.get(sitemap_url, timeout=10)
            resp.raise_for_status()
            sitemap_root = ET.fromstring(resp.content)
            
            # Extract URLs that match target titles
            # Example: https://www.govinfo.gov/app/details/CFR-2024-title12-vol1
            for loc in sitemap_root.findall('sm:url/sm:loc', ns):
                detail_url = loc.text
                match = re.search(r'CFR-(\d{4})-title(\d+)-vol\d+', detail_url)
                if match:
                    year = match.group(1)
                    title = match.group(2)
                    
                    if title in target_titles:
                        # Construct the bulk data API XML download URL directly
                        # Format: https://www.govinfo.gov/content/pkg/CFR-2024-title12-vol1/xml/CFR-2024-title12-vol1.xml
                        pkg_id = detail_url.split('/')[-1]
                        xml_url = f"https://www.govinfo.gov/content/pkg/{pkg_id}/xml/{pkg_id}.xml"
                        xml_download_urls.append((year, title, pkg_id, xml_url))

        except Exception as e:
            print(f"❌ Error processing sitemap {sitemap_url}: {e}")
            
    return xml_download_urls

def download_and_upload(xml_urls):
    """
    Downloads XML files and directly streams them into Google Cloud Storage
    """
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    
    # Ensure bucket exists
    if not bucket.exists():
        print(f"Bucket {GCS_BUCKET_NAME} does not exist. Creating it...")
        bucket.create(location="us-central1")
        
    for index, (year, title, pkg_id, url) in enumerate(xml_urls):
        print(f"[{index+1}/{len(xml_urls)}] Downloading {pkg_id}...")
        
        try:
            response = requests.get(url, stream=True, timeout=30)
            if response.status_code == 404:
                # Some CFR parts do not have XML available, only PDF/TEXT
                print(f"  ⏭️ Skipping {pkg_id} - XML format not available (404)")
                continue
                
            response.raise_for_status()
            
            # GCS Path: CFR/2024/Title-12/CFR-2024-title12-vol1.xml
            blob_path = f"raw_cfr/{year}/Title-{title}/{pkg_id}.xml"
            blob = bucket.blob(blob_path)
            
            print(f"  📤 Uploading to gs://{GCS_BUCKET_NAME}/{blob_path}...")
            
            # Force browser to download the file instead of trying to render large XMLs
            blob.content_disposition = f"attachment; filename={pkg_id}.xml"
            
            # Upload from memory to GCS without hitting local disk to save space
            blob.upload_from_string(response.content, content_type="application/xml")
            
        except Exception as e:
            print(f"  ❌ Error downloading/uploading {pkg_id}: {e}")

if __name__ == "__main__":
    print("🚀 Starting GovInfo CFR Bulk Downloader")
    
    # Generate requested years (2000-2025)
    target_years = [str(y) for y in range(2001, 2026)]
    
    # Target specific titles to limit scope (e.g. Title 12 is Banks and Banking, Title 17 is SEC)
    # The user didn't specify, so let's default to Title 12 for testing to avoid downloading Terabytes
    target_titles = ["12"] 
    
    print(f"Target Years: {target_years[0]} - {target_years[-1]}")
    print(f"Target Titles: {target_titles}")
    
    xml_urls = get_xml_urls_from_sitemaps(target_years, target_titles)
    
    print(f"\nFound {len(xml_urls)} XML files to process.")
    
    if xml_urls:
        download_and_upload(xml_urls)
    
    print("\n✅ Bulk Download Complete.")
