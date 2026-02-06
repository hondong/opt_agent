
# Examine inputs
SHOW_DEMAND = """
Compute the number of distinct cars needed in each period from the input demand data. 
Save the results in a csv file and report the csv filename.
"""

# Examine outputs
SHOW_FULFILLMENT = """
Compute the total number of cars fulfilled in each period based on the model output. 
Save the results in a csv file and report the csv filename.
Then compute the total number of cars fulfilled in all periods, and report that number.
"""

# Analyze supply chain flow
DIAGNOSE_BOTTLENECKS = """
We have a total of 28000 cars in demand but we only fulfilled 26448 cars in our planning horizon. 
Examine the supply chain flow to identify the bottlenecks.
"""

DIAGNOSE_BOTTLENECKS_V2 = """
We have a total of 28000 cars in demand but we only fulfilled 26448 cars in our planning horizon. 
Examine the supply chain flow, in addition to initial inventory levels, to identify the bottlenecks.
Note that initial inventory levels are available in file './data/initial_inventory.csv'.
Generate a summary of the supply chain flow from the model output solution.
"""
