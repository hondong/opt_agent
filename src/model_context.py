## Source data filenames

DEMAND_FILE_PATH = './data/demands.csv'
PRODUCT_GROUP_FILE_PATH = './data/products.csv'
NODES_FILE_PATH = './data/nodes.csv'
NODE_INFLOW_FILE_PATH = './data/node_inflows.csv'
ARC_FILE_PATH = './data/arcs.csv'
BOM_FILE_PATH = './data/bom.csv'
INITIAL_INVENTORY_FILE_PATH = './data/initial_inventory.csv'

## Solution data filename
SOLUTION_FILE_PATH = './output/solution.csv'

MODEL_CONTEXT_STRING = f"""
We have an optimization model solving for a car production supply chain problem. 
The model is implemented in Python using the SCIP optimization library. 
The main components of the model include supply chain nodes for seats, battery, gear, and engine.
The model aims to minimize costs while meeting customer demand and adhering 
to various constraints such as production capacities, lead times, and inventory levels.

The engine supply chain consists of 12 nodes, including four inflow nodes 'seat-trans', 'battery-trans',
'gear-prod' and 'engine-prod' where raw materials flow in. 'zp7' is the assembly node where all components are assembled into final car products,
and 'zp8' is the outflow node where finished cars are delivered to customers. 
For example to calculate the number of fulfilled cars, we can look at the flow into node 'zp8' from node 'zp7'.
Other nodes are intermediate processing and inventory nodes. The whole list of nodes is available in the data 
file {NODES_FILE_PATH} as described in data source section below.

Data source files used in the model are:

1. Car demand data in file {DEMAND_FILE_PATH}: Each row indicates one specific car, where column product_p is the unique car VIN number,
and column period_t indicates the promised time for delivery. period_t is an integer between 61 and 74.

2. Each row in product data in file {PRODUCT_GROUP_FILE_PATH} indicates one product and the product group it belongs to. 
The first column 'product_p' is the unique product ID, 
and the second column 'product_group' indicates the product group.
Car products belong to product group 'car' and can be queried using this group.
The third column transportation_size_s is not used in this model and can be ignored.
List of products in a certain group can be obtained by calling the tool 'get_product_list_by_group'.

3. File {NODES_FILE_PATH} includes all supply chain nodes in the model. Each row indicates one supply chain node.
The only column 'node_n' is the unique node ID.

4. File {NODE_INFLOW_FILE_PATH} indicates product inflows to the supply chain. Each row indicates one product flows into one node, 
with first column 'node_n' being the node ID and second column being the product id flow into this node.
No other product inflows exist.

5. File {ARC_FILE_PATH} indicates all supply chain arcs in the model. 
Each row indicates one directed arc from 'starting_node_i' (first column) to 'ending_node_j' (second column).
The third column process_lead_time_l_ij is the time periods needed to transport products from starting node to 
ending node. The fourth column 'group_g' indicates the product group allowed to be transported on this arc.

6. File {BOM_FILE_PATH} indicates the bill of materials (BOM) structure of the products. 
The data follows a recursive adjacency list model where each row represents a single directed 
edge in a product hierarchy. The first column 'mother' is the assembly or sub-assembly; 
the second column 'child' is the component or part required by the parent. The third column 
'individual_input_quantity_q_mc' is the multiplier for the child within that specific mother product.
Every product in the car product group is a root node (it never appears in the child column).
A raw material is a Leaf Node (it never appears in the mother column). 
To resolve the full BOM of individual car, you must recursively traverse the table from the car (root) to the leaves.

7. File {INITIAL_INVENTORY_FILE_PATH} indicates the initial inventory levels of products at different nodes.
The first column 'node_n' is the unique node ID, the second column 'product_p' is the unique product ID,
and the third column 'initial_inventory_I_np0' is the initial inventory level of product. You can ignore all other columns.

The optimization model computes the optimal solution and writes the solution to file {SOLUTION_FILE_PATH}.
To parse the solution and get the flow of specific products in the optimal solution, you can use the tool 'GetSolutionFlow'.

To identity the bottlenecks in the supply chain, you can examine the inventory levels of engine, gear, battery and seats at zp7 
in the last period using the tool 'GetSolutionInventory', then summarize all the engine, gear, battery and seats needed to 
construct the cars not fulfilled using BOM structure in file {BOM_FILE_PATH}, and compare the remaining inventory levels with 
the needed parts.
"""