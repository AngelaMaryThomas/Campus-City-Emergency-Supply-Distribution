# Campus-City-Emergency-Supply-Distribution
# 📦 Warehouse Location & Distribution Optimization

## 1. Problem Statement
Determine the **optimal warehouse locations and distribution plan** that minimizes total annual costs while:

- Meeting all facility demands
- Respecting warehouse capacity constraints
- Operating within the allocated budget

The objective is to identify the **best two warehouses** to operate and determine how supplies should be distributed from these warehouses to campus facilities.

---

# 2. Data Description

## 2.1 Facilities Data (`facilities.csv`)

The dataset contains **15 facilities**. For this micro-project, the following **critical facilities** were selected.

| Facility ID | Facility Name | Type | Daily Demand |
|--------------|---------------|------|--------------|
| MED_CENTER | Campus Medical Center | Hospital | 80 units |
| ENG_BUILDING | Engineering Building | Academic | 30 units |
| SCIENCE_HALL | Science Hall | Academic | 35 units |
| DORM_A | North Dormitory | Residential | 55 units |
| DORM_B | South Dormitory | Residential | 45 units |
| LIBRARY | Main Library | Academic | 25 units |

**Total Daily Demand:** **270 units**

---

## 2.2 Warehouse Data (`warehouses.csv`)

| Warehouse ID | Warehouse Name | Daily Capacity | Construction Cost | Operational Cost / Day |
|---------------|----------------|---------------|------------------|-----------------------|
| WH_NORTH | North Campus Warehouse | 400 units | $300,000 | $800 |
| WH_SOUTH | South Campus Warehouse | 350 units | $280,000 | $700 |
| WH_EAST | East Gate Warehouse | 450 units | $320,000 | $900 |

**Total Available Capacity:** **1,200 units**

---

## 2.3 Transportation Costs (`transportation_costs.csv`)

- **Data Source:** Pre-calculated cost matrix using actual distances  
- **Cost Range:** **$3.68 – $5.03 per unit**  
- **Calculation Method:** Based on geographic coordinates using the **Haversine formula**

---

# 3. Financial Constraints

- **Annual Budget:** `$1,500,000`
- **Operational Period:** `365 days`
- **Construction Cost:** Amortized over **10 years**
- **Cost Rule:** All costs must be **converted to annual values**

---

# 4. Physical & Business Constraints

### Warehouse Selection
Exactly **2 warehouses must be selected** for redundancy.

### Demand Satisfaction
Each facility must receive:
