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

import math
from datetime import datetime

from qgis.core import QgsVectorLayer, QgsVectorFileWriter, QgsVectorDataProvider, QgsField, \
                        QgsExpression, QgsFeatureRequest, QgsRasterPipe, QgsRasterFileWriter, \
                        QgsRectangle, QgsRasterLayer, QgsFeature, QgsPoint, QgsGeometry, QgsRaster
import processing
from PyQt4.QtCore import QVariant

from osgeo import gdal, ogr, osr
from osgeo import gdal_array, gdalconst

from collections import defaultdict


from conf import NODATA_VALUE, MAX_VALUE
from conf import SHIFT, SLOPE_CALC_COORD


class Timer():
    """Processing timer"""

    startTimes = dict()
    stopTimes = dict()

    @staticmethod
    def start(key=0):
        """Start the timer"""
        Timer.startTimes[key] = datetime.now()
        Timer.stopTimes[key] = None

    @staticmethod
    def stop(key=0):
        """Stop the timer"""
        Timer.stopTimes[key] = datetime.now()

    @staticmethod
    def show(key=0):
        """Print computation time"""
        if key in Timer.startTimes:
            if Timer.startTimes[key] is not None:
                if key in Timer.stopTimes:
                    if Timer.stopTimes[key] is not None:
                        delta = Timer.stopTimes[key] - Timer.startTimes[key]
                        print 'Timer delta: %s' % delta


class AdvGraph():
    """Graph class, which will contain each node.
    To use for the least cost path process"""

    def __init__(self):
        """Graph initialization"""
        self.nodes = []
        self.edges = defaultdict(list)
        self.slope_info = defaultdict(list)
        self.length = {}
        self.slope = {}

    def add_nodes(self, id, beg_id, end_id, cost):
        """Function to add a new node in the graph."""
        node = NodeGraph(id, beg_id, end_id, cost)
        self.nodes.append(node)

    def add_info(self, beg, end, length, slope):
        """Function to save info for nodes creation"""
        self.slope_info[beg].append(end)
        self.length[(beg, end)] = length
        self.slope[(beg, end)] = slope


class NodeGraph():
    """Node class, with all informations to use
    for the least cost path process"""

    def __init__(self, id, beg, end, cost):
        """Init node with id, beg_id, end_id,
        cost from the beg pixel to the end pixel"""
        self.id = id
        self.beg = beg
        self.end = end
        self.cost = cost
        self.cumcost = None
        self.edges = []

    def add_edge(self, node):
        """Function to add an edge to the node"""
        self.edges.append(node)


def imp_raster(clip):
    # Open the input raster to retrieve values in an array
    data = gdal.Open(clip, 1)
    # Retrieve proj info
    proj = data.GetProjection()
    scr = data.GetGeoTransform()
    resolution = scr[1]
    # Get raster into array
    band = data.GetRasterBand(1)
    iArray = band.ReadAsArray()

    return iArray, scr, proj, resolution


def rast_to_adv_graph(rastArray, res, nb_edge, max_slope, method, threshold, maskArray, beg_point, end_point):

    # Get Height and Width of the clip
    [H, W] = rastArray.shape

    # Authorize path in the area of the begin and end point if there are not in the mask
    if maskArray is not None:
        px_beg, py_beg = id_to_coord(beg_point)
        px_end, py_end = id_to_coord(end_point)
        if maskArray[px_beg, py_beg] == 0 or maskArray[px_end, py_end] == 0:
            maskArray = None
        else:
            for i in range(px_beg - 3, px_beg + 4):
                for j in range(py_beg - 3, py_beg + 4):
                    if 0 <= i <= H and 0 <= j <= W:
                        maskArray[i, j] = 4
            for i in range(px_end - 3, px_end + 4):
                for j in range(py_end - 3, py_end + 4):
                    if 0 <= i <= H and 0 <= j <= W:
                        maskArray[i, j] = 4

    # Init graph
    G = AdvGraph()

    nb_edge += 1
    # Raster conversion to graph if there is no mask raster
    if maskArray is None:
        # Loop over each pixel to create slope and length dictionnary
        for i in range(0, H):
            for j in range(0, W):
                nodeBeg = "x" + str(i) + "y" + str(j)
                nodeBegValue = rastArray[i, j]
                for index in range(1, nb_edge):
                    x, y = SHIFT[index]
                    nodeEnd = "x" + str(i + x) + "y" + str(j + y)
                    try:
                        nodeEndValue = rastArray[i + x, j + y]
                        if nodeBegValue != NODATA_VALUE and nodeEndValue != NODATA_VALUE:
                            # Compute cost on length + addcost based on slope percent
                            if index in [2, 4, 6, 8]:
                                length = res
                            elif index in [1, 3, 5, 7]:
                                length = res*math.sqrt(2)
                            elif index in [9, 11, 13, 15, 17, 19, 21, 23]:
                                length = res*math.sqrt(res)
                            elif index in [10, 14, 18, 22]:
                                length = 2*res*math.sqrt(2)
                            elif index in [12, 16, 20, 24]:
                                length = 2*res
                            elif index in [25, 28, 29, 32, 33, 36, 37, 40]:
                                length = res*math.sqrt(10)
                            elif index in [26, 27, 30, 31, 34, 35, 38, 39]:
                                length = res*math.sqrt(13)
                            else:
                                length = res*math.sqrt(26)
                            slope = math.fabs(nodeEndValue - nodeBegValue)/length*100
                            G.add_info(nodeBeg, nodeEnd, length, slope)
                        else:
                            G.add_info(nodeBeg, nodeEnd, NODATA_VALUE, NODATA_VALUE)
                    except IndexError:
                        continue
        ind = 0
        nodes_dict = {}
        # Loop over each pixel again, to create nodes
        for i in range(0, H):
            for j in range(0, W):
                nodeBeg = "x" + str(i) + "y" + str(j)
                for index in range(1, nb_edge):
                    x, y = SHIFT[index]
                    nodeEnd = "x" + str(i + x) + "y" + str(j + y)
                    if (i + x) > 0 and (j + y) > 0 and (i + x) < H and (j + y) < W:
                        try:
                            length = G.length[(nodeBeg, nodeEnd)]
                            slope = G.slope[(nodeBeg, nodeEnd)]
                            # if along slope is OK with the slope threshold
                            if slope <= max_slope and slope != NODATA_VALUE:
                                id = nodeBeg + '|' + nodeEnd
                                coords_list = SLOPE_CALC_COORD[index]
                                c_slope_list = []
                                c_slope = None
                                count = 0
                                # c_slope computation
                                for coords in coords_list:
                                    lx, ly = coords[0]
                                    nodeLeft = "x" + str(i + lx) + "y" + str(j + ly)
                                    rx, ry = coords[1]
                                    nodeRight = "x" + str(i + rx) + "y" + str(j + ry)
                                    if (i + lx) > 0 and (j + ly) > 0 and (i + rx) > 0 and (j + ry) > 0 and \
                                        (i + lx) < H and (j + ly) < W and (i + rx) < H and (j + ry) < W and G.slope[nodeLeft, nodeRight] != NODATA_VALUE:
                                        c_slope_list.append(G.slope[nodeLeft, nodeRight])
                                    count += 1
                                if len(c_slope_list) == count and count != 0:
                                    c_slope = sum(c_slope_list)/len(c_slope_list)
                                    pmax = 25
                                    pmin = 60
                                    larg = 4
                                    if c_slope < pmax:
                                        assise = larg/2
                                    else:
                                        assise = min(round((larg/2*(1 + ((c_slope - pmax)/(pmin - pmax))**2)), 2), larg)
                                    talus = assise**2 *larg*(c_slope/100)/2/(larg - (c_slope/100))
                                    addcost = talus
                                    cost = length*addcost + length*1
                                    G.add_nodes(id, nodeBeg, nodeEnd, cost)
                                    nodes_dict[id] = ind
                                    ind += 1
                        except IndexError:
                            continue

        nodes = G.nodes
        # Loop over nodes to establish edges between nodes with direction constraint
        for node1 in nodes:
            x2, y2 = id_to_coord(node1.end)
            id_pt1 = "x" + str(x2) + "y" + str(y2)
            list_ind = []
            for index in range(1, nb_edge):
                i, j = SHIFT[index]
                if (i+x2) > 0 and (j+y2) > 0 and (i+x2) < H and (j+y2) < W:
                    x3, y3 = (x2+i, y2+j)
                    id_pt2 = "x"+str(x3)+"y"+str(y3)
                    id_next = id_pt1+'|'+id_pt2
                    if id_next in nodes_dict:
                        list_ind.append(nodes_dict[id_next])
            for edge in list_ind:
                node2 = nodes[edge]
                if node1.id != node2.id and node1.end == node2.beg:
                    # Direction constraint method with radius of curvature
                    if method == 'r':
                        x1, y1 = id_to_coord(node1.beg)
                        x2, y2 = id_to_coord(node1.end)
                        x3, y3 = id_to_coord(node2.end)
                        az1 = math.degrees(math.atan2(x2 - x1, y2 - y1))
                        az2 = math.degrees(math.atan2(x3 - x2, y3 - y2))
                        if min(x1, x3) <= x2 <= max(x1, x3) and min(y1, y3) <= y2 <= max(y1, y3):
                            mag_v1 = math.sqrt((x1-x2)**2+(y1-y2)**2)
                            mag_v2 = math.sqrt((x3-x2)**2+(y3-y2)**2)
                            if mag_v1 < mag_v2:
                                x_v2, y_v2 = (x3 - x2, y3 - y2)
                                x3, y3 = x2 + x_v2/mag_v2*mag_v1, y2 + y_v2/mag_v2*mag_v1
                            elif mag_v2 < mag_v1:
                                x_v2, y_v2 = (x1 - x2, y1 - y2)
                                x1, y1 = x2+x_v2/mag_v1*mag_v2, y2+y_v2/mag_v1*mag_v2
                            x_v1, y_v1 = (x2 - x1, y2 - y1)
                            x_v1_ort, y_v1_ort = y_v1, -x_v1
                            x_v2, y_v2 = (x3 - x2, y3 - y2)
                            x_v2_ort, y_v2_ort = y_v2, -x_v2
                            c_v1_ort = y_v1_ort*x1+(-x_v1_ort)*y1
                            c_v1_ort = -c_v1_ort
                            c_v2_ort = y_v2_ort*x3+(-x_v2_ort)*y3
                            c_v2_ort = -c_v2_ort
                            e = [-y_v1_ort, x_v1_ort, c_v1_ort]
                            f = [-y_v2_ort, x_v2_ort, c_v2_ort]
                            x4, y4, colineaire = equationResolve(e, f)
                            if (x4 != None and y4 != None):
                                dist1 = math.sqrt((x1-x4)**2+(y1-y4)**2)*5
                                if dist1 >= threshold:
                                    node1.add_edge(node2)
                            elif colineaire == True:
                                node1.add_edge(node2)
                    # Direction constraint method with angle
                    if method == 'a':
                        x1, y1 = id_to_coord(node1.beg)
                        x2, y2 = id_to_coord(node1.end)
                        x3, y3 = id_to_coord(node2.end)
                        az1 = math.degrees(math.atan2(x2 - x1, y2 - y1))
                        az2 = math.degrees(math.atan2(x3 - x2, y3 - y2))
                        if az1 < 0 and az2 > 0:
                            angle = math.fabs(az1)+az2
                        elif az1 > 0 and az2 < 0:
                            angle = math.fabs(az2)+az1
                        else:
                            angle = math.fabs(az1-az2)
                        if angle < -180:
                            angle = angle + 360
                        if angle > 180:
                            angle = angle - 360
                        if math.fabs(angle) <= threshold:
                            node1.add_edge(node2)
    # Raster conversion to graph with mask raster
    else:
        # Loop over each pixel to create slope and length dictionnary
          for i in range(0, H):
              for j in range(0, W):
                  nodeBeg = "x" + str(i) + "y" + str(j)
                  nodeBegValue = rastArray[i, j]
                  for index in range(1, nb_edge):
                      x, y = SHIFT[index]
                      nodeEnd = "x" + str(i + x) + "y" + str(j + y)
                      try:
                          nodeEndValue = rastArray[i + x, j + y]
                          if nodeBegValue != NODATA_VALUE and nodeEndValue != NODATA_VALUE:
                              #Calculate cost on length + addcost based on slope percent
                              if index in [2, 4, 6, 8]:
                                  length = res
                              elif index in [1, 3, 5, 7]:
                                  length = res*math.sqrt(2)
                              elif index in [9, 11, 13, 15, 17, 19, 21, 23]:
                                  length = res*math.sqrt(res)
                              elif index in [10, 14, 18, 22]:
                                  length = 2*res*math.sqrt(2)
                              elif index in [12, 16, 20, 24]:
                                  length = 2*res
                              elif index in [25, 28, 29, 32, 33, 36, 37, 40]:
                                  length = res*math.sqrt(10)
                              elif index in [26, 27, 30, 31, 34, 35, 38, 39]:
                                  length = res*math.sqrt(13)
                              else:
                                  length = res*math.sqrt(26)
                              slope = math.fabs(nodeEndValue - nodeBegValue)/length*100
                              G.add_info(nodeBeg, nodeEnd, length, slope)
                          else:
                              G.add_info(nodeBeg, nodeEnd, NODATA_VALUE, NODATA_VALUE)
                      except IndexError:
                          continue
          ind = 0
          nodes_dict = {}
          # Loop over each pixel again, to create nodes
          for i in range(0, H):
              for j in range(0, W):
                  nodeBeg = "x"+str(i)+"y"+str(j)
                  for index in range(1, nb_edge):
                      x, y = SHIFT[index]
                      nodeEnd = "x"+str(i+x)+"y"+str(j+y)
                      if (i+x) > 0 and (j+y) > 0 and (i+x) < H and (j+y) < W:
                          try:
                              if maskArray[i, j] != 0 and maskArray[i+x, j+y] != 0:
                                  length = G.length[(nodeBeg, nodeEnd)]
                                  slope = G.slope[(nodeBeg, nodeEnd)]
                                  # if along slope is OK with the slope threshold
                                  if slope <= max_slope and slope != NODATA_VALUE:
                                      id = nodeBeg+'|'+nodeEnd
                                      coords_list = SLOPE_CALC_COORD[index]
                                      c_slope_list = []
                                      c_slope = None
                                      count = 0
                                      # c_slope calculation
                                      for coords in coords_list:
                                          lx, ly = coords[0]
                                          nodeLeft = "x"+str(i+lx)+"y"+str(j+ly)
                                          rx, ry = coords[1]
                                          nodeRight = "x"+str(i+rx)+"y"+str(j+ry)
                                          if (i+lx) > 0 and (j+ly) > 0 and (i+rx) > 0 and (j+ry) > 0 and \
                                              (i+lx) < H and (j+ly) < W and (i+rx) < H and (j+ry) < W and G.slope[nodeLeft, nodeRight] != NODATA_VALUE:
                                              c_slope_list.append(G.slope[nodeLeft, nodeRight])
                                          count += 1
                                      if len(c_slope_list) == count and count != 0:
                                          c_slope = sum(c_slope_list) / len(c_slope_list)
                                          pmax = 25
                                          pmin = 60
                                          larg = 4
                                          if c_slope < pmax:
                                              assise = larg/2
                                          else:
                                              assise = min(round((larg / 2*(1 + ((c_slope - pmax)/(pmin - pmax))**2)), 2), larg)
                                          talus = assise**2 *larg * (c_slope/100) / 2 /(larg - (c_slope/100))
                                          addcost = talus
                                          cost = length * addcost + length * 1
                                          G.add_nodes(id, nodeBeg, nodeEnd, cost)
                                          nodes_dict[id] = ind
                                          ind += 1
                          except IndexError:
                              continue

          # Loop over nodes to establish edges between nodes with direction constraint
          nodes = G.nodes
          for node1 in nodes:
              x2, y2 = id_to_coord(node1.end)
              id_pt1 = "x"+str(x2)+"y"+str(y2)
              list_ind = []
              for index in range(1, nb_edge):
                  i, j = SHIFT[index]
                  if (i+x2) > 0 and (j+y2) > 0 and (i+x2) < H and (j+y2) < W:
                      x3, y3 = (x2+i, y2+j)
                      id_pt2 = "x"+str(x3)+"y"+str(y3)
                      id_next = id_pt1+'|'+id_pt2
                      if id_next in nodes_dict:
                          list_ind.append(nodes_dict[id_next])
              for edge in list_ind:
                  node2 = nodes[edge]
                  if node1.id != node2.id and node1.end == node2.beg:
                      # Direction constraint method with radius of curvature
                      if method == 'r':
                          x1, y1 = id_to_coord(node1.beg)
                          x2, y2 = id_to_coord(node1.end)
                          x3, y3 = id_to_coord(node2.end)
                          az1 = math.degrees(math.atan2(x2 - x1, y2 - y1))
                          az2 = math.degrees(math.atan2(x3 - x2, y3 - y2))
                          if min(x1, x3) <= x2 <= max(x1, x3) and min(y1, y3) <= y2 <= max(y1, y3):
                              mag_v1 = math.sqrt((x1-x2)**2+(y1-y2)**2)
                              mag_v2 = math.sqrt((x3-x2)**2+(y3-y2)**2)
                              if mag_v1 < mag_v2:
                                  x_v2, y_v2 = (x3 - x2, y3 - y2)
                                  x3, y3 = x2+x_v2/mag_v2*mag_v1, y2+y_v2/mag_v2*mag_v1
                              elif mag_v2 < mag_v1:
                                  x_v2, y_v2 = (x1 - x2, y1 - y2)
                                  x1, y1 = x2+x_v2/mag_v1*mag_v2, y2+y_v2/mag_v1*mag_v2
                              x_v1, y_v1 = (x2 - x1, y2 - y1)
                              x_v1_ort, y_v1_ort = y_v1, -x_v1
                              x_v2, y_v2 = (x3 - x2, y3 - y2)
                              x_v2_ort, y_v2_ort = y_v2, -x_v2
                              c_v1_ort = y_v1_ort*x1+(-x_v1_ort)*y1
                              c_v1_ort = -c_v1_ort
                              c_v2_ort = y_v2_ort*x3+(-x_v2_ort)*y3
                              c_v2_ort = -c_v2_ort
                              e = [-y_v1_ort, x_v1_ort, c_v1_ort]
                              f = [-y_v2_ort, x_v2_ort, c_v2_ort]
                              x4, y4, colineaire = equationResolve(e, f)
                              if (x4 != None and y4 != None):
                                  dist1 = math.sqrt((x1-x4)**2+(y1-y4)**2)*5
                                  if dist1 >= threshold:
                                      node1.add_edge(node2)
                              elif colineaire == True:
                                  node1.add_edge(node2)
                      # Direction constraint method with angle
                      if method == 'a':
                          x1, y1 = id_to_coord(node1.beg)
                          x2, y2 = id_to_coord(node1.end)
                          x3, y3 = id_to_coord(node2.end)
                          az1 = math.degrees(math.atan2(x2 - x1, y2 - y1))
                          az2 = math.degrees(math.atan2(x3 - x2, y3 - y2))
                          if az1 < 0 and az2 > 0:
                              angle = math.fabs(az1)+az2
                          elif az1 > 0 and az2 < 0:
                              angle = math.fabs(az2)+az1
                          else:
                              angle = math.fabs(az1-az2)
                          if angle < -180:
                              angle = angle + 360
                          if angle > 180:
                              angle = angle - 360
                          if math.fabs(angle) <= threshold:
                              node1.add_edge(node2)
    return G


def adv_dijkstra(graph, init, last, threshold, end_ids, method, usefull_beg_tracks, usefull_end_tracks):

    nodes = graph.nodes
    beg_list = []
    del_ids = []
    # Dict to get path
    path = defaultdict(list)

    # Init
    for node in nodes:
        # Init beg nodes cumcost with the cost of the node
        if node.beg == init:
            if last != None:
                # Compare direction constraint with the last segment direction if exist
                # Direction constraint method with radius of curvature
                if method == 'r':
                    x, y = last
                    x2, y2 = id_to_coord(node.beg)
                    x1 = x2-x
                    y1 = y2-y
                    x3, y3 = id_to_coord(node.end)
                    az1 = math.degrees(math.atan2(x2 - x1, y2 - y1))
                    az2 = math.degrees(math.atan2(x3 - x2, y3 - y2))

                    if min(x1, x3) <= x2 <= max(x1, x3) and min(y1, y3) <= y2 <= max(y1, y3):

                        mag_v1 = math.sqrt((x1-x2)**2+(y1-y2)**2)
                        mag_v2 = math.sqrt((x3-x2)**2+(y3-y2)**2)

                        if mag_v1 < mag_v2:
                            x_v2, y_v2 = (x3 - x2, y3 - y2)
                            x3, y3 = x2+x_v2/mag_v2*mag_v1, y2+y_v2/mag_v2*mag_v1
                        elif mag_v2 < mag_v1:
                            x_v2, y_v2 = (x1 - x2, y1 - y2)
                            x1, y1 = x2+x_v2/mag_v1*mag_v2, y2+y_v2/mag_v1*mag_v2

                        x_v1, y_v1 = (x2 - x1, y2 - y1)
                        x_v1_ort, y_v1_ort = y_v1, -x_v1
                        x_v2, y_v2 = (x3 - x2, y3 - y2)
                        x_v2_ort, y_v2_ort = y_v2, -x_v2

                        c_v1_ort = y_v1_ort*x1+(-x_v1_ort)*y1
                        c_v1_ort = -c_v1_ort
                        c_v2_ort = y_v2_ort*x3+(-x_v2_ort)*y3
                        c_v2_ort = -c_v2_ort

                        e = [-y_v1_ort, x_v1_ort, c_v1_ort]
                        f = [-y_v2_ort, x_v2_ort, c_v2_ort]
                        x4, y4, colineaire = equationResolve(e, f)

                        if (x4 != None and y4 != None):
                            dist1 = math.sqrt((x1-x4)**2+(y1-y4)**2)*5
                            if dist1 >= threshold:
                                node.cumcost = node.cost
                                beg_list.append(node.id)
                                path[node.id].append((node.id, node.cumcost))
                            else:
                                node.cumcost = MAX_VALUE
                                path[node.id].append((node.id, node.cumcost))
                        elif colineaire == True:
                            node.cumcost = node.cost
                            beg_list.append(node.id)
                            path[node.id].append((node.id, node.cumcost))
                # Direction constraint method with angle
                elif method == 'a':
                    x, y = last
                    x2, y2 = id_to_coord(node.beg)
                    x1 = x2-x
                    y1 = y2-y
                    x3, y3 = id_to_coord(node.end)
                    az1 = math.degrees(math.atan2(x2 - x1, y2 - y1))
                    az2 = math.degrees(math.atan2(x3 - x2, y3 - y2))
                    if az1 < 0 and az2 > 0:
                        angle = math.fabs(az1)+az2
                    elif az1 > 0 and az2 < 0:
                        angle = math.fabs(az2)+az1
                    else:
                        angle = math.fabs(az1-az2)
                    if angle < -180:
                        angle = angle + 360
                    if angle > 180:
                        angle = angle - 360
                    if math.fabs(angle) <= threshold:
                        node.cumcost = node.cost
                        beg_list.append(node.id)
                        path[node.id].append((node.id, node.cumcost))
                    else:
                        node.cumcost = MAX_VALUE
                        path[node.id].append((node.id, node.cumcost))
            else:
                node.cumcost = node.cost
                beg_list.append(node.id)
                path[node.id].append((node.id, node.cumcost))
        # Init beg nodes cumcost with the cost of the node if there is previous path created
        elif node.beg in usefull_beg_tracks:
            # Direction constraint method with radius of curvature
            if method == 'r':
                x, y = usefull_beg_tracks[node.beg]
                x2, y2 = id_to_coord(node.beg)
                x1 = x2-x
                y1 = y2-y
                x3, y3 = id_to_coord(node.end)
                az1 = math.degrees(math.atan2(x2 - x1, y2 - y1))
                az2 = math.degrees(math.atan2(x3 - x2, y3 - y2))

                if min(x1, x3) <= x2 <= max(x1, x3) and min(y1, y3) <= y2 <= max(y1, y3):

                    mag_v1 = math.sqrt((x1-x2)**2+(y1-y2)**2)
                    mag_v2 = math.sqrt((x3-x2)**2+(y3-y2)**2)

                    if mag_v1 < mag_v2:
                        x_v2, y_v2 = (x3 - x2, y3 - y2)
                        x3, y3 = x2+x_v2/mag_v2*mag_v1, y2+y_v2/mag_v2*mag_v1
                    elif mag_v2 < mag_v1:
                        x_v2, y_v2 = (x1 - x2, y1 - y2)
                        x1, y1 = x2+x_v2/mag_v1*mag_v2, y2+y_v2/mag_v1*mag_v2

                    x_v1, y_v1 = (x2 - x1, y2 - y1)
                    x_v1_ort, y_v1_ort = y_v1, -x_v1
                    x_v2, y_v2 = (x3 - x2, y3 - y2)
                    x_v2_ort, y_v2_ort = y_v2, -x_v2

                    c_v1_ort = y_v1_ort*x1+(-x_v1_ort)*y1
                    c_v1_ort = -c_v1_ort
                    c_v2_ort = y_v2_ort*x3+(-x_v2_ort)*y3
                    c_v2_ort = -c_v2_ort

                    e = [-y_v1_ort, x_v1_ort, c_v1_ort]
                    f = [-y_v2_ort, x_v2_ort, c_v2_ort]
                    x4, y4, colineaire = equationResolve(e, f)

                    if (x4 != None and y4 != None):
                        dist1 = math.sqrt((x1-x4)**2+(y1-y4)**2)*5
                        if dist1 >= threshold:
                            node.cumcost = node.cost
                            beg_list.append(node.id)
                            path[node.id].append((node.id, node.cumcost))
                        else:
                            node.cumcost = MAX_VALUE
                            path[node.id].append((node.id, node.cumcost))
                    elif colineaire:
                        node.cumcost = node.cost
                        beg_list.append(node.id)
                        path[node.id].append((node.id, node.cumcost))
            # Direction constraint method with angle
            elif method == 'a':
                x, y = usefull_beg_tracks[node.beg]
                x2, y2 = id_to_coord(node.beg)
                x1 = x2-x
                y1 = y2-y
                x3, y3 = id_to_coord(node.end)
                az1 = math.degrees(math.atan2(x2 - x1, y2 - y1))
                az2 = math.degrees(math.atan2(x3 - x2, y3 - y2))
                if az1 < 0 and az2 > 0:
                    angle = math.fabs(az1)+az2
                elif az1 > 0 and az2 < 0:
                    angle = math.fabs(az2)+az1
                else:
                    angle = math.fabs(az1-az2)
                if angle < -180:
                    angle = angle + 360
                if angle > 180:
                    angle = angle - 360
                if math.fabs(angle) <= threshold:
                    node.cumcost = node.cost
                    beg_list.append(node.id)
                    path[node.id].append((node.id, node.cumcost))
                else:
                    node.cumcost = MAX_VALUE
                    path[node.id].append((node.id, node.cumcost))
        # Init end ids list if there is previous path created or end of network buffered
        elif node.end in usefull_end_tracks:
            # Direction constraint method with radius of curvature
            if method == 'r':
                x, y = usefull_end_tracks[node.end]
                x2, y2 = id_to_coord(node.end)
                x1 = x2-x
                y1 = y2-y
                x3, y3 = id_to_coord(node.beg)
                az1 = math.degrees(math.atan2(x2 - x1, y2 - y1))
                az2 = math.degrees(math.atan2(x3 - x2, y3 - y2))

                if min(x1, x3) <= x2 <= max(x1, x3) and min(y1, y3) <= y2 <= max(y1, y3):

                    mag_v1 = math.sqrt((x1-x2)**2+(y1-y2)**2)
                    mag_v2 = math.sqrt((x3-x2)**2+(y3-y2)**2)

                    if mag_v1 < mag_v2:
                        x_v2, y_v2 = (x3 - x2, y3 - y2)
                        x3, y3 = x2+x_v2/mag_v2*mag_v1, y2+y_v2/mag_v2*mag_v1
                    elif mag_v2 < mag_v1:
                        x_v2, y_v2 = (x1 - x2, y1 - y2)
                        x1, y1 = x2+x_v2/mag_v1*mag_v2, y2+y_v2/mag_v1*mag_v2

                    x_v1, y_v1 = (x2 - x1, y2 - y1)
                    x_v1_ort, y_v1_ort = y_v1, -x_v1
                    x_v2, y_v2 = (x3 - x2, y3 - y2)
                    x_v2_ort, y_v2_ort = y_v2, -x_v2

                    c_v1_ort = y_v1_ort*x1+(-x_v1_ort)*y1
                    c_v1_ort = -c_v1_ort
                    c_v2_ort = y_v2_ort*x3+(-x_v2_ort)*y3
                    c_v2_ort = -c_v2_ort

                    e = [-y_v1_ort, x_v1_ort, c_v1_ort]
                    f = [-y_v2_ort, x_v2_ort, c_v2_ort]
                    x4, y4, colineaire = equationResolve(e, f)

                    if (x4 != None and y4 != None):
                        dist1 = math.sqrt((x1-x4)**2+(y1-y4)**2)*5
                        if dist1 >= threshold:
                            end_ids.append(node.end)
                        else:
                            del_ids.append(node.id)
                    elif colineaire == True:
                        end_ids.append(node.end)
                    else:
                        del_ids.append(node.id)
            # Direction constraint method with angle
            elif method == 'a':
                x, y = usefull_end_tracks[node.end]
                x2, y2 = id_to_coord(node.end)
                x1 = x2-x
                y1 = y2-y
                x3, y3 = id_to_coord(node.beg)
                az1 = math.degrees(math.atan2(x2 - x1, y2 - y1))
                az2 = math.degrees(math.atan2(x3 - x2, y3 - y2))
                if az1 < 0 and az2 > 0:
                    angle = math.fabs(az1)+az2
                elif az1 > 0 and az2 < 0:
                    angle = math.fabs(az2)+az1
                else:
                    angle = math.fabs(az1-az2)
                if angle < -180:
                    angle = angle + 360
                if angle > 180:
                    angle = angle - 360
                if math.fabs(angle) <= threshold:
                    end_ids.append(node.end)
                else:
                    del_ids.append(node.id)

    # Delete nodes, which aren't suitable with direction constraint
    nodes = [node for node in nodes if node.id not in del_ids]

    min_node = NodeGraph(0, 0, 0, 0)
    finish = None
    fin_weight = None
    count = 0
    # Launch dijkstra algorithm
    while nodes:
        if min_node.end not in end_ids:
            min_node = None
            # Select the min cumcost node
            for i, node in enumerate(nodes):
                if node.cumcost != None:
                    if min_node is None:
                        ind = i
                        min_node = node
                    elif node.cumcost < min_node.cumcost:
                        ind = i
                        min_node = node

            # Delete the min_node
            if min_node != None and min_node.cumcost < 5000:
                nodes.pop(ind)
                # Calcul of neighboured nodes cumcost based on edges of the min_node
                for node in min_node.edges:
                    weight = min_node.cumcost + node.cost
                    if node.cumcost == None or weight < node.cumcost:
                        node.cumcost = weight
                        path[node.id].append((min_node.id, weight))
                        count += 1
                        if math.fmod(count, 10000) == 0:
                            print "...searching..."

            else:
                print 'no solution'
                finish = None
                last_beg = last
                fin_weight = None
                break
        else:
            finish = min_node.id
            print 'finish:', finish
            beg, end = finish.split('|')
            x_beg, y_beg = id_to_coord(beg)
            x_end, y_end = id_to_coord(end)
            # get last segment direction for the next path
            last_beg = (int(x_end)-int(x_beg), int(y_end)-int(y_beg))
            fin_weight = min_node.cumcost
            print 'fin_weight:', fin_weight
            break
    return path, beg_list, finish, last_beg, fin_weight


def equationResolve(e1, e2):
    """Computes coordinates for the radius of curvature"""

    determinant = e1[0]*e2[1] - e1[1]*e2[0]
    x, y = None, None
    colineaire = False
    if determinant != 0:
        x = (e1[2]*e2[1] - e1[1]*e2[2])/determinant
        y = (e1[0]*e2[2] - e1[2]*e2[0])/determinant
    else:
        colineaire = True

    return x, y, colineaire


def id_to_coord(id):
    """Convert a node id to coordinates"""
    id = id[1:]
    px, py = id.split('y')
    px, py = int(px), int(py)

    return px, py


def ids_to_coord(lcp, gt):
    """Reproj pixel coordinates to map coordinates"""

    coord_list = []
    for id in lcp:
        id = id[1:]
        px, py = id.split('y')
        px, py = int(px), int(py)
        # Convert from pixel to map coordinates.
        mx = py * gt[1] + gt[0] + gt[1]/2
        my = px * gt[5] + gt[3] - gt[5]/2
        coord_list.append((mx, my))
    # return the list of end point with x, y map coordinates
    return coord_list


def create_ridge(out_layer, lcp, id_line, point_id, nature, weight):
    """Create vector line for the path"""

    out_layer.startEditing()
    feat = QgsFeature(out_layer.pendingFields())

    # Initiate feature geometry
    line = []
    for coord in lcp:
        x, y = coord
        pt = QgsPoint(x, y)
        # Add new vertice to the linestring
        line.append(pt)
    polyline = QgsGeometry.fromPolyline(line)
    feat.setGeometry(polyline)
    feat.setAttributes([id_line, point_id, nature, weight])
    out_layer.dataProvider().addFeatures([feat])
    out_layer.commitChanges()


def get_adv_lcp(beg_list, path, end_id, method, threshold):
    """Retrieve least cost path from the path dict"""

    if end_id != None:
        pt2, pt1 = end_id.split('|')
        act = end_id
        leastCostPath = [pt1, pt2]
        print 'Create the least cost path as OGR LineString...'
        while act not in beg_list:
            pt2, pt1 = act.split('|')
            pt2 = pt2[1:]
            x2, y2 = pt2.split('y')
            pt1 = pt1[1:]
            x1, y1 = pt1.split('y')
            feasible_path = []
            for edge in path[act]:
                prev = edge[0]
                pt3, pt2 = prev.split('|')
                pt3 = pt3[1:]
                x3, y3 = pt3.split('y')
                x1, y1, x2, y2, x3, y3 = int(x1), int(y1), int(x2), int(y2), int(x3), int(y3)
                # Direction constraint method with radius of curvature
                if method == 'a':
                    az1 = math.degrees(math.atan2(x2 - x1, y2 - y1))
                    az2 = math.degrees(math.atan2(x3 - x2, y3 - y2))
                    if az1 < 0 and az2 > 0:
                        angle = math.fabs(az1)+az2
                    elif az1 > 0 and az2 < 0:
                        angle = math.fabs(az2)+az1
                    else:
                        angle = math.fabs(az1-az2)
                    if angle < -180:
                        angle = angle + 360
                    if angle > 180:
                        angle = angle - 360
                    if math.fabs(angle) <= threshold:
                        feasible_path.append(edge)
                # Direction constraint method with angle
                if method == 'r':
                    az1 = math.degrees(math.atan2(x2 - x1, y2 - y1))
                    az2 = math.degrees(math.atan2(x3 - x2, y3 - y2))
                    # if az1 != (az2+180) and az1 != (az2-180):
                    if min(x1, x3) <= x2 <= max(x1, x3) and min(y1, y3) <= y2 <= max(y1, y3):

                        mag_v1 = math.sqrt((x1-x2)**2+(y1-y2)**2)
                        mag_v2 = math.sqrt((x3-x2)**2+(y3-y2)**2)

                        if mag_v1 < mag_v2:
                            x_v2, y_v2 = (x3 - x2, y3 - y2)
                            x3, y3 = x2+x_v2/mag_v2*mag_v1, y2+y_v2/mag_v2*mag_v1
                        elif mag_v2 < mag_v1:
                            x_v2, y_v2 = (x1 - x2, y1 - y2)
                            x1, y1 = x2+x_v2/mag_v1*mag_v2, y2+y_v2/mag_v1*mag_v2

                        x_v1, y_v1 = (x2 - x1, y2 - y1)
                        x_v1_ort, y_v1_ort = y_v1, -x_v1
                        x_v2, y_v2 = (x3 - x2, y3 - y2)
                        x_v2_ort, y_v2_ort = y_v2, -x_v2

                        c_v1_ort = y_v1_ort*x1+(-x_v1_ort)*y1
                        c_v1_ort = -c_v1_ort
                        c_v2_ort = y_v2_ort*x3+(-x_v2_ort)*y3
                        c_v2_ort = -c_v2_ort

                        e = [-y_v1_ort, x_v1_ort, c_v1_ort]
                        f = [-y_v2_ort, x_v2_ort, c_v2_ort]
                        x4, y4, colineaire = equationResolve(e, f)

                        if (x4 != None and y4 != None):
                            dist1 = math.sqrt((x1-x4)**2+(y1-y4)**2)*5

                            if dist1 >= threshold:
                                feasible_path.append(edge)

                        elif colineaire == True:
                            feasible_path.append(edge)

            weight = None
            for w_path in feasible_path:
                if weight == None:
                    weight = w_path[1]
                    id = w_path[0]
                elif w_path[1] < weight:
                    weight = w_path[1]
                    id = w_path[0]
            act = id
            pt3, pt2 = id.split('|')
            leastCostPath.append(pt3)
    else:
        leastCostPath = None
    return leastCostPath, act


def getExtent(point_geom, npoint_geom, x_res, y_res, f_extent):
    """Define clip extent from the start and end point"""

    x1, y1 = point_geom
    x2, y2 = npoint_geom

    dist = math.sqrt(point_geom.sqrDist(npoint_geom))
    mod = (dist/2) % x_res
    dist = (dist/2) - mod + x_res
    facteur = 3

    xmax = max(x1, x2) + x_res/2 + int(dist)*2 + f_extent*facteur*x_res
    xmin = min(x1, x2) - x_res/2 - int(dist)*2 - f_extent*facteur*x_res
    ymax = max(y1, y2) + y_res/2 + int(dist)*2 + f_extent*facteur*y_res
    ymin = min(y1, y2) - y_res/2 - int(dist)*2 - f_extent*facteur*y_res

    return [xmin, xmax, ymin, ymax]


def getClip(DEM_layer, outpath, extent, x_res, y_res, name):
    """Create clip with the extent, previously defined"""

    name_clip = '%s\\tmp' % os.path.dirname(outpath)
    name_clip += name
    extent = str(str(extent[0])+','+str(extent[1])+','+str(extent[2])+','+str(extent[3]))
    processing.runalg('gdalogr:cliprasterbyextent', {'INPUT': DEM_layer.source(), 'PROJWIN': extent, 'OUTPUT': name_clip})
    name_clip = name_clip + '.tif'

    return name_clip


def getUsefullTrack(extent, tracks_layer, line_id, scr, point_layer, in_point):
    """Select path intersected by the clip extent"""

    nature = in_point.attribute('nature')
    rect = QgsRectangle(extent[0], extent[1], extent[2], extent[3])
    usefull_track_dict = {}
    # if first segment, select track from the road crossing
    if nature == 'start':
        boundingBox = in_point.geometry().buffer(1, 4).boundingBox()
        expre = QgsExpression('L_id != %s' % (in_point.attribute('L_id')))
        reque = QgsFeatureRequest(expre).setFilterRect(boundingBox)
        points = point_layer.getFeatures(reque)
        for point in points:
            l_id = point.attribute('L_id')
            expr = QgsExpression('L_id = %s' % (l_id))
            requ = QgsFeatureRequest(expr).setFilterRect(rect)
            t_feats = tracks_layer.getFeatures(requ)
            for feat in t_feats:
                ft_geom = feat.geometry().asPolyline()
                for i, pt in enumerate(reversed(ft_geom)):
                    if i != len(ft_geom) - 1:
                        Qpt = pt
                        Qptp = ft_geom[-i-2]
                        if rect.contains(Qptp) and rect.contains(Qpt):
                            pt_x, pt_y = id_to_coord(map2pixel(pt, scr))
                            end_id = map2pixel(ft_geom[-i-2], scr)
                            ptp_x, ptp_y = id_to_coord(end_id)
                            last = (int(ptp_x)-int(pt_x), int(ptp_y)-int(pt_y))
                            usefull_track_dict[end_id] = last
    # if end segment, select track from the road crossing
    elif nature == 'end':
        boundingBox = in_point.geometry().buffer(1, 4).boundingBox()
        expre = QgsExpression('L_id != %s'%(in_point.attribute('L_id')))
        reque = QgsFeatureRequest(expre).setFilterRect(boundingBox)
        points = point_layer.getFeatures(reque)
        for point in points:
            p_nat = point.attribute('nature')
            l_id = point.attribute('L_id')
            expr = QgsExpression('L_id = %s'%(l_id))
            requ = QgsFeatureRequest(expr).setFilterRect(rect)
            t_feats = tracks_layer.getFeatures(requ)
            for feat in t_feats:
                ft_geom = feat.geometry().asPolyline()
                if p_nat == 'start':
                    for i, pt in enumerate(reversed(ft_geom)):
                        if i != len(ft_geom)-1:
                            Qpt = pt
                            Qptp = ft_geom[-i-2]
                            if rect.contains(Qptp) and rect.contains(Qpt):
                                pt_x, pt_y = id_to_coord(map2pixel(pt, scr))
                                end_id = map2pixel(ft_geom[-i-2], scr)
                                ptp_x, ptp_y = id_to_coord(end_id)
                                last = (int(ptp_x)-int(pt_x), int(ptp_y)-int(pt_y))
                                usefull_track_dict[end_id] = last
                elif p_nat == 'end':
                    for i, pt in enumerate(ft_geom):
                        if i != len(ft_geom)-1:
                            Qpt = pt
                            Qptp = ft_geom[i+1]
                            if rect.contains(Qptp) and rect.contains(Qpt):
                                pt_x, pt_y = id_to_coord(map2pixel(pt, scr))
                                end_id = map2pixel(ft_geom[i+1], scr)
                                ptp_x, ptp_y = id_to_coord(end_id)
                                last = (int(ptp_x)-int(pt_x), int(ptp_y)-int(pt_y))
                                usefull_track_dict[end_id] = last
    # if not, select previous tracks with the same L_id
    else:
        expr = QgsExpression('L_id = %s' % line_id)
        req = QgsFeatureRequest(expr).setFilterRect(rect)
        feats = tracks_layer.getFeatures(req)
        for feat in feats:
            ft_geom = feat.geometry().asPolyline()
            for i, pt in enumerate(reversed(ft_geom)):
                if i != len(ft_geom)-1:
                    Qpt = pt
                    Qptp = ft_geom[-i-2]
                    if rect.contains(Qptp) and rect.contains(Qpt):
                        pt_x, pt_y = id_to_coord(map2pixel(pt, scr))
                        end_id = map2pixel(ft_geom[-i-2], scr)
                        ptp_x, ptp_y = id_to_coord(end_id)
                        last = (int(ptp_x)-int(pt_x), int(ptp_y)-int(pt_y))
                        usefull_track_dict[end_id] = last

    return usefull_track_dict


def map2pixel(point_geom, gt):
    """Change map coordinates to pixel coordinates"""
    mx, my = point_geom
    # Convert from map to pixel coordinates.
    px = int((my - gt[3] + gt[5]/2) / gt[5])
    py = int(((mx - gt[0] - gt[1]/2) / gt[1]))
    beg_point = "x"+str(px)+"y"+str(py)

    return beg_point


def buffEndPoint(end_point):
    """Get ids of the end nodes for end of network"""

    ids = []
    px, py = id_to_coord(end_point)
    for pi in range(px - 2, px + 3):
        for pj in range(py - 2, py + 3):
            id = 'x' + str(pi) + 'y' + str(pj)
            ids.append(id)

    return ids


def betweenPoint(point, next_point, point_layer, DEM_layer, tracks_layer, line_id, outpath, nb_edges, max_slope, method, threshold, x_res, y_res, f_extent, last_beg, Mask_layer):
    """Process to find path between two point"""
    # Get point geometry
    point_geom = point.geometry().asPoint()
    npoint_geom = next_point.geometry().asPoint()
    # Define extent
    extent = getExtent(point_geom, npoint_geom, x_res, y_res, f_extent)
    # Get clip
    dem_clip = getClip(DEM_layer, outpath, extent, x_res, y_res, '_dem')
    if Mask_layer != None:
        mask_clip = getClip(Mask_layer, outpath, extent, x_res, y_res, '_mask')
        in_array_mask, scr, proj, res = imp_raster(mask_clip)
    else:
        in_array_mask = None
    # Convert raster clip to array
    in_array, scr, proj, res = imp_raster(dem_clip)
    # Get map coordinates of points
    beg_point = map2pixel(point_geom, scr)
    end_points = []
    end_point = map2pixel(npoint_geom, scr)
    end_points.append(end_point)
    # Create graph
    G = rast_to_adv_graph(in_array, res, nb_edges, max_slope, method, threshold, in_array_mask, beg_point, end_point)
    # Get tracks that will be use to find lcp
    usefull_beg_tracks = getUsefullTrack(extent, tracks_layer, line_id, scr, point_layer, point)
    if next_point.attribute('nature') == 'end':
        other_point = None
        req = QgsFeatureRequest(QgsExpression("L_id != %s" % line_id)).setFilterRect(next_point.geometry().buffer(1, 4).boundingBox())
        other_point_it = point_layer.getFeatures(req)
        try:
            other_point = next(other_point_it)
        except StopIteration:
            pass
        if other_point != None:
            usefull_end_tracks = getUsefullTrack(extent, tracks_layer, line_id, scr, point_layer, next_point)
        else:
            end_points = buffEndPoint(end_point)
            usefull_end_tracks = []
    else:
        usefull_end_tracks = []
    #Find lcp
    path, beg_list, end_id, last_mouv, w = adv_dijkstra(G, beg_point, last_beg, threshold, end_points, method, usefull_beg_tracks, usefull_end_tracks)
    G = None

    return path, beg_list, beg_point, end_id, last_mouv, w, scr


def advanced_algo(point_layer, DEM_layer, tracks_layer, outpath, nb_edges, method, threshold, max_slope, Mask_layer):
    crs = tracks_layer.crs().toWkt()
    # raster resolution
    x_res = DEM_layer.rasterUnitsPerPixelX()
    y_res = DEM_layer.rasterUnitsPerPixelY()

    # point selection
    base_coeff = threshold*0.875

    # list line
    lines_list = []
    for point in point_layer.getFeatures():
        line_id = point.attribute('L_id')
        if line_id not in lines_list:
            lines_list.append(line_id)

    inter_count = 0
    # Loop the points for each line
    line_to_change = {}
    for line in lines_list:
        expr = QgsExpression('L_id = %s'%line)
        req = QgsFeatureRequest(expr)
        line_points = point_layer.getFeatures(req)
        last_beg = None
        list_points = []
        nature = None
        for point in line_points:
            next_point_it = None
            nnext_point_it = None
            previous_point_it = None
            pprevious_point_it = None
            nature = point.attribute('nature')
            point_id = point.attribute('P_id')
            cancel = 0
            # if point equal start or end, it will be keeped,
            # otherwise the process will defined which points
            # will be set aside, based on mean slope between points
            if nature == 'start':
                list_points.append(point_id)
                expre = QgsExpression('L_id = %s AND P_id= %s'%(line, str(int(point_id)+1)))
                reque = QgsFeatureRequest(expre)
                next_point_it = point_layer.getFeatures(reque)
                next_point = next(next_point_it)
                nnature = next_point.attribute('nature')
                point_geom = point.geometry().asPoint()
                next_point_geom = next_point.geometry().asPoint()
                point_alt = DEM_layer.dataProvider().identify(point_geom, QgsRaster.IdentifyFormatValue).results()[1]
                next_point_alt = DEM_layer.dataProvider().identify(next_point_geom, QgsRaster.IdentifyFormatValue).results()[1]
                length = round(math.sqrt(point_geom.sqrDist(next_point_geom)), 3)
                if length == 0:
                    coeff = MAX_VALUE
                else:
                    coeff = math.fabs(point_alt-next_point_alt)/length
                if coeff == MAX_VALUE and nnature == 'end':
                    cancel = 1
                elif coeff < base_coeff or nnature == 'end':
                    next_point_id = next_point.attribute('P_id')
                    list_points.append(next_point_id)
                    nature = nnature
                else:
                    expre = QgsExpression('L_id = %s AND P_id= %s'%(line, str(int(point_id)+2)))
                    reque = QgsFeatureRequest(expre)
                    nnext_point_it = point_layer.getFeatures(reque)
                    nnext_point = next(nnext_point_it)
                    nnnature = nnext_point.attribute('nature')
                    nnext_point_geom = nnext_point.geometry().asPoint()
                    nnext_point_alt = DEM_layer.dataProvider().identify(nnext_point_geom, QgsRaster.IdentifyFormatValue).results()[1]
                    length = round(math.sqrt(point_geom.sqrDist(nnext_point_geom)), 3)
                    if length == 0:
                        ncoeff = MAX_VALUE
                    else:
                        ncoeff = math.fabs(point_alt-nnext_point_alt)/length
                    if ncoeff < coeff and next_point_alt > point_alt and next_point_alt > nnext_point_alt:
                        nnext_point_id = nnext_point.attribute('P_id')
                        list_points.append(nnext_point_id)
                        nature = nnnature
                    elif ncoeff == MAX_VALUE and coeff == MAX_VALUE:
                        cancel = 1
                    else:
                        next_point_id = next_point.attribute('P_id')
                        list_points.append(next_point_id)
                        nature = nnature
            elif point_id in list_points and nature != 'end':
                expre = QgsExpression('L_id = %s AND P_id= %s'%(line, str(int(point_id)+1)))
                reque = QgsFeatureRequest(expre)
                next_point_it = point_layer.getFeatures(reque)
                next_point = next(next_point_it)
                next_point_it = None
                nnature = next_point.attribute('nature')
                point_geom = point.geometry().asPoint()
                next_point_geom = next_point.geometry().asPoint()
                point_alt = DEM_layer.dataProvider().identify(point_geom, QgsRaster.IdentifyFormatValue).results()[1]
                next_point_alt = DEM_layer.dataProvider().identify(next_point_geom, QgsRaster.IdentifyFormatValue).results()[1]
                length = round(math.sqrt(point_geom.sqrDist(next_point_geom)), 3)
                if length == 0:
                    coeff = MAX_VALUE
                else:
                    coeff = math.fabs(point_alt-next_point_alt)/length
                if coeff < base_coeff:
                    next_point_id = next_point.attribute('P_id')
                    list_points.append(next_point_id)
                    nature = nnature
                #if previous point following actual point
                elif (int(point_id) - int(list_points[-2])) == 1:
                    expre = QgsExpression('L_id = %s AND P_id= %s'%(line, str(list_points[-2])))
                    reque = QgsFeatureRequest(expre)
                    previous_point_it = point_layer.getFeatures(reque)
                    previous_point = next(previous_point_it)
                    previous_point_it = None
                    pnature = previous_point.attribute('nature')
                    previous_point_geom = previous_point.geometry().asPoint()
                    previous_point_alt = DEM_layer.dataProvider().identify(previous_point_geom, QgsRaster.IdentifyFormatValue).results()[1]
                    marge = math.fabs(point_alt-previous_point_alt)/math.fabs(point_alt-next_point_alt)
                    if previous_point_alt <= point_alt <= next_point_alt or previous_point_alt >= point_alt >= next_point_alt or marge < 0.15:
                        length = round(math.sqrt(next_point_geom.sqrDist(previous_point_geom)), 3)
                        if length == 0:
                            pcoeff = MAX_VALUE
                        else:
                            pcoeff = math.fabs(next_point_alt-previous_point_alt)/length
                        if pcoeff < base_coeff:
                            next_point_id = next_point.attribute('P_id')
                            del list_points[-1]
                            list_points.append(next_point_id)
                            nature = nnature
                        elif len(list_points) >= 3:
                            expre = QgsExpression('L_id = %s AND P_id= %s'%(line, str(list_points[-3])))
                            reque = QgsFeatureRequest(expre)
                            pprevious_point_it = point_layer.getFeatures(reque)
                            pprevious_point = next(pprevious_point_it)
                            pprevious_point_it = None
                            ppnature = pprevious_point.attribute('nature')
                            pprevious_point_geom = pprevious_point.geometry().asPoint()
                            pprevious_point_alt = DEM_layer.dataProvider().identify(pprevious_point_geom, QgsRaster.IdentifyFormatValue).results()[1]
                            marge = math.fabs(point_alt-pprevious_point_alt)/math.fabs(point_alt-next_point_alt)
                            if pprevious_point_alt <= previous_point_alt <= next_point_alt or pprevious_point_alt >= previous_point_alt >= next_point_alt or marge < 0.15:
                                length = round(math.sqrt(next_point_geom.sqrDist(pprevious_point_geom)), 3)
                                if length == 0:
                                    ppcoeff = MAX_VALUE
                                else:
                                    ppcoeff = math.fabs(next_point_alt-pprevious_point_alt)/length
                                if ppcoeff < base_coeff:
                                    next_point_id = next_point.attribute('P_id')
                                    del list_points[-1]
                                    del list_points[-1]
                                    list_points.append(next_point_id)
                                    nature = nnature
                                else:
                                    best = min(coeff, pcoeff, ppcoeff)
                                    if best < 0.15:
                                        if best == coeff:
                                            next_point_id = next_point.attribute('P_id')
                                            list_points.append(next_point_id)
                                            nature = nnature
                                        elif best == pcoeff:
                                            next_point_id = next_point.attribute('P_id')
                                            del list_points[-1]
                                            list_points.append(next_point_id)
                                            nature = nnature
                                        else:
                                            next_point_id = next_point.attribute('P_id')
                                            del list_points[-1]
                                            del list_points[-1]
                                            list_points.append(next_point_id)
                                            nature = nnature
                                    elif nnature != 'end':
                                        expre = QgsExpression('L_id = %s AND P_id= %s'%(line, str(int(point_id)+2)))
                                        reque = QgsFeatureRequest(expre)
                                        nnext_point_it = point_layer.getFeatures(reque)
                                        nnext_point = next(nnext_point_it)
                                        nnext_point_it = None
                                        nnnature = nnext_point.attribute('nature')
                                        nnext_point_geom = nnext_point.geometry().asPoint()
                                        nnext_point_alt = DEM_layer.dataProvider().identify(nnext_point_geom, QgsRaster.IdentifyFormatValue).results()[1]
                                        length = round(math.sqrt(point_geom.sqrDist(nnext_point_geom)), 3)
                                        if length == 0:
                                            ncoeff = MAX_VALUE
                                        else:
                                            ncoeff = math.fabs(point_alt-nnext_point_alt)/length
                                        if ncoeff < best and next_point_alt > point_alt and next_point_alt > nnext_point_alt:
                                            nnext_point_id = nnext_point.attribute('P_id')
                                            list_points.append(nnext_point_id)
                                            nature = nnnature
                                        else:
                                            if best == coeff:
                                                next_point_id = next_point.attribute('P_id')
                                                list_points.append(next_point_id)
                                                nature = nnature
                                            elif best == pcoeff:
                                                next_point_id = next_point.attribute('P_id')
                                                del list_points[-1]
                                                list_points.append(next_point_id)
                                                nature = nnature
                                            else:
                                                next_point_id = next_point.attribute('P_id')
                                                del list_points[-1]
                                                del list_points[-1]
                                                list_points.append(next_point_id)
                                                nature = nnature
                                    else:
                                        if best == coeff:
                                            next_point_id = next_point.attribute('P_id')
                                            list_points.append(next_point_id)
                                            nature = nnature
                                        elif best == pcoeff:
                                            next_point_id = next_point.attribute('P_id')
                                            del list_points[-1]
                                            list_points.append(next_point_id)
                                            nature = nnature
                                        else:
                                            next_point_id = next_point.attribute('P_id')
                                            del list_points[-1]
                                            del list_points[-1]
                                            list_points.append(next_point_id)
                                            nature = nnature
                            else:
                                best = min(coeff, pcoeff)
                                if best < 0.15 or nnature == 'end':
                                    if best == coeff:
                                        next_point_id = next_point.attribute('P_id')
                                        list_points.append(next_point_id)
                                        nature = nnature
                                    else:
                                        next_point_id = next_point.attribute('P_id')
                                        del list_points[-1]
                                        list_points.append(next_point_id)
                                        nature = nnature
                                else:
                                    expre = QgsExpression('L_id = %s AND P_id= %s'%(line, str(int(point_id)+2)))
                                    reque = QgsFeatureRequest(expre)
                                    nnext_point_it = point_layer.getFeatures(reque)
                                    nnext_point = next(nnext_point_it)
                                    nnext_point_it = None
                                    nnnature = nnext_point.attribute('nature')
                                    nnext_point_geom = nnext_point.geometry().asPoint()
                                    nnext_point_alt = DEM_layer.dataProvider().identify(nnext_point_geom, QgsRaster.IdentifyFormatValue).results()[1]
                                    length = round(math.sqrt(point_geom.sqrDist(nnext_point_geom)), 3)
                                    if length == 0:
                                        ncoeff = MAX_VALUE
                                    else:
                                        ncoeff = math.fabs(point_alt-nnext_point_alt)/length
                                    if ncoeff < best and next_point_alt > point_alt and next_point_alt > nnext_point_alt:
                                        nnext_point_id = nnext_point.attribute('P_id')
                                        list_points.append(nnext_point_id)
                                        nature = nnnature
                                    else:
                                        if best == coeff:
                                            next_point_id = next_point.attribute('P_id')
                                            list_points.append(next_point_id)
                                            nature = nnature
                                        else:
                                            next_point_id = next_point.attribute('P_id')
                                            del list_points[-1]
                                            list_points.append(next_point_id)
                                            nature = nnature
                        else:
                            best = min(coeff, pcoeff)
                            if best < 0.15 or nnature == 'end':
                                if best == coeff:
                                    next_point_id = next_point.attribute('P_id')
                                    list_points.append(next_point_id)
                                    nature = nnature
                                else:
                                    next_point_id = next_point.attribute('P_id')
                                    del list_points[-1]
                                    list_points.append(next_point_id)
                                    nature = nnature
                            else:
                                expre = QgsExpression('L_id = %s AND P_id= %s'%(line, str(int(point_id)+2)))
                                reque = QgsFeatureRequest(expre)
                                nnext_point_it = point_layer.getFeatures(reque)
                                nnext_point = next(nnext_point_it)
                                nnext_point_it = None
                                nnnature = nnext_point.attribute('nature')
                                nnext_point_geom = nnext_point.geometry().asPoint()
                                nnext_point_alt = DEM_layer.dataProvider().identify(nnext_point_geom, QgsRaster.IdentifyFormatValue).results()[1]
                                length = round(math.sqrt(point_geom.sqrDist(nnext_point_geom)), 3)
                                if length == 0:
                                    ncoeff = MAX_VALUE
                                else:
                                    ncoeff = math.fabs(point_alt-nnext_point_alt)/length
                                if ncoeff < best:
                                    nnext_point_id = nnext_point.attribute('P_id')
                                    list_points.append(nnext_point_id)
                                    nature = nnnature
                                else:
                                    if best == coeff:
                                        next_point_id = next_point.attribute('P_id')
                                        list_points.append(next_point_id)
                                        nature = nnature
                                    else:
                                        next_point_id = next_point.attribute('P_id')
                                        del list_points[-1]
                                        list_points.append(next_point_id)
                                        nature = nnature
                    elif nnature != 'end':
                        expre = QgsExpression('L_id = %s AND P_id= %s'%(line, str(int(point_id)+2)))
                        reque = QgsFeatureRequest(expre)
                        nnext_point_it = point_layer.getFeatures(reque)
                        nnext_point = next(nnext_point_it)
                        nnext_point_it = None
                        nnnature = nnext_point.attribute('nature')
                        nnext_point_geom = nnext_point.geometry().asPoint()
                        nnext_point_alt = DEM_layer.dataProvider().identify(nnext_point_geom, QgsRaster.IdentifyFormatValue).results()[1]
                        length = round(math.sqrt(point_geom.sqrDist(nnext_point_geom)), 3)
                        if length == 0:
                            ncoeff = MAX_VALUE
                        else:
                            ncoeff = math.fabs(point_alt-nnext_point_alt)/length
                        if ncoeff < coeff:
                            nnext_point_id = nnext_point.attribute('P_id')
                            list_points.append(nnext_point_id)
                            nature = nnnature
                        else:
                            next_point_id = next_point.attribute('P_id')
                            list_points.append(next_point_id)
                            nature = nnature
                    else:
                        next_point_id = next_point.attribute('P_id')
                        list_points.append(next_point_id)
                        nature = nnature
                elif nnature != 'end':
                    expre = QgsExpression('L_id = %s AND P_id= %s'%(line, str(int(point_id)+2)))
                    reque = QgsFeatureRequest(expre)
                    nnext_point_it = point_layer.getFeatures(reque)
                    nnext_point = next(nnext_point_it)
                    nnext_point_it = None
                    nnnature = nnext_point.attribute('nature')
                    nnext_point_geom = nnext_point.geometry().asPoint()
                    nnext_point_alt = DEM_layer.dataProvider().identify(nnext_point_geom, QgsRaster.IdentifyFormatValue).results()[1]
                    length = round(math.sqrt(point_geom.sqrDist(nnext_point_geom)), 3)
                    if length == 0:
                        ncoeff = MAX_VALUE
                    else:
                        ncoeff = math.fabs(point_alt-nnext_point_alt)/length
                    if ncoeff < coeff and next_point_alt > point_alt and next_point_alt > nnext_point_alt:
                        nnext_point_id = nnext_point.attribute('P_id')
                        list_points.append(nnext_point_id)
                        nature = nnnature
                    else:
                        next_point_id = next_point.attribute('P_id')
                        list_points.append(next_point_id)
                        nature = nnature
                else:
                    next_point_id = next_point.attribute('P_id')
                    list_points.append(next_point_id)
                    nature = nnature
        if cancel == 0:
            print 'line, point list:', line, list_points
            # Loop over the points the algo kept
            for i, point_id in enumerate(list_points):
                # Select a point
                expre = QgsExpression('L_id = %s AND P_id= %s'%(line, str(point_id)))
                reque = QgsFeatureRequest(expre)
                point_it = point_layer.getFeatures(reque)
                point = next(point_it)
                point_it = None
                nature = point.attribute('nature')
                if nature != 'end':
                    next_point = None
                    point_id = point.attribute('P_id')
                    next_id = list_points[i+1]
                    # And select the next one
                    expre = QgsExpression('L_id = %s AND P_id= %s'%(line, str(next_id)))
                    reque = QgsFeatureRequest(expre)
                    next_point_it = point_layer.getFeatures(reque)
                    try:
                        next_point = next(next_point_it)
                        next_nature = next_point.attribute('nature')
                        next_point_it = None
                    except StopIteration:
                        pass
                    if next_point != None:
                        f_extent = 2
                        end_id = None
                        print 'L_id = %s AND P_id= %s'%(line, str(next_id))
                        # Iteration to find lcp, with a more and more wide clip of interest
                        while end_id == None and f_extent < 5:
                            f_extent += 1
                            # Find lcp between the two points
                            path, beg_list, beg_point, end_id, last_beg, w, scr = betweenPoint(point, next_point, point_layer, DEM_layer, tracks_layer, line, outpath, nb_edges, max_slope, method, threshold, x_res, y_res, f_extent, last_beg, Mask_layer)

                        if end_id != None:
                            # Get lcp and convert it into coord
                            leastCostPath, act_beg = get_adv_lcp(beg_list, path, end_id, method, threshold)
                            coord_list = ids_to_coord(leastCostPath, scr)
                            end_pt = leastCostPath[0]
                            # Create the vector line
                            create_ridge(tracks_layer, coord_list, line, next_id, next_nature, w)
                            act_beg_pt2, act_beg_pt1 = act_beg.split('|')
                            # Correction on previous line if the actual line created doesn't begin at the beg point but on the previous line
                            if act_beg_pt2 != beg_point:
                                expr = QgsExpression('L_id = %s AND P_id= %s' % (line, str(next_id)))
                                req = QgsFeatureRequest(expr)
                                last_line_it = tracks_layer.getFeatures(req)
                                try:
                                    last_line = next(last_line_it)
                                    last_line_it = None
                                    first_point = last_line.geometry().asPolyline()[-1]
                                    pt_geom = QgsGeometry().fromPoint(first_point).buffer(1, 4)
                                    feat_prev_it = tracks_layer.getFeatures(QgsFeatureRequest().setFilterRect(pt_geom.boundingBox()))
                                    rm_ids = []
                                    # Identify the path to correct
                                    for f_poly in feat_prev_it:
                                        if f_poly.attribute("L_id") == str(line) and f_poly.attribute("P_id") != str(next_id):
                                            f_poly_geom = f_poly.geometry().asPolyline()
                                            for i, f_pt in enumerate(f_poly_geom):
                                                if f_pt == first_point:
                                                    rm_ids.append(f_poly.id())
                                                    attr = f_poly.attributes()
                                                    ind = i
                                            new_feat = QgsFeature(tracks_layer.pendingFields())
                                            new_line = f_poly_geom[ind:]
                                            new_geom = QgsGeometry().fromPolyline(new_line)
                                            new_feat.setGeometry(new_geom)
                                            new_feat.setAttributes(attr)
                                            tracks_layer.startEditing()
                                            tracks_layer.dataProvider().addFeatures([new_feat])
                                            tracks_layer.commitChanges()
                                            if f_poly.attribute("P_id") != point_id:
                                                diff = int(next_id) - int(f_poly.attribute('P_id'))
                                                while diff != 1:
                                                    diff = diff -1
                                                    searched_pid = int(f_poly.attribute('P_id')) + diff
                                                    expr = QgsExpression('L_id = %s AND P_id= %s'%(line, str(searched_pid)))
                                                    req = QgsFeatureRequest(expr)
                                                    searched_line_it = None
                                                    searched_line_it = tracks_layer.getFeatures(req)
                                                    try:
                                                        searched_line = next(searched_line_it)
                                                        rm_ids.append(searched_line.id())
                                                    except StopIteration:
                                                        pass
                                        elif f_poly.attribute("L_id") != str(line):
                                            expr = QgsExpression('L_id = %s' % (f_poly.attribute("L_id")))
                                            req = QgsFeatureRequest(expr).setFilterRect(point.geometry().buffer(1, 4).boundingBox())
                                            point_int_it = None
                                            point_int_it = point_layer.getFeatures(req)
                                            point_int = next(point_int_it)
                                            if point_int.attribute("nature") == "end":
                                                if f_poly.attribute("L_id") in line_to_change.keys():
                                                    line_to_change[f_poly.attribute("L_id")].append([line, next_id])
                                                else:
                                                    line_to_change[f_poly.attribute("L_id")] = [[line, next_id]]
                                    tracks_layer.startEditing()
                                    tracks_layer.dataProvider().deleteFeatures(rm_ids)
                                    tracks_layer.commitChanges()
                                except StopIteration:
                                    pass

                            expr = QgsExpression('L_id = %s AND P_id= %s' % (line, str(next_id)))
                            req = QgsFeatureRequest(expr)
                            last_line_it = tracks_layer.getFeatures(req)
                            try:
                                last_line = next(last_line_it)
                                last_geom = last_line.geometry()
                                last_geom_p = last_geom.asPolyline()
                                last_geom_e = [last_geom.asPolyline()[0], last_geom.asPolyline()[-1]]
                                feats_line = tracks_layer.getFeatures(QgsFeatureRequest().setFilterRect(last_geom.boundingBox()))
                                cros = False
                                commun = False
                                list_commun = []
                                list_cross = []
                                # Identify if the created line crosses another line
                                for feat_line in feats_line:
                                    if feat_line.id() != last_line.id():
                                        if feat_line.geometry().crosses(last_geom):
                                            print "oh it crosses"
                                            cros = True
                                            commun = False
                                            geom_cros = feat_line.geometry().asPolyline()
                                            geom_cros_e = [geom_cros[0], geom_cros[-1]]
                                        elif cros == False:
                                            for i, pt in enumerate(last_geom_p[1:-1]):
                                                ft_line_geom = feat_line.geometry().asPolyline()
                                                if pt in ft_line_geom and (i+2) not in list_commun:
                                                    commun = True
                                                    print 'got one'
                                                    geom_cros = feat_line.geometry().asPolyline()
                                                    geom_cros_e = [geom_cros[0], geom_cros[-1]]
                                                    # i+2 => +1 for the enumerate function and +1 for following geom select
                                                    list_commun.append(i+2)
                                                    list_cross.append(geom_cros_e)

                                if cros == True:
                                    attr_last_line = last_line.attributes()
                                    temp_layer = outputFormat(crs, 'tmp_Tracks')
                                    inter_count += 1
                                    temp_path = '%s\\tmp\\tmp%s_layer.shp' % (os.path.dirname(outpath), str(inter_count))
                                    print 'temp_path', temp_path
                                    QgsVectorFileWriter.writeAsVectorFormat(temp_layer, temp_path, "utf-8", None, "ESRI Shapefile")
                                    temp_layer = QgsVectorLayer(temp_path, 'temp_layer', 'ogr')
                                    temp_layer.startEditing()
                                    temp_layer.dataProvider().addFeatures([last_line])
                                    temp_layer.commitChanges()
                                    print "Let's cut"
                                    cut_line = processing.runalg('qgis:splitlineswithlines', temp_layer, tracks_layer, None)
                                    cut_line = QgsVectorLayer(cut_line['OUTPUT'], 'cut', "ogr")
                                    print 'Is it good?'
                                    for lin in cut_line.getFeatures():
                                        geom_lin = lin.geometry().asPolyline()
                                        if geom_lin[0] == last_geom_p[0]:
                                            lin.setAttributes(attr_last_line)
                                            tracks_layer.startEditing()
                                            tracks_layer.dataProvider().addFeatures([lin])
                                            tracks_layer.commitChanges()
                                            print 'OK'
                                    tracks_layer.startEditing()
                                    tracks_layer.deleteFeatures([last_line.id()])
                                    tracks_layer.commitChanges()
                                    temp_layer = None
                                    cut_line = None

                                if commun == True:
                                    attr_last_line = last_line.attributes()
                                    if list_commun[0] == list_commun[-1]:
                                        geom_lin = last_geom_p[0:list_commun[0]]
                                        if geom_lin[0] not in geom_cros_e and geom_lin[-1] not in geom_cros_e and (geom_lin[0] in last_geom_e or geom_lin[-1] in last_geom_e):
                                            lin = QgsFeature(tracks_layer.pendingFields())
                                            lin.setAttributes(attr_last_line)
                                            lin.setGeometry(QgsGeometry().fromPolyline(geom_lin))
                                            tracks_layer.startEditing()
                                            tracks_layer.dataProvider().addFeatures([lin])
                                            tracks_layer.commitChanges()
                                        geom_lin = last_geom_p[list_commun[0]:]
                                        if geom_lin[0] not in geom_cros_e and geom_lin[-1] not in geom_cros_e and (geom_lin[0] in last_geom_e or geom_lin[-1] in last_geom_e):
                                            lin = QgsFeature(tracks_layer.pendingFields())
                                            lin.setAttributes(attr_last_line)
                                            lin.setGeometry(QgsGeometry().fromPolyline(geom_lin))
                                            tracks_layer.startEditing()
                                            tracks_layer.dataProvider().addFeatures([lin])
                                            tracks_layer.commitChanges()
                                    else:
                                        pt_index = min(list_commun)
                                        geom_lin = last_geom_p[0:pt_index]
                                        if geom_lin[0] not in geom_cros_e and geom_lin[-1] not in geom_cros_e and (geom_lin[0] in last_geom_e or geom_lin[-1] in last_geom_e):
                                            lin = QgsFeature(tracks_layer.pendingFields())
                                            lin.setAttributes(attr_last_line)
                                            lin.setGeometry(QgsGeometry().fromPolyline(geom_lin))
                                            tracks_layer.startEditing()
                                            tracks_layer.dataProvider().addFeatures([lin])
                                            tracks_layer.commitChanges()
                                        tracks_layer.startEditing()
                                        tracks_layer.deleteFeatures([last_line.id()])
                                        tracks_layer.commitChanges()
                                        # for i, pt_index in enumerate(list_commun):
                                        #     elif i == 0:
                                        #         geom_lin = last_geom_p[0:pt_index]
                                        #         if geom_lin[0] not in geom_cros_e and geom_lin[-1] not in geom_cros_e and (geom_lin[0] in last_geom_e or geom_lin[-1] in last_geom_e):
                                        #             lin = QgsFeature(tracks_layer.pendingFields())
                                        #             lin.setAttributes(attr_last_line)
                                        #             lin.setGeometry(QgsGeometry().fromPolyline(geom_lin))
                                        #             tracks_layer.startEditing()
                                        #             tracks_layer.dataProvider().addFeatures([lin])
                                        #             tracks_layer.commitChanges()
                                        #     elif i == len(list_commun)-1:
                                        #         geom_lin = last_geom_p[list_commun[i-1]:pt_index]
                                        #         if geom_lin[0] not in geom_cros_e and geom_lin[-1] not in geom_cros_e and (geom_lin[0] in last_geom_e or geom_lin[-1] in last_geom_e):
                                        #             lin = QgsFeature(tracks_layer.pendingFields())
                                        #             lin.setAttributes(attr_last_line)
                                        #             lin.setGeometry(QgsGeometry().fromPolyline(geom_lin))
                                        #             tracks_layer.startEditing()
                                        #             tracks_layer.dataProvider().addFeatures([lin])
                                        #             tracks_layer.commitChanges()
                                        #         geom_lin = last_geom_p[pt_index:-1]
                                        #         if geom_lin[0] not in geom_cros_e and geom_lin[-1] not in geom_cros_e and (geom_lin[0] in last_geom_e or geom_lin[-1] in last_geom_e):
                                        #             lin = QgsFeature(tracks_layer.pendingFields())
                                        #             lin.setAttributes(attr_last_line)
                                        #             lin.setGeometry(QgsGeometry().fromPolyline(geom_lin))
                                        #             tracks_layer.startEditing()
                                        #             tracks_layer.dataProvider().addFeatures([lin])
                                        #             tracks_layer.commitChanges()
                                        #     else:
                                        #         geom_lin = last_geom_p[list_commun[i-1]:pt_index]
                                        #         if geom_lin[0] not in geom_cros_e and geom_lin[-1] not in geom_cros_e and (geom_lin[0] in last_geom_e or geom_lin[-1] in last_geom_e):
                                        #             lin = QgsFeature(tracks_layer.pendingFields())
                                        #             lin.setAttributes(attr_last_line)
                                        #             lin.setGeometry(QgsGeometry().fromPolyline(geom_lin))
                                        #             tracks_layer.startEditing()
                                        #             tracks_layer.dataProvider().addFeatures([lin])
                                        #             tracks_layer.commitChanges()
                                        #     tracks_layer.startEditing()
                                        #     tracks_layer.deleteFeatures([last_line.id()])
                                        #     tracks_layer.commitChanges()
                                    temp_layer = None
                                    cut_line = None
                            except StopIteration:
                                pass
    rm_ids = []
    print 'line_to_change:', line_to_change
    # Execute the changes
    for k in line_to_change.keys():
        expr = QgsExpression("L_id = %s AND nature = 'end'"%(k))
        req = QgsFeatureRequest(expr)
        point_feat_it = point_layer.getFeatures(req)
        point_feat = next(point_feat_it)
        rect_geom = point_feat.geometry().buffer(1, 4).boundingBox()
        expr = QgsExpression("L_id != %s"%(k))
        req = QgsFeatureRequest(expr).setFilterRect(rect_geom)
        line_feat_it = tracks_layer.getFeatures(req)
        line_feat = None
        try:
            line_feat = next(line_feat_it)
            line_feat_it = None
        except StopIteration:
            pass
        if line_feat == None:
            int_pts = []
            for int_line in line_to_change[k]:
                expr = QgsExpression('L_id = %s AND P_id= %s'%(int_line[0], int_line[1]))
                req = QgsFeatureRequest(expr)
                line_it = tracks_layer.getFeatures(req)
                try:
                    line = next(line_it)
                    line_it = None
                    int_pts.append(line.geometry().asPolyline()[-1])
                except StopIteration:
                    pass
            expr = QgsExpression('L_id = %s'%(k))
            req = QgsFeatureRequest(expr)
            line_it = tracks_layer.getFeatures(req)
            attr = None
            for f_poly in line_it:
                f_poly_geom = f_poly.geometry().asPolyline()
                for i, f_pt in enumerate(f_poly_geom):
                    if f_pt in int_pts:
                        if attr == None or (int(f_poly.attribute("P_id"))) > int(rm_p_id):
                            attr = f_poly.attributes()
                            rm_id = f_poly.id()
                            rm_p_id = f_poly.attribute("P_id")
                            ind = i
            rm_ids.append(rm_id)
            expr = QgsExpression('L_id = %s AND P_id= %s' % (k, rm_p_id))
            req = QgsFeatureRequest(expr)
            rm_ft_it = None
            rm_ft_it = tracks_layer.getFeatures(req)
            try:
                rm_ft = next(rm_ft_it)
                rm_ft_geom = rm_ft.geometry().asPolyline()
                new_feat = QgsFeature(tracks_layer.pendingFields())
                new_line = rm_ft_geom[ind:]
                new_geom = QgsGeometry().fromPolyline(new_line)
                new_feat.setGeometry(new_geom)
                new_feat.setAttributes(attr)
                tracks_layer.startEditing()
                tracks_layer.dataProvider().addFeatures([new_feat])
                tracks_layer.commitChanges()
            except StopIteration:
                pass
    tracks_layer.startEditing()
    print rm_ids
    tracks_layer.dataProvider().deleteFeatures(rm_ids)
    tracks_layer.commitChanges()


def pointChecked(point_layer):
    """Check the fields of the point layer"""
    pr = point_layer.dataProvider()

    L_index = pr.fieldNameIndex('L_id')
    P_index = pr.fieldNameIndex('P_id')

    if L_index == -1 or P_index == -1:
        point_format = False
    else:
        point_format = True

    return point_format


def outputFormat(crs, name='Tracks'):
    """Create the output file"""
    tracks_layer = QgsVectorLayer('Linestring?crs=' + crs, name, 'memory')
    name_L_id = "L_id"
    name_P_id = "P_id"
    name_nature = "nature"
    name_cost = "cost"
    provider = tracks_layer.dataProvider()
    caps = provider.capabilities()
    if caps & QgsVectorDataProvider.AddAttributes:
        res = provider.addAttributes([QgsField(name_L_id, QVariant.String),
                                      QgsField(name_P_id, QVariant.String),
                                      QgsField(name_nature, QVariant.String),
                                      QgsField(name_cost, QVariant.Double, "double", 5, 1)])
        tracks_layer.updateFields()

    return tracks_layer


def launchAutomatracks(point_layer, DEM_layer, outpath, nb_edges, method, threshold, max_slope, Mask_layer):
    """Main function to process lcp for the network"""

    time = Timer()
    time.start()

    outdir = os.path.dirname(outpath)
    if not os.path.exists(outdir):
        try:
            os.mkdir(outdir)
        except:
            print 'Error while creating %s' % outdir
    outsubdir = os.path.join(outdir, u'tmp')
    if not os.path.exists(outsubdir):
        try:
            os.mkdir(outsubdir)
        except:
            print 'Error while creating %s' % outsubdir

    if os.access(outdir, os.W_OK):
        crs = point_layer.crs().toWkt()
        tracks_layer = outputFormat(crs)

        error = QgsVectorFileWriter.writeAsVectorFormat(tracks_layer, outpath, "utf-8", None, "ESRI Shapefile")
        if error == QgsVectorFileWriter.NoError:
            print "Created output file"
        tracks_layer = QgsVectorLayer(outpath, 'tracks_layer', "ogr")
        point_format = pointChecked(point_layer)
        if point_format:
            advanced_algo(point_layer, DEM_layer, tracks_layer, outpath, int(nb_edges), method, int(threshold), int(max_slope), Mask_layer)
        time.stop()
        print 'processing Time:'
        time.show()
    else:
        print 'Error: could not write to %s' % outdir
