import pickle
import networkx as nx
import plotly.graph_objects as go
import os

def visualize_multi_hop_with_labels(pickle_path, center_node=None, hops=2):
    if not os.path.exists(pickle_path):
        print(f"❌ Error: {pickle_path} not found.")
        return

    with open(pickle_path, "rb") as f:
        G = pickle.load(f)

    # 1. Filter Subgraph
    if center_node and center_node in G:
        sub_nodes = nx.single_source_shortest_path_length(G, center_node, cutoff=hops).keys()
        sub_G = G.subgraph(sub_nodes)
    else:
        sub_G = G.subgraph(list(G.nodes())[:100])
        # Get a mix of nodes from all years present in the graph
        # import random
        # all_nodes = list(G.nodes())
        # # Shuffle to ensure we aren't just stuck in 2001
        # random.shuffle(all_nodes) 
        # sub_G = G.subgraph(all_nodes[:200]) # Increase to 200 to see more diversity

    pos = nx.spring_layout(sub_G, k=0.5, iterations=50)

    # 2. Create Edge Lines
    edge_traces = []
    edge_label_x = []
    edge_label_y = []
    edge_label_text = []

    for u, v, data in sub_G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        
        # Determine color based on relationship
        rel = data.get('relation', 'CONTAINS')
        color = '#FF4136' if rel in ['SUPERSEDES', 'REPLACES'] else '#888'
        
        # Line Trace
        edge_traces.append(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None],
            line=dict(width=1, color=color),
            hoverinfo='none', mode='lines'
        ))

        # Midpoint for the label
        edge_label_x.append((x0 + x1) / 2)
        edge_label_y.append((y0 + y1) / 2)
        edge_label_text.append(f"REL: {rel}<br>Evidence: {data.get('evidence', 'N/A')[:50]}...")

    # 3. Create Edge Label "Markers" (Invisible but hoverable)
    edge_label_trace = go.Scatter(
        x=edge_label_x, y=edge_label_y,
        mode='markers',
        hoverinfo='text',
        text=edge_label_text,
        marker=dict(size=8, color='rgba(0,0,0,0)') # Transparent markers in middle of lines
    )

    # 4. Create Node Trace
    node_x, node_y, node_text, node_color = [], [], [], []
    for node in sub_G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        attr = sub_G.nodes[node]
        node_text.append(f"ID: {node}<br>Year: {attr.get('year', 'N/A')}<br>Name: {attr.get('name', 'N/A')}")
        
        level = attr.get('level', 'State')
        if level == 'Identity': node_color.append('gold')
        elif attr.get('type') == 'Ghost': node_color.append('salmon')
        else: node_color.append('skyblue')

    node_trace = go.Scatter(
        x=node_x, y=node_y, mode='markers',
        hoverinfo='text', text=node_text,
        marker=dict(color=node_color, size=18, line=dict(width=2, color='white'))
    )

    # 5. Build Figure
    fig = go.Figure(data=edge_traces + [edge_label_trace, node_trace],
                 layout=go.Layout(
                    title='Legal Knowledge Graph: Multi-Hop Relationships',
                    template='plotly_dark',
                    showlegend=False,
                    hovermode='closest',
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
                ))

    fig.show()

if __name__ == "__main__":
    visualize_multi_hop_with_labels("local_cfr_graph.pickle")