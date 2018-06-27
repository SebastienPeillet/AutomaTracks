# -*- coding: utf-8 -*-
"""
/***************************************************************************
 reOrderDock
                                Dock for reOrder script
 Option dock initialize
                             -------------------
        begin                : 2018-04-16
        last                 : 2017-04-16
        copyright            : (C) 2017 by Peillet Sebastien
        email                : peillet.seb@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os

from PyQt4.QtGui import QColor
from PyQt4 import QtGui, uic
from PyQt4.QtCore import pyqtSignal, QVariant, Qt
from PyQt4 import QtCore
from qgis.core import QgsVectorLayer, QgsVectorFileWriter,QgsVectorDataProvider, QgsField, \
                        QgsExpression, QgsFeatureRequest, QgsRasterPipe, QgsRasterFileWriter, \
                        QgsRectangle, QgsRasterLayer, QgsFeature, QgsPoint, QgsGeometry, QgsRaster, \
                        QgsCoordinateReferenceSystem
import math
import os
from datetime import datetime

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ridgeToPointDock.ui'))

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

class ridgeToPointDock(QtGui.QDockWidget, FORM_CLASS):
    """Convert ridge line to point"""
    closingPlugin = pyqtSignal()

    def __init__(self, iface, list_vect, list_vect_ind, list_rast, list_rast_ind, parent=None):
        """Constructor."""
        super(ridgeToPointDock, self).__init__(parent)
        self.setupUi(self)
        self.lines_layer = None
        self.dem_layer = None
        self.output_path = None
        self.id_line = None
        self.min_dist = None
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.list_vect = list_vect
        self.list_vect_ind = list_vect_ind
        self.list_rast = list_rast
        self.list_rast_ind = list_rast_ind
        self.initCombo()
        self.launchButton.clicked.connect(self.launchR2P)
        self.connect(self.lineComboBox, QtCore.SIGNAL("currentIndexChanged(const QString)"),self.idComboInit)
        self.canvas.layersChanged.connect(self.layersUpdate)
        self.connect(self, QtCore.SIGNAL('triggered()'), self.closeEvent)

    def closeEvent(self, event):
        print "Closing"
        self.close()

    def initCombo(self):
        """Fill layer combo box of the dock"""
        layers = self.iface.legendInterface().layers()
        self.lineComboBox.addItems(self.list_vect)
        selected_line = self.lineComboBox.currentIndex()
        self.lines_layer = layers[self.list_vect_ind[selected_line]]
        self.idComboInit()
        self.DEMComboBox.addItems(self.list_rast)

    def idComboInit(self):
        """Fill field combo box"""
        layers = self.iface.legendInterface().layers()
        self.idLineComboBox.clear()
        selected_line = self.lineComboBox.currentIndex()
        self.lines_layer = layers[self.list_vect_ind[selected_line]]
        attr_ind = self.lines_layer.attributeList()
        attr_list = []
        for ind in attr_ind :
            attr_list.append(self.lines_layer.attributeDisplayName(ind))
        self.idLineComboBox.addItems(attr_list)

    def layersUpdate(self):
        track_text = self.lineComboBox.currentText()
        dem_text = self.DEMComboBox.currentText()
        self.listRastLayer()
        self.listVectLayer()
        track_ind = self.lineComboBox.findText(track_text)
        dem_ind = self.DEMComboBox.findText(dem_text)
        if track_ind != -1 :
            self.lineComboBox.setCurrentIndex(track_ind)
        if dem_ind != -1 :
            self.DEMComboBox.setCurrentIndex(dem_ind)
        layers = self.iface.legendInterface().layers()
        selected_line = self.lineComboBox.currentIndex()
        self.lines_layer = layers[self.list_vect_ind[selected_line]]
        self.idComboInit()
        return None

    def listRastLayer(self):
        """List raster inputs for the DEM selection"""

        # clear list and index
        self.DEMComboBox.clear()
        self.DEMComboBox.clearEditText()
        self.list_rast = []
        self.list_rast_ind = []
        layers = self.iface.legendInterface().layers()
        layer_list = []
        index = 0
        for layer in layers:
            if layer.type() == 1:
                self.list_rast.append(layer.name())
                self.list_rast_ind.append(index)
            index += 1
        self.DEMComboBox.addItems(self.list_rast)

    def listVectLayer(self):
        """List line layer for the track selection"""

        # clear list and index
        self.lineComboBox.clear()
        self.lineComboBox.clearEditText()
        self.list_vect = []
        self.list_vect_ind = []
        layers = self.iface.legendInterface().layers()
        layer_list = []
        index = 0
        for layer in layers:
            if layer.type() == 0:
                if layer.geometryType() == 1:
                    self.list_vect.append(layer.name())
                    self.list_vect_ind.append(index)
            index += 1
        self.lineComboBox.addItems(self.list_vect)

    def launchR2P(self):
        """Launch the conversion"""
        layers = self.iface.legendInterface().layers()
        # Get index of combo box
        selected_line = self.lineComboBox.currentIndex()
        selected_dem_layer = self.DEMComboBox.currentIndex()
        # Get layer that fit with the combo box index
        self.lines_layer = layers[self.list_vect_ind[selected_line]]
        self.dem_layer = layers[self.list_rast_ind[selected_dem_layer]]
        self.min_dist = self.minLengthBox.value()
        self.id_line = self.idLineComboBox.currentText()
        self.output_path = self.outputEdit.text()
        l_done = []
        time=Timer()
        time.start()
        tmp_path = os.path.dirname(self.lines_layer.source())
        # Extract all points of interest (start of line, end of line, peak, pass) from polyline layer
        pointPassage,crs,self.dem_layer= passPointSeek(self.lines_layer,self.id_line,self.dem_layer, tmp_path)
        QgsVectorFileWriter.writeAsVectorFormat(pointPassage, os.path.dirname(self.output_path)+'\\temp.shp', "utf-8", crs, "ESRI Shapefile")
        pointPassage = None
        pointPassage = QgsVectorLayer(os.path.dirname(self.output_path)+'\\temp.shp','pointpassage',"ogr")

        # print 'Remove small ridge part'
        ids_rem = []
        orphans = []
        for pt in pointPassage.getFeatures():
            pt_id = pt.id()
            pt_geom = pt.geometry().asPoint()
            pt_x,pt_y = pt_geom
            bounding_box_buff = QgsRectangle(pt_x - self.min_dist, pt_y - self.min_dist, pt_x + self.min_dist, pt_y + self.min_dist) 
            pts_near_it = pointPassage.getFeatures(QgsFeatureRequest().setFilterRect(bounding_box_buff))
            for pt_near in pts_near_it :
                pt_near_id = pt_near.id()
                if pt_near_id != pt_id :
                    dist = math.sqrt(pt_geom.sqrDist(pt_near.geometry().asPoint()))
                    if dist != 0 and dist < self.min_dist :
                        pt_Tid = pt.attribute('T_id')
                        res = pt_Tid.split('p')
                        l_id1 = res[0]
                        pt_near_Tid = pt_near.attribute('T_id')
                        res = pt_near_Tid.split('p')
                        l_id2 = res[0]
                        if l_id1 == l_id2 and ((pt_Tid[-1] == 's' and pt_near_Tid[-1]== 'e') or (pt_Tid[-1] == 'e' and pt_near_Tid[-1]== 's')) :
                            if pt_id not in ids_rem :
                                ids_rem.append(pt_id)
                            if pt_near_id not in ids_rem :
                                ids_rem.append(pt_near_id)
                            # if pt_Tid in orphans :
                                # orphans.remove(pt_Tid)
                            # if pt_near_Tid in orphans :
                                # orphans.remove(pt_near_Tid)
                            BB1 = pt.geometry().buffer(3,4).boundingBox()
                            BB2 = pt_near.geometry().buffer(3,4).boundingBox()
                            for feat1 in pointPassage.getFeatures(QgsFeatureRequest(QgsExpression("nature='start' or nature='end'")).setFilterRect(BB1)):
                                tid1 = feat1.attribute("T_id")
                                if feat1.id() not in ids_rem and tid1 not in orphans :
                                    orphans.append(tid1)
                            for feat2 in pointPassage.getFeatures(QgsFeatureRequest(QgsExpression("nature='start' or nature='end'")).setFilterRect(BB2)):
                                tid2 = feat2.attribute("T_id")
                                if feat2.id() not in ids_rem and tid2 not in orphans:
                                    orphans.append(tid2)

        pointPassage.startEditing()
        pointPassage.dataProvider().deleteFeatures(ids_rem)
        pointPassage.commitChanges()

        #Find link point between seperate line
        # print 'Find link point between seperate line'
        already_done = []
        geom_to_change = []
        for pt in pointPassage.getFeatures():
            if pt.attribute('T_id') in orphans :
                pt_id = pt.id()
                pt_nat = pt.attribute('nature')
                if pt_nat == 'end' :
                    pt_nat_opp = 'start'
                else :
                    pt_nat_opp = 'end'
                pt_opp_it = None
                pt_opp_it = pointPassage.getFeatures(QgsFeatureRequest(QgsExpression("L_id = '%s' and nature='%s'"%(pt.attribute('L_id'),pt_nat_opp))))
                pt_opp = next(pt_opp_it)
                pt_opp_geom = pt_opp.geometry().asPoint()
                pt_opp_buff = pt_opp.geometry().buffer(1,4).boundingBox()
                pt_opp_near_it = pointPassage.getFeatures(QgsFeatureRequest(QgsExpression("L_id != '%s'"%(pt_opp.attribute('L_id')))))
                list_opp = [pt_opp_near.attribute('T_id') for pt_opp_near in pt_opp_near_it]
                list_opp.append(pt_opp.attribute('T_id'))
                pt_geom = pt.geometry().asPoint()
                pt_x,pt_y = pt_geom
                bounding_box_buff = QgsRectangle(pt_x - self.min_dist*2, pt_y - self.min_dist*2, pt_x + self.min_dist*2, pt_y + self.min_dist*2)
                pts_near_it = pointPassage.getFeatures(QgsFeatureRequest().setFilterRect(bounding_box_buff))
                list_id=[]
                w0 = 0
                id0 = pt_id
                act_dist = None
                list_line=[]
                for pt_near in pts_near_it :
                    pt_near_id = pt_near.id()
                    pt_near_Tid = pt_near.attribute('T_id')
                    pt_near_geom = pt_near.geometry().asPoint()
                    if pt_near_id != pt_id and pt_near_Tid in orphans and pt_near_geom != pt_opp_geom:
                        dist = math.sqrt(pt_geom.sqrDist(pt_near_geom))
                        if dist != 0 and dist < self.min_dist*2 :
                            pt_Tid = pt.attribute('T_id')
                            res = pt_Tid.split('p')
                            l_id1 = res[0]
                            res = pt_near_Tid.split('p')
                            l_id2 = res[0]
                            if pt_id not in already_done and l_id1 != l_id2 and l_id2 not in list_line and pt_Tid[-1] in ['s','e'] and pt_near_Tid[-1] in ['s','e']:
                                list_id.append(pt_near_id)
                                list_line.append(l_id2)
                                w0+= dist
                already_done.append(pt_id)
                for id in list_id :
                    point1 = next(pointPassage.getFeatures(QgsFeatureRequest().setFilterFid(id)))
                    point1_geom = point1.geometry().asPoint()
                    pt1_x,pt1_y = point1_geom
                    bounding_box_buff1 = QgsRectangle(pt_x - self.min_dist*2, pt_y - self.min_dist*2, pt_x + self.min_dist*2, pt_y + self.min_dist*2)
                    pts1_near_it = pointPassage.getFeatures(QgsFeatureRequest().setFilterRect(bounding_box_buff1))
                    w=0
                    for opoint in pts1_near_it :
                        if id != opoint.id() and opoint.attribute('T_id') in orphans:
                            opoint_geom = opoint.geometry().asPoint()
                            p = math.sqrt(point1_geom.sqrDist(opoint_geom))
                            w += p
                    if w < w0 :
                        w0 = w
                        id0 = opoint.id()
                    already_done.append(id)
                list_id.append(pt_id)
                try :
                    list_id.remove(id0)
                except ValueError:
                    continue
                change=[id0,list_id]
                geom_to_change.append(change)

        for change in geom_to_change :
            id_fix = change[0]
            req = QgsFeatureRequest().setFilterFid(id_fix)
            point_fix_it = pointPassage.getFeatures(req)
            try :
                for point_fix in point_fix_it :
                    geom_fix = point_fix.geometry()
                    # try :
                        # orphans.remove(point_fix.attribute("T_id"))
                    # except ValueError :
                        # continue
                ids_change = change[1]
                for id_change in ids_change :
                    req = QgsFeatureRequest().setFilterFid(id_change)
                    point_change_it = pointPassage.getFeatures(req)
                    point_change = next(point_change_it)
                    # try :
                        # orphans.remove(point_change.attribute("T_id"))
                    # except ValueError :
                        # continue
                    pointPassage.startEditing()
                    pointPassage.dataProvider().changeGeometryValues({id_change : geom_fix})
                    pointPassage.commitChanges()
                    pointPassage.updateExtents()
            except StopIteration:
                pass

        # print 'Find link point between seperate line'
        already_done = []
        geom_to_change = []
        for pt in pointPassage.getFeatures():
            pt_id = pt.id()
            pt_geom = pt.geometry().asPoint()
            pt_x,pt_y = pt_geom
            bounding_box_buff = QgsRectangle(pt_x - self.min_dist, pt_y - self.min_dist, pt_x + self.min_dist, pt_y + self.min_dist)
            pts_near_it = pointPassage.getFeatures(QgsFeatureRequest().setFilterRect(bounding_box_buff))
            list_id=[]
            w0 = 0
            id0 = pt_id
            for pt_near in pts_near_it :
                pt_near_id = pt_near.id()
                pt_near_Tid = pt_near.attribute('T_id')
                if pt_near_id != pt_id :
                    dist = math.sqrt(pt_geom.sqrDist(pt_near.geometry().asPoint()))
                    if dist != 0 and dist < self.min_dist :
                        pt_Tid = pt.attribute('T_id')
                        res = pt_Tid.split('p')
                        l_id1 = res[0]
                        res = pt_near_Tid.split('p')
                        l_id2 = res[0]
                        if pt_id not in already_done and l_id1 != l_id2 and pt_Tid[-1] in ['s','e'] and pt_near_Tid[-1] in ['s','e']:
                            list_id.append(pt_near_id)
                            w0+= dist
            already_done.append(pt_id)
            for id in list_id :
                point1 = next(pointPassage.getFeatures(QgsFeatureRequest().setFilterFid(id)))
                point1_geom = point1.geometry().asPoint()
                pt1_x,pt1_y = point1_geom
                bounding_box_buff1 = QgsRectangle(pt_x - self.min_dist, pt_y - self.min_dist, pt_x + self.min_dist, pt_y + self.min_dist)
                pts1_near_it = pointPassage.getFeatures(QgsFeatureRequest().setFilterRect(bounding_box_buff1))
                w=0
                for opoint in pts1_near_it :
                    if id != opoint.id() :
                        opoint_geom = opoint.geometry().asPoint()
                        p = math.sqrt(point1_geom.sqrDist(opoint_geom))
                        w += p
                if w < w0 :
                    w0 = w
                    id0 = opoint.id()
                already_done.append(id)
            list_id.append(pt_id)
            try :
                list_id.remove(id0)
            except ValueError:
                continue
            change=[id0,list_id]
            geom_to_change.append(change)

        for change in geom_to_change :
            id_fix = change[0]
            req = QgsFeatureRequest().setFilterFid(id_fix)
            point_fix_it = pointPassage.getFeatures(req)
            try :
                for point_fix in point_fix_it :
                    geom_fix = point_fix.geometry()
                ids_change = change[1]
                for id_change in ids_change :
                    pointPassage.startEditing()
                    pointPassage.dataProvider().changeGeometryValues({id_change : geom_fix})
                    pointPassage.commitChanges()
                    pointPassage.updateExtents()
            except StopIteration:
                pass

        #Remove small ridge part at the end/start of a line
        # print 'Remove small ridge part at the end/start of a line'
        geom_to_change = []
        list_id=[]
        for pt in pointPassage.getFeatures():
            pt_id = pt.id()
            pt_geom = pt.geometry().asPoint()
            pt_x,pt_y = pt_geom
            bounding_box_buff = QgsRectangle(pt_x - self.min_dist, pt_y - self.min_dist, pt_x + self.min_dist, pt_y + self.min_dist) 
            pts_near_it = pointPassage.getFeatures(QgsFeatureRequest().setFilterRect(bounding_box_buff))
            for pt_near in pts_near_it :
                pt_near_id = pt_near.id()
                if pt_near_id != pt_id :
                    dist = math.sqrt(pt_geom.sqrDist(pt_near.geometry().asPoint()))
                    if dist != 0 and dist < self.min_dist :
                        pt_Tid = pt.attribute('T_id')
                        res = pt_Tid.split('p')
                        l_id1 = res[0]
                        pt_near_Tid = pt_near.attribute('T_id')
                        res = pt_near_Tid.split('p')
                        l_id2 = res[0]
                        if l_id1 == l_id2 and pt_Tid[-1] in ['s','e'] and pt_near_Tid[-1] not in ['s','e'] and pt_near_Tid not in list_id:
                            change = [pt_id,pt_near_id]
                            list_id.append(pt_near_Tid)
                            geom_to_change.append(change)
        id_rm = []
        # print geom_to_change

        for change in geom_to_change :
            id_fix = change[0]
            req = QgsFeatureRequest().setFilterFid(id_fix)
            point_fix_it = pointPassage.getFeatures(req)
            point_fix = next(point_fix_it)
            try :
                id_change = change[1]
                req = QgsFeatureRequest().setFilterFid(id_change)
                point_ch_it = pointPassage.getFeatures(req)
                for point_ch in point_ch_it :                
                    if point_fix.attribute('T_id')[-1] == 'e' :
                        if int(point_ch.attribute('P_id')) < int(point_fix.attribute('P_id')) :
                            pointPassage.startEditing()
                            pointPassage.changeAttributeValue(id_fix,2,point_ch.attribute('P_id'))
                            pointPassage.commitChanges()
                    else :
                        pointPassage.startEditing()
                        pointPassage.changeAttributeValue(id_fix,2,point_ch.attribute('P_id'))
                        pointPassage.commitChanges()
                id_rm.append(id_change)
            except StopIteration:
                pass
        pointPassage.startEditing()
        pointPassage.deleteFeatures(id_rm)
        pointPassage.commitChanges()
        pointPassage.updateExtents()

        #First attempt
        # print "First attempt"
        already_done = []
        geom_to_change = []
        for pt in pointPassage.getFeatures():
            pt_id = pt.id()
            pt_geom = pt.geometry().asPoint()
            pt_x,pt_y = pt_geom
            bounding_box_buff = QgsRectangle(pt_x - self.min_dist, pt_y - self.min_dist, pt_x + self.min_dist, pt_y + self.min_dist) 
            pts_near_it = pointPassage.getFeatures(QgsFeatureRequest().setFilterRect(bounding_box_buff))
            list_id=[]
            w0 = 0
            id0 = pt_id
            for pt_near in pts_near_it :
                pt_near_id = pt_near.id()
                if pt_near_id != pt_id :
                    dist = math.sqrt(pt_geom.sqrDist(pt_near.geometry().asPoint()))
                    if dist != 0 and dist < self.min_dist :
                        pt_Tid = pt.attribute('T_id')
                        res = pt_Tid.split('p')
                        l_id1 = res[0]
                        pt_near_Tid = pt_near.attribute('T_id')
                        res = pt_near_Tid.split('p')
                        l_id2 = res[0]
                        if pt_id not in already_done and pt_near_id not in already_done and l_id1 == l_id2 :
                            pt1_elev = self.dem_layer.dataProvider().identify(pt_geom,QgsRaster.IdentifyFormatValue)
                            pt2_elev = self.dem_layer.dataProvider().identify(pt_near.geometry().asPoint(),QgsRaster.IdentifyFormatValue)
                            already_done.append(pt_id)
                            already_done.append(pt_near_id)
                            if pt1_elev < pt2_elev :
                                change = pt_Tid
                            else :
                                change = pt_near_Tid
                            geom_to_change.append(change)
        # print geom_to_change
        for change in geom_to_change :
            # print 'change : ',change
            id_fix = change
            req = QgsFeatureRequest().setFilterExpression("T_id = '%s'"%(id_fix))
            point_rm_it = pointPassage.getFeatures(req)
            point_rm = point_rm_it.next()
            id_rm = point_rm.id()
            line_id = point_rm.attribute('L_id')
            point_pid = int(point_rm.attribute('P_id'))
            nat = point_rm.attribute('nature')
            fin = 0
            count = 1
            found =False
            if nat == 'end' :
                fin = 1
            else :
                pointPassage.startEditing()
                while True:
                    if found == True :
                        point_pid+=1
                    req = QgsFeatureRequest().setFilterExpression("L_id ='%s' and P_id = '%s'"%(line_id,str(point_pid+count)))
                    point_nxt_it = pointPassage.getFeatures(req)
                    found =False
                    point_nxt= None
                    try:
                        point_nxt = next(point_nxt_it)
                    except StopIteration:
                        point_nxt = None
                        continue
                    if point_nxt != None :
                        pointPassage.changeAttributeValue(point_nxt.id(),2,str(point_pid))
                        current_id = point_nxt.attribute('T_id')
                        if current_id[-1] == 'e' :
                            break
                        #print current_id
                        found = True
                        count = 1
                    else :
                        count+=1
                        found = False
                pointPassage.deleteFeatures([id_rm])
                pointPassage.commitChanges()
        pointPassage.updateExtents()


        time.stop()
        print 'processing Time :'
        time.show()
        error = QgsVectorFileWriter.writeAsVectorFormat(pointPassage, self.output_path, "utf-8", crs, "ESRI Shapefile") 
        if error == QgsVectorFileWriter.NoError:
            print "success!"
        out_layer = self.iface.addVectorLayer(self.output_path, "", "ogr")
        if not out_layer:
            print "Layer failed to load!"

            
def passPointSeek(crete_layer,ID_crete,dem_layer, PassagePoint):
    #Load ridge line layer
    inCRS = crete_layer.crs().authid()
    crs = QgsCoordinateReferenceSystem(inCRS)

    #Load dem_layer layer
    x_res = dem_layer.rasterUnitsPerPixelX()
    y_res = dem_layer.rasterUnitsPerPixelY()
        
    #Create memory layer for the result :
    pointPassage=QgsVectorLayer("Point","point",'memory')
    pointPassage.setCrs(crs)
    name_T_id = "T_id"
    name_L_id = "L_id"
    name_P_id = "P_id"
    name_nat = "nature"
    provider = pointPassage.dataProvider()
    caps = provider.capabilities()
    if caps & QgsVectorDataProvider.AddAttributes:
        res = provider.addAttributes( [ QgsField(name_T_id, QVariant.String), QgsField(name_L_id, QVariant.String), QgsField(name_P_id, QVariant.String), QgsField(name_nat, QVariant.String)] )
        pointPassage.updateFields()

    pointPassage.startEditing()


    #Loop over the features
    for feature in crete_layer.getFeatures() :
        feat_L_id = feature.attribute(ID_crete)
        geomType = feature.geometry().wkbType()
        if geomType == 2 :
            geom = feature.geometry().asPolyline()
            nb = len(geom)
            geom_clean = feature.geometry().asPolyline()
            ind=0
            for i in range(0,nb-1) :
                pt1 = geom[i]
                x1 = pt1.x()
                if x1 %10 == 2:
                    x1+=0.5
                elif x1 %10 ==8 :
                    x1+=-0.5
                y1 = pt1.y()
                if y1 %10 == 2:
                    y1+=0.5
                elif y1 %10 ==8 :
                    y1+=-0.5
                pt2 = geom[i+1]
                x2 = pt2.x()
                if x2 %10 == 2:
                    x2+=0.5
                elif x2 %10 ==8 :
                    x2+=-0.5
                y2 = pt2.y()
                if y2 %10 == 2:
                    y2+=0.5
                elif y2 %10 == 8 :
                    y2+=-0.5
                pt1 = QgsPoint(x1,y1)
                pt2 = QgsPoint(x2,y2)
                dist = math.sqrt(pt1.sqrDist(pt2))
                if dist > math.sqrt(x_res*x_res+y_res*y_res)+1 :
                    azimuth = pt1.azimuth(pt2)
                    if azimuth % 10 != 0 :
                        decoup_dist = math.sqrt(x_res*x_res+y_res*y_res)
                    else :
                        decoup_dist = x_res

                    tot_distance=0
                    pts=[]
                    while tot_distance/x_res < dist/x_res :
                        tot_distance+=decoup_dist
                        xv = round(tot_distance*math.sin(math.radians(azimuth)))
                        yv = round(tot_distance*math.cos(math.radians(azimuth)))
                        # print xv,yv, tot_distance,azimuth, x1,y1,x2,y2
                        pt = QgsPoint(pt1.x()+xv,pt1.y()+yv)
                        pts.append(pt)
                    pt1_elev = dem_layer.dataProvider().identify(pt1,QgsRaster.IdentifyFormatValue)
                    pt2_elev = dem_layer.dataProvider().identify(pt2,QgsRaster.IdentifyFormatValue)
                    min_elev = min(pt1_elev,pt2_elev)
                    max_elev = max(pt1_elev,pt2_elev)
                    points_elev=[]
                    min_list = None
                    max_list = None
                    max_id = None
                    min_id = None
                    for j,point in enumerate(pts) :
                        elev = dem_layer.dataProvider().identify(point,QgsRaster.IdentifyFormatValue)
                        if elev < min_elev :
                            if min_list == None or elev < min_list :
                                min_list = elev
                                min_id = j
                        if elev  > max_elev :
                            if max_list == None or elev < max_list :
                                max_list = elev
                                max_id = j
                    if max_id != None and min_id != None :
                        if max_id < min_id :
                            geom_clean.insert(i+1+ind,pts[max_id])
                            geom_clean.insert(i+2+ind,pts[min_id])
                            ind+=2
                        else :
                            geom_clean.insert(i+2+ind,pts[min_id])
                            geom_clean.insert(i+1+ind,pts[max_id])
                            ind+=2
                    elif max_id != None and min_id == None:
                        geom_clean.insert(i+1+ind,pts[max_id])
                        ind+=1
                    elif min_id != None and max_id == None:
                        geom_clean.insert(i+1+ind,pts[min_id])
                        ind+=1
            nb = len(geom_clean)
            elev_list = []
            for point in geom_clean :
                elev = dem_layer.dataProvider().identify(point,QgsRaster.IdentifyFormatValue)
                elev_list.append(elev.results()[1])
            count = 0
            for i in range(0,nb) :
                feat_point= QgsFeature()
                try :
                    if i == 0 :
                        feat_point.setGeometry(QgsGeometry.fromPoint(geom[0]))
                        nat='s'
                        t_id = 'l'+str(feat_L_id)+'p'+str(count)+nat
                        feat_point.setAttributes([t_id,feat_L_id,count,'start'])
                        count+=1
                        pointPassage.dataProvider().addFeatures([feat_point])
                    elif i == nb-1 :
                        feat_point.setGeometry(QgsGeometry.fromPoint(geom[-1]))
                        nat='e'
                        t_id = 'l'+str(feat_L_id)+'p'+str(count)+nat
                        feat_point.setAttributes([t_id,feat_L_id,count,'end'])
                        count+=1
                        pointPassage.dataProvider().addFeatures([feat_point])
                    elif i < 3 :
                        pass
                    elif i > nb-3 :
                        pass
                    else :
                        feat_point.setGeometry(QgsGeometry.fromPoint(geom_clean[i]))
                        min_elev1 = min(elev_list[i-3],elev_list[i-2],elev_list[i-1])
                        min_elev2 = min(elev_list[i+3],elev_list[i+2],elev_list[i+1])
                        max_elev1 = max(elev_list[i-3],elev_list[i-2],elev_list[i-1])
                        max_elev2 = max(elev_list[i+3],elev_list[i+2],elev_list[i+1])
                        if elev_list[i]< min_elev1 and elev_list[i]<= min_elev2 :
                            nat='d'
                            t_id = 'l'+str(feat_L_id)+'p'+str(count)+nat
                            feat_point.setAttributes([t_id,feat_L_id,count,'col'])
                            count+=1
                            pointPassage.dataProvider().addFeatures([feat_point])
                        if elev_list[i] >= max_elev1 and elev_list[i]> max_elev2 :
                            nat='t'
                            t_id = 'l'+str(feat_L_id)+'p'+str(count)+nat
                            feat_point.setAttributes([t_id,feat_L_id,count,'pic'])
                            count+=1
                            pointPassage.dataProvider().addFeatures([feat_point])
                    pointPassage.commitChanges()
                    pointPassage.updateExtents()
                except :
                    pass
        else :
            print 'no multiline'
    return pointPassage,crs,dem_layer
