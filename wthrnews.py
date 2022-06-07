#!/usr/bin/python
# -*- coding: utf-8 -*-

import getopt
import json
import locale
import os
import platform
import signal
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import xml.etree.ElementTree as ET

import bkgutils
import qtutils
import utils
import webutils
import pywinctl as pwc
from PyQt5 import QtWidgets, QtCore, QtGui

import settings
import wconfig
import wconstants
import wutils
import zoneinfo
from wthrnews_ui import Ui_MainWindow


class Window(QtWidgets.QMainWindow, Ui_MainWindow):

    def __init__(self, *args, **kwargs):
        QtWidgets.QMainWindow.__init__(self, *args, **kwargs)

        self.archOS = platform.platform()
        print("System Architecture Family:", self.archOS)
        self.interpreter = str(sys.version_info[0]) + "." + str(sys.version_info[1]) + "." + str(sys.version_info[2])
        print("Python interpreter version:", self.interpreter)

        # Set system locale according to the language selected on settings. If not possible, it will fallback to default
        # Use 'sudo dpkg-reconfigure locales' to install/set locales (or system preferences on non-Linux OS)
        try:
            self.cLocale = locale.setlocale(locale.LC_ALL, settings.locale)
            print("Current locale:", self.cLocale, "/ Default system locale:", locale.getdefaultlocale())
        except:
            try:
                self.cLocale = locale.setlocale(locale.LC_ALL, "")
            except:
                self.cLocale = locale.setlocale(locale.LC_ALL, locale.getdefaultlocale())
            print("Failed to set locale according to your settings. Using Default instead:", self.cLocale)

        # Get TimeZone
        self.localTZ, self.is_dst = zoneinfo.get_local_tz()
        print("Local Time Zone:", self.localTZ, "/ Daylight Saving Time:", ("+" if time.localtime().tm_isdst >= 0 else "")+str(time.localtime().tm_isdst))

        self.currentWP = bkgutils.getWallpaper()
        self.parent = self.parent()
        self.setupUi(self)
        self.widgets = self.centralwidget.findChildren(QtCore.QObject)

        x, y, locIndex, ncount, nsource, show_help = self.getOpts()
        self.xmax, self.ymax = settings.dispSize
        if settings.setAsWallpaper:
            x, y, self.xmax, self.ymax = pwc.getWorkArea()
        self.xmax, self.ymax = qtutils.initDisplay(parent=self,
                                                   pos=(x, y),
                                                   size=(self.xmax, self.ymax),
                                                   noResize=True,
                                                   frameless=settings.setAsWallpaper,
                                                   # noFocus=settings.setAsWallpaper,
                                                   # aob=settings.setAsWallpaper,
                                                   # setAsWallpaper=settings.setAsWallpaper,
                                                   opacity=255 * (1 if settings.showBkg else 0),
                                                   caption=wconstants.SYSTEM_CAPTION,
                                                   icon=utils.resource_path(__file__, wconstants.ICON_FOLDER + wconstants.ICONSET_FLATFULLCOLOR) + wconstants.SYSTEM_ICON)
        self.xmargin = self.xmax * 0.01
        self.ymargin = self.ymax * 0.01
        self.xgap = self.xmargin * 3
        self.ygap = self.ymargin * 3
        self.dispRatio = self.xmax / self.ymax
        self.labelRatio = 0.8
        self.imgRatio = 1 if self.dispRatio > 4/3 else 0.9
        self.fineTuning = 0.45

        self.font = qtutils.loadFont(utils.resource_path(__file__, wconstants.FONTS_FOLDER) + wconstants.numberfont)
        self.convertQtColors()
        self.font_color = settings.clockc
        # self.setToolTip(qtutils.setHTMLStyle('Click the tray icon to show Quick Menu', color="black", bkgcolor="white"))

        if settings.showBkg:
            style = qtutils.setStyleSheet(self.alert_label.styleSheet(), settings.nBkg, settings.nc)
        else:
            style = qtutils.setColor(self.alert_label.styleSheet(), settings.nc)

        self.resizeUI()

        self.marquee = qtutils.Marquee(parent=self.alert_label,
                                       stylesheet=style,
                                       direction=QtCore.Qt.RightToLeft,
                                       smooth=settings.smooth)

        self.update_data = None
        self.iconf = utils.resource_path(__file__, wconstants.ICON_FOLDER + settings.iconSet)
        self.bkg = ""
        self.moon = ""
        self.sunsign = ""
        self.iconNow = ""
        self.moonIconNow = ""
        self.titles = ""
        self.showingNews = False
        self.onlyTime = False
        self.help_label = None
        self.help = ""
        self.showingHelp = False
        self.onlyClock = False
        self.tzOffset = None
        self.clock1 = None
        self.clock2 = None
        self.clock3 = None
        self.clock4 = None
        self.oldPos = self.pos()

        if settings.setAsWallpaper:
            pwc.Window(self.winId()).sendBehind()

        self.updateDataStart(locIndex, ncount, nsource)

        self.menu = Menu(self)
        self.menu.menuOption.connect(self.menuOption)
        self.menu.show()

        if show_help:
            self.repaintHELP()

    def getOpts(self):

        show_help = False
        x = None
        y = None
        locIndex = 0
        ncount = 0
        nsource = ""
        try:
            opts, args = getopt.getopt(sys.argv[1:], "hx:y:l:n:s:")
            if args:
                show_help = True
            else:
                for opt, arg in opts:
                    if opt == '-h':
                        show_help = True
                    elif opt == "-x":
                        x = arg
                    elif opt == "-y":
                        y = arg
                    elif opt == "-l":
                        locIndex = arg
                    elif opt == "-n":
                        ncount = arg
                    elif opt == "-s":
                        nsource = arg

                if x is None or y is None: x = y = None

        except getopt.GetoptError:
            show_help = True

        return x, y, locIndex, ncount, nsource, show_help

    def convertQtColors(self):
        settings.cBkg = qtutils.getRGBAfromColorName(QtGui.QColor(settings.cBkg))
        settings.nBkg = qtutils.getRGBAfromColorName(QtGui.QColor(settings.nBkg))
        settings.clockc = qtutils.getRGBAfromColorName(QtGui.QColor(settings.clockc))
        settings.clockh = qtutils.getRGBAfromColorName(QtGui.QColor(settings.clockh))
        settings.nc = qtutils.getRGBAfromColorName(QtGui.QColor(settings.nc))
        settings.wc = qtutils.getRGBAfromColorName(QtGui.QColor(settings.wc))
        settings.chighlight = qtutils.getRGBAfromColorName(QtGui.QColor(settings.chighlight))
        settings.cdark = qtutils.getRGBAfromColorName(QtGui.QColor(settings.cdark))
        settings.cdim = qtutils.getRGBAfromColorName(QtGui.QColor(settings.cdim))
        settings.crcm = qtutils.getRGBAfromColorName(QtGui.QColor(settings.crcm))
        settings.crcw = qtutils.getRGBAfromColorName(QtGui.QColor(settings.crcw))
        settings.chigh = qtutils.getRGBAfromColorName(QtGui.QColor(settings.chigh))
        settings.clow = qtutils.getRGBAfromColorName(QtGui.QColor(settings.clow))
        settings.byc = qtutils.getRGBAfromColorName(QtGui.QColor(settings.byc))

    def resizeUI(self):

        self.bkg_img.resize(self.size())
        if settings.showBkg:
            if settings.bkgMode == wconstants.BKG_WEATHER:
                op = QtWidgets.QGraphicsOpacityEffect(self)
                op.setOpacity(1 - (settings.dimFactor / 255))
                self.bkg_img.setGraphicsEffect(op)
                self.bkg_img.setAutoFillBackground(True)
            elif settings.bkgMode == wconstants.BKG_SOLID:
                self.bkg_img.clear()
                self.bkg_img.setStyleSheet(qtutils.setBkgColorAlpha(qtutils.setBkgColor(self.bkg_img.styleSheet(), settings.cBkg), 255))
        else:
            self.bkg_img.clear()
            self.bkg_img.setStyleSheet(qtutils.setBkgColorAlpha(qtutils.setBkgColor(self.bkg_img.styleSheet(), settings.cBkg), 0))
        self.gridLayoutWidget.resize(self.xmax, self.ymax)

        for w in self.widgets:
            if w.objectName()[-6:] == "_label":
                w.clear()
                w.setStyleSheet(qtutils.setColor(w.styleSheet(), self.font_color))
                font = w.font()
                font.setPointSize(int(w.font().pointSize() * (self.ymax / wconstants.REF_Y)))
                w.setFont(font)
                if w.objectName()[:8] == "fh_temp_":
                    w.setFixedWidth(int(self.xmax / 18))
                w.adjustSize()
            # This is nice for square images, but not for rectangular ones
            # elif w.objectName()[-4:] == "_img":
            #     w.setScaledContents(True)

        xmargin = int(self.xgap * (5.5 + int(self.fineTuning * self.xmax / wconstants.REF_X)))
        ymargin = -int(self.ygap * (9 - int(self.fineTuning * self.ymax/wconstants.REF_Y)))
        p = self.gridLayoutWidget.frameGeometry().center() + QtCore.QPoint(xmargin, ymargin)
        self.cc_moon_img.move(p.x(), p.y())
        if self.dispRatio <= 4/3:
            font = self.hour_label.font()
            font.setPointSize(int(font.pointSize() * self.labelRatio))
            self.hour_label.setFont(font)
            self.sep_label.setFont(font)
            self.minutes_label.setFont(font)
            font = self.cc_temp_label.font()
            font.setPointSize(int(font.pointSize() * self.labelRatio))
            self.cc_temp_label.setFont(font)

    def updateDataStart(self, locIndex, ncount, nsource):
        self.update_data = UpdateData(self, self.geometry().width(), self.geometry().height(), locIndex, ncount, nsource)
        self.update_data.dataChanged.connect(self.onDataChanged)
        self.update_data.restart.connect(self.onRestart)
        self.update_data.closeAll.connect(self.closeAll)
        self.update_data.run()

    @QtCore.pyqtSlot(dict)
    def onDataChanged(self, data):

        if settings.debug: print(data)
        contents = data.keys()

        if wconstants.BKG in contents:
            self.repaintBKG(data[wconstants.BKG])

        if wconstants.HEADER in contents:
            self.repaintHEADER(data[wconstants.HEADER])

        if wconstants.MOON in contents:
            self.repaintMOON(data[wconstants.MOON])

        if wconstants.SUNSIGN in contents:
            self.repaintSUNSIGN(data[wconstants.SUNSIGN])

        if wconstants.SEP in contents:
            self.repaintSEP(data[wconstants.SEP])

        if wconstants.TIME in contents:
            self.repaintTIME(data[wconstants.TIME])

        if wconstants.CC in contents:
            # We need to remove clocks first when recovering from weather data errors
            if self.onlyTime:
                data[wconstants.ONLY_CLOCK] = "hide"
                self.repaintCLOCK(data[wconstants.ONLY_CLOCK])
                data.pop(wconstants.ONLY_CLOCK, False)
            self.repaintCC(data[wconstants.CC])

        if wconstants.ALERT in contents:
            self.repaintALERT(data[wconstants.ALERT])

        if wconstants.FF_DAILY in contents:
            self.repaintFF(data[wconstants.FF_DAILY])

        if wconstants.FF_HOURLY in contents:
            self.repaintFH(data[wconstants.FF_HOURLY])

        if wconstants.NEWS in contents:
            self.repaintNEWS(data[wconstants.NEWS])

        if wconstants.ONLY_CLOCK in contents:
            self.repaintCLOCK(data[wconstants.ONLY_CLOCK])

    def repaintBKG(self, data):
        if self.bkg != data["bkg"]:
            self.bkg = data["bkg"]
            img = QtGui.QPixmap(utils.resource_path(__file__, wconstants.BKG_FOLDER) + self.bkg)
            img = img.scaled(self.xmax, self.ymax, QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
            self.bkg_img.setPixmap(img)

    def repaintHEADER(self, data):
        self.day_label.setText(data["day"])
        self.day_week_label.setText(data["day_week"])
        self.month_label.setText(data["month"])
        self.by_label.setText(qtutils.setHTMLStyle(data["source"], color=settings.chighlight, strong=True) + data["by"])
        self.location_label.setText(data["location"])

    def repaintMOON(self, data):
        icon = data.get("moon_icon", "None")
        if icon == "None":
            self.moon_img.clear()
            self.moon = ""
        elif self.moon != icon or not self.moon_img.pixmap():
            self.moon = icon
            size = int(data["moon_icon_size"] * self.imgRatio)
            img = qtutils.resizeImageWithQT(utils.resource_path(__file__, wconstants.MOON_FOLDER) + self.moon, size, size, expand=False)
            self.moon_img.setPixmap(img)

    def repaintSUNSIGN(self, data):
        if self.sunsign != data["sunsign_icon"]:
            self.sunsign = data["sunsign_icon"]
            size = int(data["sunsign_icon_size"] * self.imgRatio)
            img = qtutils.resizeImageWithQT(utils.resource_path(__file__, wconstants.SUNSIGNS_FOLDER) + self.sunsign, size, size, expand=False)
            self.sunsign_img.setPixmap(img)

    def repaintSEP(self, data):
        style = qtutils.setColorAlpha(self.sep_label.styleSheet(), data["sep_color"])
        self.sep_label.setStyleSheet(style)
        self.sep_label.setText(data["sep"])

    def repaintTIME(self, data):
        self.hour_label.setText(data["hour"])
        self.minutes_label.setText(data["minutes"])

    def repaintCC(self, data):
        if self.iconNow != data["icon_now"]:
            self.iconNow = data["icon_now"]
            size = data["icon_now_size"] * self.imgRatio
            img = qtutils.resizeImageWithQT(utils.resource_path(__file__, data["icon_now_folder"]) + self.iconNow, size, size, expand=False)
            self.cc_img.setPixmap(img)
            self.cc_img.adjustSize()
        if "icon_now_moon_icon" in data.keys():
            if self.moonIconNow != data["icon_now_moon_icon"]:
                self.moonIconNow = data["icon_now_moon_icon"]
                size = int(data["icon_now_moon_size"] * self.imgRatio)
                img2 = qtutils.resizeImageWithQT(utils.resource_path(__file__, wconstants.MOON_W_FOLDER) + self.moonIconNow, size, size, expand=False)
                self.cc_moon_img.setPixmap(img2)
                self.cc_moon_img.adjustSize()
        else:
            self.cc_moon_img.clear()
            self.moonIconNow = ""
        self.cc_temp_label.setText(data["temp"] + qtutils.setHTMLStyle(wconstants.degree_sign, fontSize=self.cc_temp_label.font().pointSize(), valign="super"))
        self.cc_temp_text_label.setText(data["temp_text"])
        self.cc_other_cond_label.setText(data["updated"] + "\n" + data["other_conds_1"] + "\n" + data["other_conds_2"])

    def repaintALERT(self, data):

        if data["alert"] != "None":
            if not self.alert_img.pixmap():
                size = int(data["alert_icon_size"] * self.imgRatio)
                img = qtutils.resizeImageWithQT(utils.resource_path(__file__, wconstants.ALERT_ICONFOLDER) + data["alert_icon"], size, size, expand=False)
                self.alert_img.setPixmap(img)
                self.alert_img.setStyleSheet(self.alert_label.styleSheet())
            self.alert_label.setText(qtutils.setHTMLStyle(data["alert"], color=data["alert_color"], strong=True))
        else:
            self.alert_img.clear()
            self.alert_label.clear()

    def repaintFF(self, data):
        for w in self.widgets:
            name = w.objectName()
            prefix = name[:3]
            suffix = name[-6:]
            label = name[:-6]
            if prefix == "ff_":
                if suffix == "_label":
                    if "_pop_" in name:
                        style = qtutils.setColor(w.styleSheet(), data[label+"_color"])
                        w.setStyleSheet(style)
                    w.setText(data[label])
                    w.setFixedHeight(w.fontMetrics().height())
                else:
                    size = int(data["ff_icon_size"] * self.imgRatio)
                    img = qtutils.resizeImageWithQT(self.iconf + data[name], size, size, expand=False)
                    w.setPixmap(img)
                    w.adjustSize()

    def repaintFH(self, data):

        keys = data.keys()
        for w in self.widgets:
            name = w.objectName()
            prefix = name[:3]
            suffix = name[-6:]
            label = name[:-6]
            if prefix == "fh_":
                if suffix == "_label":
                    if label in keys:
                        w.setText(data[label])
                        w.setFixedHeight(w.fontMetrics().height())
                    else:
                        w.clear()
                else:
                    if name in keys:
                        size = int(data["fh_icon_size"] * self.imgRatio)
                        img = qtutils.resizeImageWithQT(self.iconf + data[name], size, size, expand=False)
                        w.setPixmap(img)
                        w.adjustSize()
                    else:
                        w.clear()

    def repaintNEWS(self, data):
        if "titles" in data.keys():
            self.showingNews = True
            self.marquee.setText(data["nsource"] + data["titles"])
            self.marquee.start()
            self.gridLayout.replaceWidget(self.alert_label, self.marquee)
            self.alert_label.hide()
            self.alert_img.hide()

        elif "stop" in data.keys():
            self.showingNews = False
            self.alert_img.show()
            self.alert_label.show()
            self.gridLayout.replaceWidget(self.marquee, self.alert_label)
            self.marquee.stop()

    def repaintHELP(self):
        if not self.help_label:
            self.help_label = QtWidgets.QLabel()
            self.help_label.setFont(self.cc_other_cond_label.font())
            if not self.help:
                with open(utils.resource_path(__file__, wconstants.RESOURCES_FOLDER) + wconstants.HELP_FILE, encoding='utf-8') as file:
                    self.help = json.load(file)
            self.help_label.setGeometry(int(self.xgap*2), int(self.ygap*2), self.xmax - int(self.xgap*4), self.ymax - int(self.ygap*4))
            self.help_label.setStyleSheet(qtutils.setBkgColorAlpha(self.marquee.styleSheet(), 255))
            text = ""
            for key in self.help.keys():
                text += "\t" + self.help[key] + "\n"
            text += "\n\n\t\t\t" + "Press Escape to EXIT this help"
            self.help_label.setText(text)
            self.layout().addWidget(self.help_label)
        self.help_label.show()
        self.showingHelp = True

    def repaintCLOCK(self, data):
        if data == "hide" and self.onlyTime:
            self.hideClocks()
            self.onlyTime = False

        else:
            self.iconNow = self.moonIconNow = self.moon = self.sunsign = ""
            self.onlyTime = True
            self.showClocks()

    def showClocks(self):

        if not self.tzOffset:
            self.tzOffset = zoneinfo.get_world_clock_offsets(settings.timeZones)

        for w in self.widgets:
            name = w.objectName()
            prefix = name[:3]
            if prefix in ("ff_", "fh_", "cc_"):
                w.clear()
            self.hour_label.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
            self.sep_label.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
            self.minutes_label.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)

        size = int((self.ymax - self.ff_1_img.x()) / 3)
        bkcolor = qtutils.getBkgColor(self.ff_1_img.styleSheet())
        rgbColor = qtutils.getRGBAfromColorRGB(settings.clockc)
        color = QtGui.QColor().fromRgb(rgbColor[0], rgbColor[1], rgbColor[2], rgbColor[3])

        self.ff_day_1_label.setText(self.tzOffset[0][0])
        if not self.clock1:
            self.clock1 = qtutils.Clock(bcolor=color, bkcolor=bkcolor, size=size, hoffset=self.tzOffset[0][1],
                                        moffset=self.tzOffset[0][2])
        self.clock1.show()
        self.gridLayout.replaceWidget(self.ff_1_img, self.clock1)
        self.ff_1_img.hide()

        self.ff_day_2_label.setText(self.tzOffset[1][0])
        if not self.clock2:
            self.clock2 = qtutils.Clock(bcolor=color, bkcolor=bkcolor, size=size, hoffset=self.tzOffset[1][1],
                                        moffset=self.tzOffset[1][2])
        self.clock2.show()
        self.gridLayout.replaceWidget(self.ff_2_img, self.clock2)
        self.ff_2_img.hide()

        self.ff_day_3_label.setText(self.tzOffset[2][0])
        if not self.clock3:
            self.clock3 = qtutils.Clock(bcolor=color, bkcolor=bkcolor, size=size, hoffset=self.tzOffset[2][1],
                                        moffset=self.tzOffset[2][2])
        self.clock3.show()
        self.gridLayout.replaceWidget(self.ff_3_img, self.clock3)
        self.ff_3_img.hide()

        self.ff_day_4_label.setText(self.tzOffset[3][0])
        if not self.clock4:
            self.clock4 = qtutils.Clock(bcolor=color, bkcolor=bkcolor, size=size, hoffset=self.tzOffset[3][1],
                                        moffset=self.tzOffset[3][2])
        self.clock4.show()
        self.gridLayout.replaceWidget(self.ff_4_img, self.clock4)
        self.ff_4_img.hide()

    def hideClocks(self):

        if self.clock1 and self.clock2 and self.clock3 and self.clock4:

            self.ff_1_img.show()
            self.gridLayout.replaceWidget(self.clock1, self.ff_1_img)
            self.clock1.stop()
            self.clock1.hide()

            self.ff_2_img.show()
            self.gridLayout.replaceWidget(self.clock2, self.ff_2_img)
            self.clock2.stop()
            self.clock2.hide()

            self.ff_3_img.show()
            self.gridLayout.replaceWidget(self.clock3, self.ff_3_img)
            self.clock3.stop()
            self.clock3.hide()

            self.ff_4_img.show()
            self.gridLayout.replaceWidget(self.clock4, self.ff_4_img)
            self.clock4.stop()
            self.clock4.hide()

        self.hour_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        self.sep_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        self.minutes_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)

    # Comment this to use tray icon only and not standard context menu (which should not activate in Wallpaper Mode):
    def contextMenuEvent(self, event):
        if not settings.setAsWallpaper:
            self.menu.showMenu(event.pos())
        super(Window, self).contextMenuEvent(event)

    @QtCore.pyqtSlot(int, int, str)
    def onRestart(self, locIndex, ncount, nsource):
        param = " -x %s -y %s -l %s -n %s -s %s" % (str(self.pos().x()), str(self.pos().y()), str(locIndex), str(ncount), str(nsource))
        cmd = os.path.abspath(sys.executable)
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        if "python" in cmd:
            cmd += " " + os.path.abspath(__file__) + param
            subprocess.Popen(cmd, creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP, shell=False, close_fds=True)
        else:
            subprocess.Popen(cmd + param, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP, shell=False, close_fds=True)
        self.closeAll()

    @QtCore.pyqtSlot(str)
    def menuOption(self, key):
        if key == "H":
            if self.showingHelp:
                self.help_label.hide()
                self.showingHelp = False
            else:
                self.showingHelp = True
                self.repaintHELP()
        elif key == "Q":
            self.closeAll()
        else:
            char = QtGui.QKeySequence.fromString(key)[0]
            event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, char, QtCore.Qt.NoModifier)
            self.update_data.catchAction(event)

    def keyPressEvent(self, event):

        if event.key() == QtCore.Qt.Key_Escape:
            if self.showingHelp:
                self.help_label.hide()
                self.showingHelp = False
            else:
                self.update_data.catchAction(QtCore.QEvent.Close)
                self.closeAll()
        super(Window, self).keyPressEvent(event)

    def mousePressEvent(self, event):
        self.oldPos = event.globalPos()
        super(Window, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self.isFullScreen() and not settings.showBkg and not settings.setAsWallpaper:
            delta = QtCore.QPoint(event.globalPos() - self.oldPos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPos()
        super(Window, self).mouseMoveEvent(event)

    def closeEvent(self, event):
        self.update_data.catchAction(QtCore.QEvent.Close)
        self.closeAll()

    @QtCore.pyqtSlot()
    def closeAll(self):
        if settings.setAsWallpaper:
            self.setParent(self.parent)
            self.hide()
            # For an unknown reason, it remains in the background, so it requires to force setting previous wallpaper
            bkgutils.setWallpaper(self.currentWP)
        QtWidgets.QApplication.quit()


class Menu(QtWidgets.QWidget):

    menuOption = QtCore.pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        QtWidgets.QWidget.__init__(self, *args, **kwargs)

        self.setupUI()

    def setupUI(self):

        self.contextMenu = QtWidgets.QMenu(self)
        self.contextMenu.setStyleSheet("""
            QMenu {border: 1px inset #666; font-size: 18px; background-color: #333; color: #fff; padding: 5; padding-left: 20}
            QMenu:selected {background-color: #666; color: #fff;}""")

        self.locAct = self.contextMenu.addMenu("Select Weather location")
        self.locAct.addAction(settings.location[0][0], lambda: self.execAction("1"))
        self.locAct.addAction(settings.location[1][0], lambda: self.execAction("2"))
        self.locAct.addAction(settings.location[2][0], lambda: self.execAction("3"))

        self.newsAct = self.contextMenu.addMenu("Select News source")
        self.newsAct.addAction(wconstants.NEWS_1, lambda: self.execAction("A"))
        self.newsAct.addAction(wconstants.NEWS_2, lambda: self.execAction("B"))

        self.contextMenu.addSeparator()
        self.contextMenu.addAction("Toggle Clock/Weather mode", lambda: self.execAction("C"))
        self.contextMenu.addAction("Open Settings", lambda: self.execAction("S"))

        self.contextMenu.addSeparator()
        self.contextMenu.addAction("Show/Hide Help", lambda: self.execAction("H"))
        self.contextMenu.addAction("Quit", lambda: self.execAction("Q"))

        self.trayIcon = QtWidgets.QSystemTrayIcon(QtGui.QIcon(utils.resource_path(__file__, wconstants.ICON_FOLDER + wconstants.ICONSET_FLATFULLCOLOR) + wconstants.SYSTEM_ICON), self)
        self.trayIcon.setContextMenu(self.contextMenu)
        self.trayIcon.setToolTip("Weather and News by alef")
        self.trayIcon.show()

    def showMenu(self, pos=QtCore.QPoint(0, 0)):
        self.contextMenu.exec_(self.mapToGlobal(pos))

    def execAction(self, key):
        self.menuOption.emit(key)


class UpdateData(QtWidgets.QMainWindow):

    dataChanged = QtCore.pyqtSignal(dict)
    closeAll = QtCore.pyqtSignal()
    restart = QtCore.pyqtSignal(int, int, str)

    def __init__(self, parent=None, x=None, y=None, locIndex=0, ncount=0, nsource=""):
        QtWidgets.QMainWindow.__init__(self, parent)
        if settings.debug: print("INIT", time.strftime("%H:%M:%S"))

        self.xmax = x
        self.ymax = y
        self.xmin = self.ymin = 0
        self.xmargin = self.xmax * 0.01
        self.ymargin = self.ymax * 0.01
        self.xgap = self.xmargin * 3
        self.ygap = self.ymargin * 3

        self.data = {}

        # These values will change according to some conditions. "Saving" them to self. variables
        self.firstRun = True
        self.showBkg = settings.showBkg and settings.bkgMode != wconstants.BKG_SOLID
        self.bkg = None
        self.prevBkg = None
        self.nsource = (nsource if nsource else wconstants.nsource1)
        self.nURL = wconstants.nURL1
        self.dist_limit = 0
        if settings.use_current_location and not settings.clockMode:
            self.dist_limit = self.check_location()
        self.location = settings.location[int(locIndex)][0]
        self.zip_code = settings.location[int(locIndex)][1]
        self.prevMinimized = False

        # Settings
        self.iconScaleC = int(
            self.ymax * wconstants.iconSizeC / wconstants.REF_Y * wconstants.ICON_SCALE.get(settings.iconSet, 1.0))
        self.iconScaleF = int(
            self.ymax * wconstants.iconSizeF / wconstants.REF_Y * wconstants.ICON_SCALE.get(settings.iconSet, 1.0))
        self.moonIconScale = int(self.ymax * wconstants.moonIconSize / wconstants.REF_Y)
        self.sunsignIconScale = int(self.ymax * wconstants.sunsignIconSize / wconstants.REF_Y)
        self.alertIconScale = int(self.ymax * wconstants.alertIconSize / wconstants.REF_Y)

        # Other variables
        self.counter = 0
        self.wUpdated = False
        self.wUpdateError = False
        self.showingNews = False
        self.nCount = int(ncount)
        self.menu = None
        self.showingMenu = False
        self.updateWeather = False
        self.menu = None
        self.menu2 = None
        self.configRun = None
        self.configQuit = None
        self.showingConfig = False
        self.help = None
        self.changedWhileNews = False
        self.brightness = -1
        self.keyP = None
        self.onlyTime = False
        self.onlyTimePrev = None
        self.user_clockMode = False
        self.errCount = 0
        self.sepPos = 0
        self.titles = ''
        self.titlesHead = ''
        self.pics = [None, None, None, None, None]
        self.tzOffset = None
        self.WtzOffset = 0
        self.nightTime = False
        self.xMoon = 0
        self.sunsign = None
        self.sunsign_icon = None
        self.moonHIcon = None
        self.rectHeader = None
        self.imgHeader = None
        self.rectTime = None
        self.imgTime = None
        self.rectCC = None
        self.imgCC = None
        self.rectFF = None
        self.imgFF = None
        self.rectAlert = None
        self.imgAlert = None

        # Weather info initialization
        self.wcc = ''
        self.wff = ''
        self.bkgCode = wconstants.DEFAULT_BKG
        self.iconNow = wconstants.DEFAULT_ICON
        self.iconNowPrev = None
        self.iconImgC = None
        self.bkgCodePrev = None
        self.iconC2 = None
        self.iconC2Prev = None
        self.iconImgC2 = None
        self.temp = ''
        self.temptext = ''
        self.feels_like = '0'
        self.wind_speed = '0'
        self.baro = '29.95'
        self.wind_dir = 'S'
        self.humid = '50.0'
        self.uvi = '0'
        self.moon = None
        self.prevMoon = None
        self.moonPrev = None
        self.moonIcon = None
        self.alert_start = ""
        self.alert_end = ""
        self.alert = None
        self.alertIcon = None
        self.wLastUpdate = ''
        self.wPrevUpdate = ''
        self.wLastForecastUpdate = ''
        self.last = ''
        self.day = []
        for i in range(wconstants.NSUB): self.day.append('')
        self.icon = []
        for i in range(wconstants.NSUB): self.icon.append('na')
        self.iconPrev = []
        for i in range(wconstants.NSUB): self.iconPrev.append(None)
        self.iconImg = []
        for i in range(wconstants.NSUB): self.iconImg.append(None)
        self.iconNight = []
        for i in range(wconstants.NSUB): self.iconNight.append('')
        self.rain = []
        for i in range(wconstants.NSUB): self.rain.append('')
        self.temps = []
        for i in range(wconstants.NSUB): self.temps.append(['', ''])
        self.hTemps = []
        for i in range(wconstants.hourly_number): self.hTemps.append('')
        self.hIcons = []
        for i in range(wconstants.hourly_number): self.hIcons.append(None)
        self.hIconPrev = ''
        self.hHours = []
        for i in range(wconstants.hourly_number): self.hHours.append('')
        self.sunrise = '07:00'
        self.sr = '07'
        self.sunset = '20:00'
        self.sn = '20'

        self.update_weather_obj = None
        self.update_weather_thread = None
        self.updateWeatherStart()
        self.update_news_obj = None
        self.update_news_thread = None
        self.updateNewsStart()

        self.secTimer = QtCore.QTimer(self)
        self.secTimer.timeout.connect(self.display_separator)
        self.secTimer.start(1000)
        self.weatherTimer = QtCore.QTimer(self)
        self.weatherTimer.timeout.connect(self.update_weather)
        self.weatherTimer.start(wconstants.min_update_weather * 60 * 1000)
        self.configTimer = QtCore.QTimer(self)
        self.configTimer.timeout.connect(self.check_config)
        self.newsTimer = QtCore.QTimer(self)
        self.newsTimer.timeout.connect(self.check_news)

    def check_location(self):
        if settings.debug: print("GET_LOC", time.strftime("%H:%M:%S"))

        loc = webutils.get_location_by_ip(wconstants.gIPURL % settings.lang)
        if loc:
            loc1 = (float(loc[3]), float(loc[4]))
            loc2 = (float(settings.location[0][1].split("lat=")[1].split("&")[0]),
                    float(settings.location[0][1].split("&lon=")[1]))
            dist = webutils.get_distanceByCoordinates(loc1, loc2, settings.disp_units)
            if dist < int(wconstants.distLimit[settings.disp_units]):
                dist = 0
            if settings.use_current_location:
                locations = [(loc[0] + (", " + loc[1] if loc[1] else "") + (", " + loc[2] if loc[2] else ""),
                              "lat=" + str(loc[3]) + "&lon=" + str(loc[4]))]
                for i in range(0, len(settings.location)):
                    locations.append(settings.location[i])
                settings.location = locations
        else:
            dist = -1

        return dist

    def show_all(self):

        self.display_header()
        self.display_time()
        self.update_weather(firstRun=True)
        if self.nCount > 0 and settings.newsMode != wconstants.NEWS_ALWAYSOFF:
            self.update_news(self.nsource)

    def display_bkg(self):
        if settings.debug: print("DISP_BKG", time.strftime("%H:%M:%S"))

        if self.showBkg:
            if settings.bkgMode == wconstants.BKG_WEATHER \
                    and not settings.clockMode and not self.user_clockMode and not self.onlyTime:
                code = str(self.bkgCode)
            else:
                code = str(wconstants.DEFAULT_BKG)

            # Prepare Background only if changed since last time
            if code != self.bkgCodePrev:
                self.bkgCodePrev = code
                data = {"bkg": code + wconstants.BKG_EXT}
                self.data[wconstants.BKG] = data

    def display_header(self):
        if settings.debug: print("DISP_HEADER", time.strftime("%H:%M:%S"))

        self.data[wconstants.HEADER] = {}
        self.display_calendar()
        self.display_by()
        self.display_location()
        self.display_astronomics()
        self.dataChanged.emit(self.data)
        self.data.pop(wconstants.HEADER, False)
        self.data.pop(wconstants.SUNSIGN, False)
        self.data.pop(wconstants.MOON, False)

    def display_calendar(self):
        if settings.debug: print("DISP_CALENDAR", time.strftime("%H:%M:%S"))

        tm = time.strftime("%A/%B/%d/%Y/%m").split("/")
        data = {"day_week": tm[0],
                "month": tm[1],
                "day": tm[2]}
        self.data[wconstants.HEADER].update(data)

    def display_by(self):
        if settings.debug: print("DISP_BY", time.strftime("%H:%M:%S"))

        data = {"source": wconstants.WEATHER_1,
                "by": " | " + wconstants.SYSTEM_CAPTION[-7:]}
        self.data[wconstants.HEADER].update(data)

    def display_location(self):
        if settings.debug: print("DISP_LOC", time.strftime("%H:%M:%S"))

        if not self.location:
            self.location = settings.location[0][0]

        data = {"location": self.location}
        self.data[wconstants.HEADER].update(data)

    def display_astronomics(self):
        if settings.debug: print("DISP_ASTRO", time.strftime("%H:%M:%S"))

        if settings.showSunSigns:
            current_sunsign = wutils.get_constellation()
            if self.sunsign != current_sunsign:
                self.sunsign = current_sunsign
                data = {"sunsign_icon": current_sunsign + wconstants.ICON_EXT,
                        "sunsign_icon_size": wconstants.sunsignIconSize * self.ymax / wconstants.REF_Y}
                self.data[wconstants.SUNSIGN] = data

        self.moon = wutils.convert_moon_phase(wutils.get_moon_position())
        if settings.moonMode in (wconstants.MOON_BOTH, wconstants.MOON_ONHEADER):
            if self.moon != self.prevMoon:
                self.prevMoon = self.moon
                data = {"moon_icon": self.moon + wconstants.ICON_EXT,
                        "moon_icon_size": wconstants.sunsignIconSize * self.ymax / wconstants.REF_Y * 0.7}
                self.data[wconstants.MOON] = data

    def display_separator(self):
        if settings.debug: print("DISP_SEP", time.strftime("%H:%M:%S"))

        seconds = int(time.strftime("%S"))
        if seconds == 0:
            self.display_time()
        else:
            data = {"sep": ":",
                    "sep_color": int(255 / (seconds % 2 + 1))}
            self.data[wconstants.SEP] = data

            self.dataChanged.emit(self.data)
            self.data.pop(wconstants.SEP, False)

    def display_time(self):
        if settings.debug: print("DISP_TIME", time.strftime("%H:%M:%S"))

        tm = time.strftime("%H%M%S")
        hours = tm[:2]
        minutes = tm[2:4]
        seconds = tm[4:]
        data = {"hour": hours, "minutes": minutes}
        self.data[wconstants.TIME] = data
        data = {"sep": ":",
                "sep_color": int(255 / (int(seconds) % 2 + 1))}
        self.data[wconstants.SEP] = data

        if int(hours) == 0 and int(minutes) == 0:
            self.display_header()
            self.onWeatherUpdated({"OK": self.wcc}, False)

        self.nightTime = (self.sunset <= hours+minutes or self.sunrise >= hours+minutes)
        if self.sunset == hours+minutes or self.sunrise == hours+minutes:
            self.show_weather()

        self.dataChanged.emit(self.data)
        self.data.pop(wconstants.TIME, False)
        self.data.pop(wconstants.SEP, False)

        if not self.showingNews and \
                (settings.newsMode == wconstants.NEWS_ALWAYSON or
                 (settings.newsMode == wconstants.NEWS_PERIOD and int(minutes) % wconstants.min_update_news == 0)):
            self.update_news()

    @QtCore.pyqtSlot()
    def updateWeatherStart(self):
        self.update_weather_obj = UpdateWeather()
        self.update_weather_thread = QtCore.QThread()
        self.update_weather_obj.moveToThread(self.update_weather_thread)
        self.update_weather_obj.weatherUpdated.connect(self.onWeatherUpdated)
        self.update_weather_thread.start()

    @QtCore.pyqtSlot()
    def updateWeatherStop(self):
        self.update_weather_thread.requestInterruption()
        self.update_weather_thread.quit()
        self.update_weather_thread.wait()

    @QtCore.pyqtSlot(dict, bool)
    def onWeatherUpdated(self, data, firstRun):

        if "OK" in data.keys():
            self.wUpdated = True
            self.wUpdateError = False
            self.wcc = data["OK"]
            self.parse_openweathermap(self.wcc, force=firstRun)

            if self.onlyTime:
                self.onlyTime = False
            self.show_weather()

        elif "KO" in data.keys():
            self.wUpdated = False
            self.wUpdateError = True
            self.errCount += 1
            if firstRun or self.errCount > wconstants.errMax:
                self.onlyTime = True
                self.show_only_clock()
                print("No Weather info or obsolete. Falling back to World Clocks")
            else:
                print("Error getting Weather update from", settings.wsource, "at", self.last, self.errCount, "times")
            print(data["KO"])

    def update_weather(self, firstRun=False):
        if settings.debug: print("UPD_WEATHER", time.strftime("%H:%M:%S"))

        errorReading = False
        if settings.debug:
            try:
                with open("openweathermap.json", encoding='UTF-8') as file:
                    self.wcc = json.load(file)
                self.onWeatherUpdated({"OK": self.wcc}, firstRun)
            except:
                errorReading = True

        if not settings.debug or errorReading:
            # Get Weather information from source
            url = wconstants.weatherURL % (self.zip_code, settings.disp_units, settings.lang_code)
            QtCore.QMetaObject.invokeMethod(self.update_weather_obj, 'updateWeather', QtCore.Qt.QueuedConnection,
                                            QtCore.Q_ARG(str, url),
                                            QtCore.Q_ARG(bool, firstRun))

    def parse_openweathermap(self, w, force=False):
        if settings.debug: print("PARSE_OPENW", time.strftime("%H:%M:%S"))

        # Current Conditions
        cc = w["current"]
        ff = w["daily"][0]
        self.WtzOffset = int(w["timezone_offset"])
        self.temp = str(int(cc["temp"]))
        self.feels_like = str(int(cc["feels_like"])) + wconstants.degree_sign
        self.iconNow = wutils.convert_weather_code(str(cc["weather"][0]["id"]))
        self.bkgCode = self.iconNow
        self.temptext = str(cc["weather"][0]["description"]).capitalize()
        self.wind_speed = str(cc["wind_speed"] * wconstants.windScale[settings.disp_units])
        self.wind_dir = wutils.convert_win_direction(cc["wind_deg"], settings.lang)
        self.baro = str("%.2f" % (cc["pressure"] * wconstants.baroScale[settings.disp_units]))
        self.humid = str(cc["humidity"])
        self.uvi = str(int(cc["uvi"]))
        self.moon = wutils.convert_moon_phase(ff["moon_phase"])
        self.sunrise = time.strftime("%H:%M", time.gmtime(cc["sunrise"] + self.WtzOffset))
        self.sunset = time.strftime("%H:%M", time.gmtime(cc["sunset"] + self.WtzOffset))
        hmCurrent = time.strftime("%H:%M")
        self.nightTime = (self.sunset <= hmCurrent or self.sunrise > hmCurrent)
        if self.showBkg and settings.bkgMode == wconstants.BKG_WEATHER:
            if self.nightTime:
                self.bkgCode = wutils.getNightBkg(cc["weather"][0]["icon"][:-1])
            elif self.iconNow == "32":
                if float(self.temp) >= wconstants.tempHigh[settings.disp_units]:
                    self.iconNow = "36"
                    self.bkgCode = "36"
                elif float(self.temp) <= wconstants.tempLow[settings.disp_units]:
                    self.bkgCode = "25"

        self.alert_start = ""
        self.alert_end = ""
        self.alert = None
        wind_speed = float(ff["wind_speed"] * wconstants.windScale[settings.disp_units])
        uvi = float(ff["uvi"])
        if "alerts" in w.keys() and w["alerts"][0]["end"] > cc["dt"]:
            self.alert_start = time.strftime("%H:%M", time.gmtime(w["alerts"][0]["start"] + self.WtzOffset))
            self.alert_end = time.strftime("%H:%M", time.gmtime(w["alerts"][0]["end"] + self.WtzOffset))
            self.alert = w["alerts"][0]["event"]
        elif wind_speed >= wconstants.WindHigh[settings.disp_units]:
            self.alert = settings.texts["121"] + \
                         " - " + str(wind_speed) + " " + wconstants.windSpeed[settings.disp_units]
        elif uvi >= wconstants.UVIHigh:
            self.alert = settings.texts["120"] + " " + \
                         settings.texts[str(wconstants.uviUnits[min(int(uvi), 11)])] + \
                         " - " + str(uvi)

        # No apparent way to detect if data has already been updated
        wUpdated = False
        self.wLastUpdate = self.temp + self.feels_like + self.iconNow + self.temptext + self.wind_speed + self.wind_dir + self.baro + self.humid
        if self.wPrevUpdate != self.wLastUpdate or force:
            self.wPrevUpdate = self.wLastUpdate
            wUpdated = True
            self.last = hmCurrent

            # Daily Forecasts
            i = 0
            j = 0
            current = int(time.strftime("%y%m%d"))
            while i < wconstants.NSUB and j < 8:
                day_data = w["daily"][j]
                if int(time.strftime("%y%m%d", time.gmtime(day_data["dt"]))) >= current:
                    self.day[i] = time.strftime("%A, %d", time.gmtime(day_data["dt"] + self.WtzOffset))
                    self.day[i] = time.strftime("%A", time.gmtime(day_data["dt"] + self.WtzOffset)) +\
                                  time.strftime(", %d", time.gmtime(day_data["dt"] + self.WtzOffset))
                    self.icon[i] = wutils.convert_weather_code(str(day_data["weather"][0]["id"]))
                    self.iconNight[i] = "na"
                    self.rain[i] = str(int(round(day_data["pop"] * 100 / 5, 0)) * 5)
                    self.temps[i][0] = str(int(day_data["temp"]["max"])) + wconstants.degree_sign
                    self.temps[i][1] = str(int(day_data["temp"]["min"])) + wconstants.degree_sign
                    i += 1
                j += 1

            # Hourly Forecasts
            i = 0
            j = 0
            while i < wconstants.hourly_number and j < 48:
                hour_data = w["hourly"][j]
                dt = hour_data["dt"]
                if dt > cc["dt"]:
                    self.hHours[i] = time.strftime("%H:%M", time.gmtime(dt + self.WtzOffset))
                    self.hTemps[i] = str(int(hour_data["temp"])) + wconstants.degree_sign
                    icon = wutils.convert_weather_code(str(hour_data["weather"][0]["id"]))
                    code = str(hour_data["weather"][0]["icon"])
                    if code[-1:] == "n":
                        icon = wutils.get_night_icons(icon)
                    self.hIcons[i] = icon
                    i += 1
                j += 1

        return wUpdated

    def show_weather(self):
        if settings.debug: print("SHOW_WEATHER", time.strftime("%H:%M:%S"))

        # Background (will take effect if weather background)
        self.display_bkg()

        # Current Conditions
        self.display_current_conditions()

        # Alerts
        self.display_alert()

        # Daily Forecasts
        self.data[wconstants.FF_DAILY] = {}
        for i in range(wconstants.NSUB):
            self.display_daily_forecasts(i)

        # Hourly Forecasts
        self.data[wconstants.FF_HOURLY] = {}
        for i in range(wconstants.hourly_number):
            self.display_hourly_forecasts(i)

        self.dataChanged.emit(self.data)
        self.data.pop(wconstants.BKG, False)
        self.data.pop(wconstants.CC, False)
        self.data.pop(wconstants.MOON, False)
        self.data.pop(wconstants.ALERT, False)
        self.data.pop(wconstants.FF_DAILY, False)
        self.data.pop(wconstants.FF_HOURLY, False)

    def display_current_conditions(self):
        if settings.debug: print("DISP_CURR", time.strftime("%H:%M:%S"))

        # PREPARE Current conditions Icon
        icon = self.iconNow
        folder = wconstants.ICON_FOLDER + settings.iconSet
        scale = self.iconScaleC
        drawMoonWIcon = False
        drawMoonPhase = settings.moonMode in (wconstants.MOON_ONCURRENT, wconstants.MOON_BOTH)
        if self.nightTime:
            icon = wutils.get_night_icons(self.iconNow)
            if drawMoonPhase and self.moon and icon != self.iconNow:
                icon = self.moon
                folder = wconstants.MOON_FOLDER
                scale = self.moonIconScale
                drawMoonPhase = False

                # Until you find a full set of night icons, mix moon + weather icons (if they don't include sun or moon)
                self.iconC2 = wutils.getMoonWIcons(self.iconNow)
                if self.iconC2 is not None:
                    drawMoonWIcon = True

        data = {}
        if drawMoonWIcon:
            data["icon_now_moon_icon"] = self.iconC2 + wconstants.ICON_EXT
            data["icon_now_moon_size"] = self.iconScaleC * 0.7

        if drawMoonPhase:
            self.prevMoon = self.moon
            self.data[wconstants.MOON] = {"moon_icon": self.moon + wconstants.ICON_EXT,
                                          "moon_icon_size": wconstants.sunsignIconSize * self.ymax / wconstants.REF_Y}
        elif settings.moonMode != wconstants.MOON_ONHEADER:
            self.prevMoon = ""
            self.data[wconstants.MOON] = {"moon_icon": "None"}

        data["icon_now"] = icon + wconstants.ICON_EXT
        data["icon_now_folder"] = folder
        data["icon_now_size"] = scale
        data["temp"] = self.temp
        data["temp_text"] = self.temptext
        data["updated"] = settings.texts["106"] + " " + self.last
        self.data[wconstants.CC] = data

        if settings.debug: print("DISP_OTHER", time.strftime("%H:%M:%S"))

        windchill = settings.texts["101"] + " " + self.feels_like
        windspeed = settings.texts["102"] + " " + (
                    "%.0f %s" % (float(self.wind_speed), wconstants.windSpeed[settings.disp_units]))
        winddir = settings.texts["103"] + " " + self.wind_dir
        self.data[wconstants.CC]["other_conds_1"] = windchill + "   " + windspeed + "   " + winddir

        barometer = settings.texts["104"] + " " + self.baro + wconstants.baroUnits[settings.disp_units]
        humidity = settings.texts["105"] + " " + self.humid + "%"
        uvi = "UVI " + settings.texts[str(wconstants.uviUnits[min(int(self.uvi), 11)])]
        self.data[wconstants.CC]["other_conds_2"] = barometer + "   " + humidity + "   " + uvi

    def display_alert(self):
        if settings.debug: print("DISP_ALERT", time.strftime("%H:%M:%S"))

        if self.alert is not None:
            prefix = ""
            if self.alert_start:
                prefix = self.alert_start + " - " + self.alert_end + ": "
            data = {"alert": prefix + self.alert,
                    "alert_color": settings.chighlight,
                    "alert_icon": wconstants.ALERT_ICON + wconstants.ICON_EXT,
                    "alert_icon_size": wconstants.alertIconSize * self.ymax / wconstants.REF_Y}
        else:
            data = {"alert": "None"}
        self.data[wconstants.ALERT] = data

    def display_daily_forecasts(self, subwin):
        if settings.debug: print("DISP_DAILY", time.strftime("%H:%M:%S"))

        crc = settings.clockc
        if int(self.rain[subwin]) >= wconstants.RainHigh:
            crc = settings.crcw
        elif int(self.rain[subwin]) >= 20:
            crc = settings.crcm

        data = {"ff_day_" + str(subwin + 1): self.day[subwin],
                "ff_" + str(subwin + 1) + "_img": self.icon[subwin] + wconstants.ICON_EXT,
                "ff_icon_size": self.iconScaleF,
                "ff_max_" + str(subwin + 1): self.temps[subwin][0],
                "ff_min_" + str(subwin + 1): self.temps[subwin][1],
                "ff_pop_" + str(subwin + 1): self.rain[subwin] + "%",
                "ff_pop_" + str(subwin + 1) + "_color": crc}
        self.data[wconstants.FF_DAILY].update(data)

    def display_hourly_forecasts(self, subwin):
        if settings.debug: print("DISP_HOURLY", time.strftime("%H:%M:%S"))

        data = {"fh_temp_"+str(subwin+1): self.hTemps[subwin]}
        if self.hIcons[subwin] != self.hIconPrev or subwin == 0:
            self.hIconPrev = self.hIcons[subwin]
            data["fh_"+str(subwin+1)+"_img"] = self.hIcons[subwin] + wconstants.ICON_EXT
            data["fh_icon_size"] = int(self.iconScaleF / 2)
        if subwin % 2 == 0:
            data["fh_time_"+str(subwin+1)] = self.hHours[subwin]
        self.data[wconstants.FF_HOURLY].update(data)

    def show_only_clock(self):
        self.data[wconstants.ONLY_CLOCK] = "True"
        self.display_bkg()
        self.dataChanged.emit(self.data)
        self.data.pop(wconstants.BKG, False)
        self.data.pop(wconstants.ONLY_CLOCK, False)

    @QtCore.pyqtSlot()
    def updateNewsStart(self):
        self.update_news_obj = UpdateNews()
        self.update_news_thread = QtCore.QThread()
        self.update_news_obj.moveToThread(self.update_news_thread)
        self.update_news_obj.newsUpdated.connect(self.onNewsUpdated)
        self.update_news_thread.start()

    @QtCore.pyqtSlot()
    def updateNewsStop(self):
        self.update_news_thread.requestInterruption()
        self.update_news_thread.quit()
        self.update_news_thread.wait()

    @QtCore.pyqtSlot(dict)
    def onNewsUpdated(self, data):
        if settings.debug: print("NEWS UPDATED", time.strftime("%H:%M:%S"))

        if "OK" in data.keys():
            n = data["OK"]
            hm = time.strftime('%H:%M')
            self.titlesHead = self.nsource + " " + hm + " | "
            self.titles = ""

            # Get news from RSS source and parse them into string variable
            if self.nsource == wconstants.NEWS_1:
                self.parse_rtve(n)
            elif self.nsource == wconstants.NEWS_2:
                self.parse_bbc(n)
            else:
                print("ERROR: Unknown News source. Unable to access/parse it. Check settings!")

        elif "KO" in data.keys():
            print("Error getting News from", self.nsource)
            print(data["KO"])

        if self.titles:
            self.show_news()

        if settings.alternSource:
            if self.nsource == wconstants.nsource2:
                self.nsource = wconstants.nsource1
                self.nURL = wconstants.nURL1 % settings.lang
            else:
                self.nsource = wconstants.nsource2
                self.nURL = wconstants.nURL2

    def update_news(self, nsource=None):
        if settings.debug: print("UPD_NEWS", time.strftime("%H:%M:%S"))

        if nsource:
            if nsource == wconstants.nsource1:
                self.nsource = wconstants.nsource1
                self.nURL = wconstants.nURL1
            elif nsource == wconstants.nsource2:
                self.nsource = wconstants.nsource2
                self.nURL = wconstants.nURL2

        QtCore.QMetaObject.invokeMethod(self.update_news_obj, 'updateNews', QtCore.Qt.QueuedConnection,
                                        QtCore.Q_ARG(str, self.nURL))

    def parse_rtve(self, n):
        if settings.debug: print("PARSE_RTVE", time.strftime("%H:%M:%S"))

        n = ET.fromstring(n)
        try:
            i = 0
            for item in n.findall('./page/items/com.irtve.plataforma.rest.model.dto.news.NewsDTO'):
                if i < wconstants.newsNumber:
                    self.titles += item.find('longTitle').text + settings.separator
                    i += 1
                else:
                    break

        except:
            print("Error parsing News from:", self.nsource)
            print(traceback.format_exc())

    def parse_bbc(self, n):
        if settings.debug: print("PARSE_BBC", time.strftime("%H:%M:%S"))

        n = ET.fromstring(n)
        try:
            i = 0
            for item in n.findall('./channel/item'):
                if i < wconstants.newsNumber:
                    self.titles += item.find('title').text + settings.separator
                    i += 1
                else:
                    break
        except:
            print("Error parsing News from:", self.nsource)
            print(traceback.format_exc())

    def show_news(self):
        if settings.debug: print("SHOW_NEWS", time.strftime("%H:%M:%S"))

        self.nCount = 0
        self.newsTimer.start(1000)
        self.showingNews = True
        data = {"nsource": self.titlesHead,
                "titles": self.titles}
        self.data[wconstants.NEWS] = data
        self.dataChanged.emit(self.data)
        self.data.pop(wconstants.NEWS, False)

    def check_news(self):

        if self.nCount < wconstants.nTime:
            self.nCount += 1
        else:
            self.newsTimer.stop()
            data = {"stop": True}
            self.showingNews = False
            self.data[wconstants.NEWS] = data
            self.dataChanged.emit(self.data)
            self.data.pop(wconstants.NEWS, False)

    def show_config(self):
        if not self.showingConfig:
            self.showingConfig = True
            if self.configRun is None:
                t = wconfig.WeatherConfig()
                self.configQuit = threading.Event()  # Using an event to effectively close thread
                self.configRun = threading.Thread(target=t.run, args=(self.configQuit, self.parent().pos().x(), self.parent().pos().y()))
            self.configRun.start()
            self.configTimer.start(1000)

    def check_config(self):

        if not self.configRun.is_alive():
            self.configTimer.stop()
            self.showingConfig = False
            self.configQuit.set()
            self.configRun.join()
            locIndex = 0
            for i, code in enumerate(settings.location):
                if code[1] == self.zip_code:
                    locIndex = i
                    break
            self.restart.emit(locIndex, self.nCount, self.nsource)

    def catchAction(self, event):

        if isinstance(event, QtGui.QCloseEvent):
            if self.configRun:
                self.configQuit.set()
                self.configRun.join()
                self.secTimer.stop()
                self.newsTimer.stop()
                self.configTimer.stop()

        if isinstance(event, QtGui.QKeyEvent):

            key = event.key()

            if key in (QtCore.Qt.Key_Q, QtCore.Qt.Key_Escape):
                if self.configRun:
                    self.configQuit.set()
                    self.configRun.join()
                    self.secTimer.stop()
                    self.newsTimer.stop()
                    self.configTimer.stop()

            elif "1" <= QtGui.QKeySequence(key).toString() <= str(len(settings.location)) and \
                    not settings.clockMode and self.keyP != key:
                # Change Weather Location (assigned to numbers) and show Weather
                locIndex = int(QtGui.QKeySequence(key).toString())
                self.user_clockMode = False
                self.location = settings.location[locIndex - 1][0]
                self.zip_code = settings.location[locIndex - 1][1]
                self.display_header()
                self.wLastUpdate = ""
                self.bkgCodePrev = None
                self.update_weather(firstRun=True)

            elif key in (QtCore.Qt.Key_A, QtCore.Qt.Key_B) and \
                    not settings.clockMode and self.keyP != key:
                # Select first (A) or second (B) News source and force update/showing News
                if key == QtCore.Qt.Key_A:
                    self.update_news(wconstants.nsource1)
                elif key == QtCore.Qt.Key_B:
                    self.update_news(wconstants.nsource2)
                self.update_news()

            elif key == QtCore.Qt.Key_S and not self.showingConfig:
                self.show_config()

            elif key == QtCore.Qt.Key_C:
                if self.user_clockMode:
                    # Back to Weather mode
                    self.user_clockMode = False
                    self.update_weather()
                else:
                    # World Clocks Mode (no weather)
                    self.user_clockMode = True
                    self.show_only_clock()

            self.keyP = key

    def run(self):

        self.show_all()


class UpdateWeather(QtCore.QThread):

    weatherUpdated = QtCore.pyqtSignal(dict, bool)

    def __init__(self, parent=None):
        QtCore.QThread.__init__(self, parent)

    @QtCore.pyqtSlot(str, bool)
    def updateWeather(self, url, firstRun=False):
        if settings.debug: print("UPD_WEATHER_TH", time.strftime("%H:%M:%S"))

        # Get Weather information from source
        try:
            with urllib.request.urlopen(url, timeout=settings.timeout) as response:
                # Decoding is needed only by arm-Linux, and only for JSON responses (not XML)
                wcc = json.loads(response.read().decode('utf8'))
                data = {"OK": wcc}
        except:
            tb_content = traceback.format_exc()
            data = {"KO": tb_content}

        self.weatherUpdated.emit(data, firstRun)

    def run(self):
        QtCore.QThread.run(self)


class UpdateNews(QtCore.QThread):

    newsUpdated = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        QtCore.QThread.__init__(self, parent)

    @QtCore.pyqtSlot(str)
    def updateNews(self, url):

        # Get news from RSS source and parse them into string variable
        try:
            # requests module returns obsolete info (caching?) for rtve API
            with urllib.request.urlopen(url, timeout=settings.timeout*2) as response:
                n = response.read()
                data = {"OK": n}
        except:
            tb_content = traceback.format_exc()
            data = {"KO": tb_content}

        self.newsUpdated.emit(data)

    def run(self):
        QtCore.QThread.run(self)


def sigint_handler(*args):
    # https://stackoverflow.com/questions/4938723/what-is-the-correct-way-to-make-my-pyqt-application-quit-when-killed-from-the-co
    app.closeAllWindows()


def exception_hook(exctype, value, tb):
    # https://stackoverflow.com/questions/56991627/how-does-the-sys-excepthook-function-work-with-pyqt5
    traceback_formated = traceback.format_exception(exctype, value, tb)
    traceback_string = "".join(traceback_formated)
    print(traceback_string, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    if "python" in sys.executable.lower():
        # This will allow to manage Ctl-C interruption (e.g. when running from IDE)
        signal.signal(signal.SIGINT, sigint_handler)
        timer = QtCore.QTimer()
        timer.start(500)
        timer.timeout.connect(lambda: None)
        # This will allow to show some tracebacks (not all, anyway)
        sys._excepthook = sys.excepthook
        sys.excepthook = exception_hook
    win = Window()
    win.show()
    try:
        app.exec_()
    except:
        pass
