# -*- coding: utf-8 -*-
import os
import datetime
from qgis.core import (
    QgsProject, QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsVectorLayer, QgsFeature, QgsFillSymbol, QgsLinePatternFillSymbolLayer,
    QgsSimpleLineSymbolLayer, QgsSimpleFillSymbolLayer, QgsVectorFileWriter,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterField,
    QgsProcessingParameterColor, QgsProcessingParameterEnum,
    QgsProcessingParameterNumber, QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination
)
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QColor

class CreateRisicozoneAlgorithm(QgsProcessingAlgorithm):

    INPUT_LAYER = 'INPUT_LAYER'
    FIELD = 'FIELD'
    FACTOR = 'FACTOR'
    FILL_COLOR = 'FILL_COLOR'
    STROKE_COLOR = 'STROKE_COLOR'
    PATTERN = 'PATTERN'
    QML_STYLE = 'QML_STYLE'
    OUTPUT_FILE = 'OUTPUT_FILE'

    PATTERNS = ['Effen', 'Diagonaal 45° (Risicozone)', 'Diagonaal 135°', 'Horizontaal', 'Verticaal', 'Kruis']

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CreateRisicozoneAlgorithm()

    def name(self):
        return 'risicozone_clean_layer_v20'

    def displayName(self):
        return self.tr('Risicozone')

    def group(self):
        return self.tr('')

    def groupId(self):
        return ''

    def shortHelpString(self):
        return self.tr(
            "### REFERENTIE TABEL\n"
            "Onderstaande waarden gelden voor een boom van **60 cm**:\n\n"
            "| Factor | Diameter Zone |\n"
            "| :--- | :--- |\n"
            "| **0.050** | **6.0 meter** |\n"
            "| 0.055 | 6.6 meter |\n"
            "| 0.060 | 7.2 meter |\n"
            "| 0.065 | 7.8 meter |\n"
            "| 0.070 | 8.4 meter |\n"
            "| 0.075 | 9.0 meter |\n"
            "| 0.080 | 9.6 meter |\n"
            "| 0.085 | 10.2 meter |\n"
            "| 0.090 | 10.8 meter |\n"
            "| 0.095 | 11.4 meter |\n"
            "| **0.100** | **12.0 meter** |\n\n"
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT_LAYER, self.tr('Bomenlaag (punten)'), [QgsProcessing.TypeVectorPoint]))
        
        self.addParameter(QgsProcessingParameterField(self.FIELD, self.tr('Veld met stamdiameter (cm)'), parentLayerParameterName=self.INPUT_LAYER, defaultValue='Stamdiameter'))

        param_factor = QgsProcessingParameterNumber(self.FACTOR, self.tr('Risicofactor (Referentie tabel links)'), type=QgsProcessingParameterNumber.Double, defaultValue=0.050, minValue=0.001, maxValue=1.0)
        param_factor.setMetadata({'widget_wrapper': {'decimals': 3, 'step': 0.005}})
        self.addParameter(param_factor)

        self.addParameter(QgsProcessingParameterColor(self.FILL_COLOR, self.tr('Kleur patroon'), defaultValue=QColor('#e81111')))
        self.addParameter(QgsProcessingParameterColor(self.STROKE_COLOR, self.tr('Kleur rand'), defaultValue=QColor('#e81111')))
        self.addParameter(QgsProcessingParameterEnum(self.PATTERN, self.tr('Kies Patroon'), options=self.PATTERNS, defaultValue=1))
        self.addParameter(QgsProcessingParameterFile(self.QML_STYLE, self.tr('Custom .qml (Optioneel)'), optional=True))
        
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT_FILE, self.tr('Opslaglocatie (Leeg = Auto-Save)'), fileFilter='GeoPackage (*.gpkg)', optional=True))

    def processAlgorithm(self, parameters, context, feedback):
        bomen_layer = self.parameterAsVectorLayer(parameters, self.INPUT_LAYER, context)
        field_name = self.parameterAsString(parameters, self.FIELD, context).strip()
        factor = self.parameterAsDouble(parameters, self.FACTOR, context)
        pattern_idx = self.parameterAsEnum(parameters, self.PATTERN, context)
        
        # 1. PAD LOGICA - Uniek bestand op schijf
        raw_output = parameters.get(self.OUTPUT_FILE)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if not raw_output or "TEMPORARY_OUTPUT" in str(raw_output):
            project_path = QgsProject.instance().fileName()
            if project_path:
                dir_name = os.path.dirname(project_path)
                project_base = os.path.splitext(os.path.basename(project_path))[0]
                output_path = os.path.join(dir_name, f"{project_base}_Risicozone_{timestamp}.gpkg")
            else:
                output_path = os.path.join(os.path.expanduser("~"), "Documents", f"Risicozone_{timestamp}.gpkg")
        else:
            output_path = self.parameterAsFileOutput(parameters, self.OUTPUT_FILE, context)

        # 2. Processing
        crs = bomen_layer.sourceCrs().authid()
        temp_layer = QgsVectorLayer(f"Polygon?crs={crs}", "temp", "memory")
        temp_layer.dataProvider().addAttributes(bomen_layer.fields())
        temp_layer.updateFields()

        features = []
        for feat in bomen_layer.getFeatures():
            if feedback.isCanceled(): break
            try:
                val = float(str(feat[field_name]).replace(',', '.'))
                geom = feat.geometry().buffer(val * factor, 22)
                new_feat = QgsFeature(temp_layer.fields())
                new_feat.setGeometry(geom)
                new_feat.setAttributes(feat.attributes())
                features.append(new_feat)
            except: continue
        
        temp_layer.dataProvider().addFeatures(features)
        QgsVectorFileWriter.writeAsVectorFormatV3(temp_layer, output_path, context.transformContext(), QgsVectorFileWriter.SaveVectorOptions())

        # 3. Laden & Styling - LAAGNAAM IS NU "Risicozone"
        final_layer = QgsVectorLayer(output_path, "Risicozone", "ogr")
        
        qml_path = self.parameterAsFile(parameters, self.QML_STYLE, context)
        if qml_path and os.path.exists(qml_path):
            final_layer.loadNamedStyle(qml_path)
        else:
            fill_color = self.parameterAsColor(parameters, self.FILL_COLOR, context)
            stroke_color = self.parameterAsColor(parameters, self.STROKE_COLOR, context)
            final_symbol = QgsFillSymbol()
            if pattern_idx == 0:
                sl = QgsSimpleFillSymbolLayer(); sl.setFillColor(fill_color); sl.setStrokeStyle(0)
                final_symbol.changeSymbolLayer(0, sl)
            else:
                lp = QgsLinePatternFillSymbolLayer(); lp.setColor(fill_color); lp.setDistance(2.0); lp.setLineWidth(0.3)
                angles = {1: 45, 2: 135, 3: 0, 4: 90, 5: 45}; lp.setLineAngle(angles.get(pattern_idx, 45))
                final_symbol.changeSymbolLayer(0, lp)
                if pattern_idx == 5:
                    cp = QgsLinePatternFillSymbolLayer(); cp.setColor(fill_color); cp.setDistance(2.0); cp.setLineWidth(0.3); cp.setLineAngle(135)
                    final_symbol.appendSymbolLayer(cp)
            outline = QgsSimpleLineSymbolLayer(); outline.setColor(stroke_color); outline.setWidth(0.46)
            final_symbol.appendSymbolLayer(outline)
            final_symbol.setOpacity(0.60)
            if final_layer.renderer(): final_layer.renderer().setSymbol(final_symbol)

        QgsProject.instance().addMapLayer(final_layer)
        return {'OUTPUT': output_path}