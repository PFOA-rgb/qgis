# -*- coding: utf-8 -*-
import os
import datetime
from qgis.core import (
    QgsProject, QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsVectorLayer, QgsFeature, QgsField, QgsFillSymbol, QgsSymbolLayerRegistry,
    QgsSimpleFillSymbolLayer, QgsLineSymbol, QgsSymbol, QgsVectorFileWriter,
    QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings, QgsVectorLayerSimpleLabeling,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterField,
    QgsProcessingParameterBoolean, QgsProcessingParameterColor,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFile, QgsProcessingParameterFileDestination,
    QgsApplication, Qgis
)
from qgis.PyQt.QtCore import QCoreApplication, QVariant, Qt
from qgis.PyQt.QtGui import QColor

class KroonprojectieV31Algorithm(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    FIELD = 'FIELD'
    SHOW_INDICATOR = 'SHOW_INDICATOR'
    LINE_STYLE = 'LINE_STYLE'
    FILL_COLOR = 'FILL_COLOR'
    STROKE_COLOR = 'STROKE_COLOR'
    OUTPUT_FILE = 'OUTPUT_FILE'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return KroonprojectieV31Algorithm()

    def name(self):
        return 'kroonprojectie_v31_final'

    def displayName(self):
        return self.tr('Kroonprojectie')

    def group(self):
        return self.tr('')

    def groupId(self):
        return ''

    def shortHelpString(self):
        return self.tr(
            "### REFERENTIE TABEL\n"
            "De straal van de cirkel is de helft van de diameter ($radius = diameter / 2$):\n\n"
            "| Diameter Boom | Straal (Buffer) |\n"
            "| :--- | :--- |\n"
            "| 4.0 meter | 2.0 meter |\n"
            "| 6.0 meter | 3.0 meter |\n"
            "| 8.0 meter | 4.0 meter |\n"
            "| **10.0 meter** | **5.0 meter** |\n"
            "| 12.0 meter | 6.0 meter |\n\n"
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT, self.tr('Selecteer de bomenlaag'), [QgsProcessing.TypeVectorPoint]))
        self.addParameter(QgsProcessingParameterField(self.FIELD, self.tr('Selecteer veld met kroondiameter'), parentLayerParameterName=self.INPUT, defaultValue='Kroondiameter'))
        self.addParameter(QgsProcessingParameterBoolean(self.SHOW_INDICATOR, self.tr('Toon straal-indicator op de kaart'), defaultValue=True))
        
        self.addParameter(
            QgsProcessingParameterEnum(
                self.LINE_STYLE,
                self.tr('Lijnstijl'),
                options=['Solid', 'Dash', 'Dot', 'Dash Dot', 'Dash Dot Dot'],
                defaultValue=1  # Aangepast naar Dash als standaard
            )
        )
        
        self.addParameter(QgsProcessingParameterColor(self.FILL_COLOR, self.tr('Vulkleur (Fill)'), defaultValue=QColor(44, 110, 55, 80)))
        self.addParameter(QgsProcessingParameterColor(self.STROKE_COLOR, self.tr('Lijnkleur (Stroke)'), defaultValue=QColor(0, 0, 0, 255)))
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT_FILE, self.tr('Opslaglocatie (Leeg = Auto-Save)'), fileFilter='GeoPackage (*.gpkg)', optional=True))

    def processAlgorithm(self, parameters, context, feedback):
        input_layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        if not input_layer: raise QgsProcessingException("Invoerlaag niet gevonden.")
        
        field_name = self.parameterAsString(parameters, self.FIELD, context).strip()
        show_indicator = self.parameterAsBool(parameters, self.SHOW_INDICATOR, context)
        fill_color = self.parameterAsColor(parameters, self.FILL_COLOR, context)
        stroke_color = self.parameterAsColor(parameters, self.STROKE_COLOR, context)
        
        # Lijnstijl mapping naar Qt objecten en QGIS strings
        line_style_idx = self.parameterAsInt(parameters, self.LINE_STYLE, context)
        
        # Qt objecten voor de fill omtrek
        qt_styles = [Qt.SolidLine, Qt.DashLine, Qt.DotLine, Qt.DashDotLine, Qt.DashDotDotLine]
        chosen_qt_style = qt_styles[line_style_idx]
        
        # String namen voor de QgsLineSymbol
        qgis_styles = ['solid', 'dash', 'dot', 'dash dot', 'dash dot dot']
        chosen_qgis_style = qgis_styles[line_style_idx]
        
        # Tijdstempel met seconden voor unieke bestandsnaam
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_output = parameters.get(self.OUTPUT_FILE)
        if not raw_output or "TEMPORARY_OUTPUT" in str(raw_output):
            project_path = QgsProject.instance().fileName()
            if project_path:
                dir_name = os.path.dirname(project_path)
                project_base = os.path.splitext(os.path.basename(project_path))[0]
                output_path = os.path.join(dir_name, f"{project_base}_Kroonprojectie_{timestamp}.gpkg")
            else:
                output_path = os.path.join(os.path.expanduser("~"), "Documents", f"Kroonprojectie_{timestamp}.gpkg")
        else:
            output_path = self.parameterAsFileOutput(parameters, self.OUTPUT_FILE, context)

        # Nieuwe laag aanmaken
        crs = input_layer.sourceCrs().authid()
        temp_layer = QgsVectorLayer(f"Polygon?crs={crs}", "temp", "memory")
        fields = input_layer.fields()
        if show_indicator: fields.append(QgsField("Radius_m", QVariant.Double))
        temp_layer.dataProvider().addAttributes(fields)
        temp_layer.updateFields()

        features = []
        for feat in input_layer.getFeatures():
            if feedback.isCanceled(): break
            try:
                val = float(str(feat[field_name]).replace(',', '.'))
                if val <= 0: continue
                radius = val / 2
                geom = feat.geometry().buffer(radius, 22)
                new_feat = QgsFeature(temp_layer.fields())
                new_feat.setGeometry(geom)
                attributes = feat.attributes()
                if show_indicator: attributes.append(radius)
                new_feat.setAttributes(attributes)
                features.append(new_feat)
            except: continue
        
        temp_layer.dataProvider().addFeatures(features)
        QgsVectorFileWriter.writeAsVectorFormatV3(temp_layer, output_path, context.transformContext(), QgsVectorFileWriter.SaveVectorOptions())

        # Laden in QGIS
        final_layer = QgsVectorLayer(output_path, "Kroonprojectie", "ogr")
        
        # --- STYLING ---
        simple_fill = QgsSimpleFillSymbolLayer()
        simple_fill.setFillColor(fill_color)
        simple_fill.setStrokeColor(stroke_color)
        simple_fill.setStrokeWidth(0.26)
        simple_fill.setStrokeStyle(chosen_qt_style)
        
        symbol = QgsFillSymbol()
        symbol.changeSymbolLayer(0, simple_fill)

        if show_indicator:
            # Diagonale lijn (45 graden)
            expr = 'make_line(centroid($geometry), project(centroid($geometry), "Radius_m", 45))'
            registry = QgsApplication.symbolLayerRegistry()
            metadata = registry.symbolLayerMetadata("GeometryGenerator")
            line_gen = metadata.createSymbolLayer({"geometryModifier": expr, "symbolType": "Line"})
            
            sub_line = QgsLineSymbol.createSimple({
                'color': stroke_color.name(), 
                'width': '0.3',
                'outline_style': chosen_qgis_style
            })
            line_gen.setSubSymbol(sub_line)
            symbol.appendSymbolLayer(line_gen)
            
            # Labeling r = ...m
            lbl = QgsPalLayerSettings()
            lbl.isExpression = True
            lbl.fieldName = "'r = ' || format_number(\"Radius_m\", 1) || 'm'"
            lbl.placement = QgsPalLayerSettings.Line
            lbl.geometryGeneratorEnabled = True
            lbl.geometryGenerator = expr
            lbl.geometryGeneratorType = Qgis.GeometryType.Line
            
            fmt = QgsTextFormat()
            fmt.setSize(8)
            fmt.setColor(QColor(0, 0, 0))
            
            buf = QgsTextBufferSettings()
            buf.setEnabled(True)
            buf.setSize(0.8)
            buf.setColor(QColor(255, 255, 255))
            fmt.setBuffer(buf)
            
            lbl.setFormat(fmt)
            final_layer.setLabeling(QgsVectorLayerSimpleLabeling(lbl))
            final_layer.setLabelsEnabled(True)

        if final_layer.renderer():
            final_layer.renderer().setSymbol(symbol)

        QgsProject.instance().addMapLayer(final_layer)
        return {'OUTPUT': output_path}