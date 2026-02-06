from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List
from pyscipopt import Model as SCIPModel, quicksum
import pandas as pd # pyright: ignore[reportMissingModuleSource]
import networkx as nx # pyright: ignore[reportMissingModuleSource]
import logging
from collections import Counter

@dataclass(frozen=False)
class Operation:
    input_groups: List[str]
    input_group_quantities: List[int]
    output_group: str
    output_group_quantity: int

INFLOW_NODE_LIST = [
    'engine-prod',
    'gear-prod',
    'seat-trans', 
    'battery-trans'
]

DATA_PATH = './data'
OUTPUT_PATH = './output'

logging.basicConfig(level=logging.INFO)
class CarProductionSupplyChainModel:
    def __init__(
            self, data_path: str = DATA_PATH, 
            output_path: str = OUTPUT_PATH
        ) -> None:
        self.INITIAL_PERIOD: int = 60
        self.FIRST_PLANNING_PERIOD: int = self.INITIAL_PERIOD + 1
        self.LAST_PLANNING_PERIOD: int = 74
        self.data_path = data_path
        self.output_path = output_path
        # Load data and initialize model parameters here
        self.bom = self._get_bom()
        self.supply_chain_graph: nx.DiGraph = self.build_supply_chain_graph()
        self.product_to_group, self.group_to_products = self._get_product_groups()
        self.scip_model = SCIPModel("CarProductionSupplyChain")
        self.operations = self._get_operations()
        self.analyze_bom()
        self.build_model()
    
    def analyze_bom(self) -> None:
        # Analyze the Bill of Materials (BOM) structure
        # input is a dictionary where key is product and value is a dictionary of components and their quantities
        # needed to build that product.
        # Check if the following assumptions are correct:
        # Each car requires exactly one engine product type, one battery product BEV, one gear product type, and one seat product type.
        # print out anmolies if any.
        missing_children_dict: Dict[str, List[str]] = {
            'engine': [],
            'battery': [],
            'gear': [],
            'seat': []
        }
        for car_product in self.bom:
            if not car_product.isdigit(): # not a car vin
                continue
            children_products = self.bom[car_product].keys()
            children_groups: List[str] = [self.product_to_group[child] for child in children_products]
            group_counter = Counter(children_groups)
            for group_name in missing_children_dict.keys():
                assert group_counter.get(group_name, 0) <= 1, \
                    f"Car product {car_product} has multiple {group_name} children."
                if group_name not in group_counter:
                    missing_children_dict[group_name].append(car_product)
        for group_name in missing_children_dict:
            logging.warning(f"{len(missing_children_dict[group_name])} car products miss {group_name} children.")


    def build_model(
            self,
        ) -> None:
            # Define variables, constraints, and objective function here
            # Example: self.model.addVar(...), self.model.addCons(...), self.model.setObjective(...)
            self._add_vars()
            self._add_constraints()
            self.delivery_penalty_score = self.get_demand_matching_scores()
            self._set_objective()
            self.scip_model.optimize()
            self.best_sol = self.scip_model.getBestSol()
            # # self.show_specific_variables(['zp7'], self.group_to_products['engine'], periods=[60, 61, 62, 63])
            self.save_solution()
    
    def _add_vars(
        self,
    ) -> None:
        self.edge_flow_vars = self._add_flow_vars()
        
        self.inventory_vars = self._add_inventory_vars()

        self.inflow_vars = self._add_inflow_vars()

    def _add_inflow_vars(
        self,
    ) -> Dict[Tuple[str, str, int], Any]:
        # Declear SCIP variables for four nodes with inflow:
        # engine-prod with engine products
        # gear-prod with gear products
        # seat-trans with seat-component products
        # battery-trans with battery-component products
        # for all periods between INITIAL_PERIOD and LAST_PLANNING_PERIODS
        inflow_var_dict: Dict[Tuple[str, str, int], Any] = {}
        inflow_var_info_list: List[Dict[str, Any]] = []
        
        nodes_with_inflow = [
            ('engine-prod', 'engine'),
            ('gear-prod', 'gear'),
            ('seat-trans', 'seat-component'),
            ('battery-trans', 'battery-component')
        ]
        
        for node, group in nodes_with_inflow:
            products = self.group_to_products[group]
            logging.info(f"Defining inflow variables at node {node} for {len(products)} products in group {group}")
            for p in products:
                for t in range(self.INITIAL_PERIOD, self.LAST_PLANNING_PERIOD + 1):
                    var_name = f"inflow_{node}_{p}_{t}"
                    var = self.scip_model.addVar(var_name, vtype="INTEGER", lb=0)
                    inflow_var_dict[node, p, t] = var
                    
                    # Collect variable information
                    inflow_var_info_list.append({
                        'node': node,
                        'product_name': p,
                        'period': t,
                        'lower_bound': 0,
                        'upper_bound': None
                    })
        
        # Create DataFrame with all variable information
        inflow_var_info_df = pd.DataFrame(inflow_var_info_list)
        logging.info(f"Created inflow variables information dataframe with {len(inflow_var_info_df)} variables")
        inflow_var_info_df.to_csv(f'{self.output_path}/inflow_variable_info.csv', index=False)
        
        return inflow_var_dict
        
    def _add_inventory_vars(self) -> Dict[Tuple[str, str, int], Any]:
        inv_var_info_list: List[Dict[str, Any]] = []
        inv_var_dict: Dict[Tuple[str, str, int], Any] = {}
        # Add inventory variables for seat-component products at seat-trans node
        self._add_inv_vars_generic(
            var_dict=inv_var_dict, 
            var_info_list=inv_var_info_list,
            node_list=['seat-trans', 'seat-prod'],
            products = self.group_to_products['seat-component'],
        )
        # Add inventory variables for seat products at seat-inv node
        self._add_inv_vars_generic(
            var_dict=inv_var_dict, 
            var_info_list=inv_var_info_list,
            node_list=['seat-inv', 'zp7'],
            products = self.group_to_products['seat'],
        )
        # Add inventory variables for battery-component products at battery-trans node
        self._add_inv_vars_generic(
            var_dict=inv_var_dict, 
            var_info_list=inv_var_info_list,
            node_list=['battery-trans', 'battery-prod'],
            products = self.group_to_products['battery-component'],
        )
        # Add inventory variables for battery products at battery-inv node
        self._add_inv_vars_generic(
            var_dict=inv_var_dict, 
            var_info_list=inv_var_info_list,
            node_list=['battery-inv', 'zp7'],
            products = self.group_to_products['battery'],
        )
        # Add inventory variables for engine products at engine-inv node
        self._add_inv_vars_generic(
            var_dict=inv_var_dict, 
            var_info_list=inv_var_info_list,
            node_list=['gear-prod', 'gear-inv', 'zp7'],
            products = self.group_to_products['gear'],
        )
        self._add_inv_vars_generic(
            var_dict=inv_var_dict, 
            var_info_list=inv_var_info_list,
            node_list=['engine-prod', 'engine-inv', 'zp7'],
            products = self.group_to_products['engine'],
        )
        # Don't need inventory tracking for zp8 node (end customer delivery point)
        # self._add_inv_vars_generic(
        #     var_dict=inv_var_dict, 
        #     var_info_list=inv_var_info_list,
        #     node_list=['zp8'],
        #     products = self.group_to_products['car'],
        # )
        # Create DataFrame with all variable information
        inv_var_info_df = pd.DataFrame(inv_var_info_list)
        logging.info(f"Created inventory variables information dataframe with {len(inv_var_info_df)} variables")
        logging.info(f"Variable dataframe sample:\n{inv_var_info_df.head()}")
        inv_var_info_df.to_csv(f'{self.output_path}/inventory_variable_info.csv', index=False)
        return inv_var_dict

    def _add_inv_vars_generic(
            self,
            var_dict: Dict[Tuple[str, str, int], Any],
            var_info_list: List[Dict[str, Any]],
            node_list: List[str],
            products: List[str],
        ) -> None:
        # Declare inventory variables for specified nodes and products 
        # from period INITIAL_PERIOD to LAST_PLANNING_PERIODS
        for node in node_list:
            logging.info(f"Defining inventory variables at node {node} for {len(products)} products")
            for p in products:
                for t in range(self.INITIAL_PERIOD, self.LAST_PLANNING_PERIOD + 1):
                    var_name = f"inventory_{node}_{p}_{t}"
                    var = self.scip_model.addVar(var_name, vtype="INTEGER", lb=0)
                    var_dict[node, p, t] = var
                    
                    # Collect variable information
                    var_info_list.append({
                        'node': node,
                        'product_name': p,
                        'period': t,
                        'lower_bound': 0,
                        'upper_bound': None
                    })

    def _add_flow_vars(
        self, 
    ) -> Dict[Tuple[str, str, str, int], Any]:
        flow_var_info_list: List[Dict[str, Any]] = []
        flow_var_dict: Dict[Tuple[str, str, str, int], Any] = {}
        # Add flow variables for engione products on specific edges
        self._add_flow_vars_generic(
            var_dict=flow_var_dict, 
            var_info_list=flow_var_info_list,
            edge_list=[
                ('engine-prod', 'engine-inv'),
                ('engine-inv', 'zp7')
            ],
            products = self.group_to_products['engine'],
        )

        # Add flow variables for gear products on specific edges
        self._add_flow_vars_generic(
            var_dict=flow_var_dict, 
            var_info_list=flow_var_info_list,
            edge_list=[
                ('gear-prod', 'gear-inv'),
                ('gear-inv', 'zp7')
            ],
            products = self.group_to_products['gear'],
        )

        # Add flow variables for seat-components products 
        self._add_flow_vars_generic(
            var_dict=flow_var_dict, 
            var_info_list=flow_var_info_list,
            edge_list=[
                ('seat-trans', 'seat-prod'),
            ],
            products = self.group_to_products['seat-component'],
        )

        # Add flow variables for seat products 
        self._add_flow_vars_generic(
            var_dict=flow_var_dict, 
            var_info_list=flow_var_info_list,
            edge_list=[
                ('seat-prod', 'seat-inv'),
                ('seat-inv', 'zp7')
            ],
            products = self.group_to_products['seat'],
        )

        # Add flow variables for seat-components products 
        self._add_flow_vars_generic(
            var_dict=flow_var_dict, 
            var_info_list=flow_var_info_list,
            edge_list=[
                ('battery-trans', 'battery-prod'),
            ],
            products = self.group_to_products['battery-component'],
        )

        # Add flow variables for seat products 
        self._add_flow_vars_generic(
            var_dict=flow_var_dict, 
            var_info_list=flow_var_info_list,
            edge_list=[
                ('battery-prod', 'battery-inv'),
                ('battery-inv', 'zp7')
            ],
            products = self.group_to_products['battery'],
        )

        # Add flow variables for seat products 
        self._add_flow_vars_generic(
            var_dict=flow_var_dict, 
            var_info_list=flow_var_info_list,
            edge_list=[
                ('zp7', 'zp8'),
            ],
            products = self.group_to_products['car'],
        )
        # Create DataFrame with all variable information
        flow_var_info_df = pd.DataFrame(flow_var_info_list)
        logging.info(f"Created variable information dataframe with {len(flow_var_info_df)} variables")
        logging.info(f"Variable dataframe sample:\n{flow_var_info_df.head()}")
        flow_var_info_df.to_csv(f'{self.output_path}/flow_variable_info.csv', index=False)
        return flow_var_dict

    def _add_flow_vars_generic(
            self,
            var_dict: Dict[Tuple[str, str, str, int], Any],
            var_info_list: List[Dict[str, Any]],
            edge_list: List[Tuple[str, str]],
            products: List[str],
        ) -> None:
            # Declare flow variables specifically for two edges below:
            # (1) engine-prod -> engine-inv
            # (2) engine-inv -> zp7
            # and all engine products in all periods between INITIAL_PERIOD and LAST_PLANNING_PERIODS
            
            for edge in self.supply_chain_graph.edges(data=True):
                start_node, end_node, edge_data = edge
                if (start_node, end_node) not in edge_list:
                    continue
                
                logging.info(f"Defining flow variables on edge {start_node} -> {end_node} for {len(products)} products")
               
                # Get max flow limits if they exist
                product_period_to_flow_limit: Dict[Tuple[str, int], int] = edge_data['max_flow_per_product_period']
                
                for p in products:
                    for t in range(self.INITIAL_PERIOD, self.LAST_PLANNING_PERIOD + 1):
                        # Get upper bound from max_flow_per_product_period if available, otherwise use a large default
                        flow_limit: Optional[int] = product_period_to_flow_limit.get((p, t), None)
                        
                        var_name = f"flow_{start_node}_{end_node}_{p}_{t}"
                        var = self.scip_model.addVar(var_name, vtype="INTEGER", lb=0, ub=flow_limit)
                        var_dict[start_node, end_node, p, t] = var
                        
                        # Collect variable information
                        var_info_list.append({
                            'start_node': start_node,
                            'end_node': end_node,
                            'product_name': p,
                            'period': t,
                            'lower_bound': 0,
                            'upper_bound': flow_limit
                        })

    def _add_constraints(self) -> None:
        self._set_initial_conditions()
        self._add_inflow_node_flow_balance_constraints()
        self._add_flow_through_node_flow_balance_constraints()
        self._add_production_node_flow_balance_constraints()
        self._add_delivery_constraints()
    
    def _add_delivery_constraints(self) -> None:
        # Add constraint for each car product: sum of flow from zp7 to zp8 across all periods <= 1
        # This prevents duplicated fulfillment of the same product
        car_products = self.group_to_products['car']
        num_cons_added: int = 0
        
        for p in car_products:
            # Sum flow of product p from zp7 to zp8 across all periods
            flow_list = []
            for t in range(self.FIRST_PLANNING_PERIOD, self.LAST_PLANNING_PERIOD + 1):
                if ('zp7', 'zp8', p, t) in self.edge_flow_vars:
                    flow_list.append(self.edge_flow_vars['zp7', 'zp8', p, t])
            
            if flow_list:  # Only add constraint if there are variables
                flow_sum = quicksum(flow_list)
                
                # Add constraint: sum <= 1
                self.scip_model.addCons(
                    flow_sum <= 1,
                    name=f"delivery_unique_{p}"
                )
                num_cons_added += 1
        
        logging.info(f"Added {num_cons_added} delivery constraints to prevent duplicated fulfillment.")

    def _set_initial_conditions(self) -> None:
        # Set inventory variables at INITIAL_PERIOD
        num_inv_set = 0
        for (node, p, t), var in self.inventory_vars.items():
            if t == self.INITIAL_PERIOD:
                initial_inv = self.supply_chain_graph.nodes[node]['product_initial_inventory'].get(p, 0)
                self.scip_model.addCons(var == initial_inv, name=f"initial_inv_{node}_{p}")
                num_inv_set += 1
        
        # Set flow variables at INITIAL_PERIOD
        num_flow_set = 0
        for (start, end, p, t), var in self.edge_flow_vars.items():
            if t == self.INITIAL_PERIOD:
                initial_flow = self.supply_chain_graph.edges[start, end]['initial_flow'].get((t, p), 0)
                self.scip_model.addCons(var == initial_flow, name=f"initial_flow_{start}_{end}_{p}")
                num_flow_set += 1
        
        logging.info(f"Set {num_inv_set} initial inventory constraints and {num_flow_set} initial flow constraints at period {self.INITIAL_PERIOD}.")

    def _add_inflow_node_flow_balance_constraints(self) -> None:
        nodes_with_inflow = [
            ('engine-prod', 'engine'),
            ('gear-prod', 'gear'),
            ('seat-trans', 'seat-component'),
            ('battery-trans', 'battery-component')
        ]
        num_cons_added: int = 0
        for node, group in nodes_with_inflow:
            products = self.group_to_products[group]
            initial_inventories = self.supply_chain_graph.nodes[node]['product_initial_inventory']
            
            # Outgoing edges from this node
            out_edges = list(self.supply_chain_graph.out_edges(node))
            assert len(out_edges) == 1, f"Node {node} should have exactly one outgoing edge."
            only_out_edge = out_edges[0]
            
            for p in products:
                for t in range(self.FIRST_PLANNING_PERIOD, self.LAST_PLANNING_PERIOD + 1):
                    # I_{n,p,t} = I_{n,p,t-1} + Inflow_{n,p,t} - sum(Flow_{n,j,p,t})
                    
                    inflow = self.inflow_vars[node, p, t]
                    prev_inv = self.inventory_vars[node, p, t-1]
                    curr_inv = self.inventory_vars[node, p, t]
                    
                    out_flow = self.edge_flow_vars[node, only_out_edge[1], p, t]
                    
                    self.scip_model.addCons(
                        curr_inv == prev_inv + inflow - out_flow,
                        name=f"flow_balance_{node}_{p}_{t}"
                    )
                    num_cons_added += 1
        logging.info(f"Added {num_cons_added} inflow node flow balance constraints.")

    def _add_flow_through_node_flow_balance_constraints(self) -> None:
        flow_through_nodes = [
            ('gear-inv', 'gear'),
            ('engine-inv', 'engine'),
            ('battery-inv', 'battery'),
            ('seat-inv', 'seat')
        ]
        num_cons_added: int = 0
        for node, group in flow_through_nodes:
            products = self.group_to_products[group]
            initial_inventories = self.supply_chain_graph.nodes[node]['product_initial_inventory']
            
            in_edges = list(self.supply_chain_graph.in_edges(node, data=True))
            assert len(in_edges) == 1, f"Node {node} should have exactly one incoming edge."
            only_in_edge = in_edges[0]
            out_edges = list(self.supply_chain_graph.out_edges(node))
            assert len(out_edges) == 1, f"Node {node} should have exactly one outgoing edge."
            only_out_edge = out_edges[0]
            
            for p in products:
                for t in range(self.FIRST_PLANNING_PERIOD, self.LAST_PLANNING_PERIOD + 1):
                    # Inflow from incoming edges with lead time
                    inflow_sum = 0
                    i, _, edge_data = only_in_edge
                    lead_time = edge_data['lead_time']
                    arrival_time = t - lead_time
                    if arrival_time < self.INITIAL_PERIOD:
                        # Use initial flow from edge data
                        inflow_sum += edge_data['initial_flow'].get((arrival_time, p), 0)
                    else:
                        # Use flow variable from edge_flow_vars
                        inflow_sum += self.edge_flow_vars[i, node, p, arrival_time]
                    
                    # Outflow to outgoing edges
                    outflow_sum = self.edge_flow_vars[node, only_out_edge[1], p, t]
                    
                    prev_inv = self.inventory_vars[node, p, t-1]
                    curr_inv = self.inventory_vars[node, p, t]
                    
                    self.scip_model.addCons(
                        curr_inv == prev_inv + inflow_sum - outflow_sum,
                        name=f"flow_balance_{node}_{p}_{t}"
                    )
                    num_cons_added += 1
        logging.info(f"Added {num_cons_added} flow through node flow balance constraints.")

    def _add_production_node_flow_balance_constraints(self) -> None:
        production_nodes = [
            ('zp7', ['engine', 'gear', 'battery', 'seat']),
            ('seat-prod', ['seat-component']),
            ('battery-prod', ['battery-component'])
        ]
        num_cons_added: int = 0
        for node, input_groups in production_nodes:
            in_edges = list(self.supply_chain_graph.in_edges(node, data=True))
            out_edges = list(self.supply_chain_graph.out_edges(node))
            assert len(out_edges) == 1, f"Node {node} should have exactly one outgoing edge."
            only_out_edge = out_edges[0]
            
            for group in input_groups:
                products = self.group_to_products[group]
                for p in products:
                    for t in range(self.FIRST_PLANNING_PERIOD, self.LAST_PLANNING_PERIOD + 1):
                        # Inflow from incoming edges with lead time
                        inflow_list = []
                        for i, _, edge_data in in_edges:
                            lead_time = edge_data['lead_time']
                            arrival_time = t - lead_time
                            if arrival_time < self.INITIAL_PERIOD:
                                inflow_list.append(edge_data['initial_flow'].get((arrival_time, p), 0))
                            else:
                                if (i, node, p, arrival_time) in self.edge_flow_vars:
                                    inflow_list.append(self.edge_flow_vars[i, node, p, arrival_time])
                        inflow_sum = quicksum(inflow_list)
                        
                        # Production consumption
                        consumption_list = []
                        only_out_edge_name = only_out_edge[1]
                        edge_group = self.supply_chain_graph.edges[node, only_out_edge_name]['transport_group']
                        possible_output_products = self.group_to_products[edge_group]
                        for output_product in possible_output_products:
                            qty_needed = self.bom.get(output_product, {}).get(p, 0)
                            if qty_needed > 0:
                                if (node, only_out_edge_name, output_product, t) in self.edge_flow_vars:
                                    consumption_list.append(self.edge_flow_vars[node, only_out_edge_name, output_product, t] * qty_needed)
                        consumption = quicksum(consumption_list)
                        
                        prev_inv = self.inventory_vars[node, p, t-1]
                        curr_inv = self.inventory_vars[node, p, t]
                        
                        self.scip_model.addCons(
                            curr_inv == prev_inv + inflow_sum - consumption,
                            name=f"flow_balance_prod_{node}_{p}_{t}"
                        )
                        num_cons_added += 1
        logging.info(f"Added {num_cons_added} production node flow balance constraints.")

    def _get_bom(self) -> Dict[str, Dict[str, int]]:
        # Load Bill of Materials from CSV file
        bom_df = pd.read_csv(f'{self.data_path}/bom.csv')
        bom: Dict[str, Dict[str, int]] = {}
        for _, row in bom_df.iterrows():
            product_str = str(row['mother'])
            component_str = str(row['child'])
            quantity = int(row['individual_input_quantity_q_mc'])
            if product_str == component_str and quantity == 1:
                logging.info(f"Skipping self-referential BOM entry for product {product_str}")
                continue
            if product_str not in bom:
                bom[product_str] = {}
            assert component_str not in bom.get(product_str, {}), \
                f"Duplicate BOM entry for product {product_str} and component {component_str}"
            bom[product_str][component_str] = quantity
        # # logging.info(f"Sample BOM entry: {next(iter(bom.items()))}")
        # # Fix data to have one BEV battery component per car
        # for car_product in bom:
        #     if not car_product.isdigit(): # not a car vin
        #         continue
        #     if 'BEV' not in bom[car_product]:
        #         # Assign a default battery component product
        #         bom[car_product]['BEV'] = 1
        return bom

    def get_demand_matching_scores(self) -> Dict[str, Dict[int,int]]:
        # Get a dict from car product to period to a score quantity
        demand_df = pd.read_csv(f'{self.data_path}/demands.csv')
        product_to_demand_period: Dict[str, int] = {}
        for _, row in demand_df.iterrows():
            car_product: str = str(row['product_p'])
            product_to_demand_period[car_product] = int(row['demand_d_npt'])

        score_dict: Dict[str, Dict[int, int]] = {}
        for car_product in product_to_demand_period:
            demand_period = product_to_demand_period[car_product]
            score_dict[car_product] = {
                deliver_period: max(deliver_period-demand_period, 0)
                for deliver_period in range(self.FIRST_PLANNING_PERIOD, self.LAST_PLANNING_PERIOD + 1)
            }

        return score_dict


    def _get_all_nodes(self) -> List[Tuple[str, Any]]:
        # Load node in the supply chain graph from CSV file
        node_df = pd.read_csv(f'{self.data_path}/nodes.csv')
        all_nodes = [str(n) for n in node_df['node_n']]

        # Get initial inventory data
        initial_inventory_df = pd.read_csv(f'{self.data_path}/initial_inventories.csv')
        node_to_product_to_initial_inventory: Dict[str, Dict[str, int]] = {}
        for _, row in initial_inventory_df.iterrows():
            node_str = str(row['node_n'])
            product_str = str(row['product_p'])
            node_to_product_to_initial_inventory.setdefault(node_str,{})[product_str] = row['initial_inventory_I_np0']

        # Get admissible inflow products per node
        admissible_inflow_df = pd.read_csv(f'{self.data_path}/nodes_inflow.csv')
        node_to_admissible_inflow_products: Dict[str, List[str]] = {}
        for _, row in admissible_inflow_df.iterrows():
            node_str = str(row['node_n'])
            assert node_str in all_nodes, f"Admissible inflow node {node_str} not in all nodes list"
            node_to_admissible_inflow_products.setdefault(node_str, []).append(str(row['product_p']))

        return [
            (
                n, 
                {
                    'product_initial_inventory': node_to_product_to_initial_inventory.get(n, {}),
                    'admissible_inflow_products': node_to_admissible_inflow_products.get(n, [])
                }
            )
            for n in all_nodes
        ]

    def build_supply_chain_graph(self) -> nx.DiGraph:
        # Build the supply chain graph using networkx or similar library

        # Create a directed graph to hold all nodes and edges
        G = nx.DiGraph()

        # Add all nodes to the graph
        all_nodes = self._get_all_nodes()
        logging.info(f"\nAll nodes with data: \n{all_nodes}")
        G.add_nodes_from(all_nodes)
        # print out number of nodes in graph G
        logging.info(f"Total number of nodes added to the graph: {G.number_of_nodes()}")
        # print out data of node engine-prod
        logging.info(f"\nData of node 'engine-prod': \n{G.nodes['engine-prod']}")

        # Add edges with flow as weight
        edge_df = pd.read_csv(f'{self.data_path}/arcs.csv')
        edge_period_capacity_df = pd.read_csv(f'{self.data_path}/capacity_at_arc.csv').drop_duplicates()
        edge_period_capacity_dict = edge_period_capacity_df.set_index(['starting_node_i', 'ending_node_j', 'period_t'])['capacity_c_ijt'] \
            .unstack(level='period_t') \
            .apply(dict, axis=1).to_dict()
        logging.info(f"\nEdge period capacity dict: \n{edge_period_capacity_dict}")
        
        initial_flow_df = pd.read_csv(f'{self.data_path}/initial_flows.csv').drop_duplicates()
        edge_period_product_flow: Dict[Tuple[str, str], Dict[Tuple[int, str], int]] = {}
        for _, row in initial_flow_df.iterrows():
            edge_period_product_flow.setdefault((row['starting_node_i'], row['ending_node_j']), {})[(row['period_t'], row['product_p'])] = row['initial_flow']
        logging.info(f"\nEdge period product flow dict: \n{edge_period_product_flow}")

        # Max flow per group per arc
        max_flow_group_arc_df = pd.read_csv(f'{self.data_path}/max_flow_group_per_arc.csv').drop_duplicates()
        edge_group_period_capacity: Dict[Tuple[str, str], Dict[Tuple[str, int], int]] = {}
        for _, row in max_flow_group_arc_df.iterrows():
            edge_group_period_capacity.setdefault((row['starting_node_i'], row['ending_node_j']), {})[(row['group_g'], row['period_t'])] = row['planned_flow']

        # Max flow per product per arc
        max_flow_product_arc_df = pd.read_csv(f'{self.data_path}/max_flow_product_per_arc.csv').drop_duplicates()
        edge_product_period_capacity: Dict[Tuple[str, str], Dict[Tuple[str, int], int]] = {}
        for _, row in max_flow_product_arc_df.iterrows():
            edge_product_period_capacity.setdefault((row['starting_node_i'], row['ending_node_j']), {})[(row['product_p'], row['period_t'])] = row['planned_flow']
    
        for _, row in edge_df.iterrows():
            G.add_edge(row['starting_node_i'], row['ending_node_j'], 
                lead_time=row['process_lead_time_l_ij'],
                transport_group=row['group_g'],
                period_capacity=edge_period_capacity_dict.get((row['starting_node_i'], row['ending_node_j']), {}),
                initial_flow=edge_period_product_flow.get((row['starting_node_i'], row['ending_node_j']), {}),
                max_flow_per_group_period=edge_group_period_capacity.get((row['starting_node_i'], row['ending_node_j']), {}),
                max_flow_per_product_period=edge_product_period_capacity.get((row['starting_node_i'], row['ending_node_j']), {})
            )
        logging.info(f"\nData Frame of edges: \n{edge_df.to_string(index=False)}")
        logging.info(f"\nData Frame of edge capacity: \n{edge_period_capacity_df.to_string(index=False)}")
        logging.info(f"Supply chain graph built with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
        return G

    def _get_operations(self) -> Dict[str, Operation]: 
        # Load operations from CSV file, returns node_name -> Operation
        operations_df = pd.read_csv(f'{self.data_path}/operations.csv')
        operations = {}
        for _, row in operations_df.iterrows():
            node_name = str(row['node_n'])
            if node_name not in operations:
                operations[node_name] = Operation(
                    input_groups=[],
                    input_group_quantities=[],
                    output_group='',
                    output_group_quantity=0
                )
            input_group = str(row['input_product_group_x'])
            output_group = str(row['output_product_group_y'])
            input_quantity = int(row['input_quantity_in_nxy'])
            output_quantity = int(row['output_quantity_out_nxy'])
            operations[node_name].input_groups.append(input_group)
            operations[node_name].input_group_quantities.append(input_quantity)
            assert operations[node_name].output_group == '' or operations[node_name].output_group == output_group, \
                f"Conflicting output groups for node {node_name}: {operations[node_name].output_group} vs {output_group}"
            operations[node_name].output_group = output_group
            assert operations[node_name].output_group_quantity == 0 or operations[node_name].output_group_quantity == output_quantity, \
                f"Conflicting output quantities for node {node_name}: {operations[node_name].output_group_quantity} vs {output_quantity}"
            operations[node_name].output_group_quantity = output_quantity
        logging.info(f"Operations loaded: {operations}")
        return operations

    def _get_product_groups(self) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
        # Load product groups from CSV file
        product_to_group: Dict[str, str] = {}
        group_to_products: Dict[str, List[str]] = {}
        df = pd.read_csv(f'{self.data_path}/products.csv')
        for _, row in df.iterrows():
            assert row['product_p'] not in product_to_group, f"Duplicate product found: {row['product_p']}"
            product_to_group[row['product_p']] = row['group_g']
            group_to_products.setdefault(row['group_g'], []).append(row['product_p'])
        
        # Print out product groups for verification
        for group in group_to_products:
            logging.info(f"Group {group} has {len(group_to_products[group])} items.")
        return product_to_group, group_to_products

    def examine_node(self, node: str) -> None:
        # Function to examine a specific node in the supply chain graph
        if node in self.supply_chain_graph:
            data = self.supply_chain_graph.nodes[node]
            logging.info(f"Node {node} data: {data}")
        else:
            logging.warning(f"Node {node} not found in the supply chain graph.")

    def examine_edge(self, start_node: str, end_node: str) -> None:
        # Function to examine a specific edge in the supply chain graph
        if self.supply_chain_graph.has_edge(start_node, end_node):
            data = self.supply_chain_graph.edges[start_node, end_node]
            logging.info(f"Edge from {start_node} to {end_node} data: {data}")
        else:
            logging.warning(f"Edge from {start_node} to {end_node} not found in the supply chain graph.")

    def _set_objective(self) -> None:
        # Define the objective function for the optimization model
        # Summation of all flow variables and inventory variables over all periods from FIRST_PLANNING_PERIODS to LAST_PLANNING_PERIODS
        obj_expr = 0
        # obj_expr = 0.1*quicksum(
        #     var for (start, end, p, t), var in self.edge_flow_vars.items()
        #     if self.FIRST_PLANNING_PERIOD <= t <= self.LAST_PLANNING_PERIOD
        # )
        
        # obj_expr += 0.1*quicksum(
        #     var for (node, p, t), var in self.inventory_vars.items()
        #     if self.FIRST_PLANNING_PERIOD <= t <= self.LAST_PLANNING_PERIOD
        # )
        
        # Add penalty term for missed or delayed deliveries
        # Penalize based on delivery time relative to demand time
        delivery_penalty_expr = 0.01*quicksum(
            self.edge_flow_vars['zp7', 'zp8', p, t] * self.delivery_penalty_score[p][t]
            for p in self.group_to_products['car']
            for t in range(self.FIRST_PLANNING_PERIOD, self.LAST_PLANNING_PERIOD + 1)
            if ('zp7', 'zp8', p, t) in self.edge_flow_vars and p in self.delivery_penalty_score and t in self.delivery_penalty_score[p]
        )

        obj_expr += 1 * quicksum(
            1 - quicksum(
                self.edge_flow_vars['zp7', 'zp8', p, t]
                for t in range(self.FIRST_PLANNING_PERIOD, self.LAST_PLANNING_PERIOD + 1)
                if ('zp7', 'zp8', p, t) in self.edge_flow_vars
            )
            for p in self.group_to_products['car']
        )

        self.scip_model.setObjective(obj_expr, "minimize")

    def show_specific_variables(self, nodes: List[str], products: List[str], periods: List[int]) -> None:
        # Show indicated flow variable and inventory variable value in the best solution found by SCIP
        if self.best_sol is None:
            logging.warning("No solution found.")
            return

        logging.info(f"--- Querying variables for nodes: {nodes}, products: {products}, periods: {periods} ---")
        
        # Check Flow Variables
        for (start, end, p, t), var in self.edge_flow_vars.items():
            if (start in nodes or end in nodes) and p in products and t in periods:
                val = self.scip_model.getSolVal(self.best_sol, var)
                logging.info(f"flow_{start}_{end}_{p}_{t}: {val}")

        # Check Inventory Variables
        for (node, p, t), var in self.inventory_vars.items():
            if node in nodes and p in products and t in periods:
                val = self.scip_model.getSolVal(self.best_sol, var)
                logging.info(f"inventory_{node}_{p}_{t}: {val}")

        # Check Inflow Variables
        for (node, p, t), var in self.inflow_vars.items():
            if node in nodes and p in products and t in periods:
                val = self.scip_model.getSolVal(self.best_sol, var)
                logging.info(f"inflow_{node}_{p}_{t}: {val}")

    def save_solution(self, output_filename: str = f'solution.csv') -> None:
        # Save solved solution to a csv file with two columns: variable name and variable value
        if self.best_sol is None:
            logging.warning("No solution found to save.")
            return
        
        solution_data = []
        
        # Flow variables
        for (start, end, p, t), var in self.edge_flow_vars.items():
            val = self.scip_model.getSolVal(self.best_sol, var)
            solution_data.append({'variable_name': f"flow_{start}_{end}_{p}_{t}", 'variable_value': val})
            
        # Inventory variables
        for (node, p, t), var in self.inventory_vars.items():
            val = self.scip_model.getSolVal(self.best_sol, var)
            solution_data.append({'variable_name': f"inventory_{node}_{p}_{t}", 'variable_value': val})
            
        # Inflow variables
        for (node, p, t), var in self.inflow_vars.items():
            val = self.scip_model.getSolVal(self.best_sol, var)
            solution_data.append({'variable_name': f"inflow_{node}_{p}_{t}", 'variable_value': val})
                     
        df = pd.DataFrame(solution_data)
        output_path = f'{self.output_path}/{output_filename}'
        df.to_csv(output_path, index=False)
        logging.info(f"Solution saved to {output_path}")