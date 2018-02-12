#!/usr/bin/env python
# -*- coding: utf-8 -*-
""""
/***************************************************************************
 Utils.py

 Perform a least cost path with a raster conversion in graph
 
 Need : OsGeo library
                              -------------------
        begin                : 2018-01-26
        copyright            : (C) 2017 by Peillet Sebastien
        email                : peillet.seb@gmail.com
 ***************************************************************************/
"""
import os
import sys
from qgis.core import QgsVectorLayer, QgsVectorFileWriter,QgsVectorDataProvider, QgsField, \
                        QgsExpression, QgsFeatureRequest, QgsRasterPipe, QgsRasterFileWriter, \
                        QgsRectangle, QgsRasterLayer, QgsFeature, QgsPoint, QgsGeometry
import processing
from PyQt4.QtCore import QVariant
from osgeo import gdal
from osgeo import ogr
from osgeo import osr
from osgeo import gdal_array
from osgeo import gdalconst
from collections import defaultdict
from datetime import datetime
import math

#Timer to show processing time
class Timer():
  startTimes=dict()
  stopTimes=dict()

  @staticmethod
  def start(key = 0):
    Timer.startTimes[key] = datetime.now()
    Timer.stopTimes[key] = None

  @staticmethod
  def stop(key = 0):
    Timer.stopTimes[key] = datetime.now()

  @staticmethod
  def show(key = 0):
    if key in Timer.startTimes:
      if Timer.startTimes[key] is not None:
        if key in Timer.stopTimes:
          if Timer.stopTimes[key] is not None:
            delta = Timer.stopTimes[key] - Timer.startTimes[key]
            print delta

class AdvGraph ():
    def __init__(self) :
        self.nodes = []
        self.edges=defaultdict(list)
        self.slope_info=defaultdict(list)
        self.length = {}
        self.slope = {}
        self.weight = {}
    
    def add_nodes(self, id, beg_id, end_id, cost) :
        node = NodeGraph(id,beg_id, end_id, cost)
        self.nodes.append(node)
    
    def add_info(self, beg, end, length, slope):
        self.slope_info[beg].append(end)
        self.length[(beg,end)] = length
        self.slope[(beg,end)] = slope

class NodeGraph():
    def __init__(self, id, beg, end, cost) :
        self.id = id
        self.beg = beg
        self.end = end
        self.cost = cost
        self.cumcost = None
        self.edges = []
    
    def add_edge(self,node) :
        self.edges.append(node)
        
    
def imp_raster(dem_clip):
    # Open the input raster to retrieve values in an array
    data = gdal.Open(dem_clip,1)
    proj = data.GetProjection()
    scr = data.GetGeoTransform()
    resolution = scr[1]

    band=data.GetRasterBand(1)
    iArray=band.ReadAsArray()
    
    return iArray, scr, proj, resolution

def rast_to_adv_graph(rastArray, res, nb_edge, max_slope, method, threshold) :
    G= AdvGraph()
    
    [H,W] = rastArray.shape
    
    #Shifts to get every edges from each nodes. For now, based on 48 direction like :
    #     |   |   |   | 43|   | 42|   |   |   |
    #  ---|---|---|---|---|---|---|---|---|---|---
    #     |   |   |   |   |   |   |   |   |   |
    #  ---|---|---|---|---|---|---|---|---|---|---
    #     |   |   | 30| 29|   | 28| 27|   |   |
    #  ---|---|---|---|---|---|---|---|---|---|---
    #     |   | 31| 14| 13| 12| 11| 10| 26|   |
    #  ---|---|---|---|---|---|---|---|---|---|---
    #   44|   | 32| 15| 3 | 2 | 1 | 9 | 25|   | 41
    #  ---|---|---|---|---|---|---|---|---|---|---
    #     |   |   | 16| 4 | 0 | 8 | 24|   |   |
    #  ---|---|---|---|---|---|---|---|---|---|---
    #   45|   | 33| 17| 5 | 6 | 7 | 23| 40|   | 48
    #  ---|---|---|---|---|---|---|---|---|---|---
    #     |   | 34| 18| 19| 20| 21| 22| 39|   |
    #  ---|---|---|---|---|---|---|---|---|---|---
    #     |   |   | 35| 36|   | 37| 38|   |   |
    #  ---|---|---|---|---|---|---|---|---|---|---
    #     |   |   |   |   |   |   |   |   |   |
    #  ---|---|---|---|---|---|---|---|---|---|---
    #     |   |   |   | 46|   | 47|   |   |   |

    
    
    #          px  py
    shift = [( 0,  0), #0
             (-1,  1), #1
             (-1,  0), #2
             (-1, -1), #3
             ( 0, -1), #4
             ( 1, -1), #5
             ( 1,  0), #6
             ( 1,  1), #7
             ( 0,  1), #8
             (-1,  2), #9
             (-2,  2), #10
             (-2,  1), #11
             (-2,  0), #12
             (-2, -1), #13
             (-2, -2), #14
             (-1, -2), #15
             ( 0, -2), #16
             ( 1, -2), #17
             ( 2, -2), #18
             ( 2, -1), #19
             ( 2,  0), #20
             ( 2,  1), #21
             ( 2,  2), #22
             ( 1,  2), #23
             ( 0,  2), #24
             (-1,  3), #25
             (-2,  3), #26
             (-3,  2), #27
             (-3,  1), #28
             (-3, -1), #29
             (-3, -2), #30
             (-2, -3), #31
             (-1, -3), #32
             ( 1, -3), #33
             ( 2, -3), #34
             ( 3, -2), #35
             ( 3, -1), #36
             ( 3,  1), #37
             ( 3,  2), #38
             ( 2,  3), #39
             ( 1,  3), #40
             (-1,  5), #41
             (-5,  1), #42
             (-5, -1), #43
             (-1, -5), #44
             ( 1, -5), #45
             ( 5, -1), #46
             ( 5,  1), #47
             ( 1,  5)  #48
             ]
             
    slope_calc_coord  =    [( 0,  0),                                                                                                       #0
                            ([ [shift[2]  ,  shift[8]] ]),                                                                                  #1
                            ([ [shift[4]  ,  shift[8]] , [shift[3]  ,  shift[1]] ]),                                                        #2
                            ([ [shift[4]  ,  shift[2]] ]),                                                                                  #3
                            ([ [shift[6]  ,  shift[2]] , [shift[5]  ,  shift[3]] ]),                                                        #4
                            ([ [shift[4]  ,  shift[6]] ]),                                                                                  #5
                            ([ [shift[8]  ,  shift[4]] , [shift[7]  ,  shift[5]] ]),                                                        #6
                            ([ [shift[8]  ,  shift[6]] ]),                                                                                  #7
                            ([ [shift[2]  ,  shift[6]] , [shift[1]  ,  shift[7]] ]),                                                        #8
                            ([ [shift[2]  ,  shift[7]] , [shift[11] ,  shift[24]] , [shift[12],  shift[8]]  , [shift[1]  , shift[23]] ]),   #9
                            ([ [shift[11] ,  shift[9]] , [shift[2]  ,  shift[8]] ]) ,                                                       #10
                            ([ [shift[3]  ,  shift[8]] , [shift[2]  ,  shift[24]] , [shift[12],  shift[9]]  , [shift[13] , shift[1]]  ]),   #11
                            ([ [shift[13] ,  shift[11]], [shift[3]  ,  shift[1]]  , [shift[4] ,  shift[8]] ]) ,                             #12
                            ([ [shift[4]  ,  shift[1]] , [shift[3]  ,  shift[11]] , [shift[16],  shift[2]]  , [shift[15] , shift[12]] ]),   #13
                            ([ [shift[4]  ,  shift[2]] , [shift[15] ,  shift[13]] ]),                                                       #14
                            ([ [shift[5]  ,  shift[2]] , [shift[4]  ,  shift[12]] , [shift[16],  shift[13]] , [shift[17] , shift[3]]  ]),   #15
                            ([ [shift[17] ,  shift[15]], [shift[5]  ,  shift[3]]  , [shift[6] ,  shift[2]] ]) ,                             #16
                            ([ [shift[6]  ,  shift[3]] , [shift[20] ,  shift[4]]  , [shift[5] ,  shift[15]] , [shift[19] , shift[16]] ]),   #17
                            ([ [shift[6]  ,  shift[4]] , [shift[19] ,  shift[17]] ]),                                                       #18
                            ([ [shift[7]  ,  shift[4]] , [shift[6]  ,  shift[16]] , [shift[21],  shift[5]]  , [shift[20] , shift[17]] ]),   #19
                            ([ [shift[8]  ,  shift[4]] , [shift[5]  ,  shift[7]]  , [shift[21],  shift[19]] ]),                             #20
                            ([ [shift[8]  ,  shift[5]] , [shift[24] ,  shift[6]]  , [shift[7] ,  shift[19]] , [shift[23] , shift[20]] ]),   #21
                            ([ [shift[8]  ,  shift[6]] , [shift[23] ,  shift[21]] ]),                                                       #22
                            ([ [shift[1]  ,  shift[6]] , [shift[8]  ,  shift[20]] , [shift[24],  shift[21]] , [shift[9]  , shift[7]]  ]),   #23
                            ([ [shift[2]  ,  shift[6]] , [shift[7]  ,  shift[1]]  , [shift[9] ,  shift[23]] ]),                             #24
                            ([ [shift[2]  ,  shift[21]] , [shift[12]  ,  shift[7]] , [shift[1],  shift[22]] , [shift[11]  , shift[23]]  ]),   #25
                            ([ [shift[2]  ,  shift[22]] , [shift[12]  ,  shift[23]] , [shift[1],  shift[39]] , [shift[13]  , shift[7]]  ]),   #26
                            ([ [shift[3]  ,  shift[23]] , [shift[2]  ,  shift[40]] , [shift[13],  shift[24]] , [shift[14]  , shift[8]]  ]),   #27
                            ([ [shift[3]  ,  shift[24]] , [shift[15]  ,  shift[8]] , [shift[13],  shift[9]] , [shift[14]  , shift[1]]  ]),    #28
                            ([ [shift[4]  ,  shift[9]] , [shift[16]  ,  shift[1]] , [shift[3],  shift[10]] , [shift[15]  , shift[11]]  ]),    #29
                            ([ [shift[4]  ,  shift[10]] , [shift[16]  ,  shift[11]] , [shift[3],  shift[27]] , [shift[17]  , shift[1]]  ]),   #30
                            ([ [shift[5]  ,  shift[11]] , [shift[4]  ,  shift[28]] , [shift[17],  shift[12]] , [shift[18]  , shift[2]]  ]),   #31
                            ([ [shift[5]  ,  shift[12]] , [shift[19]  ,  shift[2]] , [shift[17],  shift[13]] , [shift[18]  , shift[3]]  ]),   #32
                            ([ [shift[6]  ,  shift[13]] , [shift[20]  ,  shift[3]] , [shift[5],  shift[14]] , [shift[19]  , shift[15]]  ]),   #33
                            ([ [shift[6]  ,  shift[14]] , [shift[20]  ,  shift[15]] , [shift[5],  shift[31]] , [shift[21]  , shift[3]]  ]),   #34
                            ([ [shift[6]  ,  shift[32]] , [shift[7]  ,  shift[15]] , [shift[21],  shift[16]] , [shift[22]  , shift[4]]  ]),   #35
                            ([ [shift[7]  ,  shift[16]] , [shift[23]  ,  shift[4]] , [shift[21],  shift[17]] , [shift[22]  , shift[5]]  ]),   #36
                            ([ [shift[8]  ,  shift[17]] , [shift[24]  ,  shift[5]] , [shift[7],  shift[18]] , [shift[23]  , shift[19]]  ]),   #37
                            ([ [shift[8]  ,  shift[18]] , [shift[24]  ,  shift[19]] , [shift[7],  shift[35]] , [shift[23]  , shift[36]]  ]),  #38
                            ([ [shift[1]  ,  shift[19]] , [shift[9]  ,  shift[20]] , [shift[8],  shift[36]] , [shift[10]  , shift[6]]  ]),    #39
                            ([ [shift[1]  ,  shift[20]] , [shift[9]  ,  shift[21]] , [shift[24],  shift[37]] , [shift[11]  , shift[6]]  ]),   #40
                            ([ [shift[12]  ,  shift[37]] , [shift[28]  ,  shift[22]] , [shift[27],  shift[39]]  ]),                           #41
                            ([ [shift[14]  ,  shift[25]] , [shift[32]  ,  shift[24]] , [shift[30],  shift[26]]  ]),                           #42
                            ([ [shift[16]  ,  shift[25]] , [shift[32]  ,  shift[10]] , [shift[30],  shift[26]]  ]),                           #43
                            ([ [shift[18]  ,  shift[29]] , [shift[36]  ,  shift[12]] , [shift[34],  shift[30]]  ]),                           #44
                            ([ [shift[20]  ,  shift[29]] , [shift[36]  ,  shift[14]] , [shift[35],  shift[31]]  ]),                           #45
                            ([ [shift[22]  ,  shift[33]] , [shift[40]  ,  shift[16]] , [shift[38],  shift[34]]  ]),                           #46
                            ([ [shift[24]  ,  shift[33]] , [shift[40]  ,  shift[18]] , [shift[39],  shift[35]]  ]),                           #47
                            ([ [shift[10]  ,  shift[37]] , [shift[28]  ,  shift[20]] , [shift[26],  shift[38]]  ])                            #48
                            ] 

    nb_edge+=1
    
    #Loop over each pixel again to create slope and length dictionnary    
    for i in range(0,H) :
        for j in range(0,W) :
            nodeBeg = "x"+str(i)+"y"+str(j)
            nodeBegValue= rastArray[i,j]
            for index in range(1,nb_edge) :
                x,y=shift[index]
                nodeEnd="x"+str(i+x)+"y"+str(j+y)
                try :
                    nodeEndValue= rastArray[i+x,j+y]
                    #Calculate cost on length + addcost based on slope percent
                    if index in [2,4,6,8] :
                        length = res
                    elif index in [1,3,5,7] :
                        length = res*math.sqrt(2)
                    elif index in [9,11,13,15,17,19,21,23]:
                        length = res*math.sqrt(res)
                    elif index in [10,14,18,22] :
                        length = 2*res*math.sqrt(2)
                    elif index in [12,16,20,24] :
                        length = 2*res
                    elif index in [25,28,29,32,33,36,37,40] :
                        length = res*math.sqrt(10)
                    elif index in [26,27,30,31,34,35,38,39] :
                        length = res*math.sqrt(13)
                    else :
                        length = res*math.sqrt(26)
                    slope = math.fabs(nodeEndValue-nodeBegValue)/length*100
                    # #max slope accepted in percent
                    # max_slope_wanted= 12
                    # if slope <= max_slope_wanted :
                    G.add_info(nodeBeg,nodeEnd,length,slope)
                except IndexError :
                    continue
    
    ind=0
    nodes_dict={}
    for i in range(0,H) :
        for j in range(0,W) :
            nodeBeg = "x"+str(i)+"y"+str(j)
            for index in range(1,nb_edge) :
                x,y=shift[index]
                nodeEnd="x"+str(i+x)+"y"+str(j+y)
                if (i+x) > 0 and (j+y) > 0 and (i+x) < H and (j+y) < W  :
                    try :
                        length = G.length[(nodeBeg, nodeEnd)]
                        slope = G.slope[(nodeBeg, nodeEnd)]
                        if slope <= max_slope :
                            id = nodeBeg+'|'+nodeEnd
                            coords_list = slope_calc_coord[index]
                            c_slope_list=[]
                            c_slope = None
                            count = 0
                            
                            for coords in coords_list :
                                lx,ly = coords[0]
                                nodeLeft="x"+str(i+lx)+"y"+str(j+ly)
                                rx,ry = coords[1]
                                nodeRight="x"+str(i+rx)+"y"+str(j+ry)
                                if (i+lx) > 0 and (j+ly) > 0 and (i+rx) > 0 and (j+ry) > 0 and\
                                    (i+lx) < H and (j+ly) < W and (i+rx) < H and (j+ry) < W :
                                    c_slope_list.append(G.slope[nodeLeft,nodeRight])
                                count+=1
                            if len(c_slope_list) == count and count != 0 :
                                c_slope = sum(c_slope_list) / len(c_slope_list)
                                
                                pmax = 25
                                pmin = 60
                                larg = 4
                                
                                if c_slope < pmax :
                                    assise = larg/2
                                else :
                                    assise = min(round((larg / 2*(1 + ((c_slope - pmax)/(pmin - pmax))**2)),2),larg)
                                talus  = assise**2 *larg * (c_slope/100) / 2 /(larg - (c_slope/100))
                                addcost = talus
                                
                                cost = length * addcost + length * 1
                                G.add_nodes(id, nodeBeg, nodeEnd, cost)
                                nodes_dict[id] = ind
                                ind+=1
                    except IndexError :
                        continue
    nodes = G.nodes
    
    for node1 in nodes :
        x2,y2 = id_to_coord(node1.end)
        id_pt1 = "x"+str(x2)+"y"+str(y2)
        list_ind = []
        for index in range(1,nb_edge) :
            i,j = shift[index]
            if (i+x2) > 0 and (j+y2) > 0 and (i+x2) < H and (j+y2) < W :
                x3,y3 = (x2+i,y2+j)
                id_pt2 = "x"+str(x3)+"y"+str(y3)
                id_next = id_pt1+'|'+id_pt2
                if id_next in nodes_dict :
                    list_ind.append(nodes_dict[id_next])
                
        for edge in list_ind :
            node2 = nodes[edge]
            if node1.id != node2.id and node1.end == node2.beg :                            
                if method == 'r' :
                    x1,y1 = id_to_coord(node1.beg)
                    x2,y2 = id_to_coord(node1.end)
                    x3,y3 = id_to_coord(node2.end)
                    az1 = math.degrees(math.atan2(x2 - x1, y2 - y1))
                    az2 = math.degrees(math.atan2(x3 - x2, y3 - y2))
                    
                    if min(x1,x3) <= x2 <= max(x1,x3) and min(y1,y3) <= y2 <= max(y1,y3):
                    
                        mag_v1 = math.sqrt((x1-x2)**2+(y1-y2)**2)
                        mag_v2 = math.sqrt((x3-x2)**2+(y3-y2)**2)
                        
                        if mag_v1 < mag_v2 :
                            x_v2 , y_v2 = (x3 - x2, y3 - y2)
                            x3,y3 = x2+x_v2/mag_v2*mag_v1 ,y2+y_v2/mag_v2*mag_v1
                        elif mag_v2 < mag_v1 :
                            x_v2 , y_v2 = (x1 - x2, y1 - y2)
                            x1,y1 = x2+x_v2/mag_v1*mag_v2 ,y2+y_v2/mag_v1*mag_v2
                            
                        x_v1 , y_v1 = (x2 - x1, y2 - y1)
                        x_v1_ort , y_v1_ort = y_v1 , -x_v1
                        x_v2 , y_v2 = (x3 - x2, y3 - y2)
                        x_v2_ort , y_v2_ort = y_v2 , -x_v2
                        
                        c_v1_ort = y_v1_ort*x1+(-x_v1_ort)*y1
                        c_v1_ort = -c_v1_ort
                        c_v2_ort = y_v2_ort*x3+(-x_v2_ort)*y3
                        c_v2_ort = -c_v2_ort
                        
                        e = [-y_v1_ort,x_v1_ort,c_v1_ort]
                        f = [-y_v2_ort,x_v2_ort,c_v2_ort]
                        x4 , y4, colineaire = equationResolve(e,f)

                        if (x4 != None and y4 != None) :
                            dist1 = math.sqrt((x1-x4)**2+(y1-y4)**2)*5
                            
                            if dist1 >= threshold :
                                node1.add_edge(node2)
                        
                        elif colineaire == True :
                            node1.add_edge(node2)
                
                if method == 'a' :
                    x1,y1 = id_to_coord(node1.beg)
                    x2,y2 = id_to_coord(node1.end)
                    x3,y3 = id_to_coord(node2.end)
                    az1 = math.degrees(math.atan2(x2 - x1, y2 - y1))
                    az2 = math.degrees(math.atan2(x3 - x2, y3 - y2))
                    if az1 < 0 and az2 > 0 :
                        angle = math.fabs(az1)+az2
                    elif az1 > 0 and az2 < 0 :
                        angle = math.fabs(az2)+az1
                    else :
                        angle = math.fabs(az1-az2)
                    if angle < -180 :
                        angle = angle + 360
                    if angle > 180 :
                        angle = angle - 360
                    if math.fabs(angle) <= threshold :
                        node1.add_edge(node2)
    return G

def adv_dijkstra(graph, init, last, threshold,end_id) :            
    nodes = graph.nodes
    
    beg_list = []
    
    #dict to get path
    path = defaultdict(list)
    
    #Init
    for node in nodes :
        if node.beg == init :
            if last != None :
                x,y = last
                x2,y2 = id_to_coord(node.beg)
                x1 = x2-x
                y1 = y2-y
                x3,y3 = id_to_coord(node.end)
                az1 = math.degrees(math.atan2(x2 - x1, y2 - y1))
                az2 = math.degrees(math.atan2(x3 - x2, y3 - y2))
                
                if min(x1,x3) <= x2 <= max(x1,x3) and min(y1,y3) <= y2 <= max(y1,y3):
                
                    mag_v1 = math.sqrt((x1-x2)**2+(y1-y2)**2)
                    mag_v2 = math.sqrt((x3-x2)**2+(y3-y2)**2)
                    
                    if mag_v1 < mag_v2 :
                        x_v2 , y_v2 = (x3 - x2, y3 - y2)
                        x3,y3 = x2+x_v2/mag_v2*mag_v1 ,y2+y_v2/mag_v2*mag_v1
                    elif mag_v2 < mag_v1 :
                        x_v2 , y_v2 = (x1 - x2, y1 - y2)
                        x1,y1 = x2+x_v2/mag_v1*mag_v2 ,y2+y_v2/mag_v1*mag_v2
                        
                    x_v1 , y_v1 = (x2 - x1, y2 - y1)
                    x_v1_ort , y_v1_ort = y_v1 , -x_v1
                    x_v2 , y_v2 = (x3 - x2, y3 - y2)
                    x_v2_ort , y_v2_ort = y_v2 , -x_v2
                    
                    c_v1_ort = y_v1_ort*x1+(-x_v1_ort)*y1
                    c_v1_ort = -c_v1_ort
                    c_v2_ort = y_v2_ort*x3+(-x_v2_ort)*y3
                    c_v2_ort = -c_v2_ort
                    
                    e = [-y_v1_ort,x_v1_ort,c_v1_ort]
                    f = [-y_v2_ort,x_v2_ort,c_v2_ort]
                    x4 , y4, colineaire = equationResolve(e,f)

                    if (x4 != None and y4 != None) :
                        dist1 = math.sqrt((x1-x4)**2+(y1-y4)**2)*5
                        if dist1 >= threshold :
                            node.cumcost = node.cost
                            beg_list.append(node.id)
                            path[node.id].append((node.id,node.cumcost))
                        else :
                            node.cumcost = 9999
                            path[node.id].append((node.id,node.cumcost))
                    elif colineaire == True :
                        node.cumcost = node.cost
                        beg_list.append(node.id)
                        path[node.id].append((node.id,node.cumcost))
            else :
                node.cumcost = node.cost
                beg_list.append(node.id)
                path[node.id].append((node.id,node.cumcost))

    
    min_node = NodeGraph(0,0,0,0)
    finish = None
    fin_weight = None
    count = 0
    while nodes: 
        if min_node.end != end_id:
            min_node = None
            for i,node in enumerate(nodes) :
                if node.cumcost != None :
                    if min_node is None :
                        ind = i
                        min_node = node
                    elif node.cumcost < min_node.cumcost :
                        ind = i
                        min_node = node
            
            if min_node != None :
                nodes.pop(ind)
                
                for node in min_node.edges :
                    weight = min_node.cumcost + node.cost
                    if node.cumcost == None or weight < node.cumcost :
                        node.cumcost = weight
                        path[node.id].append((min_node.id,weight))
                        count+=1
                        if math.fmod(count,10000) == 0 :
                            print "...searching..."
            
            else :
                print 'no solution'
                finish = None
                last_beg = last
                fin_weight = None
                break
        else :
            finish = min_node.id
            print finish
            beg,end = finish.split('|')
            x_beg,y_beg = id_to_coord(beg)
            x_end,y_end = id_to_coord(end)
            last_beg = (int(x_end)-int(x_beg),int(y_end)-int(y_beg))
            fin_weight = min_node.cumcost
            print fin_weight
            break
    return path, beg_list, finish, last_beg, fin_weight
                    
def equationResolve(e1,e2):
    determinant=e1[0]*e2[1]-e1[1]*e2[0]
    x , y = None,None
    colineaire = False
    if determinant != 0:
        x=(e1[2]*e2[1]-e1[1]*e2[2])/determinant
        y=(e1[0]*e2[2]-e1[2]*e2[0])/determinant
    else :
        colineaire = True
    return x, y, colineaire
    
def id_to_coord(id):
    id=id[1:]
    px,py=id.split('y')
    px,py=int(px),int(py)
    return px,py

def ids_to_coord(lcp,gt):
    #Reproj pixel coordinates to map coordinates
    coord_list = []
    for id in lcp :
        id=id[1:]
        px,py=id.split('y')
        px,py=int(px),int(py)
        
        #Convert from pixel to map coordinates.
        mx = py * gt[1] + gt[0] + gt[1]/2
        my = px * gt[5] + gt[3] - gt[5]/2
        
        coord_list.append((mx,my))
    #return the list of end point with x,y map coordinates
    return coord_list

def create_ridge(out_layer,lcp,id_line,point_id, weight) :
    out_layer.startEditing()
    feat = QgsFeature(out_layer.pendingFields())

    #Initiate feature geometry
    line = []
    for coord in lcp :
        x,y = coord
        pt= QgsPoint(x, y)
        #Add new vertice to the linestring
        line.append(pt)
    polyline = QgsGeometry.fromPolyline(line)
    feat.setGeometry(polyline)
    feat.setAttributes([id_line,point_id,weight])
    out_layer.dataProvider().addFeatures([feat])
    out_layer.commitChanges()

def get_adv_lcp(beg_list,path,end_id, method,threshold) :
    if end_id != None :
        pt2, pt1 = end_id.split('|')
        act=end_id
        leastCostPath=[pt1,pt2]
        print 'Create the least cost path as OGR LineString...'
        while act not in beg_list :
            pt2, pt1 = act.split('|')
            pt2 = pt2[1:]
            x2, y2 = pt2.split('y')
            pt1 = pt1[1:]
            x1, y1 = pt1.split('y')
            feasible_path=[]
            for edge in path[act] :
                prev = edge[0]
                pt3, pt2 = prev.split('|')
                pt3= pt3[1:]
                x3, y3 = pt3.split('y')
                x1,y1,x2,y2,x3,y3 = int(x1),int(y1),int(x2),int(y2),int(x3),int(y3)
                if method == 'a' :
                    az1 = math.degrees(math.atan2(x2 - x1, y2 - y1))
                    az2 = math.degrees(math.atan2(x3 - x2, y3 - y2))
                    if az1 < 0 and az2 > 0 :
                        angle = math.fabs(az1)+az2
                    elif az1 > 0 and az2 < 0 :
                        angle = math.fabs(az2)+az1
                    else :
                        angle = math.fabs(az1-az2)
                    if angle < -180 :
                        angle = angle + 360
                    if angle > 180 :
                        angle = angle - 360
                    if math.fabs(angle) <= threshold :
                        feasible_path.append(edge)
                        
                if method == 'r' :
                    az1 = math.degrees(math.atan2(x2 - x1, y2 - y1))
                    az2 = math.degrees(math.atan2(x3 - x2, y3 - y2))
                    # if az1 != (az2+180) and az1 != (az2-180):
                    if min(x1,x3) <= x2 <= max(x1,x3) and min(y1,y3) <= y2 <= max(y1,y3):
                    
                        mag_v1 = math.sqrt((x1-x2)**2+(y1-y2)**2)
                        mag_v2 = math.sqrt((x3-x2)**2+(y3-y2)**2)
                        
                        if mag_v1 < mag_v2 :
                            x_v2 , y_v2 = (x3 - x2, y3 - y2)
                            x3,y3 = x2+x_v2/mag_v2*mag_v1 ,y2+y_v2/mag_v2*mag_v1
                        elif mag_v2 < mag_v1 :
                            x_v2 , y_v2 = (x1 - x2, y1 - y2)
                            x1,y1 = x2+x_v2/mag_v1*mag_v2 ,y2+y_v2/mag_v1*mag_v2
                            
                        x_v1 , y_v1 = (x2 - x1, y2 - y1)
                        x_v1_ort , y_v1_ort = y_v1 , -x_v1
                        x_v2 , y_v2 = (x3 - x2, y3 - y2)
                        x_v2_ort , y_v2_ort = y_v2 , -x_v2
                        
                        c_v1_ort = y_v1_ort*x1+(-x_v1_ort)*y1
                        c_v1_ort = -c_v1_ort
                        c_v2_ort = y_v2_ort*x3+(-x_v2_ort)*y3
                        c_v2_ort = -c_v2_ort
                        
                        e = [-y_v1_ort,x_v1_ort,c_v1_ort]
                        f = [-y_v2_ort,x_v2_ort,c_v2_ort]
                        x4 , y4, colineaire = equationResolve(e,f)
 
                        if (x4 != None and y4 != None) :
                            dist1 = math.sqrt((x1-x4)**2+(y1-y4)**2)*5
                            
                            if dist1 >= threshold :
                                feasible_path.append(edge)
                        
                        elif colineaire == True :
                            feasible_path.append(edge)
                                    
            weight = None
            for w_path in feasible_path :
                if weight == None :
                    weight = w_path[1]
                    id = w_path[0]
                elif path[1] < weight :
                    weight = w_path[1]
                    id = w_path[0]
            act = id
            pt3, pt2 = id.split('|')
            leastCostPath.append(pt3)
    else :
        leastCostPath = None
    return leastCostPath

def getExtent(point_geom, npoint_geom, x_res, y_res, f_extent):
    x1,y1 = point_geom
    x2,y2 = npoint_geom

    dist = math.sqrt(point_geom.sqrDist(npoint_geom))
    mod = (dist/2) % x_res
    dist = (dist/2) - mod + x_res

    xmax = max(x1,x2) + x_res/2 + int(dist) + f_extent * 3 * x_res 
    xmin = min(x1,x2) - x_res/2 - int(dist) - f_extent * 3 * x_res
    ymax = max(y1,y2) + y_res/2 + int(dist) + f_extent * 3 * y_res
    ymin = min(y1,y2) - y_res/2 - int(dist) - f_extent * 3 * y_res
    extent = [xmin, xmax, ymin, ymax]
    return extent

def getClip(DEM_layer, outpath, extent, x_res, y_res):
    dem_clip = '%s\\tmp' % os.path.dirname(outpath)
    extent=str(str(extent[0])+','+str(extent[1])+','+str(extent[2])+','+str(extent[3]))
    processing.runalg('gdalogr:cliprasterbyextent', {'INPUT':DEM_layer.source(),'PROJWIN':extent, 'OUTPUT':dem_clip})
    dem_clip = dem_clip+'.tif'
    return dem_clip

def map2pixel(point_geom,gt):
    mx,my = point_geom
    #Convert from map to pixel coordinates.
    px = int(( my - gt[3] + gt[5]/2) / gt[5])
    py = int(((mx - gt[0] - gt[1]/2) / gt[1]))
    beg_point = "x"+str(px)+"y"+str(py)
    return beg_point

def betweenPoint(point, next_point, DEM_layer, outpath, nb_edges, max_slope, method, threshold, x_res, y_res, f_extent, last_beg):
    point_geom = point.geometry().asPoint()
    npoint_geom = next_point.geometry().asPoint()
    extent = getExtent(point_geom, npoint_geom, x_res, y_res, f_extent)
    dem_clip = getClip(DEM_layer, outpath, extent, x_res, y_res)
    in_array, scr, proj, res = imp_raster(dem_clip)
    G = rast_to_adv_graph(in_array, res, nb_edges, max_slope, method, threshold)
    beg_point = map2pixel(point_geom, scr)
    end_point = map2pixel(npoint_geom, scr)
    path, beg_list, end_id,last_mouv, w = adv_dijkstra(G,beg_point,last_beg,threshold,end_point,)

    return path, beg_list, end_id, last_mouv, w, scr

def advanced_algo(point_layer,DEM_layer,tracks_layer,outpath,nb_edges,method,threshold,max_slope):
    crs = tracks_layer.crs().toWkt()
    #resolution raster
    x_res = DEM_layer.rasterUnitsPerPixelX()
    y_res = DEM_layer.rasterUnitsPerPixelY()

    #list line
    lines_list=[]
    for point in point_layer.getFeatures() :
        line_id = point.attribute('L_id')
        if line_id not in lines_list :
            lines_list.append(line_id)

    #loop the points for each line
    for line in lines_list :
        expr = QgsExpression('L_id = %s'%line)
        req = QgsFeatureRequest(expr)
        line_points = point_layer.getFeatures(req)
        last_beg = None
        for point in line_points :
            nature = point.attribute('nature')
            if nature != 'end' :
                next_point = None
                point_id = point.attribute('P_id')
                next_id = int(point_id) + 1
                expre = QgsExpression('L_id = %s AND P_id= %s'%(line, str(next_id)))
                reque = QgsFeatureRequest(expre)
                next_point_it = point_layer.getFeatures(reque)

                try :
                    next_point = next(next_point_it)
                except StopIteration:
                    pass
                if next_point != None :
                    f_extent = -1
                    end_id = None
                    while end_id == None and f_extent < 5:
                        f_extent+=1
                        path, beg_list, end_id, last_beg, w, scr = betweenPoint(point, next_point, DEM_layer, outpath, nb_edges, max_slope, method, threshold, x_res, y_res, f_extent, last_beg)

                    if end_id != None :
                        leastCostPath = get_adv_lcp(beg_list,path,end_id, method,threshold)
                        
                        coord_list = ids_to_coord(leastCostPath,scr)
                        end_pt = leastCostPath[0] 
                        create_ridge(tracks_layer,coord_list,line,point_id,w)
                        expr = QgsExpression('L_id = %s AND P_id= %s'%(line, str(point_id)))
                        req = QgsFeatureRequest(expr)
                        last_line_it = tracks_layer.getFeatures(req)
                        try :
                            last_line = next(last_line_it)
                            print last_line.id()
                            last_geom = last_line.geometry()
                            feats_line = tracks_layer.getFeatures(QgsFeatureRequest().setFilterRect(last_geom.boundingBox()))
                            cros= False
                            for feat_line in feats_line:
                                if feat_line.geometry().crosses(last_geom):
                                    print "oh it crosses"
                                    cros = True
                                    geom_cros = feat_line.geometry().asPolyline()
                                    geom_cros_e = [geom_cros[0],geom_cros[-1]]
                            if cros == True :
                                attr_last_line = last_line.attributes()
                                temp_layer = outputFormat(crs,'tmp_Tracks')
                                temp_path = '%s\\tmp_layer.shp' % os.path.dirname(outpath)
                                QgsVectorFileWriter.writeAsVectorFormat(temp_layer, temp_path, "utf-8", None, "ESRI Shapefile")
                                temp_layer = QgsVectorLayer(temp_path,'temp_layer','ogr')
                                temp_layer.startEditing()
                                temp_layer.dataProvider().addFeatures([last_line])
                                temp_layer.commitChanges()
                                print "let's cut"
                                cut_line = processing.runalg('qgis:splitlineswithlines',temp_layer,tracks_layer,None)
                                cut_line = QgsVectorLayer(cut_line['OUTPUT'],'cut',"ogr")
                                print 'is it good ?'
                                for lin in cut_line.getFeatures() :
                                    geom_lin = lin.geometry().asPolyline()
                                    if geom_lin[0] not in geom_cros_e and geom_lin[-1] not in geom_cros_e :
                                        lin.setAttributes(attr_last_line)
                                        tracks_layer.startEditing()
                                        tracks_layer.deleteFeatures([last_line.id()])
                                        tracks_layer.commitChanges()
                                        tracks_layer.startEditing()
                                        tracks_layer.dataProvider().addFeatures([lin])
                                        tracks_layer.commitChanges()
                                        print 'ok'
                                temp_layer = None
                                cut_line = None
                        except StopIteration:
                            pass



def pointChecked(point_layer) :
    pr = point_layer.dataProvider()

    L_index = pr.fieldNameIndex('L_id')
    P_index = pr.fieldNameIndex('P_id')

    if L_index == -1 or P_index == -1 :
        point_format = False
    else :
        point_format = True

    return point_format

def outputFormat(crs, name='Tracks'):
    tracks_layer = QgsVectorLayer('Linestring?crs=' + crs,name,'memory')
    name_L_id = "L_id"
    name_P_id = "P_id"
    name_cost = "cost"
    provider = tracks_layer.dataProvider()
    caps = provider.capabilities()
    if caps & QgsVectorDataProvider.AddAttributes:
        res = provider.addAttributes( [ QgsField(name_L_id, QVariant.String) ,
                                        QgsField(name_P_id, QVariant.String) ,
                                        QgsField(name_cost, QVariant.Double,"double", 5, 1) ] )
        tracks_layer.updateFields()

    return tracks_layer

def launchAutomatracks(point_layer, DEM_layer, outpath, nb_edges,method,threshold,max_slope) :
    time=Timer()
    time.start()

    if os.path.exists(os.path.dirname(outpath)) ==False :
        try :
            os.mkdir(os.path.dirname(outpath))
        except :
            print 'no write access'

    if os.access(os.path.dirname(outpath), os.W_OK) == True :
        crs = point_layer.crs().toWkt()
        tracks_layer = outputFormat(crs)

        error = QgsVectorFileWriter.writeAsVectorFormat(tracks_layer, outpath, "utf-8", None, "ESRI Shapefile") 
        if error == QgsVectorFileWriter.NoError:
            print "output prepared"

        tracks_layer = QgsVectorLayer(outpath,'tracks_layer',"ogr")
        point_format = pointChecked(point_layer)

        if point_format == True :
            advanced_algo(point_layer,DEM_layer,tracks_layer,outpath,int(nb_edges),method,int(threshold),int(max_slope))

        time.stop()
        print 'processing Time :'
        time.show()



    else :
        print 'no write access'