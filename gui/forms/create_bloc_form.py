import re
import os 
from qgis.PyQt import uic 
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QGridLayout, QDialog, QWidget, QTableWidgetItem, QDialogButtonBox, QCompleter
from qgis.core import QgsAttributeEditorField as attrfield, Qgis, QgsProject, QgsVectorLayer, QgsDefaultValue, QgsAttributeEditorContainer, QgsRelation, QgsRelationContext
from ...service import get_service
from ...database.version import __version__
from ...database.create_bloc import write_sql_bloc, load_custom
from ...qgis_utilities import tr, Alias, QGisProjectManager as manager
from ...project import Project
from ...utility.json_utils import open_json, get_propertie, save_to_json, add_dico
from ...utility.string import normalized_name

Formules_de_base = []
Input_de_base = {}
_custom_qml_dir = os.path.join(os.path.expanduser('~'), '.cycle', 'qml')
if not os.path.exists(_custom_qml_dir):
    os.makedirs(_custom_qml_dir)

class CreateBlocWidget(QDialog):
    
    def __init__(self, project_name, log_manager, parent=None):
        QDialog.__init__(self, parent)
        current_dir = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_dir, "create_bloc.ui"), self)
        
        self.__log_manager = log_manager
        self.__project = Project(project_name, self.__log_manager)
        self.__project_name = project_name
        
        self.geom.addItems(['Point', 'LineString', 'Polygon'])       
        self.type_list = self.__project.fetchall("select table_name from information_schema.tables where table_schema = 'api' and table_name like '%_type_table'")
        for k in range(len(self.type_list)) : 
            self.type_list[k] = self.type_list[k][0].replace('_type_table', '')
        self.type_list = ['real', 'integer', 'list'] + self.type_list
        self.entree_type.addItems(self.type_list)
        # 2 = output
        self.sortie_type.addItems(self.type_list)
        self.possible_values_text.setEnabled(False)
        self.possible_values_text2.setEnabled(False)
        
        self.input = {key : Input_de_base[key] for key in Input_de_base}
        self.output = {}
        self.formula = Formules_de_base[:]
        self.formula_description = {}
        self.default_values = {}
        self.possible_values = {}
        self.other_types = {}
        
        # Input tab
        self.entree_type.currentIndexChanged.connect(self.__update_entree_type)
        self.add_input.clicked.connect(self.__add_input)
        self.delete_input.clicked.connect(self.__delete_input)
        
        self.table_input.setRowCount(len(self.input))
        i = 0
        for key, value in self.input.items():
            self.table_input.setItem(i, 0, QTableWidgetItem(key))
            self.table_input.setItem(i, 1, QTableWidgetItem(value))
            self.table_input.setItem(i, 2, QTableWidgetItem('Null'))
            i+=1

        # Output tab
        self.sortie_type.currentIndexChanged.connect(self.__update_sortie_type)
        self.add_output.clicked.connect(self.__add_output)
        self.delete_output.clicked.connect(self.__delete_output)
        
        # Formula tab
        self.add_formula.clicked.connect(self.__add_formula)
        self.warning_formula.setStyleSheet("color: orange")
        self.warning_formula.setText('Enter the formula in the form of "A = B [+-*/^] 10*C==\'elem of list\' ..." \n where A, B, C are the names of the input or output')
        self.delete_formula.clicked.connect(self.__delete_formula)
        self.completer_list = list(self.input.keys()) + list(self.output.keys())
        self.completer = FormulaCompleter(self.completer_list)
        self.formula_text.setCompleter(self.completer)
        self.completer.setFilterMode(Qt.MatchContains)
        
        self.formula_list = self.__project.fetchall("select name from api.formulas")
        self.formula_list = [name[0] for name in self.formula_list]
        self.formula_name_completer = QCompleter(self.formula_list)
        self.formula_list = set(self.formula_list)
        self.description.setCompleter(self.formula_name_completer) 
        self.description.textChanged.connect(self.__is_known_formula)
        
        # Group line edit
        layertree_custom = manager.layertree_custom(self.__project.qgs)
        layertree = manager.layertree()
        layertree = add_dico(layertree, layertree_custom)
        self.group_completer = GrpCompleter(list(layertree.keys()), layertree)
        self.group.setCompleter(self.group_completer)
        self.group.textChanged.connect(lambda : self.group_completer.update_completions(self.group.text()))
        
        # Copy other blocs 
        
        b_types = self.__project.fetchall("select b_type from api.input_output group by b_type")
        b_types = [b_type[0] for b_type in b_types]
        self.combo_bloc.addItems([''] + b_types)
        self.combo_bloc.currentIndexChanged.connect(self.__copy_bloc)
        
        # Ok button
        existing_bloc = self.__project.fetchall("select table_name from information_schema.tables where table_schema = 'api' and table_name like '%_bloc'")
        existing_bloc = set([bloc[0].replace('_bloc', '') for bloc in existing_bloc])
        self.bloc_name.textChanged.connect(lambda _ : self.enable_ok_button(existing_bloc))
        self.ok_button = self.buttons.button(QDialogButtonBox.Ok)
        self.ok_button.setEnabled(False)   
        self.ok_button.clicked.connect(self.__create_bloc)
        print(self.__dict__)
        self.exec_()
    
    def __add_formula(self):
        formula = self.formula_text.text()
        description = self.description.text()
        detail = self.detail_level.value()
        if self.verify_formula(formula):
            formula = formula.lower()
            self.formula.append(formula)
            self.formula_description[formula] = [self.description.text(), self.comment.toPlainText(), detail]
            self.table_formula.setRowCount(len(self.formula))
            print(formula, description)
            self.table_formula.setItem(len(self.formula)-1, 0, QTableWidgetItem(formula))
            self.table_formula.setItem(len(self.formula)-1, 1, QTableWidgetItem(str(detail)))
            self.table_formula.setItem(len(self.formula)-1, 2, QTableWidgetItem(description))
            self.formula_text.clear()
            self.description.clear()
            self.comment.clear()
    
    def  __is_known_formula(self):
        if self.description.text() in self.formula_list:
            formula_info = self.__project.fetchone(f"select formula, detail_level, comment from api.formulas where name = '{self.description.text()}'")
            self.formula_text.setText(formula_info[0])
            self.detail_level.setValue(formula_info[1])
            self.comment.setPlainText(formula_info[2])
            
            
    
    def verify_formula(self, formula):
        # Faudra vérifier les formules sur le point de vue synthax.
        return True
    
    def __delete_formula(self):
        items = self.table_formula.selectedItems()
        if len(items)>0:
            selected_row = self.table_formula.row(items[0])
            self.formula.remove(self.table_formula.item(selected_row, 0).text())
            del self.formula_description[self.table_formula.item(selected_row, 0).text()]
            self.table_formula.removeRow(selected_row)
    
    def __update_entree_type(self):
        type_ = self.entree_type.currentText()
        if type_ == 'list':
            self.possible_values_text.setEnabled(True)
            self.warning_input.setText('Enter the possible values separated by a semicolon')
            self.warning_input.setStyleSheet("color: orange; font-weight: bold")
        elif type_ != 'real' and type_ != 'integer':
            self.possible_values_text.setEnabled(False)
            self.warning_input.clear()
            self.entree_name.setText(type_)
        else:
            self.possible_values_text.setEnabled(False)
            self.warning_input.clear()
            
    def __add_input(self):
        name = self.entree_name.text()
        type_ = self.entree_type.currentText()
        default_value = self.entree_default_value.text()
        if self.entree_type.currentText() == 'list':
            possible_values = self.possible_values_text.text()
        else : possible_values = ''
        name, type_, default_value, possible_values, verified = self.verify_input(name, type_, default_value, possible_values)
        if verified:
            self.completer_list.append(name)
            self.completer.update_words(self.completer_list)
            self.input[name] = type_
            if type_ not in ['real', 'integer', 'list']:
                self.other_types[name] = type_
            self.default_values[name] = default_value
            self.possible_values[name] = possible_values
            
            self.table_input.setRowCount(len(self.input))
            self.table_input.setItem(len(self.input)-1, 0, QTableWidgetItem(name))
            self.table_input.setItem(len(self.input)-1, 1, QTableWidgetItem(type_))
            self.table_input.setItem(len(self.input)-1, 2, QTableWidgetItem(default_value))
            self.table_input.setItem(len(self.input)-1, 3, QTableWidgetItem(str(possible_values)))
        
            # clear the input fields
            self.entree_name.clear()
            self.entree_default_value.clear()
            self.possible_values_text.clear()
    
    def verify_input(self, name, type_, default_value, possible_values):
        # Faudra vérifier le format des données rentrées pour éviter tout problème 
        if possible_values :
            possible_values = possible_values.split(';')
            possible_values = [value.strip() for value in possible_values]
        return normalized_name(name).strip(), type_, default_value, possible_values, True
    
    
    def __delete_input(self):
        items = self.table_input.selectedItems()
        if len(items)>0:
            selected_row = self.table_input.row(items[0])
            del self.input[self.table_input.item(selected_row, 0).text()]
            if self.table_input.item(selected_row, 0).text() in self.completer_list :
                self.completer_list.remove(self.table_input.item(selected_row, 0).text())
            self.completer.update_words(self.completer_list)
            self.table_input.removeRow(selected_row)

    def __update_sortie_type(self):
        type_ = self.sortie_type.currentText()
        if type_ == 'list':
            self.possible_values_text2.setEnabled(True)
            self.warning_output.setText('Enter the possible values separated by a semicolon')
            self.warning_output.setStyleSheet("color: orange; font-weight: bold")
        elif type_ != 'real' and type_ != 'integer':
            self.possible_values_text2.setEnabled(False)
            self.warning_input.clear()
            self.sortie_name.setText(type_)
        else:
            self.possible_values_text2.setEnabled(False)
            self.warning_output.clear()
    
    def __add_output(self):
        name = self.sortie_name.text()
        type_ = self.sortie_type.currentText()
        default_value = self.sortie_default_value.text()
        if self.sortie_type.currentText() == 'list':
            possible_values = self.possible_values_text2.text()
        else : possible_values = ''
        name, type_, default_value, possible_values, verified = self.verify_input(name, type_, default_value, possible_values)
        if verified:
            self.completer_list.append(name)
            self.completer.update_words(self.completer_list)
            
            self.default_values[name] = default_value
            self.possible_values[name] = possible_values
            self.output[name] = type_
            if type_ not in ['real', 'integer', 'list']:
                self.other_types[name] = type_
                
            self.table_output.setRowCount(len(self.output))
            self.table_output.setItem(len(self.output)-1, 0, QTableWidgetItem(name))
            self.table_output.setItem(len(self.output)-1, 1, QTableWidgetItem(type_))
            self.table_output.setItem(len(self.output)-1, 2, QTableWidgetItem(default_value))
            self.table_output.setItem(len(self.output)-1, 3, QTableWidgetItem(str(possible_values)))
        
            # clear the input fields
            self.sortie_name.clear()
            self.sortie_default_value.clear()
            self.possible_values_text2.clear()
    
    def __delete_output(self):
        items = self.table_output.selectedItems()
        if len(items)>0:
            selected_row = self.table_output.row(items[0])
            del self.output[self.table_output.item(selected_row, 0).text()]
            if self.table_output.item(selected_row, 0).text() in self.completer_list :
                self.completer_list.remove(self.table_output.item(selected_row, 0).text())
            self.completer.update_words(self.completer_list)
            self.table_output.removeRow(selected_row)
    
    def enable_ok_button(self, bloc_exists): 
        bloc_name = self.bloc_name.text()
        if bloc_name in bloc_exists:
            self.warning_bloc.setText('This bloc already exists')
            self.warning_bloc.setStyleSheet("color: red")
            self.ok_button.setEnabled(False)    
        elif bloc_name != '' : 
            self.warning_bloc.clear()
            self.ok_button.setEnabled(True)
        elif bloc_name == '' : 
            self.warning_bloc.setText('Enter a name for the bloc')
            self.warning_bloc.setStyleSheet("color: orange")
            self.ok_button.setEnabled(False)
      
          
    # def normalize_name(self, name):
    #     # Faudra normaliser le nom pour éviter les problèmes
    #     char_to_remove = ["'", '"', '(', ')', '[', ']', '{', '}', '<', '>', '!', '?', '.', ',', ';', ':', '/', '\\', '|', '@', '#', '$', '%', '^', '&', '*', '+', '=', '~', '`']
    #     #return name.replace(' ', '_').translate(None, ''.join(char_to_remove))
    #     rx = '[' + re.escape(''.join(char_to_remove)) + ']'
    #     return re.sub(rx, '', name).strip().replace(' ', '_')
    
    def __copy_bloc(self):
        b_type = self.combo_bloc.currentText()
        if not b_type : 
            return 
        query_inp = f"""
        with inp_out as (select inputs, outputs from api.input_output 
        where b_type = '{b_type}')
        select data_type as inp_type, column_name as inp_col from information_schema.columns, inp_out
        where table_schema = 'api' and table_name='{b_type}_bloc'
        and column_name = any(inp_out.inputs)
        """
        query_out = f"""
        with inp_out as (select inputs, outputs from api.input_output 
        where b_type = '{b_type}')
        select data_type as out_type, column_name as out_col from information_schema.columns, inp_out
        where table_schema = 'api' and table_name='{b_type}_bloc'
        and column_name = any(inp_out.outputs)
        """
        query_default = f"""
        select jsonb_object_agg(column_name, column_default) from information_schema.columns
        where table_schema='api' and table_name='{b_type}_bloc'
        """
        defaults= self.__project.fetchone(query_default)[0]
        print(defaults)
        values_inp = self.__project.fetchall(query_inp)
        values_out = self.__project.fetchall(query_out)
        for val in values_inp:
            v = val[0]
            if val[0] != 'integer' or val[0] != 'real' or val[0] != 'list':
                v = val[0].replace('_type', '')
            self.input[val[1]] = v
        for val in values_out:
            v = val[0]
            if val[0] != 'integer' or val[0] != 'real' or val[0] != 'list':
                v = v.replace('_type', '')
            self.output[val[1]] = v
        
        self.table_input.setRowCount(len(self.input))
        i = 0
        for key, value in self.input.items():
            self.table_input.setItem(i, 0, QTableWidgetItem(key))
            self.table_input.setItem(i, 1, QTableWidgetItem(value))
            if defaults.get(key) : 
                if '::' in defaults[key]:
                    # (value)::type
                    self.default_values[key] = defaults[key].split(':')[0][1:-1]
                else : 
                    self.default_values[key] = defaults[key]
                self.table_input.setItem(i, 2, QTableWidgetItem(self.default_values[key]))
            i += 1
            
        self.table_output.setRowCount(len(self.output))
        i = 0
        for key, value in self.output.items():
            self.table_output.setItem(i, 0, QTableWidgetItem(key))
            self.table_output.setItem(i, 1, QTableWidgetItem(value))
            if defaults.get(key) : 
                self.default_values[key] = defaults[key]
                self.table_output.setItem(i, 2, QTableWidgetItem(defaults[key]))
            i += 1
        
        query_formula = f"""
        with f_names as (select default_formulas from api.input_output where b_type = '{b_type}')
        select name, formula, detail_level, comment from api.formulas, f_names where name = any(default_formulas) ;
        """
        formulas = self.__project.fetchall(query_formula)
        for f in formulas:
            self.formula.append(f[1])
            self.formula_description[f[1]] = [f[0], f[3], f[2]]
        
        self.table_formula.setRowCount(len(self.formula))
        i = 0
        for f in self.formula:
            self.table_formula.setItem(i, 0, QTableWidgetItem(f))
            self.table_formula.setItem(i, 1, QTableWidgetItem(str(self.formula_description[f][2])))
            self.table_formula.setItem(i, 2, QTableWidgetItem(self.formula_description[f][0]))
            i += 1
        
        
    def __create_bloc(self):
        """
        Utilise toutes les informations rentrées pour créer définir un blocs dans la base de données 
        à l'aide de la fonction `write_sql_bloc`, 
        puis initialise la couche comme dans `qgis_utilities`.
        """
        
        self.default_values['shape'] = self.geom.currentText()
        
        layer_name = self.bloc_name.text()
        
        norm_name = normalized_name(self.bloc_name.text())
        
        # create db bloc and load it
        sql_path = os.path.join(self.__project.directory, 'custom_blocs.sql')
        query = write_sql_bloc(self.__project_name, norm_name, self.geom.currentText(), self.input, self.output, self.default_values, 
                       self.possible_values, f'{norm_name}_bloc', self.formula, self.formula_description, path=sql_path)
        print("bonjour1")
        load_custom(self.__project_name, query=query)
        print("bonjour 2")
        
        # add layer to qgis
        # Faudra tester tout ça dans un script à part je pense 
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        
        grp_path = self.group.text()
        grps = grp_path.split('/')
        grp = ''
        while grp == '' and grps:
            grp = grps.pop(-1)
        
        if grps : root = root.findGroup(grps[-1]) 
        
        if grp == '' : g = root
        else : g = root.findGroup(grp) or root.insertGroup(0, grp) # On changera sûrement l'index plus tard
        
        sch, tbl, key = "api", f'{norm_name}_bloc', 'name'
        uri = f'''dbname='{self.__project_name}' service={get_service()} sslmode=disable key='{key}' checkPrimaryKeyUnicity='0' table="{sch}"."{tbl}" ''' + ' (geom)'
        print(uri)
        layer = QgsVectorLayer(uri, layer_name, "postgres")
        project.addMapLayer(layer, False)
        g.addLayer(layer)
        if not layer.isValid():
            raise RuntimeError(f'layer {layer_name} is invalid')
        
        # load qml styling file to the layer and rearrange the style with the entrees and sorties
        qml_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'ressources', 'qml')
        if self.geom.currentText() == 'Point':
            qml_file = os.path.join(qml_dir, 'point.qml')
        elif self.geom.currentText() == 'LineString':
            qml_file = os.path.join(qml_dir, 'linestring.qml')
        elif self.geom.currentText() == 'Polygon':
            qml_file = os.path.join(qml_dir, 'polygon.qml')

        layer.loadNamedStyle(qml_file)
        
        fields = layer.fields()
        config = layer.editFormConfig()
        config.setLayout(config.EditorLayout(1))
        tabs = config.tabs()
        input_tab = tabs[-2]
        output_tab = tabs[-1]
        idx = 0
        default_values = self.__project.fetchone(f"select jsonb_object_agg(column_name, column_default) from information_schema.columns where table_schema='api' and table_name='{norm_name}_bloc'")[0]
        dico_ref = {}
        for field in fields:
            defval = QgsDefaultValue()
            fieldname = field.name()
            if fieldname.strip() == 'model' : 
                defval.setExpression('@current_model')
                layer.setDefaultValueDefinition(idx, defval) 
                
            if fieldname.strip() in self.input:
                if fieldname.strip() in self.possible_values and self.possible_values[fieldname.strip()]:
                    if not dico_ref.get(fieldname.strip()):
                        dico_ref[fieldname.strip()] = [] 
                    dico_ref[fieldname].append(self.add_list_container(layer, input_tab, fieldname, idx, fields, default_values))
                elif fieldname.strip() in self.other_types: 
                    if not dico_ref.get(fieldname.strip()):
                        dico_ref[fieldname.strip()] = [] 
                    dico_ref[fieldname].append(self.add_list_container(layer, input_tab, fieldname, idx, fields, default_values))
                else :
                    input_tab.addChildElement(attrfield(field.name(), idx, input_tab)) # à vérifier sur la doc si c'est bien comme ça
                    layer.setFieldAlias(idx, Alias.get(fieldname, ''))
            elif fieldname.strip() in self.output :
                if fieldname.strip() in self.possible_values and self.possible_values[fieldname.strip()]:
                    dico_ref[fieldname] = self.add_list_container(layer, output_tab, fieldname, idx, fields, default_values)
                else : 
                    print("on y passe ?")
                    output_tab.addChildElement(attrfield(field.name(), idx, output_tab))
            idx+=1
        layer.setEditFormConfig(config)
        
        qml_path = os.path.join(_custom_qml_dir, f'{norm_name}_bloc.qml')
        # Faudra vérifier que les noms sont cohérents avec qgies utilities 
        layer.saveNamedStyle(qml_path)
        
        # add bloc in the custom layertree json
        path_layertree = os.path.join(self.__project.directory, 'layertree_custom.json')
        try :
            layertree = open_json(path_layertree)
        except FileNotFoundError : 
            layertree = {}

        branch = get_propertie(grp, layertree)
        if not branch:
            branch = layertree
            grp_final = grp
            for grp in grps:
                try : 
                    branch = branch[grp]
                except KeyError :
                    branch[grp] = {}
            if not branch.get(grp_final):
                branch[grp_final] = {}
            branch[grp_final][layer_name] = {"bloc" : [layer_name, "api", f'{norm_name}_bloc', "name"]}
        else:
            branch[layer_name] = {'bloc' : [layer_name, "api", f'{norm_name}_bloc', "name"]}
        
        if not layertree.get('Properties'):
            layertree['Properties'] = {}
        for fieldname in dico_ref:
            layertree['Properties'][fieldname] = dico_ref[fieldname][0][0]
            layertree['Properties'][fieldname+'__ref'] = [tab[1] for tab in dico_ref[fieldname]]
        save_to_json(layertree, path_layertree)
        # Faudra vérifier qu'il ne se passe pas de dingz avec le fait que le json soit pas le même que l'autre non custom.
        
        self.__log_manager.notice(f"bloc {layer_name} created")
        
    def add_list_container(self, layer, tab, fieldname, idx, fields, default_values):
        # Create the container in the attribute form
        container = QgsAttributeEditorContainer(fieldname.upper(), tab)
        container.setColumnCount(2)
        container.addChildElement(attrfield(fieldname, idx, container))
        container.addChildElement(attrfield(fieldname+"_fe", fields.indexOf(fieldname+"_fe"), container))
        defval = QgsDefaultValue()
        try : default = self.__project.fetchone(f"select {default_values[fieldname]}") 
        except : default = ''
        if default : default = default[0]
        # defval.setExpression(str(default))
        # layer.setDefaultValueDefinition(idx, defval) 
        # The first part will be saved in the qml file
        
        # Add the propertie layer to the project 
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        g = root.findGroup(tr('Propriétés')) or root.insertGroup(-1, tr('Propriétés'))
        
        layers = project.mapLayersByName(Alias.get(fieldname, ''))
        if not layers:
            sch, tbl, key = "api", f'{fieldname}_type_table', 'val'
            layer_name = f'{fieldname}'
            uri = f'''dbname='{self.__project_name}' service={get_service()} sslmode=disable key='{key}' checkPrimaryKeyUnicity='0' table="{sch}"."{tbl}" '''
            prop_layer = QgsVectorLayer(uri, layer_name, "postgres")
            prop_layer.setDisplayExpression('val')
            project.addMapLayer(prop_layer, False)
            g.addLayer(prop_layer)
            if not prop_layer.isValid():
                raise RuntimeError(f'layer {layer_name} is invalid')
        else : 
            prop_layer = layers[0]
        
        default_fe = f"attribute(get_feature(layer:='{prop_layer.id()}', attribute:='val', value:=coalesce(\"{fieldname}\", '{default}')), 'fe')"
        defval.setExpression(default_fe)
        defval.setApplyOnUpdate(True)
        layer.setDefaultValueDefinition(fields.indexOf(fieldname+"_fe"), defval) # saved in the qml file
        
        tab.addChildElement(container)
        name = 'ref_' + fieldname + '_' + layer.name()
        referencedLayer, referencedField = prop_layer.id(), 'val'
        referencingLayer, referencingField = layer.id(), fieldname
        relation = QgsRelation(QgsRelationContext(project))
        relation.setName(name)
        relation.setReferencedLayer(referencedLayer)
        relation.setReferencingLayer(referencingLayer)
        relation.addFieldPair(referencingField, referencedField)
        relation.setStrength(QgsRelation.Association)
        relation.updateRelationStatus()
        relation.generateId()
        # assert(relation.isValid())
        project.relationManager().addRelation(relation)
        
        return ([prop_layer.name(), sch, tbl, key], [name, 'val', layer.name(), referencingField])
        
        
            
class FormulaCompleter(QCompleter):
    def __init__(self, words, parent=None):
        words += ['co2_c', 'co2_e', 'no2_e', 'ch4_e']
        super().__init__(words, parent)
        self.setFilterMode(Qt.MatchContains)
        self.setCompletionMode(QCompleter.PopupCompletion)
        self.pattern = '[' + re.escape('+-/*^= ()') + ']'
        self.mod = self.model()

    def splitPath(self, path):
        # Split the input text into words
        return [re.split(self.pattern, path)[-1]]

    def pathFromIndex(self, index):
        # Get the current text from the widget
        current_text = self.widget().text()
        # Split the current text into words
        last = re.split(self.pattern, current_text)[-1]
        if len(current_text) > len(last) + 1: 
            symbol = current_text[-len(last)-1]
        else : 
            symbol = ''
        # Replace the last word with the completion
        new_last = index.data()
        # Join the words back into a single string
        if len(current_text) > len(last) + 1:
            return current_text[:-len(last)-1] + symbol + new_last
        else :
            return new_last
        
    def update_words(self, new_words):
        # Update the model with the new list of words
        self.mod.setStringList(new_words)
        self.setModel(self.mod)

class GrpCompleter(QCompleter):
    def __init__(self, words, layertree, parent=None):
        print("init", words)
        super().__init__(words, parent)
        self.layertree = layertree
        self.setFilterMode(Qt.MatchContains)
        self.setCompletionMode(QCompleter.PopupCompletion)
        self.mod = self.model()
        self.mod.setStringList(words)
        self.setModel(self.mod)
        self.length = 0
            
    def splitPath(self, path):
        print("split", path)
        print(self.model().stringList())
        return [path.split('/')[-1]]
    
    def pathFromIndex(self, index) :
        current_text = self.widget().text()
        parts = current_text.split('/')
        completed = index.data()
        if len(parts) > 1:
            return '/'.join(parts[:-1]) + '/' + completed
        else:
            return completed
        
    def update_completions(self, path):
        parts = path.split('/')
        if len(parts) != self.length:
            self.length = len(parts)
        else:
            return
        if len(parts) > 1:
            ref = parts[-2]
        else : 
            ref = ''
        if ref : 
            branch = get_propertie(ref, self.layertree)
        else : 
            branch = self.layertree
        if isinstance(branch, dict):
            completions = list(branch.keys())
        else:
            completions = []
        if 'bloc' in completions : 
            completions.remove('bloc')
        self.mod.setStringList(completions)
        print("bonjour", completions)


if __name__ == '__main__':
    app = CreateBlocWidget()