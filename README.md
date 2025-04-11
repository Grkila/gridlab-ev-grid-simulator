# Automated Generation of geo-referenced medium-voltage (MV) Grid Models based on OpenStreetMap (OSM) Data

This tool generates a synthetic medium-voltage (MV) power grid topology and a [pandapower](https://www.pandapower.org/) simulation model for a specified area by using OpenStreetMap (OSM) data.
The reconstructed topology is geo-referenced, i.e. lines follow streets and paths from OSM.
The tool outputs interactive HTML files and a pandapower file, which can be used for simulation and system analysis.

## Methodology

The approach is described in detail in the publication:

Tobias Gebhard; Andrea Tundis; Florian Steinke:
"Automated Generation of Urban Medium-voltage Grids using OpenStreetMap Data", 
*2024 IEEE PES Innovative Smart Grid Technologies Europe (ISGT EUROPE)*
https://doi.org/10.1109/ISGTEUROPE62998.2024.10863461

https://www.researchgate.net/publication/387261923_Automated_Generation_of_Urban_Medium-voltage_Grids_using_OpenStreetMap_Data

**Abstract:**
Realistic geo-referenced electrical distribution grid (DG) models are of great importance for power system analysis and resilience studies. However, DG data are usually not publicly available. In this study, we develop a new process for the automated generation of medium-voltage (MV) grid topologies, specifically for urban areas, based on openly available data and open-source software. OpenStreetMap (OSM) data on power infrastructure, street layouts, and land use, are used as the only input source. In contrast to previous works on DG reconstruction, we use available OSM data on substation locations. Different existing methods are combined in a new, hybrid approach by considering the incompleteness of OSM data, taking the street network into account, and applying the Capacitated vehicle routing problem (CVRP) to find cost-optimal routes for power lines. Our method is tested with a German city as a case study. Furthermore, we verify the result using land use data and evaluate the quality of power-related OSM data. The results demonstrate that our approach can yield realistic geo-referenced MV grid topologies, even with incomplete OSM power data.

## Setup

Tested with Python 3.10.

Create a virtual environment and activate:
```
python -m venv venv
.\venv\scripts\activate
```

Install the packages:
```
pip install -r requirements.txt
pip install geopandas==1.0.1
```


## Configuration

The config file ``config.json`` defines the area of the grid reconstruction and requires some prior information to be provided.

* The city (or multiple cities) are defined in "cities_list".
* The HV-MV Substations must be pre-defined and provided in the queries list. The allowed connections can be restricted with the "pairs" field. 
* If desired, certain OSM substations can be excluded in the "ex_nwr" field.
* If desired, additional transformers can be added using "add_transf_by_coord" (1st element is coordinates, 2nd is the capacity in MW). The coordinates can be copied from the Land Use HTML map by clicking on a location. Also, custom consumers with a provided demand can be defined ("Special Consumers").
* Parameters for the VRPy Routing Optimization can be adjusted in "2"
* Voltage Levels, standard trafo size, and other factors can be adjusted in "3"/"pandapower"

A config file for the German city of Darmstadt is included as an example.
For a new area of interest, the config needs to be adjusted accordingly.

## Run

Execute ``main.py`` and follow the instructions of the GUI.

