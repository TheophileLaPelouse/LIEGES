import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication, QMessageBox, QToolButton, QDockWidget, QInputDialog, QTableWidgetItem, QScrollArea
from ...qgis_utilities import QGisProjectManager, tr 
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT, FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from .graph_widget import GraphWidget

class RecapResults(QDockWidget) : 
    
    def __init__(self, model_name, project) : 
        QDockWidget.__init__(self, tr("Results"))
        uic.loadUi(os.path.join(os.path.dirname(__file__), 'resume_resultat.ui'), self)
        
        # self.scroll = QScrollArea()
        # self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        # self.scroll.setWidgetResizable(True)
        # self.scroll.setWidget(self.dockWidgetContents)
        
        for k in range(6) : 
            button = getattr(self, f'pushButton_{k+1}')
            button.clicked.connect(lambda _, index=k+1: self.navigate(index))
        
        self.__project = project
        
        self.__current_fig = None
        self.__current_model = model_name 
        self.__recap_table = None 
        self.__results = None 
        
        # self.graph_pie_e = GraphWidget(self.pie_chart_e, dpi=75)
        # self.graph_pie_c = GraphWidget(self.pie_chart_c, dpi=75)
        self.graph_bar_e = GraphWidget(self.bar_chart_e, dpi=75)
        self.graph_bar_c = GraphWidget(self.bar_chart_c, dpi=75)
        
        model_list = self.__project.models
        self.update_model_list()
        self.model_combo.currentIndexChanged.connect(self.show_results)
        
        if model_name is not None : 
            print("ici")
            self.model_combo.setCurrentText(model_name)
        
    def update_model_list(self) : 
        model_list = self.__project.models
        print('list', model_list)
        self.model_combo.clear()
        self.model_combo.addItems([''] + model_list)    
    
    def show_results(self, index_change, model_name = None) : 
        print(index_change)
        # On fait un peu bourrain mais en vrai même si on a 500 blocs, ça reste linéaire donc ça passe 
        if model_name is None :
            model_name = self.model_combo.currentText()
        print("wut ?")
        print('model', model_name)
        results = self.__project.fetchall(f"select name, res, co2_eq_e, co2_eq_c from api.results where model = '{model_name}'")
        self.__results = {}
        for result in results : 
            self.__results[result[0]] = {}
            unknowns = []
            detail = None
            for formula in result[1]['data'] : 
                if formula['in use'] :
                    detail = formula['detail']                    
                if formula['unknown'] : 
                    unknowns += formula['unknown']
            self.__results[result[0]]['unknown'] = list(set(unknowns)) # Pas très beau mais pour une liste de max 10 valeurs très efficace
            self.__results[result[0]]['detail'] = detail
            self.__results[result[0]]['co2_eq_e'] = result[2]
            self.__results[result[0]]['co2_eq_c'] = result[3]
            # self.__results[result[0]]['data'] = result[1]['data']
        # Cette variable sera réutilisée pour les graphes plus précise dans l'affichage des résultats plus complet
        self.__current_model = model_name
        self.__recap_table = {}
        for key in self.__results : 
            self.__recap_table[key] = [key, self.__results[key]['unknown'], 
                                       self.__results[key]['co2_eq_e'], self.__results[key]['co2_eq_c'], 
                                       self.__results[key]['detail']]
        self.table_recap.setRowCount(len(self.__recap_table))
        idx = 0
        for key, values in self.__recap_table.items() : 
            for k in range(5) : 
                self.table_recap.setItem(idx, k, QTableWidgetItem(str(values[k])))
                if idx % 2 == 0 :
                    self.table_recap.item(idx, k).setBackground(Qt.lightGray)
                # if values[4] : 
                #     font = self.table_recap.item(idx, k).font()
                #     font.setBold(True)
                #     self.table_recap.item(idx, k).setFont(font)
            idx += 1
            
        self.table_recap.resizeColumnsToContents()
        self.table_recap.setShowGrid(True)
        self.table_recap.setSortingEnabled(True)
        
        self.show_plot()
        
    def show_plot(self, bloc_name = None, dpi = 75, edgecolor = 'grey', color = {'co2' : 'grey', 'ch4' : 'brown', 'n2o' : 'yellow'}) :
        print("show", self.__current_model)
        print(f"select api.get_histo_data('{self.__current_model}')")
        data = self.__project.fetchone(f"select api.get_histo_data('zef')")
        data = data[0]
        print(data)
        # pie e 
        fields = ['co2_e', 'ch4_e', 'n2o_e', 'co2_c', 'ch4_c', 'n2o_c', 'co2_eq_e', 'co2_eq_c']
        for field in fields :
            label = getattr(self, f'label_{field}')
            if field[:5] == 'co2_eq' : 
                fieldstr = 'CO2eq'
            else : 
                fieldstr = field[:3].upper()
            print(field)
            label.setText(fieldstr + f' (kg{fieldstr}/an)' + ' : ' + str(data['total'][field]))
            label.setStyleSheet("""
                QLabel {
                    border: 1px solid black;
                    padding: 5px;
                    margin: 2px;
                    font-size: 10px;
                }
            """)
        # data_pie_e = [data['total'][field] for field in fields]
        # labels = ['CO2', 'CH4', 'N2O']
        # self.graph_pie_e.pie_chart(data_pie_e, labels, color, tr("Total emission for exploitation (kgGas/an)"))
        # self.title_pie_e.setText(tr("Emission totale exploitation (kgGas/an)"))
        
        # pie c
        # fields = ['co2_c', 'ch4_c', 'n2o_c']
        # data_pie_c = [data['total'][field] for field in fields]
        # labels = ['CO2', 'CH4', 'N2O']
        # self.graph_pie_c.pie_chart(data_pie_c, labels, color, tr("Total emission for construction (kgGas)"))    
        # self.title_pie_c.setText(tr("Emission total construction (kgGas)"))
        
        # bars
        bars = {'co2_e' : [], 'ch4_e': [], 'n2o_e': [], 'co2_c' : [], 'ch4_c': [], 'n2o_c': []}
        for key in data : 
            if key != 'total' :
                for field in bars : 
                    bars[field].append(data[key][field])
        r = range(len(bars['co2_e']))        
        
        names = list(data.keys())
        names.remove('total')
        bars_c = {'co2' : bars['co2_c'], 'ch4' : bars['ch4_c'], 'n2o' : bars['n2o_c']}
        bars_e = {'co2' : bars['co2_e'], 'ch4' : bars['ch4_e'], 'n2o' : bars['n2o_e']}
        self.graph_bar_c.bar_chart(r, bars_c, 'c', names, color, edgecolor, tr("Emmission construction (kgGaz)"), tr('kg de GES émis'), tr('Blocs du modèle %s' % self.__current_model))
        self.graph_bar_e.bar_chart(r, bars_e, 'e', names, color, edgecolor, tr("Emission exploitation (kgGaz/an)"), tr('kg de GES émis par an'), tr('Blocs du modèle %s' % self.__current_model))   
        
        # self.title_bar_e.setText(tr("Emission exploitation (kgGaz/an)"))
        # self.title_bar_c.setText(tr("Emission construction (kgGaz)"))
        
    def navigate(self, index) :
        if index == 1 : 
            self.stackedWidget.setCurrentIndex(2)
        elif index == 6 : 
            self.stackedWidget.setCurrentIndex(0)
        elif index % 2 == 0 : 
            self.stackedWidget.setCurrentIndex(self.stackedWidget.currentIndex() + 1)
        else :
            self.stackedWidget.setCurrentIndex(self.stackedWidget.currentIndex() - 1)
            