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
                        QgsExpression, QgsFeatureRequest
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

class Graph ():
    def __init__(self):
        self.nodes=set()
        self.edges=defaultdict(list)
        self.slope_info=defaultdict(list)
        self.length = {}
        self.slope = {}
        self.weight = {}
    
    def add_nodes(self, id):
        self.nodes.add(id)
    
    def add_edge(self, beg, end, w):
        self.edges[beg].append(end)
        self.weight[(beg,end)] = w
        
    def add_info(self, beg, end, length, slope):
        self.slope_info[beg].append(end)
        self.length[(beg,end)] = length
        self.slope[(beg,end)] = slope

class AdvGraph ():
    def __init__(self) :
        self.nodes = defaultdict(list)
        self.edges=defaultdict(list)
        self.slope_info=defaultdict(list)
        self.length = {}
        self.slope = {}
        self.weight = {}
    
    def add_nodes(self, id, beg_id, end_id, cost) :
        data = [beg_id, end_id, cost]
        self.nodes[id].append(data)
    
    def add_edge (self, beg, end):
        self.edges[beg[0]].append(end)
        self.weight[(beg[0],end)] = self.nodes[end][0][2]
    
    def add_info(self, beg, end, length, slope):
        self.slope_info[beg].append(end)
        self.length[(beg,end)] = length
        self.slope[(beg,end)] = slope
        
    
def imp_raster():
    print 'ENTER input raster path'
    iFile_name=raw_input()

    # Open the input raster to retrieve values in an array
    data = gdal.Open(iFile_name,1)
    proj = data.GetProjection()
    scr = data.GetGeoTransform()
    resolution = scr[1]

    band=data.GetRasterBand(1)
    iArray=band.ReadAsArray()
    
    return iArray, scr, proj, resolution

def imp_init_point(gt):
    print 'ENTER input init point path'
    iFile_name=raw_input()
    
    init_list = []
    
    #Open the init point shapefile to project each feature in pixel coordinates
    ds=ogr.Open(iFile_name)
    lyr=ds.GetLayer()
    src = lyr.GetSpatialRef()
    for feat in lyr:
        geom = feat.GetGeometryRef()
        mx,my=geom.GetX(), geom.GetY()

        #Convert from map to pixel coordinates.
        px = int(( my - gt[3] + gt[5]/2) / gt[5])
        py = int(((mx - gt[0] - gt[1]/2) / gt[1]))
        init_list.append((px,py))
    
    #return the list of init point with x,y pixel coordinates
    return init_list, src
    
def output_prep(src):
    #Initialize the shapefile output
    
    print 'path output :'
    oLineFile_name=raw_input()
    oDriver=ogr.GetDriverByName("ESRI Shapefile")
    if os.path.exists(oLineFile_name):
        oDriver.DeleteDataSource(oLineFile_name)
    oDataSource=oDriver.CreateDataSource(oLineFile_name)
    
    #Create a LineString layer
    oLayer = oDataSource.CreateLayer("ridge",src,geom_type=ogr.wkbLineString)
    
    #Add two fields to store the col_id and the pic_id
    colID_field=ogr.FieldDefn("col_id",ogr.OFTString)
    picID_field=ogr.FieldDefn("pic_id",ogr.OFTString)
    weight_field=ogr.FieldDefn("weight",ogr.OFTReal)
    oLayer.CreateField(colID_field)
    oLayer.CreateField(picID_field)
    oLayer.CreateField(weight_field)
    
    return oLineFile_name
 
def out_point_prep(src):
    print 'point output :'
    oPointFile_name = raw_input()
    oDriver=ogr.GetDriverByName("ESRI Shapefile")
    if os.path.exists(oPointFile_name):
        oDriver.DeleteDataSource(oPointFile_name)
    oDataSource=oDriver.CreateDataSource(oPointFile_name)
    
    #Create a LineString layer
    oLayer = oDataSource.CreateLayer("point",src,geom_type=ogr.wkbPoint)
    ordreID_field=ogr.FieldDefn("ordre_id",ogr.OFTString)
    nodeID_field=ogr.FieldDefn("node_id",ogr.OFTString)
    weightID_field=ogr.FieldDefn("weight",ogr.OFTReal)
    pathID_field=ogr.FieldDefn("path_id",ogr.OFTString)
    previous_field = ogr.FieldDefn("previous",ogr.OFTString)
    oLayer.CreateField(ordreID_field)
    oLayer.CreateField(nodeID_field)
    oLayer.CreateField(weightID_field)
    oLayer.CreateField(pathID_field)
    oLayer.CreateField(previous_field)
    
    return oPointFile_name

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
                    except IndexError :
                        continue
    nodes = G.nodes
    
    for node1 in nodes.items() :
        x2,y2 = id_to_coord(node1[1][0][1])
        id_pt1 = "x"+str(x2)+"y"+str(y2)
        list_pos_edge = []
        for index in range(1,nb_edge) :
            i,j = shift[index]
            if (i+x2) > 0 and (j+y2) > 0 and (i+x2) < H and (j+y2) < W :
                x3,y3 = (x2+i,y2+j)
                id_pt2 = "x"+str(x3)+"y"+str(y3)
                id_next = id_pt1+'|'+id_pt2
                if id_next in nodes :
                    list_pos_edge.append(id_next)
        
        for node2 in list_pos_edge :
            if node1[0] != node2 and node1[1][0][1] == nodes[node2][0][0] :
                if method == 'angle' :
                        x1,y1 = id_to_coord(node1[1][0][0])
                        x2,y2 = id_to_coord(node1[1][0][1])
                        x3,y3 = id_to_coord(nodes[node2][0][1])
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
                            G.add_edge(node1[0] , node2)
                            
                if method == 'radius' :
                    x1,y1 = id_to_coord(node1[1][0][0])
                    x2,y2 = id_to_coord(node1[1][0][1])
                    x3,y3 = id_to_coord(nodes[node2][0][1])
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
                                G.add_edge(node1, node2)
                        
                        elif colineaire == True :
                            G.add_edge(node1, node2)
    return G
    
def rast_to_graph(rastArray, res, nb_edge, max_slope) :
    G= Graph()
    
    
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
    #Loop over each pixel to convert it into nodes
    for i in range(0,H) :
        for j in range(0,W) :
            #node id based on x and y pixel coordinates
            nodeName = "x"+str(i)+"y"+str(j)
            G.add_nodes(nodeName)

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
                                G.add_edge(nodeBeg, nodeEnd, cost)
                    except IndexError :
                        continue
    
    return G

def adv_dijkstra(graph, init, end_list) :
    #change the end point coordinates to graph id
    end_name=[]
    for end_point in end_list :
        print end_point
        x,y=end_point
        end_id = "x"+str(x)+"y"+str(y)
        if end_id != init :
            end_name.append(end_id)
            
    nodes = graph.nodes
    
    beg_list = []
    visited = {}
    
    #dict to get path
    path = defaultdict(list)
    
    #Init
    for node in nodes.items() :
        if node[1][0][0] == init :
            visited[node[0]] = node[1][0][2]
            beg_list.append(node[0])
            path[node[0]].append((node[0],visited[node[0]]))

    
    
    min_node = [0,[[0,0]]]
    while nodes: 
        if min_node[1][0][1] not in end_name:
            min_node = None
            for node in nodes.items():
                if node[0] in visited:
                    if node[1][0][1] in end_name :
                        finish = node[0]
                    if min_node is None:
                        min_node = node
                    elif visited[node[0]] < visited[min_node[0]]:
                        min_node = node
            
            if min_node != None :
                current_weight = visited[min_node[0]]
                 
                #Part to create point on real time
                # if min_node in path : 
                    # pid,w = path[min_node][-1]
                # else :
                    # pid = ''
                # if out_point != None :
                    # createPoint(out_point, min_node, scr, current_weight, nb_path, pid)
                del nodes[min_node[0]]
                
                for edge in graph.edges[min_node[0]]:
                    weight = current_weight + graph.weight[(min_node[0], edge)]
                    if edge[0] not in visited or weight < visited[edge]:
                        visited[edge] = weight
                        path[edge].append((min_node[0],weight))
            
            else :
                print 'no solution'
                finish = None
                break
        else :
            break
    return path, beg_list, finish, visited
                    
    
def dijkstra(graph, init, end_list, scr, method, threshold, out_point, nb_path):
    #change the end point coordinates to graph id
    end_name=[]
    for end_point in end_list :
        x,y=end_point
        end_id = "x"+str(x)+"y"+str(y)
        if end_id != init :
            end_name.append(end_id)
    
    #dict to get visited nodes and path
    visited = {init: 0}
    path = defaultdict(list)

    nodes = set(graph.nodes)

    #dijkstra algo
    min_node = None
    while nodes: 
        if min_node not in end_name:
            min_node = None
            for node in nodes:
                if node in visited:
                    if node in end_name :
                        finish = node
                    if min_node is None:
                        min_node = node
                    elif visited[node] < visited[min_node]:
                        min_node = node
            
            if min_node != None :
                current_weight = visited[min_node]
                if min_node in path : 
                    pid,w = path[min_node][-1]
                else :
                    pid = ''
                if out_point != None :
                    createPoint(out_point, min_node, scr, current_weight, nb_path, pid)
                nodes.remove(min_node)
                
                
                for edge in graph.edges[min_node]:
                    if method == 'angle' :
                        if min_node in path : 
                            pid,w = path[min_node][-1]
                            x1,y1 = id_to_coord(pid)
                            x2,y2 = id_to_coord(min_node)
                            x3,y3 = id_to_coord(edge)
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
                                weight = current_weight + graph.weight[(min_node, edge)]
                                if edge not in visited or weight < visited[edge]:
                                    visited[edge] = weight
                                    path[edge].append((min_node,weight))
                        else :
                            weight = current_weight + graph.weight[(min_node, edge)]
                            if edge not in visited or weight < visited[edge]:
                                visited[edge] = weight
                                path[edge].append((min_node,weight))
                                
                    if method == 'radius' :
                        if min_node in path : 
                            pid,w = path[min_node][-1]
                            x1,y1 = id_to_coord(pid)
                            x2,y2 = id_to_coord(min_node)
                            x3,y3 = id_to_coord(edge)
                            
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
                                        weight = current_weight + graph.weight[(min_node, edge)]
                                        if edge not in visited or weight < visited[edge]:
                                            visited[edge] = weight
                                            path[edge].append((min_node,weight))
                                elif colineaire == True :
                                    weight = current_weight + graph.weight[(min_node, edge)]
                                    if edge not in visited or weight < visited[edge]:
                                        visited[edge] = weight
                                        path[edge].append((min_node,weight))
                        else :
                            weight = current_weight + graph.weight[(min_node, edge)]
                            if edge not in visited or weight < visited[edge]:
                                visited[edge] = weight
                                path[edge].append((min_node,weight))
            else :
                print 'no solution'
                finish = None
                break
        else :
            break
    return path, finish, visited


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
        my = px * gt[5] + gt[3] + gt[5]/2
        
        coord_list.append((mx,my))
    #return the list of end point with x,y map coordinates
    return coord_list

def create_ridge(oFile,lcp, col, pic, weight) :
    driver= ogr.GetDriverByName("ESRI Shapefile")
    
    #Open the output shapefile
    iDataSource = driver.Open(oFile,1)
    iLayer = iDataSource.GetLayer()
    featDefn = iLayer.GetLayerDefn()
    
    #Initiate feature
    feat = ogr.Feature(featDefn)
    
    #Initiate feature geometry
    line = ogr.Geometry(ogr.wkbLineString)
    for coord in lcp :
        x,y = coord
        #Add new vertice to the linestring
        line.AddPoint(x,y)
    feat.SetGeometry(line)
    
    #Update the data field
    print pic
    feat.SetField("col_id",col)
    feat.SetField("pic_id",pic)
    feat.SetField("weight",weight)
    iLayer.CreateFeature(feat)
    feature = None
    iDataSource = None
  
def createPoint(oFile, node, gt, weight, nb_path, previous) :
    driver= ogr.GetDriverByName("ESRI Shapefile")
    
    #Open the output shapefile
    iDataSource = driver.Open(oFile,1)
    iLayer = iDataSource.GetLayer()
    featDefn = iLayer.GetLayerDefn()
    count = iLayer.GetFeatureCount()
    #Initiate feature
    feat = ogr.Feature(featDefn)
    px,py=id_to_coord(node)
    #Initiate feature geometry
    point = ogr.Geometry(ogr.wkbPoint)
    mx = py * gt[1] + gt[0] + gt[1]/2
    my = px * gt[5] + gt[3] + gt[5]/2
    point.AddPoint(mx,my)
    feat.SetGeometry(point)
    feat.SetField('ordre_id',count+1)
    feat.SetField('node_id',node)
    feat.SetField('weight',weight)
    feat.SetField('path_id', nb_path)
    feat.SetField('previous', previous)
    iLayer.CreateFeature(feat)
    
    
    feature = None
    iDataSource = None

def get_lcp(beg_id,path,end_id):
    if end_id != None :
        act=end_id
        leastCostPath=[end_id]
        print 'Create the least cost path as OGR LineString...'
        while act not in beg_id :
            id,w=path[act][-1]
            act=id
            leastCostPath.append(id)
    else :
        leastCostPath = None
    return leastCostPath

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
                if method == 'angle' :
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
                        
                if method == 'radius' :
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
    
def standard_algo():
    #Main function
    print 'Import raster...'
    in_array, scr, proj, res = imp_raster()
    print 'Import raster done'
    
    
    print 'Import vector ...'
    beg_list, scr_shp = imp_init_point(scr)
    print '%s feature(s)' % len(beg_list)
    print 'Import vector done'

    print 'Name vector output...'
    print 'path :'
    out_line=output_prep(scr_shp)
    print 'Get points process history ? (y/n)'
    point_save = raw_input()
    if point_save == 'y' :
        out_point = out_point_prep(scr_shp)
    else :
        out_point = None
    
    print 'Edges model : (8/24/40/48)'
    nb_edge = int(input())
    if nb_edge not in [8,24,40,48] :
       print "Wrong edges model, %s edges model does'nt exist" % str(nb_edge)
    
    print 'Method a/r (angle/radius) :'
    method = raw_input()
    if method == 'a' or method == 'angle' :
        method = 'angle'
        print "Angle max (%) :"
        threshold = int(input())
    elif method == 'r' or method == 'radius' :
        method = 'radius'
        print "Radius min (m) :"
        threshold = int(input())
    else :
        print "Wrong method"
        exit()
    
    print 'Along slope limit : (percent, ex : 10 for 10 %)'
    max_slope= int(input())
    

    
    print 'Convert rast to graph...'
    G = rast_to_graph(in_array, res, nb_edge, max_slope)
    print 'Convert rast to graph done'

    print '%s nodes in the graph' % len(G.nodes)
    sum_nodes=0
    for node in G.nodes :
        sum_nodes += len(G.edges[node])
    print '%s edges in the graph' % sum_nodes

    #Begin to search least_cost path for each beg point
    i=0
    time=Timer()
    time.start()
    for beg_point in beg_list :
        x,y = beg_point
        beg_id = "x"+str(x)+"y"+str(y)
        print 'Searching the least cost path for %s' % beg_id
        path, end_id, visited = dijkstra(G,beg_id,beg_list, scr, method, threshold, out_point,i)
        i+=1
        print 'Searching the least cost path done'
        
        leastCostPath = get_lcp(beg_id,path,end_id)
        
        if leastCostPath != None :
            filename="lcp"+str(i)+".txt"
            file = open(filename,"w")
            file.write(str(leastCostPath))
            file.close()
            
            filename="path"+str(i)+".txt"
            file = open(filename,"w")
            file.write(str(path))
            file.close()
            
            coord_list = ids_to_coord(leastCostPath,scr)
            id,w=path[end_id][-1]
            create_ridge(out_line,coord_list,beg_id,end_id,w)
            print 'Create the least cost path as OGR LineString done'
        else :
            print 'No path'
        
    time.stop()
    print 'processing Time :'
    time.show()

def advanced_algo(point_layer,L_ind,P_ind,DEM_layer,tracks_layer,nb_edges,method,threshold,max_slope):
    lines_list=[]
    for point in point_layer.getFeatures() :
        line_id = point.attribute('L_id')
        if line_id not in lines_list :
            lines_list.append(line_id)

    for line in lines_list :
        print 'line : %s' %line
        expr = QgsExpression('L_id = %s'%line)
        req = QgsFeatureRequest(expr)
        line_points = point_layer.getFeatures(req)
        for point in line_points :
            point_id = point.attribute('P_id')
            print 'point : %s' %point_id



    # i=0
    # for beg_point in point_list :
    #     x,y = beg_point
    #     beg_id = "x"+str(x)+"y"+str(y)    
    #     print 'Convert rast to graph...'
    #     G = rast_to_adv_graph(in_array, res, nb_edges, max_slope, method, threshold)
    #     print 'Convert rast to graph done'

    #     print '%s nodes in the graph' % len(G.nodes)
    #     sum_nodes=0
    #     for node in G.nodes :
    #         sum_nodes += len(G.edges[node])
    #     print '%s edges in the graph' % sum_nodes

    #     #Begin to search least_cost path for each beg point
    #     print 'Searching the least cost path for %s' % beg_id
    #     path, beg_list, end_id, visited = adv_dijkstra(G,beg_id,point_list)
    #     print end_id
    #     i+=1
    #     print 'Searching the least cost path done'
        
    #     if end_id != None :
    #         filename="path"+str(i)+".txt"
    #         file = open(filename,"w")
    #         file.write(str(path))
    #         file.close()
            
    #         leastCostPath = get_adv_lcp(beg_list,path,end_id, method,threshold)
                
    #         filename="lcp"+str(i)+".txt"
    #         file = open(filename,"w")
    #         file.write(str(leastCostPath))
    #         file.close()
            
    #         filename="lcp"+str(i)+".txt"
    #         file = open(filename,"w")
    #         file.write(str(visited))
    #         file.close()
            
    #         coord_list = ids_to_coord(leastCostPath,scr)
    #         end_pt = leastCostPath[0] 
    #         w = visited[end_id]
    #         create_ridge(out_line,coord_list,beg_id,end_pt,w)
    #         print 'Create the least cost path as OGR LineString done'

def pointChecked(point_layer) :
    pr = point_layer.dataProvider()

    L_index = pr.fieldNameIndex('L_id')
    P_index = pr.fieldNameIndex('P_id')

    if L_index == -1 or P_index == -1 :
        point_format = False
    else :
        point_format = True

    return point_format, L_index, P_index

def outputFormat(crs):
    tracks_layer = QgsVectorLayer('Linestring?crs=' + crs,'Tracks','memory')
    name_L_id = "L_id"
    name_P1_id = "P1_id"
    name_P2_id= "P2_id"
    name_cost = "cost"
    provider = tracks_layer.dataProvider()
    caps = provider.capabilities()
    if caps & QgsVectorDataProvider.AddAttributes:
        res = provider.addAttributes( [ QgsField(name_L_id, QVariant.String) ,
                                        QgsField(name_P1_id, QVariant.String),
                                        QgsField(name_P2_id, QVariant.String),
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
        tracks_layer= outputFormat(crs)

        time.stop()
        print 'processing Time :'
        time.show()

        point_format, L_ind, P_ind = pointChecked(point_layer)

        if point_format == True :
            advanced_algo(point_layer,L_ind,P_ind,DEM_layer,tracks_layer,nb_edges,method,threshold,max_slope)

        error = QgsVectorFileWriter.writeAsVectorFormat(tracks_layer, outpath, "utf-8", None, "ESRI Shapefile") 
        if error == QgsVectorFileWriter.NoError:
            print "success!"

    else :
        print 'no write access'