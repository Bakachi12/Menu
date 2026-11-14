import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QEvent,QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QScrollArea,QPushButton
from desplazamiento import DesplazamientoGlobal

class AndroidTouchTest(unittest.TestCase):
    def test_synthesized_drag_scrolls_without_clicking_button(self):
        app=QApplication.instance() or QApplication([])
        with patch.dict(os.environ,{'MENU_ANDROID_TEST':'1'}):
            window=QWidget();layout=QVBoxLayout(window)
            area=QScrollArea();area.setWidgetResizable(True);layout.addWidget(area)
            content=QWidget();content.setMinimumHeight(1200)
            button=QPushButton('Producto',content);button.setGeometry(10,200,180,70)
            area.setWidget(content);window.resize(300,500);window.show();app.processEvents()
            drag=DesplazamientoGlobal(window);clicks=[];button.clicked.connect(lambda:clicks.append(1))
            start=button.mapToGlobal(button.rect().center())
            def send(kind,offset,buttons):
                global_pos=QPointF(start.x(),start.y()+offset)
                local=global_pos-QPointF(button.mapToGlobal(button.rect().topLeft()))
                event=QMouseEvent(kind,local,local,global_pos,Qt.MouseButton.LeftButton if kind!=QEvent.Type.MouseMove else Qt.MouseButton.NoButton,buttons,Qt.KeyboardModifier.NoModifier,Qt.MouseEventSource.MouseEventSynthesizedByQt)
                QApplication.sendEvent(button,event)
            send(QEvent.Type.MouseButtonPress,0,Qt.MouseButton.LeftButton)
            send(QEvent.Type.MouseMove,-120,Qt.MouseButton.LeftButton)
            send(QEvent.Type.MouseButtonRelease,-120,Qt.MouseButton.NoButton)
            self.assertGreater(area.verticalScrollBar().value(),80)
            self.assertEqual(clicks,[])
            drag.desactivar();window.close();window.deleteLater();app.processEvents()
