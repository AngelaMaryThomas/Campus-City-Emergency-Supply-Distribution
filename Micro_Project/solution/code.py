import pandas as pd
import pulp
import matplotlib.pyplot as plt
import os
import sys
import folium
from folium import plugins

# ==========================================
# 1. CORE CONFIGURATION & CONSTANTS
# ==========================================
class Config:
    DATA_PATH = "../datafiles/" # Adjusted for your folder structure
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
# 5. INTERACTIVE GEOSPATIAL VISUALIZATION
# ==========================================
def plot_distribution(data, open_vars, flow_vars, total_cost):
    f_geo = data['geo'].set_index('facility_id').loc[Config.FACILITIES]
    w_geo = data['nodes'].set_index('warehouse_id').loc[Config.SITES]

    # Initialize map centered on the campus area
    m = folium.Map(
        location=[f_geo['latitude'].mean(), f_geo['longitude'].mean()],
        zoom_start=15,
        tiles='CartoDB positron'
    )

    # 1. Add Warehouses to Map
    for w in Config.SITES:
        is_active = pulp.value(open_vars[w]) == 1
        color = 'green' if is_active else 'red'
        icon_type = 'university' if is_active else 'minus-circle'
        
        folium.Marker(
            location=[w_geo.loc[w, 'latitude'], w_geo.loc[w, 'longitude']],
            popup=f"<b>Warehouse: {w}</b><br>Status: {'ACTIVE' if is_active else 'CLOSED'}",
            tooltip=f"Warehouse {w}",
            icon=folium.Icon(color=color, icon=icon_type, prefix='fa')
        ).add_to(m)

    # 2. Add Facilities and Shipping Routes
    for f in Config.FACILITIES:
        # Plot Facility
        folium.CircleMarker(
            location=[f_geo.loc[f, 'latitude'], f_geo.loc[f, 'longitude']],
            radius=10,
            color='#2c3e50',
            fill=True,
            fill_color='#34495e',
            fill_opacity=0.7,
            popup=f"Facility: {f}",
            tooltip=f
        ).add_to(m)

        # Draw Shipping Flows
        for w in Config.SITES:
            vol = pulp.value(flow_vars[w][f])
            if vol and vol > 0:
                # Calculate thickness based on volume (normalized)
                # Adjust '1500' based on your typical shipping volumes
                lw = 1 + (vol / 1500) 
                
                points = [
                    [w_geo.loc[w, 'latitude'], w_geo.loc[w, 'longitude']],
                    [f_geo.loc[f, 'latitude'], f_geo.loc[f, 'longitude']]
                ]
                
                folium.PolyLine(
                    locations=points,
                    weight=lw,
                    color='#3498db',
                    opacity=0.6,
                    tooltip=f"Route: {w} to {f}<br>Annual Volume: {vol:,} units"
                ).add_to(m)

    # 3. Add a Floating Summary Box (HTML/CSS)
    summary_html = f'''
        <div style="position: fixed; 
                    top: 10px; right: 10px; width: 280px; height: auto; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px; border-radius: 5px;
                    box-shadow: 3px 3px 5px rgba(0,0,0,0.2);">
            <b>Network Optimization Report</b><br>
            <hr style="margin: 5px 0;">
            <b>Total Annual Cost:</b> ${total_cost:,.2f}<br>
            <b>Budget Utilization:</b> {(total_cost/Config.MAX_BUDGET)*100:.1f}%<br>
            <b>Status:</b> <span style="color: green;">OPTIMAL</span>
        </div>
    '''
    m.get_root().html.add_child(folium.Element(summary_html))

    # Save and instructions
    output_filename = "Campus_Optimization_Map.html"
    m.save(output_filename)
    print(f"✔ Interactive Folium map saved as: {output_filename}")
    
    # Note: Folium doesn't show directly in terminal like plt.show()
    # It creates an HTML file you can open in any browser.

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
