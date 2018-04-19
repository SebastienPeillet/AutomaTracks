# AutomaTracks <img src="http://open.geoexmachina.fr/img/article/AM_icon.png"></img>

Automatracks is a Qgis 2.XX plugin to generate least cost path tracks from a point network. Least cost path between two points is calculated with a specific cost function. This function is based on the earthwork that will be necessary to build the tracks, so the main cost is due to cross slope along the tracks.

## Install
Download the entire folder and copy it in the following folder :
  - `Users/.qgis2/python/plugins/`
 
## Interface overview

- Main onglet

<img src="http://open.geoexmachina.fr/img/article/Automatracks_dock.png"></img>

The main onglet provide the form to process least cost path tracks from a point network. The user has to complete the form with the point network layer, the dem layer and the output path. He can chose the number of edges for the graph conception (cf. Principle), the direction constraint method and its threshold, and also the tolerated slope along the tracks. He can also add a mask layer to prevent that the track goes into restricted area. The mask layer disallow graph conception on area where there is a 0 value, the other values allow graph conception.

- Preprocessing tools onglet

<img src="http://open.geoexmachina.fr/img/article/Automatracks_dock2.png"></img>

This onglet provides two tools to generate the point network used in AutomaTracks.

1. Convert ridges to point network

<img src="http://open.geoexmachina.fr/img/article/Automatracks_dock_script.png"></img>

Input : ridge_layer, unique id attr, min length, dem_layer, output_path

This tools will generate points from the ridge, keeping starting and ending points of a ridge polyline and also pass and peak points.

2. Re-order points from a begin point

<img src="http://open.geoexmachina.fr/img/article/Automatracks_dock_script2.png"></img>

Input : point network layer, outlet layer, output path

This tools orders points with L_id from a begin point (or outlet).


## Principle
- Network processing

Automatracks uses the graph theorie to find least cost paths. Each point of the network has **L_id** (line id) and **P_id** (point id) attributes. Automatracks build tracks following theses attributes. It begins with the point that the minimum **L_id** and the *"start"* attribute in the **nature** field. The next point is found with incrementating the **P_id**. From these two points, Automatracks will define an area to clip the DEM (and the mask) layer to reduce time process. The DEM clip will be used to compute the graph with cost between each nodes. It will produce track between these two points, then it does the same with the *n* point to the *"n + 1"* point. If there is tracks previously builded in the clip area, the *"n"* track can also begin from these *"n - x"* tracks.

- Least Cost Path and Dijkstra adaptated to tracks necessities

There are some important aspects to keep in mind to builds passable tracks. Vehicules can't wheel without maneuver if tracks don't respect simple rule about radius of curvature. The radius of curvature threshold (or degree threshold) must be fixed according to the vehicules turning radius. Futhermore, vehicules can't wheel on too steep tracks. So it's possible to fix a threshold.

In a first step, the graph was composed like following :

-- **nodes** were generated from pixels of the DEM clip,

-- **edges** were generated between each node and its neighbours, only if the edge **fulfills the along slope threshold**, computing the cost from the cross slope the between the two nodes.


But due to radius of curvature, the graph changes into :

-- **nodes** are generated from the edges of the previous method... so technically nodes are directed lines between two pixels

-- **edges** are generated between nodes if these nodes fulfill the radius of curvature threshold. Indeed we can determine azimut of each node and relate them to the radius of curvature threshold.


So with this method, how many nodes and edges are generated ?

It can be settled by the user with the edges number option : 8, 24, 40, 48 edges ?


For each pixel, Automatracks will generated nodes from this model :

<img src="http://open.geoexmachina.fr/img/article/liaison_pixel.png" width=600></img>

At the end the graph is only composed from nodes that fulfill length slope threshold (and are not in the mask area if it exists) and theses nodes are related to each other only if they fulfill the radius curvature threshold.

From this graph, it's easy to use the Dijkstra algorithm to find the least cost path, based on the cost of the nodes.


## Illustrated examples to come

"Such empty" as Reddit said

