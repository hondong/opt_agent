from typing import Dict, Tuple
import pandas as pd
from smolagents import CodeAgent, tool, InferenceClientModel, Tool

# Tool to suggest a menu based on the occasion

@tool
def examine_demand() -> str:
    """
    Examines the customer demand data in the car production supply chain model.
    Returns a summary of the demand data.
    """
    from opt_model import CarProductionSupplyChainModel

    model = CarProductionSupplyChainModel(data_path='./data')
    demand_summary = "To be implemented: summary of customer demand data"
    return demand_summary

@tool
def get_product_list_by_group(product_group: str) -> list[str]:
    """
    Retrieves a list of product IDs belonging to the specified product group.
    
    Args:
        product_group (str): The product group to filter by (e.g., 'car', 'engine', etc.).
        
    Returns:
        list[str]: A list of product IDs in the specified product group.
    """
    product_file_path = './data/products.csv'
    df = pd.read_csv(product_file_path)
    filtered_products = df[df['group_g'] == product_group]['product_p'].tolist()
    return filtered_products


class GetSolutionFlow(Tool):
    name = "get_solution_flow"
    description = "Get a dataframe of solution flow of the car production supply chain model." \
    "The output is a dataframe with columns 'from_node', 'to_node', 'product', 'period', 'quantity'. " \
    "A row is added only when the flow quantity is non-zero."
    
    inputs = {
        "product_list" :
        {
            "type": "array",
            "description": "A list of product id's (of type string) to consider in the flow examination.",
        }
    }

    output_type = "object"

    def forward(self, product_list: list[str]) -> pd.DataFrame:
        output_file = "./output/solution.csv"
        df = pd.read_csv(output_file)
        df_flow = df[df['variable_name'].str.startswith('flow')].copy()
        df_flow[['prefix', 'from_node','to_node', 'product', 'period']] = df_flow['variable_name'].str.split('_', expand=True)
        df_flow = df_flow[df_flow['product'].isin(product_list)]
        df_flow.rename(columns={'variable_value': 'quantity'}, inplace=True)
        return df_flow[['from_node', 'to_node', 'product', 'period', 'quantity']].copy()
    

class GetSolutionInventory(Tool):
    name = "get_solution_inventory"
    description = "Get a dataframe of solution inventory of the car production supply chain model." \
    "The output is a dataframe with columns 'node', 'product', 'period', 'inventory'. " \
    "A row exists only when the inventory quantity is non-zero."
    
    inputs = {
        "node" :
        {
            "type": "string",
            "description": "The node id (of type string) to consider in the inventory examination.",
        },
        "product_list" :
        {
            "type": "array",
            "description": "A list of product id's (of type string) to consider in the inventory examination.",
        }
    }

    output_type = "object"

    def forward(self, node:str, product_list: list[str]) -> pd.DataFrame:
        output_file = "./output/solution.csv"
        df = pd.read_csv(output_file)
        df_inventory = df[df['variable_name'].str.startswith('inventory')].copy()
        df_inventory[['prefix', 'node', 'product', 'period']] = df_inventory['variable_name'].str.split('_', expand=True)
        df_inventory = df_inventory[df_inventory['node']==node]
        df_inventory = df_inventory[df_inventory['product'].isin(product_list)]
        df_inventory.rename(columns={'variable_value': 'inventory'}, inplace=True)
        return df_inventory[['node', 'product', 'period', 'inventory']].copy()