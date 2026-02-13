import json
import os
import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx
import pandas as pd
import numpy as np
from datetime import datetime
from matplotlib.patches import FancyArrowPatch

RESULTS_DIR = "experiments/results"
SIM_RESULTS_FILE = os.path.join(RESULTS_DIR, "simulation_results.json")
GRAPH_STRUCT_FILE = os.path.join(RESULTS_DIR, "graph_structure.json")

# Set Seaborn theme for professional look
sns.set_theme(style="whitegrid")
plt.rcParams['figure.dpi'] = 300
plt.rcParams['font.family'] = 'sans-serif'

def load_data():
    with open(SIM_RESULTS_FILE, 'r') as f:
        results = json.load(f)
    with open(GRAPH_STRUCT_FILE, 'r') as f:
        graph_data = json.load(f)
    return results, graph_data

def plot_dataset_blobs(graph_data):
    """
    Visualizes the document ecosystem as 'blobs' over time.
    """
    nodes = graph_data['nodes']
    data = []
    for n in nodes:
        # Fix: Date might have time component "2020-01-01 00:00:00"
        date_str = n['date'].split(" ")[0]
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        data.append({
            "Date": dt,
            "Type": n['type'],
            "Year": dt.year,
            "Month": dt.month,
            "Cluster": n['id'].split("_")[1] # Extract cluster ID for some jitter
        })
    
    df = pd.DataFrame(data)
    
    # Add some random jitter to Y-axis (Type) for visualization if needed, 
    # but seaborn handles categorical Y well.
    
    plt.figure(figsize=(12, 6))
    
    # Custom palette
    palette = {
        'Contract': '#3498db', 
        'Amendment': '#e74c3c', 
        'Addendum': '#2ecc71', 
        'Policy': '#9b59b6', 
        'Standard': '#f1c40f'
    }
    
    ax = sns.scatterplot(
        data=df, 
        x="Date", 
        y="Type", 
        hue="Type", 
        style="Type", 
        s=150, 
        alpha=0.6,
        palette=palette,
        edgecolor='black',
        linewidth=0.5
    )
    
    plt.title("Enterprise Document Ecosystem: Temporal Clusters", fontsize=16, fontweight='bold', pad=20)
    plt.xlabel("Timeline", fontsize=12)
    plt.ylabel("Document Type", fontsize=12)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', title="Doc Type", frameon=False)
    
    # Add annotations for a few clusters to show "chains"
    # Just draw a few lines connecting same cluster arrows
    # This is tricky with scatterplot, so we'll skip complex arrows for now to keep it clean.
    
    plt.tight_layout()
    
    out_path = os.path.join(RESULTS_DIR, "dataset_blobs.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Saved {out_path}")

def plot_accuracy_comparison(results):
    """
    Plots Naive RAG vs Agentic KG accuracy using a professional bar chart.
    """
    naive_score = sum(1 for r in results if r['naive_correct']) / len(results) * 100
    agent_score = sum(1 for r in results if r['agent_correct']) / len(results) * 100
    
    data = {
        "System": ["Naive RAG", "Agentic KG"],
        "Accuracy (%)": [naive_score, agent_score]
    }
    df = pd.DataFrame(data)
    
    plt.figure(figsize=(8, 6))
    ax = sns.barplot(x="System", y="Accuracy (%)", data=df, palette=["#95a5a6", "#2ecc71"], saturation=0.8)
    
    # Add percentage labels
    for i, v in enumerate([naive_score, agent_score]):
        ax.text(i, v + 2, f"{v:.1f}%", ha='center', fontweight='bold', fontsize=14, color='black')
        
    plt.ylim(0, 110)
    plt.title("Retrieval Accuracy on Superseding Logic", fontsize=16, fontweight='bold', pad=20)
    plt.ylabel("Accuracy (%)", fontsize=12)
    plt.xlabel("", fontsize=12)
    
    sns.despine()
    
    out_path = os.path.join(RESULTS_DIR, "accuracy_comparison.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Saved {out_path}")

def plot_graph_topology(graph_data):
    """
    Visualizes a SUBSET of the graph to show the topology clearly without overcrowding.
    """
    G = nx.DiGraph()
    
    # Pick first few clusters to visualize
    # Filter edges that belong to Cluster 0, 1, 2
    target_nodes = set()
    
    # We want to show a nice chain. Let's find a chain of length > 2
    edges_to_draw = []
    
    # Group edges by cluster
    cluster_edges = {}
    for edge in graph_data['edges']:
        # Extract cluster ID from e.g. "Doc_12_Base" -> "12"
        try:
            c_id = edge['source'].split("_")[1]
            if c_id not in cluster_edges: cluster_edges[c_id] = []
            cluster_edges[c_id].append(edge)
        except:
            continue
            
    # Select 2-3 clusters with interesting structure
    selected_clusters = []
    for cid, edges in cluster_edges.items():
        if len(edges) >= 2:
            selected_clusters.append(cid)
            if len(selected_clusters) >= 3: break
            
    for cid in selected_clusters:
        for edge in cluster_edges[cid]:
            G.add_edge(edge['source'], edge['target'], relation=edge['relation'])
            target_nodes.add(edge['source'])
            target_nodes.add(edge['target'])
            
    # Add node metadata
    node_map = {n['id']: n for n in graph_data['nodes']}
    for n_id in target_nodes:
        if n_id in node_map:
            # Simplify label: "Doc_12_Amd_1" -> "Amd 1"
            parts = n_id.split("_")
            if "Base" in n_id: label = "Contract"
            else: label = f"{parts[2]} {parts[3]}"
            
            G.add_node(n_id, type=node_map[n_id]['type'], label=label)

    plt.figure(figsize=(10, 8))
    pos = nx.spring_layout(G, seed=42, k=1.5)
    
    # Color mapping
    color_map = {'Contract': '#3498db', 'Amendment': '#e74c3c', 'Addendum': '#2ecc71', 'Policy': '#9b59b6', 'Standard': '#f1c40f'}
    node_colors = [color_map.get(G.nodes[n].get('type'), '#95a5a6') for n in G.nodes]
    
    # Draw Nodes
    nx.draw_networkx_nodes(G, pos, node_size=2000, node_color=node_colors, alpha=0.9, edgecolors='white', linewidths=2)
    
    # Labels
    labels = nx.get_node_attributes(G, 'label')
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=9, font_color="white", font_weight="bold")
    
    # Draw edges with different styles
    # Supersedes = Red Solid
    # Refers = Gray Dashed
    
    supersedes_edges = [(u,v) for u,v,d in G.edges(data=True) if d['relation'] == 'SUPERSEDES']
    refers_edges = [(u,v) for u,v,d in G.edges(data=True) if d['relation'] == 'REFERS_TO']
    
    nx.draw_networkx_edges(
        G, pos, 
        edgelist=supersedes_edges,
        edge_color='#e74c3c', 
        width=2.5, 
        arrowsize=25, 
        connectionstyle="arc3,rad=0.1",
        label='SUPERSEDES'
    )
    
    nx.draw_networkx_edges(
        G, pos, 
        edgelist=refers_edges,
        edge_color='#34495e', 
        style='dashed',
        width=2, 
        arrowsize=20, 
        connectionstyle="arc3,rad=0.2",
        label='REFERS_TO'
    )
    
    # Custom Legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label='Contract Base', markerfacecolor='#3498db', markersize=15),
        Line2D([0], [0], marker='o', color='w', label='Amendment', markerfacecolor='#e74c3c', markersize=15),
        Line2D([0], [0], color='#e74c3c', lw=2.5, label='SUPERSEDES (Temporal)'),
        Line2D([0], [0], color='#34495e', lw=2, linestyle='--', label='REFERS_TO (Pointer)'),
    ]
    plt.legend(handles=legend_elements, loc='upper right', frameon=True, fancybox=True, framealpha=0.9)
    
    plt.title("Micro-Topology check: 3 Sample Clusters", fontsize=16, fontweight='bold')
    plt.axis('off')
    
    out_path = os.path.join(RESULTS_DIR, "graph_topology.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Saved {out_path}")

def plot_problem_visualization():
    """
    Schematic diagram showing the High Level Architecture.
    """
    # We will use simple patches to draw a block diagram
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6)
    
    # Draw System Blocks
    import matplotlib.patches as patches
    
    def draw_box(x, y, w, h, color, text, subtext=""):
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1", linewidth=2, edgecolor=color, facecolor='white')
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2 + 0.2, text, ha='center', va='center', fontsize=12, fontweight='bold', color='black')
        if subtext:
            ax.text(x + w/2, y + h/2 - 0.2, subtext, ha='center', va='center', fontsize=9, color='#555')
            
    # 1. Ingestion / Crawler
    draw_box(1, 2.5, 2.5, 2, '#3498db', "Recursive Crawler", "LLM Extraction")
    
    # 2. Graph Store
    draw_box(4.5, 2.5, 3, 2, '#2ecc71', "Knowledge Graph", "Nodes: Clauses\nEdges: Supersedes")
    
    # 3. Query Engine
    draw_box(8.5, 2.5, 2.5, 2, '#9b59b6', "Traversal Engine", "Get Valid Node")
    
    # Arrows
    arrow_style = "Simple, tail_width=0.5, head_width=4, head_length=8"
    kw = dict(arrowstyle=arrow_style, color="#34495e")
    
    # Input -> Crawler
    ax.add_patch(FancyArrowPatch((0.2, 3.5), (0.9, 3.5), **kw))
    ax.text(0.5, 3.7, "Docs", ha='center', fontsize=10)
    
    # Crawler -> Graph
    ax.add_patch(FancyArrowPatch((3.6, 3.5), (4.4, 3.5), **kw))
    ax.text(4.0, 3.7, "Builds", ha='center', fontsize=10)
    
    # Graph <-> Engine
    ax.add_patch(FancyArrowPatch((7.6, 3.5), (8.4, 3.5), **kw))
    ax.text(8.0, 3.7, "Queries", ha='center', fontsize=10)
    
    # User Query -> Engine
    ax.add_patch(FancyArrowPatch((9.75, 5.5), (9.75, 4.6), **kw))
    ax.text(9.75, 5.7, "User Query", ha='center', fontsize=10, fontweight='bold')
    
    # Engine -> Answer
    ax.add_patch(FancyArrowPatch((9.75, 2.4), (9.75, 1.0), **kw))
    ax.text(9.75, 0.8, "Valid Answer", ha='center', fontsize=10, fontweight='bold')

    plt.title("Agentic Knowledge Graph Architecture", fontsize=16, fontweight='bold')
    plt.axis('off')
    
    out_path = os.path.join(RESULTS_DIR, "problem_visualization.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Saved {out_path}")

if __name__ == "__main__":
    if not os.path.exists(SIM_RESULTS_FILE):
        print("No results file found. Run agentic_research_simulation.py first.")
    else:
        res, graph = load_data()
        plot_dataset_blobs(graph)
        plot_accuracy_comparison(res)
        plot_graph_topology(graph)
        plot_problem_visualization()
