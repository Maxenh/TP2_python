import maya.cmds as cmds
import sys
import json
import os

from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QMainWindow, QWidget, QLineEdit, QVBoxLayout, QPushButton, QLabel
from functools import wraps

def ctrl_z(name):
    def decorator(func): #le decorator permet d'ajouter des commandes supplémentaire a des raccourcis si je comprend bien
        @wraps(func)
        def wrapp(*args, **kwargs): #chunk semble indiquer une liste de ce qui peut etre Undo
            cmds.undoInfo(openChunk=True, chunkName=name)
            try:
                return func(*args, **kwargs)
            finally: 
                cmds.undoInfo(closeChunk=True)
        return wrapp
    return decorator

class Window(QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Organize the Outliner")
        self.resize(500,100)

        self.targets = [] #cree la selection des objets, mais ne l'assigne que dans les def
        self.selection= False
        
        self.match_avec_JSON = []
        #garde en mémoire les valeurs de couleur loader par le JSON 
        self.initial_colors = {}
        self.colors ={}
        self.colors_enabled = False

        #garde en mémoire l'ordre initial des objets du outliner
        self.intial_order = {}
        self.sort_enabled =False

        self.json_path = QLineEdit("Add your JSON path here")

         #créer le bouton pour appliquer la couleur
        self.toggle_button = QPushButton("Apply Colors: OFF")
        self.toggle_button.setEnabled(False)

        #créer le bouton pour organisé les éléments du outliner
        self.croissant_button = QPushButton("Croissant: OFF")
        self.croissant_button.setEnabled(False)

        #créer le bouton pour la sélection
        self.selection_button =QPushButton("Apply to Selection Only: OFF")

        layout = QVBoxLayout()
        layout.addWidget(self.json_path)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.croissant_button)
        layout.addWidget(self.selection_button)
        self.setLayout(layout)

        #creation des actions dans le organize the outliner box
        self.json_path.returnPressed.connect(self.open_json)
        self.toggle_button.clicked.connect(self.toggle_colors)
        self.croissant_button.clicked.connect(self.toggle_croissant)
        self.selection_button.clicked.connect(self.toggle_selection)

        
        
    def open_json(self):
        path = self.json_path.text()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.colors = json.load(f)
                
            print("JSON ouvert: ", self.colors)

        except (OSError, json.JSONDecodeError) as e:
            print("Erreur de lecture du ficher JSON :", e)
            return

        object_count = 0
#verifie si les valeurs écrites dans le JSON sont valide 
        for prefix, color in self.colors.items(): 

            if not isinstance(color, (list, tuple)) or len(color) != 3:
                print("La couleur n'est pas valide :", prefix, color)
                continue

            
            #cherche dans le outliner de maya les items qui ont le meme prefix que dans le JSON et les stockent dans objects
            objects = cmds.ls(prefix + "*", type="transform", long=True) or []

            self.match_avec_JSON.extend(objects)

            
            print(f"{prefix} : {len(objects)} objet trouvé")

            #applique la couleur 
            for obj in objects:
                try:
                    cmds.setAttr(obj + ".useOutlinerColor", True)
                    cmds.setAttr(obj + ".outlinerColor", *color)

                    object_count += 1
                    print("Couleur appliquée :", obj)

                except RuntimeError as e:
                    print("Erreur sur", obj, ":", e)
    
        self.colors_enabled = True
        self.toggle_button.setText("Apply Colors: ON")
        self.toggle_button.setEnabled(True)
        self.sort_enabled = True
        self.croissant_button.setText("Ascending Order: OFF")
        self.croissant_button.setEnabled(True)
        
    @ctrl_z("Toggle Outliner Colors")
    def toggle_colors(self): #on off de la couleur et du text du bouton

        self.update_target()
        
        #permet le toggle on off des valeurs
        self.colors_enabled = not self.colors_enabled
        print(self.colors_enabled)
        

        if self.colors_enabled:
            self.toggle_button.setText("Apply Colors: ON")
            for obj in self.targets:

                    try: 
                        cmds.setAttr(obj+ ".useOutlinerColor", True)
                    except RuntimeError as e:
                        print("Erreur sur", obj, ":", e)
        else:
            print("Made to else")
            self.toggle_button.setText("Apply Colors: OFF")
            for obj in self.targets:
                try:
                    cmds.setAttr(obj + ".useOutlinerColor", False)
                    
                    print(obj, cmds.getAttr(obj+".outlinerColor"))


                except RuntimeError as e:
                    print("Erreur du reset de couleur sur",obj,":",e)

    @ctrl_z("Toggle Croissant")        
    def toggle_croissant(self):
        self.update_target()
        #si le JSON ne fonctionne pas, on ne fait pas les prochaines actions
        if not self.match_avec_JSON:
            return

        targets = self.targets

#créer une liste qui permet de conserver la hiérarchie dans maya
        groups ={}
        for obj in targets:
            parents = cmds.listRelatives(
                obj, parent=True, fullPath=True
            ) or []

            parent= parents[0] if parents else None
            groups.setdefault(parent, set()).add(obj)

        if not self.sort_enabled:
            self.intial_order ={}
            for parent, targets_in_group in groups.items():
                children = (
                    cmds.listRelatives(
                        parent, children=True, type="transform", fullPath=True
                    ) or []
                    if parent else
                    cmds.ls(assemblies=True, long=True) or []
                )

            #fait le tri en ordre croissant rsplit("|",1) permet de couper le chemin a la derniere partie et -1 conserve la derniere partie
                self.intial_order[parent] = children[:]
                ordered = iter(sorted(
                    targets_in_group, key=lambda obj: obj.rsplit("|", 1)[-1].casefold() #casefold = maj ou min pas d'influence
                ))

            #permet de laissé les items qui ne sont pas dans le JSON, a leur place.
                desired = [
                    next(ordered) 
                    if obj in targets_in_group 
                    else obj
                    for obj in children
                ]

                for obj in reversed(desired):
                    cmds.reorder(obj, front=True)

            self.sort_enabled = True
            self.croissant_button.setText("Ascending Order: ON")
        else:
            for parent, original in self.intial_order.items():
                for obj in reversed(original):
                    if cmds.objExists(obj):
                        cmds.reorder(obj, front=True)
            self.sort_enabled = False
            self.croissant_button.setText("Ascending Order: OFF")

    def update_target(self): #fonction utiliser dans presque tous les def, permet de mettre a jour la selection d'objets
        if self.selection:
            
            self.targets = cmds.ls(selection=True, type="transform", long=True) or []
        else:
            
            self.targets = cmds.ls(type="transform", long=True) or []
        print("target:",self.targets)

    @ctrl_z("Toggle Selection")
    def toggle_selection(self): #toggle seulement le texte du bouton
        self.selection = not self.selection

        if self.selection:
            self.selection_button.setText("Apply to Selection Only: ON")
        else:
            self.selection_button.setText("Apply to Selection Only: OFF")

        self.update_target()

    def selections(self): #fait le calcul du toggle_selection et applique les objets selectionner au targets variable.
        targets = set(self.match_avec_JSON)
        if not self.selection:
            return targets
        selected = set(cmds.ls(selection=True, long=True)or [])
        return targets.intersection(selected)

window = Window()
window.show()
