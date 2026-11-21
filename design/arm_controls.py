"""FreeCAD live joint panel. Geometry and expressions remain usable without this panel."""
from pathlib import Path
import runpy
import FreeCAD as App, FreeCADGui as Gui
from PySide import QtCore, QtWidgets
ROOT=Path(__file__).resolve().parent
path=str(ROOT/'MG995_5DOF_Movable.FCStd')
doc=next((d for d in App.listDocuments().values() if d.getObject('JointControls')),None)
if doc is None:doc=App.openDocument(path)
App.setActiveDocument(doc.Name)
jac_api=runpy.run_path(str(ROOT/'arm_kinematics.py'))
mw=Gui.getMainWindow()
old=mw.findChild(QtWidgets.QDockWidget,'MG995JointPanel')
if old:mw.removeDockWidget(old);old.deleteLater()
dock=QtWidgets.QDockWidget('MG995 Arm - joint controls',mw);dock.setObjectName('MG995JointPanel')
panel=QtWidgets.QWidget();layout=QtWidgets.QVBoxLayout(panel)
label=QtWidgets.QLabel('Five arm joints + gripper\nDrag a slider or enter an angle.');label.setWordWrap(True);layout.addWidget(label)
rows={}
specs=[('BaseYaw','1  Base yaw',-80,80),('ShoulderPitch','2  Shoulder pitch',15,95),('ElbowPitch','3  Elbow pitch',-85,85),('WristPitch','4  Wrist pitch',-55,55),('WristRoll','5  Wrist roll',-80,80),('GripperOpening','6  Gripper opening',0,35)]
updating=False
def apply(name,value):
    global updating
    if updating:return
    updating=True
    try:
        slider,spin=rows[name];slider.setValue(round(value*10));spin.setValue(value)
        setattr(doc.JointControls,name,float(value));doc.recompute();refresh_jacobian();Gui.updateGui()
    finally:updating=False
for name,title,lo,hi in specs:
    layout.addWidget(QtWidgets.QLabel(title))
    row=QtWidgets.QHBoxLayout();slider=QtWidgets.QSlider(QtCore.Qt.Horizontal);slider.setRange(lo*10,hi*10)
    spin=QtWidgets.QDoubleSpinBox();spin.setRange(lo,hi);spin.setDecimals(1);spin.setSuffix(' deg');spin.setSingleStep(1)
    value=getattr(doc.JointControls,name).Value;slider.setValue(round(value*10));spin.setValue(value)
    rows[name]=(slider,spin);row.addWidget(slider,1);row.addWidget(spin);layout.addLayout(row)
    slider.valueChanged.connect(lambda v,k=name:apply(k,v/10));spin.valueChanged.connect(lambda v,k=name:apply(k,v))
layout.addSpacing(10)
presets=QtWidgets.QComboBox();presets.addItems(['Choose pose...','Home','Raised','Reach','Folded'])
poses={'Home':[0,55,-65,20,0,16],'Raised':[0,85,-45,0,0,16],'Reach':[0,25,-10,0,0,10],'Folded':[0,85,-85,-35,0,0]}
def set_pose(text):
    if text in poses:
        for (name,*_),value in zip(specs,poses[text]):apply(name,value)
presets.currentTextChanged.connect(set_pose);layout.addWidget(presets)
mount=QtWidgets.QComboBox();mount.addItems(['Desk base','Chassis adapter'])
mount.setCurrentIndex(0 if doc.JointControls.AdapterThickness.Value>7 else 1)
def set_mount(index):
    desk=index==0
    doc.Desk_Adapter.Visibility=desk;doc.DeskMount.Visibility=desk
    doc.Chassis_Adapter.Visibility=not desk;doc.ChassisMount.Visibility=not desk
    doc.JointControls.AdapterThickness=8 if desk else 6;doc.recompute()
mount.currentIndexChanged.connect(set_mount);layout.addWidget(mount)
show=QtWidgets.QCheckBox('Show servos and purchased hardware');show.setChecked(True)
def show_refs(visible):
    for obj in doc.Objects:
        if obj.Name.startswith('Ref_') and obj.Name!='Ref_Tool_reference':obj.Visibility=visible
show.toggled.connect(show_refs);layout.addWidget(show)
buttons=QtWidgets.QHBoxLayout();fit=QtWidgets.QPushButton('Fit view');save=QtWidgets.QPushButton('Save pose')
fit.clicked.connect(lambda:Gui.activeDocument().activeView().fitAll());save.clicked.connect(lambda:doc.save())
buttons.addWidget(fit);buttons.addWidget(save);layout.addLayout(buttons)
jac_label=QtWidgets.QLabel();jac_label.setWordWrap(True);layout.addWidget(jac_label)
def current_jacobian():
    return jac_api['evaluate'](jac_api['model_from_document'](doc),[getattr(doc.JointControls,k).Value for k in jac_api['JOINT_PROPERTIES']])
def refresh_jacobian():
    result=current_jacobian();singular=result['position']['rank']<3 or result['five_joint_geometric']['rank']<5
    condition=max(result['position']['condition_number'] or float('inf'),result['five_joint_geometric']['condition_number'] or float('inf'))
    text=jac_api['status_text'](result)
    if singular:text+='\nSingular configuration'
    elif condition>200:text+='\nNear singular (scaled condition > 200)'
    jac_label.setText(text);jac_label.setStyleSheet('color: %s; font-weight: bold;'%('#b42318' if singular else '#986000' if condition>200 else '#167044'))
def jacobian_details():
    result=current_jacobian();position=', '.join('%.3f'%v for v in result['tcp_world_mm'])
    matrix='\n'.join(' '.join('%10.4f'%v for v in row) for row in result['J0_rows_vx_vy_vz_wx_wy_wz'])
    msg=QtWidgets.QMessageBox(mw);msg.setWindowTitle('Base-frame J0 check')
    msg.setText(jac_api['status_text'](result)+'\nTCP XYZ (mm): '+position)
    msg.setInformativeText('Five arm joints; gripper opening excluded. Linear rows use mm/rad.\nThe 6 x 5 matrix has no determinant. Rank loss indicates singularity.\nUse Show Details for J0 and singular values.')
    msg.setDetailedText('Columns: yaw, shoulder, elbow, wrist pitch, wrist roll\nRows: vx, vy, vz, wx, wy, wz\n\n'+matrix+'\n\nXYZ singular values (mm/rad):\n'+str(result['position']['singular_values_mm_per_rad'])+'\n\nFull singular values (linear rows / 359mm):\n'+str(result['five_joint_geometric']['singular_values']))
    msg.exec_()
jac_button=QtWidgets.QPushButton('Jacobian details');jac_button.clicked.connect(jacobian_details);layout.addWidget(jac_button)
refresh_jacobian()
note=QtWidgets.QLabel('Preview controls only. Parts can pass through one another; contact limits are not enforced.');note.setWordWrap(True)
layout.addWidget(note);layout.addStretch();dock.setWidget(panel);dock.setMinimumWidth(330)
mw.addDockWidget(QtCore.Qt.RightDockWidgetArea,dock);dock.show()
if Gui.activeDocument():
    Gui.activeDocument().activeView().viewAxonometric();Gui.activeDocument().activeView().fitAll()
# Keep references for FreeCAD's macro lifetime and allow a second invocation to replace the panel.
App.MG995ArmPanel=dock
