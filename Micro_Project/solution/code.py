import pandas as pd
import pulp
import matplotlib.pyplot as plt
import os
import sys

# ==========================================
# 1. CORE CONFIGURATION & CONSTANTS
# ==========================================
class Config:
    DATA_PATH = "../data/" # Adjusted for your folder structure
    FACILITIES = ['MED_CENTER', 'ENG_BUILDING', 'SCIENCE_HALL', 'DORM_A', 'DORM_B', 'LIBRARY']
    SITES = ['WH_NORTH', 'WH_SOUTH', 'WH_EAST']
    
    YEAR_DAYS = 365
    LIFE_SPAN = 10  
    MAX_BUDGET = 1500000

# ==========================================
# 2. DATA INGESTION ENGINE
# ==========================================
def load_and_verify_data():
    try:
        files = {
            'reqs': 'demands.csv',
            'nodes': 'warehouses.csv',
            'costs': 'transportation_costs.csv',
            'geo': 'facilities.csv'
        }
        data = {k: pd.read_csv(os.path.join(Config.DATA_PATH, v)) for k, v in files.items()}
        print("✔ Dataset verified and loaded successfully.")
        return data
    except FileNotFoundError as e:
        print(f"✘ CRITICAL ERROR: File not found.\nDetails: {e}")
        sys.exit()

# ==========================================
# 3. TRANSFORMATION & PREP
# ==========================================
def prepare_parameters(raw_data):
    f_demand = raw_data['reqs'].set_index('facility_id')['daily_demand']
    annual_reqs = (f_demand.loc[Config.FACILITIES] * Config.YEAR_DAYS).to_dict()

    wh_data = raw_data['nodes'].set_index('warehouse_id').loc[Config.SITES]
    annual_caps = (wh_data['capacity'] * Config.YEAR_DAYS).to_dict()
    
    fixed_overhead = {
        idx: (row['construction_cost'] / Config.LIFE_SPAN) + (row['operational_cost'] * Config.YEAR_DAYS)
        for idx, row in wh_data.iterrows()
    }

    transit_map = raw_data['costs'].set_index(['from_warehouse', 'to_facility'])['cost_per_unit'].to_dict()
    
    return annual_reqs, annual_caps, fixed_overhead, transit_map

# ==========================================
# 4. LINEAR PROGRAMMING (MILP)
# ==========================================
def run_optimization(demands, caps, overhead, shipping):
    network_opt = pulp.LpProblem("Logistics_Redundancy_Network", pulp.LpMinimize)

    is_open = pulp.LpVariable.dicts("Active", Config.SITES, cat='Binary')
    flow = pulp.LpVariable.dicts("Units", (Config.SITES, Config.FACILITIES), lowBound=0, cat='Integer')

    total_fixed = pulp.lpSum([overhead[w] * is_open[w] for w in Config.SITES])
    total_transit = pulp.lpSum([shipping[(w, f)] * flow[w][f] for w in Config.SITES for f in Config.FACILITIES])
    network_opt += total_fixed + total_transit

    for f in Config.FACILITIES:
        network_opt += pulp.lpSum([flow[w][f] for w in Config.SITES]) == demands[f]

    for w in Config.SITES:
        network_opt += pulp.lpSum([flow[w][f] for f in Config.FACILITIES]) <= caps[w] * is_open[w]

    network_opt += pulp.lpSum([is_open[w] for w in Config.SITES]) == 2
    network_opt += (total_fixed + total_transit) <= Config.MAX_BUDGET

    network_opt.solve(pulp.PULP_CBC_CMD(msg=0))
    return network_opt, is_open, flow

# ==========================================
# 5. ENHANCED VISUALIZATION
# ==========================================
def plot_distribution(data, open_vars, flow_vars, total_cost):
    f_geo = data['geo'].set_index('facility_id').loc[Config.FACILITIES]
    w_geo = data['nodes'].set_index('warehouse_id').loc[Config.SITES]

    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Calculate Max Flow for line scaling
    all_flows = [pulp.value(flow_vars[w][f]) for w in Config.SITES for f in Config.FACILITIES]
    max_flow = max(all_flows) if any(all_flows) else 1

    # 1. Draw connections (Hub and Spoke)
    for w in Config.SITES:
        for f in Config.FACILITIES:
            vol = pulp.value(flow_vars[w][f])
            if vol and vol > 0:
                # Line width scales with shipping volume
                lw = 1 + (vol / max_flow) * 6
                ax.plot([w_geo.loc[w, 'longitude'], f_geo.loc[f, 'longitude']],
                        [w_geo.loc[w, 'latitude'], f_geo.loc[f, 'latitude']],
                        color='#3498db', alpha=0.4, linewidth=lw, zorder=1)

    # 2. Plot Facilities
    ax.scatter(f_geo['longitude'], f_geo['latitude'], color='#2c3e50', 
               s=150, marker='o', label='Campus Facilities', zorder=3, edgecolors='white')

    # 3. Plot Warehouses
    for w in Config.SITES:
        is_active = pulp.value(open_vars[w]) == 1
        color = '#27ae60' if is_active else '#e74c3c'
        marker = 's'
        size = 350 if is_active else 150
        alpha = 1.0 if is_active else 0.4
        
        ax.scatter(w_geo.loc[w, 'longitude'], w_geo.loc[w, 'latitude'], 
                   c=color, marker=marker, s=size, alpha=alpha,
                   label=f'{w} (Open)' if is_active else None, 
                   zorder=4, edgecolors='black')

    # 4. Text Annotations
    for i, txt in enumerate(Config.FACILITIES):
        ax.annotate(txt, (f_geo.iloc[i].longitude, f_geo.iloc[i].latitude), 
                    xytext=(5,5), textcoords='offset points', fontsize=8, fontweight='bold')

    # 5. Display Total Cost and Summary on the PNG
    summary_box = (
        f"NETWORK OPTIMIZATION REPORT\n"
        f"{'='*30}\n"
        f"TOTAL ANNUAL COST: ${total_cost:,.2f}\n"
        f"BUDGET UTILIZATION: {(total_cost/Config.MAX_BUDGET)*100:.1f}%\n"
        f"STATUS: OPTIMAL"
    )
    
    # Text box in the upper left corner
    plt.text(0.02, 0.96, summary_box, transform=ax.transAxes, fontsize=11,
             verticalalignment='top', family='monospace', fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8, edgecolor='#bdc3c7'))

    ax.set_title("Campus City Strategic Supply Chain Map", fontsize=15, fontweight='bold', pad=20)
    ax.legend(loc='lower right', frameon=True, shadow=True)
    
    # Save and Show
    output_filename = "Campus_Optimization_Report.png"
    plt.savefig(output_filename, dpi=300, bbox_inches='tight')
    print(f"✔ Optimized PNG saved as: {output_filename}")
    plt.show()

# ==========================================
# 6. EXECUTION
# ==========================================
def main():
    raw_data = load_and_verify_data()
    demands, caps, overhead, transit_costs = prepare_parameters(raw_data)
    
    model, open_status, flow_status = run_optimization(demands, caps, overhead, transit_costs)
    
    if pulp.LpStatus[model.status] == 'Optimal':
        total_val = pulp.value(model.objective)
        print(f"\n--- OPTIMAL STRATEGY IDENTIFIED ---")
        print(f"Total Yearly Cost: ${total_val:,.2f}")
        
        plot_distribution(raw_data, open_status, flow_status, total_val)
    else:
        print("⚠ Infeasible: Constraints too tight for the given budget.")

if __name__ == "__main__":
    main()