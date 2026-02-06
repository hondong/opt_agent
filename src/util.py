
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

def split_excel_data():

    # Read the Excel file
    excel_file = './data/2020_dataset_OfAutomotiveProductionNetwork.xlsb'
    xlsx = pd.ExcelFile(excel_file)

    # Save each sheet as a CSV
    for sheet_name in xlsx.sheet_names:
        df = pd.read_excel(xlsx, sheet_name=sheet_name)
        df.to_csv(f'./data/{sheet_name}.csv', index=False)
        print(f'Saved {sheet_name}.csv')


def visualize_initial_flow():

    # Read the CSV file
    df = pd.read_csv('data/initial_flows.csv')

    # Create a directed graph
    G = nx.DiGraph()

    # Add edges with flow as weight
    for _, row in df.iterrows():
        G.add_edge(row['starting_node_i'], row['ending_node_j'], 
                weight=row['initial_flow'],
                product=row['product_p'],
                period=row['period_t'])

    # Create the visualization
    plt.figure(figsize=(15, 10))
    pos = nx.spring_layout(G, k=2, iterations=50)

    # Draw the network
    nx.draw_networkx_nodes(G, pos, node_size=500, node_color='lightblue')
    nx.draw_networkx_labels(G, pos, font_size=8)
    nx.draw_networkx_edges(G, pos, edge_color='gray', arrows=True, 
                        arrowsize=10, alpha=0.5)
    
    # Draw edge labels with weights
    edge_labels = nx.get_edge_attributes(G, 'weight')
    nx.draw_networkx_edge_labels(G, pos, edge_labels, font_size=6)

    plt.title('Network Flow Visualization')
    plt.axis('off')
    plt.tight_layout()
    plt.savefig('network_flow.png', dpi=300, bbox_inches='tight')
    plt.show()


def show_data_statistics():
    import glob
    import os

    # Create the search pattern: folder_path + '/*.csv'
    # os.path.join handles different operating system path separators (like / or \)
    search_pattern = os.path.join('./data', '*.csv')
    
    # glob.glob returns a list of paths matching the pattern
    csv_files = glob.glob(search_pattern)

    # Save each sheet as a CSV
    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        print(f'Statistics for {os.path.basename(csv_file)}:')
        print(df.describe(include='all'))
        print('\n')