# # import networkx as nx
# # import pickle
# # import matplotlib.pyplot as plt
# # import matplotlib.patches as mpatches
# # from google.cloud import storage
# # from datetime import datetime
# # import numpy as np

# # # --- CONFIGURATION ---
# # BUCKET_NAME = "legal_clean_contracts_bucket"
# # GRAPH_FILE = "legal_knowledge_graph.pickle"
# # TARGET_TICKER = "LCID"

# # def visualize_grouped_timeline():
# #     # 1. Load & Filter Data
# #     storage_client = storage.Client()
# #     full_G = pickle.loads(storage_client.bucket(BUCKET_NAME).blob(GRAPH_FILE).download_as_bytes())

# #     hero_nodes = [
# #         n for n in full_G.nodes() 
# #         if n.startswith(TARGET_TICKER) and full_G.degree(n) > 0
# #     ]
# #     G = full_G.subgraph(hero_nodes).copy()

# #     # 2. Setup Figure
# #     plt.figure(figsize=(16, 8), dpi=300)
# #     ax = plt.gca()

# #     # 3. Hierarchical Positioning Logic
# #     pos = {}
# #     nodes_by_year = {}
# #     min_year = 3000
# #     max_year = 0

# #     # Sort nodes and group by year
# #     sorted_nodes = sorted(hero_nodes, key=lambda x: x.split('_')[1])
    
# #     for node in sorted_nodes:
# #         date_str = node.split('_')[1]
# #         dt = datetime.strptime(date_str, "%Y-%m-%d")
# #         year = dt.year
        
# #         if year not in nodes_by_year:
# #             nodes_by_year[year] = []
# #         nodes_by_year[year].append(node)
        
# #         min_year = min(min_year, year)
# #         max_year = max(max_year, year)

# #     # Calculate X-Positions: Year Block + Month Offset
# #     # Space per year = 10 units. Month = 10/12 units.
# #     YEAR_WIDTH = 5.0
    
# #     for year in range(min_year, max_year + 1):
# #         if year not in nodes_by_year: continue
        
# #         # Draw Year Separator Line (Grid)
# #         plt.axvline(x=(year - min_year) * YEAR_WIDTH - 1, color='#bdc3c7', linestyle='--', alpha=0.3)
        
# #         # Label the Year at the bottom
# #         plt.text((year - min_year) * YEAR_WIDTH + (YEAR_WIDTH/2) - 1, -1.5, str(year), 
# #                  fontsize=14, fontweight='bold', color='#7f8c8d', ha='center')

# #         # Position nodes within this year's block
# #         for node in nodes_by_year[year]:
# #             dt = datetime.strptime(node.split('_')[1], "%Y-%m-%d")
            
# #             # X = Base Year Start + (Month / 12 * Width)
# #             # We add a little index jitter if multiple docs in same month
# #             month_offset = (dt.month / 12.0) * (YEAR_WIDTH - 1)
# #             x_pos = ((year - min_year) * YEAR_WIDTH) + month_offset
            
# #             # Y = 0 (Linear)
# #             pos[node] = (x_pos, 0)

# #     # 4. Draw Edges (Curved Hops)
# #     for u, v, data in G.edges(data=True):
# #         rel = data.get('relation', 'AMENDS')
# #         color = '#e74c3c' if 'SUPERSEDES' in rel else '#3498db'
        
# #         # Arc height depends on distance
# #         dist = abs(pos[u][0] - pos[v][0])
# #         rad = 0.3 if dist < 3 else 0.5
# #         if pos[u][0] > pos[v][0]: rad = -rad # Flip arc if backwards link
            
# #         ax.annotate("",
# #                     xy=pos[v], xycoords='data',
# #                     xytext=pos[u], textcoords='data',
# #                     arrowprops=dict(arrowstyle="->", color=color,
# #                                     connectionstyle=f"arc3,rad={-0.4}", # consistent upward curve
# #                                     lw=1.5, alpha=0.8))

# #     # 5. Draw Nodes
# #     node_colors = ['#2ecc71' if n == sorted_nodes[-1] else '#95a5a6' for n in sorted_nodes]
# #     nx.draw_networkx_nodes(G, pos, node_size=1200, node_color=node_colors, edgecolors='#34495e')

# #     # 6. Labels (Month-Day only)
# #     # Since Year is big at the bottom, node label can just be "Feb 22"
# #     labels = {}
# #     for node in G.nodes():
# #         dt = datetime.strptime(node.split('_')[1], "%Y-%m-%d")
# #         labels[node] = dt.strftime("%b\n%d") # e.g. "Feb 22"
        
# #     nx.draw_networkx_labels(G, pos, labels, font_size=8, font_weight='bold', font_color='black')

# #     # 7. Final Polish
# #     plt.title(f"Yearly clustered Contract Lineage: {TARGET_TICKER}", fontsize=16, pad=30)
# #     plt.ylim(-2, 3) # Give space for arcs above and year labels below
# #     plt.axis('off')

# #     # Legend
# #     legend_patches = [
# #         mpatches.Patch(color='#95a5a6', label='Historical Version'),
# #         mpatches.Patch(color='#2ecc71', label='Current Active Truth'),
# #         mpatches.Patch(color='#3498db', label='Amendment Path'),
# #     ]
# #     plt.legend(handles=legend_patches, loc='upper left', frameon=False)

# #     plt.tight_layout()
# #     plt.savefig("grouped_timeline_viz.png", bbox_inches='tight')
# #     print("✅ Saved 'grouped_timeline_viz.png'")

# # if __name__ == "__main__":
# #     visualize_grouped_timeline()

# #!/usr/bin/env python3
# # visualize_kg.py
# import argparse, os, pickle, tempfile
# from collections import Counter
# from datetime import datetime
# import networkx as nx
# import pandas as pd
# import matplotlib.pyplot as plt
# import seaborn as sns
# import plotly.graph_objects as go
# from pyvis.network import Network
# from dateutil import parser as dateparse
# import numpy as np
# from google.cloud import storage

# plt.rcParams['figure.dpi'] = 150

# # ----------------- GCS helper -----------------
# def parse_gs_uri(gs_uri):
#     assert gs_uri.startswith("gs://"), "gcs uri must start with gs://"
#     parts = gs_uri[5:].split("/",1)
#     bucket = parts[0]
#     path = parts[1] if len(parts)>1 else ""
#     return bucket, path

# def gcs_download(bucket_name, blob_path, local_path, overwrite=True):
#     os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
#     if os.path.exists(local_path) and not overwrite:
#         return local_path
#     client = storage.Client()
#     bucket = client.bucket(bucket_name)
#     blob = bucket.blob(blob_path)
#     blob.download_to_filename(local_path)
#     return local_path

# # ----------------- IO / DF conversion -----------------
# def load_kg(path):
#     with open(path, 'rb') as f:
#         G = pickle.load(f)
#     if not isinstance(G, (nx.DiGraph, nx.MultiDiGraph)):
#         raise ValueError("Expected networkx DiGraph or MultiDiGraph")
#     return G

# def nodes_to_df(G):
#     rows = []
#     for n, d in G.nodes(data=True):
#         rows.append({
#             "node": n,
#             "accession": d.get("accession", str(n)),
#             "company": d.get("company"),
#             "date": d.get("date"),
#             "type": d.get("type"),
#             "title": d.get("title", "")[:400]
#         })
#     df = pd.DataFrame(rows)
#     df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')
#     return df

# def edges_to_df(G):
#     rows=[]
#     if G.is_multigraph():
#         for u,v,k,attr in G.edges(keys=True,data=True):
#             rows.append({"src":u,"tgt":v,"tag":attr.get("tag","unknown"), "confidence": attr.get("confidence", None)})
#     else:
#         for u,v,attr in G.edges(data=True):
#             rows.append({"src":u,"tgt":v,"tag":attr.get("tag","unknown"), "confidence": attr.get("confidence", None)})
#     return pd.DataFrame(rows)

# def filter_years(df_nodes, start_year=None, end_year=None):
#     if start_year:
#         df_nodes = df_nodes[df_nodes['date_parsed'].dt.year >= start_year]
#     if end_year:
#         df_nodes = df_nodes[df_nodes['date_parsed'].dt.year <= end_year]
#     return df_nodes

# # ----------------- Visuals -----------------
# def aggregate_company_type_graph(G, df_nodes, df_edges, topk_companies=10, out_png=None):
#     company_counts = df_nodes['company'].value_counts().dropna()
#     top_companies = company_counts.head(topk_companies).index.tolist()
#     agg_edges = Counter()
#     agg_nodes = Counter()
#     for _, row in df_edges.iterrows():
#         try:
#             src_meta = G.nodes[row['src']]; tgt_meta = G.nodes[row['tgt']]
#         except KeyError:
#             continue
#         if src_meta.get('company') not in top_companies and tgt_meta.get('company') not in top_companies:
#             continue
#         a = (src_meta.get('company'), src_meta.get('type'))
#         b = (tgt_meta.get('company'), tgt_meta.get('type'))
#         agg_nodes[a]+=1; agg_nodes[b]+=1
#         agg_edges[(a,b,row['tag'])] += 1
#     H = nx.DiGraph()
#     for (comp,typ),cnt in agg_nodes.items():
#         label=f"{comp}\n{typ}\n#{cnt}"
#         H.add_node((comp,typ), label=label, size=cnt)
#     for (a,b,tag),cnt in agg_edges.items():
#         H.add_edge(a,b, tag=tag, weight=cnt)
#     if len(H)==0:
#         print("No aggregated nodes to plot.")
#         return
#     pos = nx.spring_layout(H, k=0.7, seed=42)
#     plt.figure(figsize=(10,8))
#     sizes = [max(200, H.nodes[n]['size']*20) for n in H.nodes()]
#     nx.draw_networkx_nodes(H, pos, node_size=sizes, node_color='skyblue')
#     nx.draw_networkx_labels(H, pos, labels={n:H.nodes[n]['label'] for n in H.nodes()}, font_size=8)
#     edge_colors = []
#     for u,v in H.edges():
#         t = H.edges[u,v].get('tag','')
#         edge_colors.append({'amends':'tab:green','supersedes':'tab:orange','replaces':'tab:red'}.get(t,'gray'))
#     nx.draw_networkx_edges(H, pos, arrowstyle='->', arrowsize=12, edge_color=edge_colors, width=1.5)
#     plt.title("Aggregated Company x FilingType Graph (top companies)")
#     plt.axis('off')
#     if out_png:
#         plt.savefig(out_png, bbox_inches='tight')
#         print("Saved:", out_png)
#     else:
#         plt.show()

# def interactive_subgraph_pyvis(G, df_nodes, df_edges, company=None, max_nodes=300, out_html="subgraph.html"):
#     if company:
#         nodes_comp = df_nodes[df_nodes['company']==company]['node'].tolist()
#         if not nodes_comp:
#             raise ValueError("No nodes for company: "+company)
#         sub_nodes = set(nodes_comp)
#         for n in list(nodes_comp):
#             if hasattr(G, "predecessors"):
#                 sub_nodes.update(list(G.predecessors(n)))
#                 sub_nodes.update(list(G.successors(n)))
#         sub_nodes = list(sub_nodes)[:max_nodes]
#         SG = G.subgraph(sub_nodes).copy()
#     else:
#         deg = sorted(G.degree(), key=lambda x: x[1], reverse=True)
#         top = [n for n,_ in deg[:max_nodes]]
#         SG = G.subgraph(top).copy()
#     net = Network(height="800px", width="100%", notebook=False, directed=True)
#     for n,d in SG.nodes(data=True):
#         label = f"{d.get('company','')}\\n{d.get('type','')}\\n{d.get('accession','')}"
#         title = f"Date: {d.get('date','')}<br>{d.get('title','')[:400]}"
#         net.add_node(n, label=label, title=title, color='lightblue')
#     if SG.is_multigraph():
#         for u,v,k,attr in SG.edges(keys=True,data=True):
#             tag = attr.get('tag','')
#             color = {'amends':'green','supersedes':'orange','replaces':'red'}.get(tag,'gray')
#             net.add_edge(u, v, title=tag, color=color)
#     else:
#         for u,v,attr in SG.edges(data=True):
#             tag = attr.get('tag','')
#             color = {'amends':'green','supersedes':'orange','replaces':'red'}.get(tag,'gray')
#             net.add_edge(u, v, title=tag, color=color)
#     net.toggle_physics(True)
#     net.save_graph(out_html)
#     print("Saved interactive view:", out_html)

# def timeline_gantt_for_company(G, df_nodes, df_edges, company, out_html="timeline.html"):
#     dfc = df_nodes[df_nodes['company']==company].sort_values('date_parsed')
#     if dfc.empty:
#         raise ValueError("No nodes for company: "+company)
#     dfc = dfc.reset_index(drop=True)
#     dfc['label'] = dfc['type'].astype(str) + " | " + dfc['accession'].astype(str)
#     fig = go.Figure()
#     fig.add_trace(go.Scatter(
#         x=dfc['date_parsed'],
#         y=dfc['label'],
#         mode='markers+text',
#         marker=dict(size=8),
#         text=dfc['type'],
#         textposition="middle right",
#         name='filings'
#     ))
#     for _, row in df_edges.iterrows():
#         if row['src'] in dfc['node'].values and row['tgt'] in dfc['node'].values:
#             try:
#                 src_date = dfc[dfc['node']==row['src']]['date_parsed'].iloc[0]
#                 tgt_date = dfc[dfc['node']==row['tgt']]['date_parsed'].iloc[0]
#                 src_label = dfc[dfc['node']==row['src']]['label'].iloc[0]
#                 tgt_label = dfc[dfc['node']==row['tgt']]['label'].iloc[0]
#                 fig.add_annotation(x=src_date, y=src_label, ax=tgt_date, ay=tgt_label,
#                                    xref='x', yref='y', axref='x', ayref='y',
#                                    showarrow=True, arrowhead=3,
#                                    arrowsize=1, arrowwidth=1,
#                                    arrowcolor={'amends':'green','supersedes':'orange','replaces':'red'}.get(row['tag'],'gray'),
#                                    opacity=0.7)
#             except Exception:
#                 continue
#     fig.update_layout(title=f"Filing Timeline and Amendment Edges: {company}",
#                       xaxis_title="Date", height=600)
#     fig.write_html(out_html)
#     print("Saved timeline:", out_html)

# def sankey_transition_plot(G, df_edges, out_html="sankey.html", topk=20):
#     rows=[]
#     for _, r in df_edges.iterrows():
#         try:
#             src_type = G.nodes[r['src']].get('type','UNK')
#             tgt_type = G.nodes[r['tgt']].get('type','UNK')
#             rows.append((src_type, tgt_type, r['tag']))
#         except KeyError:
#             continue
#     d = pd.DataFrame(rows, columns=['src_type','tgt_type','tag'])
#     if d.empty:
#         print("No edges for sankey.")
#         return
#     grp = d.groupby(['src_type','tgt_type','tag']).size().reset_index(name='count').sort_values('count', ascending=False).head(topk)
#     labels = list(pd.unique(grp['src_type'].tolist() + grp['tgt_type'].tolist()))
#     label_index = {l:i for i,l in enumerate(labels)}
#     sources = [label_index[r['src_type']] for _,r in grp.iterrows()]
#     targets = [label_index[r['tgt_type']] for _,r in grp.iterrows()]
#     values = grp['count'].tolist()
#     colors = ["rgba(31,119,180,0.8)" if t=='amends' else "rgba(255,127,14,0.8)" if t=='supersedes' else "rgba(214,39,40,0.8)" for t in grp['tag']]
#     link = dict(source=sources, target=targets, value=values, color=colors)
#     node = dict(label=labels, pad=15, thickness=20)
#     fig = go.Figure(data=[go.Sankey(node=node, link=link)])
#     fig.update_layout(title_text="Type-to-Type Transitions (top flows)", font_size=10, height=600)
#     fig.write_html(out_html)
#     print("Saved sankey:", out_html)

# def diagnostics_plots(G, df_nodes, df_edges, out_prefix="diag"):
#     degs = np.array([G.degree(n) for n in df_nodes['node']])
#     if len(degs)>0:
#         plt.figure(figsize=(5,3))
#         sns.histplot(degs, bins=50, log_scale=(True, True))
#         plt.xlabel("Degree"); plt.title("Degree distribution (log-log)")
#         plt.tight_layout()
#         plt.savefig(f"{out_prefix}_degree.png")
#         plt.close()
#         print("Saved:", f"{out_prefix}_degree.png")
#     hop_lengths=[]
#     companies = df_nodes['company'].dropna().unique()
#     for c in companies:
#         nodes_c = df_nodes[df_nodes['company']==c]['node'].tolist()
#         if len(nodes_c)<2: continue
#         try:
#             sub = G.subgraph(nodes_c)
#             lengths = dict(nx.all_pairs_shortest_path_length(sub))
#             for u, dct in lengths.items():
#                 for v,l in dct.items():
#                     hop_lengths.append(l)
#         except Exception:
#             continue
#     if hop_lengths:
#         sns.ecdfplot(hop_lengths)
#         plt.xlabel("Hop length"); plt.ylabel("ECDF"); plt.title("Hop length CDF across companies")
#         plt.tight_layout()
#         plt.savefig(f"{out_prefix}_hop_cdf.png")
#         plt.close()
#         print("Saved:", f"{out_prefix}_hop_cdf.png")

# # ----------------- Main -----------------
# def main():
#     p = argparse.ArgumentParser()
#     p.add_argument("--gcs-uri", type=str, default=None, help="gs://bucket/path/to/kg.pkl")
#     p.add_argument("--local-kg", type=str, default=None, help="local path to kg pickle (skip gcs download)")
#     p.add_argument("--out-dir", type=str, default="figs")
#     p.add_argument("--start-year", type=int, default=None)
#     p.add_argument("--end-year", type=int, default=None)
#     p.add_argument("--company", type=str, default=None, help="Ticker/CIK to produce detailed subgraph & timeline")
#     p.add_argument("--topk-companies", type=int, default=8)
#     args = p.parse_args()
#     os.makedirs(args.out_dir, exist_ok=True)

#     if args.gcs_uri:
#         bucket, blob = parse_gs_uri(args.gcs_uri)
#         local_tmp = os.path.join(args.out_dir, os.path.basename(blob))
#         print(f"Downloading KG from gs://{bucket}/{blob} -> {local_tmp}")
#         local_kg_path = gcs_download(bucket, blob, local_tmp)
#     elif args.local_kg:
#         local_kg_path = args.local_kg
#     else:
#         raise ValueError("Provide --gcs-uri or --local-kg")

#     print("Loading KG:", local_kg_path)
#     G = load_kg(local_kg_path)
#     df_nodes = nodes_to_df(G)
#     df_edges = edges_to_df(G)

#     if args.start_year or args.end_year:
#         df_nodes = filter_years(df_nodes, args.start_year, args.end_year)
#         valid_nodes = set(df_nodes['node'])
#         df_edges = df_edges[df_edges['src'].isin(valid_nodes) & df_edges['tgt'].isin(valid_nodes)]

#     aggregate_company_type_graph(G, df_nodes, df_edges, topk_companies=args.topk_companies, out_png=os.path.join(args.out_dir,"agg_company_type.png"))

#     if args.company:
#         interactive_subgraph_pyvis(G, df_nodes, df_edges, company=args.company, max_nodes=400, out_html=os.path.join(args.out_dir,f"{args.company}_subgraph.html"))
#         timeline_gantt_for_company(G, df_nodes, df_edges, args.company, out_html=os.path.join(args.out_dir,f"{args.company}_timeline.html"))
#     else:
#         interactive_subgraph_pyvis(G, df_nodes, df_edges, company=None, max_nodes=300, out_html=os.path.join(args.out_dir,"top_subgraph.html"))

#     sankey_transition_plot(G, df_edges, out_html=os.path.join(args.out_dir,"sankey.html"))
#     diagnostics_plots(G, df_nodes, df_edges, out_prefix=os.path.join(args.out_dir,"diag"))
#     print("All visualizations saved to", args.out_dir)

# if __name__ == "__main__":
#     main()

#!/usr/bin/env python3
# visualize_kg.py
"""
Download KG pickle from GCS or load local, then produce visualizations:
- agg_company_type.png
- {company}_subgraph.html (interactive)
- {company}_timeline.html
- sankey.html
- diag_degree.png, diag_hop_cdf.png

Usage examples:
  export GOOGLE_APPLICATION_CREDENTIALS="/path/to/sa-key.json"
  pip install -r requirements.txt
  python visualize_kg.py --gcs-uri gs://my-bucket/path/to/kg.pkl --out-dir figs --company TSLA --start-year 2018 --end-year 2024
  python visualize_kg.py --local-kg /local/path/kg.pkl --out-dir figs
"""
import argparse
import os
import pickle
from collections import Counter
import networkx as nx
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
from pyvis.network import Network
from dateutil import parser as dateparse
import numpy as np
from google.cloud import storage
import re
import html as html_mod

plt.rcParams['figure.dpi'] = 150

# ----------------- GCS helper -----------------
def parse_gs_uri(gs_uri):
    assert gs_uri.startswith("gs://"), "gcs uri must start with gs://"
    parts = gs_uri[5:].split("/",1)
    bucket = parts[0]
    path = parts[1] if len(parts)>1 else ""
    return bucket, path

def gcs_download(bucket_name, blob_path, local_path, overwrite=True):
    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
    if os.path.exists(local_path) and not overwrite:
        return local_path
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.download_to_filename(local_path)
    return local_path

# ----------------- IO / DF conversion -----------------
def load_kg(path):
    with open(path, 'rb') as f:
        G = pickle.load(f)
    if not isinstance(G, (nx.DiGraph, nx.MultiDiGraph)):
        raise ValueError("Expected networkx DiGraph or MultiDiGraph")
    return G

def nodes_to_df(G):
    rows = []
    for n, d in G.nodes(data=True):
        rows.append({
            "node": n,
            "accession": d.get("accession", str(n)),
            "company": d.get("company"),
            "date": d.get("date"),
            "type": d.get("type"),
            "title": d.get("title", "")[:400]
        })
    df = pd.DataFrame(rows)
    df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')
    return df

def edges_to_df(G):
    rows=[]
    if G.is_multigraph():
        for u,v,k,attr in G.edges(keys=True,data=True):
            rows.append({"src":u,"tgt":v,"tag":attr.get("tag","unknown"), "confidence": attr.get("confidence", None)})
    else:
        for u,v,attr in G.edges(data=True):
            rows.append({"src":u,"tgt":v,"tag":attr.get("tag","unknown"), "confidence": attr.get("confidence", None)})
    return pd.DataFrame(rows)

def filter_years_allow_missing(df_nodes, start_year=None, end_year=None):
    if not (start_year or end_year):
        return df_nodes
    local_df = df_nodes.copy()
    mask_with_date = local_df['date_parsed'].notna()
    mask = pd.Series(True, index=local_df.index)
    if start_year:
        mask &= (~mask_with_date) | (local_df['date_parsed'].dt.year >= start_year)
    if end_year:
        mask &= (~mask_with_date) | (local_df['date_parsed'].dt.year <= end_year)
    return local_df[mask]

# ----------------- Label formatting -----------------
def fmt_label(raw, max_len=200, html_breaks=False):
    raw = (raw or "")
    if html_breaks:
        lbl_html = html_mod.escape(raw).replace('\n', '<br>')
        short = lbl_html if len(lbl_html) <= max_len else lbl_html[:max_len] + '...'
        return short, lbl_html
    collapsed = re.sub(r'\s+', ' ', raw).strip()
    short = collapsed if len(collapsed) <= max_len else collapsed[:max_len] + '...'
    return short, collapsed

# ----------------- Visuals -----------------
def aggregate_company_type_graph(G, df_nodes, df_edges, topk_companies=10, out_png=None):
    company_counts = df_nodes['company'].value_counts().dropna()
    if company_counts.empty:
        print("No company metadata available for aggregation.")
        return
    top_companies = company_counts.head(topk_companies).index.tolist()
    agg_edges = Counter()
    agg_nodes = Counter()
    for _, row in df_edges.iterrows():
        try:
            src_meta = G.nodes[row['src']]; tgt_meta = G.nodes[row['tgt']]
        except KeyError:
            continue
        if src_meta.get('company') not in top_companies and tgt_meta.get('company') not in top_companies:
            continue
        a = (src_meta.get('company'), src_meta.get('type'))
        b = (tgt_meta.get('company'), tgt_meta.get('type'))
        agg_nodes[a]+=1; agg_nodes[b]+=1
        agg_edges[(a,b,row['tag'])] += 1
    H = nx.DiGraph()
    for (comp,typ),cnt in agg_nodes.items():
        raw = f"{comp} {typ} #{cnt}"
        short, _ = fmt_label(raw, max_len=80, html_breaks=False)
        H.add_node((comp,typ), label=short, size=cnt)
    for (a,b,tag),cnt in agg_edges.items():
        H.add_edge(a,b, tag=tag, weight=cnt)
    if len(H)==0:
        print("No aggregated nodes to plot.")
        return
    pos = nx.spring_layout(H, k=0.7, seed=42)
    plt.figure(figsize=(10,8))
    sizes = [max(200, H.nodes[n]['size']*20) for n in H.nodes()]
    nx.draw_networkx_nodes(H, pos, node_size=sizes, node_color='skyblue')
    nx.draw_networkx_labels(H, pos, labels={n:H.nodes[n]['label'] for n in H.nodes()}, font_size=8)
    edge_colors = []
    for u,v in H.edges():
        t = H.edges[u,v].get('tag','')
        edge_colors.append({'amends':'tab:green','supersedes':'tab:orange','replaces':'tab:red'}.get(t,'gray'))
    nx.draw_networkx_edges(H, pos, arrowstyle='->', arrowsize=12, edge_color=edge_colors, width=1.5)
    plt.title("Aggregated Company x FilingType Graph (top companies)")
    plt.axis('off')
    if out_png:
        plt.savefig(out_png, bbox_inches='tight')
        print("Saved:", out_png)
    else:
        plt.show()

def nodes_for_company_token(G, df_nodes, company_token):
    # exact attr match first
    attr_matches = df_nodes[df_nodes['company']==company_token]['node'].tolist()
    if attr_matches:
        return attr_matches
    # prefix match on node id (e.g., "TSLA_...")
    pref = [n for n in G.nodes() if str(n).startswith(f"{company_token}_")]
    if pref:
        return pref
    # substring fallback
    substr = [n for n in G.nodes() if company_token.lower() in str(n).lower()]
    return substr

def interactive_subgraph_pyvis(G, df_nodes, df_edges, company=None, max_nodes=300, out_html="subgraph.html"):
    # select nodes
    if company:
        nodes_comp = nodes_for_company_token(G, df_nodes, company)
        if not nodes_comp:
            raise ValueError("No nodes for company: "+company)
        sub_nodes = set(nodes_comp)
        for n in list(nodes_comp):
            if hasattr(G, "predecessors"):
                sub_nodes.update(list(G.predecessors(n)))
                sub_nodes.update(list(G.successors(n)))
        sub_nodes = list(sub_nodes)[:max_nodes]
        SG = G.subgraph(sub_nodes).copy()
    else:
        deg = sorted(G.degree(), key=lambda x: x[1], reverse=True)
        top = [n for n,_ in deg[:max_nodes]]
        SG = G.subgraph(top).copy()
    net = Network(height="800px", width="100%", notebook=False, directed=True)
    for n,d in SG.nodes(data=True):
        raw_label = f"{d.get('company','')} {d.get('type','')} {d.get('accession','')}".strip()
        short_label, full_title = fmt_label(d.get('title','') or raw_label, max_len=180, html_breaks=True)
        hover = f"Date: {d.get('date','')}<br>{full_title}"
        net.add_node(n, label=short_label, title=hover, color='lightblue')
    if SG.is_multigraph():
        for u,v,k,attr in SG.edges(keys=True,data=True):
            tag = attr.get('tag','')
            color = {'amends':'green','supersedes':'orange','replaces':'red'}.get(tag,'gray')
            net.add_edge(u, v, title=tag, color=color)
    else:
        for u,v,attr in SG.edges(data=True):
            tag = attr.get('tag','')
            color = {'amends':'green','supersedes':'orange','replaces':'red'}.get(tag,'gray')
            net.add_edge(u, v, title=tag, color=color)
    net.toggle_physics(True)
    # use save_graph which avoids Jinja2 template render issues in some envs
    net.save_graph(out_html)
    print("Saved interactive view:", out_html)

def timeline_gantt_for_company(G, df_nodes, df_edges, company, out_html="timeline.html"):
    dfc = df_nodes[df_nodes['company']==company].sort_values('date_parsed')
    # fallback: match by prefix if df_nodes company attr not present
    if dfc.empty:
        matched = [n for n in G.nodes() if str(n).startswith(f"{company}_")]
        rows = []
        for n in matched:
            d = G.nodes[n]
            rows.append((n, d.get('date'), d.get('type'), d.get('title')))
        dfc = pd.DataFrame(rows, columns=["node","date","type","title"])
        dfc['date_parsed'] = pd.to_datetime(dfc['date'], errors='coerce')
        if dfc.empty:
            raise ValueError("No nodes for company: "+company)
    dfc = dfc.reset_index(drop=True)
    dfc['label'] = dfc['type'].astype(str) + " | " + dfc['node'].astype(str)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dfc['date_parsed'],
        y=dfc['label'],
        mode='markers+text',
        marker=dict(size=8),
        text=dfc['type'],
        textposition="middle right",
        name='filings'
    ))
    for _, row in df_edges.iterrows():
        if row['src'] in dfc['node'].values and row['tgt'] in dfc['node'].values:
            try:
                src_date = dfc[dfc['node']==row['src']]['date_parsed'].iloc[0]
                tgt_date = dfc[dfc['node']==row['tgt']]['date_parsed'].iloc[0]
                src_label = dfc[dfc['node']==row['src']]['label'].iloc[0]
                tgt_label = dfc[dfc['node']==row['tgt']]['label'].iloc[0]
                fig.add_annotation(x=src_date, y=src_label, ax=tgt_date, ay=tgt_label,
                                   xref='x', yref='y', axref='x', ayref='y',
                                   showarrow=True, arrowhead=3,
                                   arrowsize=1, arrowwidth=1,
                                   arrowcolor={'amends':'green','supersedes':'orange','replaces':'red'}.get(row['tag'],'gray'),
                                   opacity=0.7)
            except Exception:
                continue
    fig.update_layout(title=f"Filing Timeline and Amendment Edges: {company}",
                      xaxis_title="Date", height=600)
    fig.write_html(out_html)
    print("Saved timeline:", out_html)

def sankey_transition_plot(G, df_edges, out_html="sankey.html", topk=20):
    rows=[]
    for _, r in df_edges.iterrows():
        try:
            src_type = G.nodes[r['src']].get('type','UNK')
            tgt_type = G.nodes[r['tgt']].get('type','UNK')
            rows.append((src_type, tgt_type, r['tag']))
        except KeyError:
            continue
    d = pd.DataFrame(rows, columns=['src_type','tgt_type','tag'])
    if d.empty:
        print("No edges for sankey.")
        return
    grp = d.groupby(['src_type','tgt_type','tag']).size().reset_index(name='count').sort_values('count', ascending=False).head(topk)
    labels = list(pd.unique(grp['src_type'].tolist() + grp['tgt_type'].tolist()))
    label_index = {l:i for i,l in enumerate(labels)}
    sources = [label_index[r['src_type']] for _,r in grp.iterrows()]
    targets = [label_index[r['tgt_type']] for _,r in grp.iterrows()]
    values = grp['count'].tolist()
    colors = ["rgba(31,119,180,0.8)" if t=='amends' else "rgba(255,127,14,0.8)" if t=='supersedes' else "rgba(214,39,40,0.8)" for t in grp['tag']]
    link = dict(source=sources, target=targets, value=values, color=colors)
    node = dict(label=labels, pad=15, thickness=20)
    fig = go.Figure(data=[go.Sankey(node=node, link=link)])
    fig.update_layout(title_text="Type-to-Type Transitions (top flows)", font_size=10, height=600)
    fig.write_html(out_html)
    print("Saved sankey:", out_html)

def diagnostics_plots(G, df_nodes, df_edges, out_prefix="diag"):
    degs = np.array([G.degree(n) for n in df_nodes['node']]) if not df_nodes.empty else np.array([])
    if len(degs)>0:
        plt.figure(figsize=(5,3))
        sns.histplot(degs, bins=50, log_scale=(True, True))
        plt.xlabel("Degree"); plt.title("Degree distribution (log-log)")
        plt.tight_layout()
        plt.savefig(f"{out_prefix}_degree.png")
        plt.close()
        print("Saved:", f"{out_prefix}_degree.png")
    hop_lengths=[]
    companies = df_nodes['company'].dropna().unique() if 'company' in df_nodes.columns else []
    for c in companies:
        nodes_c = df_nodes[df_nodes['company']==c]['node'].tolist()
        if len(nodes_c)<2: continue
        try:
            sub = G.subgraph(nodes_c)
            lengths = dict(nx.all_pairs_shortest_path_length(sub))
            for u, dct in lengths.items():
                for v,l in dct.items():
                    hop_lengths.append(l)
        except Exception:
            continue
    if hop_lengths:
        sns.ecdfplot(hop_lengths)
        plt.xlabel("Hop length"); plt.ylabel("ECDF"); plt.title("Hop length CDF across companies")
        plt.tight_layout()
        plt.savefig(f"{out_prefix}_hop_cdf.png")
        plt.close()
        print("Saved:", f"{out_prefix}_hop_cdf.png")

# ----------------- Main -----------------
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gcs-uri", type=str, default=None, help="gs://bucket/path/to/kg.pkl")
    p.add_argument("--local-kg", type=str, default=None, help="local path to kg pickle (skip gcs download)")
    p.add_argument("--out-dir", type=str, default="figs")
    p.add_argument("--start-year", type=int, default=None)
    p.add_argument("--end-year", type=int, default=None)
    p.add_argument("--company", type=str, default=None, help="Ticker/CIK to produce detailed subgraph & timeline")
    p.add_argument("--topk-companies", type=int, default=8)
    args = p.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    if args.gcs_uri:
        bucket, blob = parse_gs_uri(args.gcs_uri)
        local_tmp = os.path.join(args.out_dir, os.path.basename(blob))
        print(f"Downloading KG from gs://{bucket}/{blob} -> {local_tmp}")
        local_kg_path = gcs_download(bucket, blob, local_tmp)
    elif args.local_kg:
        local_kg_path = args.local_kg
    else:
        raise ValueError("Provide --gcs-uri or --local-kg")

    print("Loading KG:", local_kg_path)
    G = load_kg(local_kg_path)
    df_nodes = nodes_to_df(G)
    df_edges = edges_to_df(G)

    # filter while allowing nodes without dates
    df_nodes = filter_years_allow_missing(df_nodes, start_year=args.start_year, end_year=args.end_year)
    valid_nodes = set(df_nodes['node'])
    df_edges = df_edges[df_edges['src'].isin(valid_nodes) & df_edges['tgt'].isin(valid_nodes)]

    aggregate_company_type_graph(G, df_nodes, df_edges, topk_companies=args.topk_companies, out_png=os.path.join(args.out_dir,"agg_company_type.png"))

    if args.company:
        try:
            interactive_subgraph_pyvis(G, df_nodes, df_edges, company=args.company, max_nodes=400, out_html=os.path.join(args.out_dir,f"{args.company}_subgraph.html"))
            timeline_gantt_for_company(G, df_nodes, df_edges, args.company, out_html=os.path.join(args.out_dir,f"{args.company}_timeline.html"))
        except ValueError as e:
            print("Company-specific visualizations failed:", e)
            print("You can list prefixes in the KG with:")
            print("python - <<'PY'\nimport pickle\nG=pickle.load(open('%s','rb'))\nprint('\\n'.join(sorted({str(n).split('_')[0] for n in G.nodes()})))\nPY" % local_kg_path)
    else:
        interactive_subgraph_pyvis(G, df_nodes, df_edges, company=None, max_nodes=300, out_html=os.path.join(args.out_dir,"top_subgraph.html"))

    sankey_transition_plot(G, df_edges, out_html=os.path.join(args.out_dir,"sankey.html"))
    diagnostics_plots(G, df_nodes, df_edges, out_prefix=os.path.join(args.out_dir,"diag"))
    print("All visualizations saved to", args.out_dir)

if __name__ == "__main__":
    main()
