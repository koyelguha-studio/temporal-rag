# Running the CFR Pipeline

To run the pipeline and verify that data flows correctly from govinfo.gov down to the final Knowledge Graph, follow these steps in order. 

Make sure you have your virtual environment active and authenticated to Google Cloud:
```bash
source .venv/bin/activate
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/key.json" # If running locally and not on GCE
```

## Step 1: Download the Raw CFR XML Data
This script connects to the GovInfo API and streams the XML documents for exactly what you request into the raw bucket (`legal_raw_contracts_bucket`).

**How to run:**
1. Open `cfr-downloader/main.py`.
2. Scroll to the bottom and adjust the `target_years` (e.g. `2020` to `2025`) and `target_titles` (e.g. `["12"]`). *Note: Downloading 25 years of all titles will take a massive amount of storage, so start small for verification.*
3. Run the script:
   ```bash
   python ctr-downloader/main.py
   ```
4. **Verification**: Go to your Google Cloud Console > Cloud Storage and verify that `legal_raw_contracts_bucket` now contains `raw_cfr/.../` paths with `.xml` files.

---

## Step 2: Preprocess the XML into Clean Text
The `cfr-preprocessor` is designed as a Google Cloud Function that triggers automatically when a file lands in the `legal_raw_contracts_bucket`.

**How to run:**
1. **Cloud deployment:** Deploy the function to GCP, setting the trigger to `google.storage.object.finalize` on the `legal_raw_contracts_bucket`.
   ```bash
   cd cfr-preprocessor
   gcloud functions deploy process_cfr_submission \
     --runtime python310 \
     --trigger-resource legal_raw_contracts_bucket \
     --trigger-event google.storage.object.finalize
   ```
2. **Verification**: After it runs, go to `legal_clean_contracts_bucket`. You should see `.txt` files named like `Title-12_2024-01-01_CFR-PART_CFR-2024-title12-vol1.txt`. Open one to confirm it contains the `SOURCE METADATA` header and clean regulatory text without XML tags.

---

## Step 3: Build the Knowledge Graph
The `builder` is also a Cloud Function that triggers when the preprocessor deposits the clean `.txt` files into the `legal_clean_contracts_bucket`.

**How to run:**
1. **Cloud deployment:** Deploy the builder function to GCP using the clean bucket as its trigger.
   ```bash
   cd builder
   gcloud functions deploy build_knowledge_graph \
     --runtime python310 \
     --trigger-resource legal_clean_contracts_bucket \
     --trigger-event google.storage.object.finalize
   ```
2. **Verification**: 
   - Check the Logs via Google Cloud Logs Explorer for the `build_knowledge_graph` function. Look for logs saying `+ Node: TITLE-12_2024-01-01_CFR-PART` and `🔗 Link: [id] -> [target]`.
   - Download the resulting graph blob locally:
     ```bash
     gcloud storage cp gs://legal_clean_contracts_bucket/legal_knowledge_graph.pickle .
     ```
   - Inspect the file by loading it with NetworkX in python:
     ```python
     import pickle, networkx as nx
     G = pickle.load(open('legal_knowledge_graph.pickle', 'rb'))
     print("Nodes:", len(G.nodes()))
     print("Edges:", len(G.edges()))
     ```
