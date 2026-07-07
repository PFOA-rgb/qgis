import os
from datetime import datetime
from typing import Any, Optional
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsProject,
    QgsMarkerSymbol,
    QgsSingleSymbolRenderer,
    QgsProperty,
    QgsSymbolLayer,
    QgsPalLayerSettings,           
    QgsTextFormat,                 
    QgsVectorLayerSimpleLabeling,
    Qgis  
)
from qgis.PyQt.QtGui import QColor

class BomenConverterAlgorithm(QgsProcessingAlgorithm):
    INPUT_FILE = "INPUT_FILE"
    OUTPUT_GPKG = "OUTPUT_GPKG"

    def name(self) -> str:
        return "excel_to_bomen_gpkg"

    def displayName(self) -> str:
        return "Importeer GeoJSON"

    def group(self) -> str:
        return ""

    def groupId(self) -> str:
        return ""

    def shortHelpString(self) -> str:
        return "Converteer GeoJSON naar GeoPackage"

    def initAlgorithm(self, config: Optional[dict[str, Any]] = None):
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_FILE,
                "Selecteer Excel GeoJSON file",
                behavior=QgsProcessingParameterFile.File,
                extension="geojson"
            )
        )

        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_GPKG,
                "Opslaglocatie GeoPackage (Leeg = Auto-save)",
                fileFilter="GeoPackage (*.gpkg)",
                optional=True
            )
        )

    def processAlgorithm(self, parameters: dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback) -> dict[str, Any]:
        input_path = self.parameterAsFile(parameters, self.INPUT_FILE, context)
        raw_output = parameters.get(self.OUTPUT_GPKG)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if not raw_output or raw_output == 'TEMPORARY_OUTPUT':
            base_path = os.path.splitext(input_path)[0]
            output_path = f"{base_path}_{timestamp}.gpkg"
        else:
            user_path = self.parameterAsFile(parameters, self.OUTPUT_GPKG, context)
            base_path, ext = os.path.splitext(user_path)
            output_path = f"{base_path}_{timestamp}{ext}"

        # 1. Load the GeoJSON
        vlayer = QgsVectorLayer(input_path, "Temp_Import", "ogr")
        if not vlayer.isValid():
            feedback.reportError("Could not load the GeoJSON file!")
            return {self.OUTPUT_GPKG: output_path}

        # 2. Setup Save Options
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = "Bomen" 
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
        
        transform_context = QgsProject.instance().transformContext()
        
        # 3. Write Permanent GeoPackage
        error_code, error_msg, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
            vlayer, output_path, transform_context, options
        )

        if error_code == QgsVectorFileWriter.NoError:
            final_layer = QgsVectorLayer(output_path, "Bomen", "ogr")
            if final_layer.isValid():
                
                # --- APPLY SYMBOLOGY ---
                symbol = QgsMarkerSymbol.createSimple({
                    'name': 'circle',
                    'color': '#2d7d32',
                    'outline_color': '#1b4d1f'
                })
                
                symbol_layer = symbol.symbolLayer(0)
                size_expression = "scale_linear(@map_scale, 350, 1000, 2.8, 1.5)"
                symbol_layer.setDataDefinedProperty(
                    QgsSymbolLayer.PropertySize, 
                    QgsProperty.fromExpression(size_expression)
                )
                
                renderer = QgsSingleSymbolRenderer(symbol)
                final_layer.setRenderer(renderer)
                
                # --- ADD SMART LABELS ---
                label_settings = QgsPalLayerSettings()
                label_settings.fieldName = "coalesce(to_string(\"Boomnr.\"), '')"
                label_settings.isExpression = True
                
                text_format = QgsTextFormat()
                text_format.setSize(9)
                text_format.setColor(QColor("black"))
                
                label_settings.placement = Qgis.LabelPlacement.OverPoint
                label_settings.setFormat(text_format)
                
                labeling = QgsVectorLayerSimpleLabeling(label_settings)
                final_layer.setLabelsEnabled(True)
                final_layer.setLabeling(labeling)
                final_layer.triggerRepaint()
                
                # --- ZET QGIS PROJECT TITEL ---
                # Haal de eerste boom op en kijk of "ProjectTitel" bestaat
                try:
                    first_feature = next(final_layer.getFeatures())
                    if "ProjectTitel" in first_feature.fields().names():
                        project_title = first_feature["ProjectTitel"]
                        if project_title:
                            QgsProject.instance().setTitle(project_title)
                except StopIteration:
                    # De laag bevat geen bomen, dus we doen niets
                    pass
                # ------------------------------
                
                # --- ADD TO ROOT OF LAYER TREE ---
                QgsProject.instance().addMapLayer(final_layer, False)
                root = QgsProject.instance().layerTreeRoot()
                root.insertLayer(0, final_layer)
                
                feedback.pushInfo(f"Success! Saved as: {os.path.basename(output_path)}")
            else:
                feedback.reportError("GeoPackage created but failed to load.")
        else:
            feedback.reportError(f"Export failed: {error_msg}")

        return {self.OUTPUT_GPKG: output_path}

    def createInstance(self):
        return BomenConverterAlgorithm()