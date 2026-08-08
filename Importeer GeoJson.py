import json
import os
import tempfile
from datetime import datetime
from typing import Any, Optional
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsFeature,
    QgsCoordinateReferenceSystem,
    QgsField,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsWkbTypes,
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


def parse_coordinate_value(value):
    if isinstance(value, (int, float)):
        return value, False
    if not isinstance(value, str):
        return value, False

    text = value.strip().replace(" ", "")
    if not text:
        return value, False

    if "," in text and "." in text:
        if text.rfind(",") < text.rfind("."):
            normalized = text.replace(",", "")
        else:
            normalized = text.replace(".", "").replace(",", ".")
    elif "," in text:
        normalized = text.replace(",", ".")
    else:
        normalized = text

    try:
        return float(normalized), True
    except ValueError:
        return value, False


def normalize_geojson_coordinates(coordinates):
    if not isinstance(coordinates, list):
        return coordinates, 0

    if len(coordinates) >= 2 and not isinstance(coordinates[0], list) and not isinstance(coordinates[1], list):
        normalized = []
        changes = 0
        for value in coordinates:
            parsed, changed = parse_coordinate_value(value)
            normalized.append(parsed)
            if changed:
                changes += 1
        return normalized, changes

    normalized = []
    changes = 0
    for part in coordinates:
        normalized_part, part_changes = normalize_geojson_coordinates(part)
        normalized.append(normalized_part)
        changes += part_changes
    return normalized, changes


def create_normalized_geojson(input_path, feedback):
    try:
        with open(input_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return input_path, None

    total_changes = 0
    features = data.get("features", []) if isinstance(data, dict) else []
    for feature in features:
        geometry = feature.get("geometry") if isinstance(feature, dict) else None
        if not geometry or "coordinates" not in geometry:
            continue
        geometry["coordinates"], changes = normalize_geojson_coordinates(geometry["coordinates"])
        total_changes += changes

    if total_changes == 0:
        return input_path, None

    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".geojson",
        prefix="qgis_import_normalized_",
        delete=False,
    )
    with temp_file:
        json.dump(data, temp_file, ensure_ascii=False)

    feedback.pushInfo(f"{total_changes} coördinaatwaardes genormaliseerd voor import.")
    return temp_file.name, temp_file.name


def layer_looks_like_rd(layer):
    extent = layer.extent()
    if extent.isEmpty():
        return False

    center_x = (extent.xMinimum() + extent.xMaximum()) / 2
    center_y = (extent.yMinimum() + extent.yMaximum()) / 2
    return 0 <= center_x <= 300000 and 300000 <= center_y <= 620000


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

        # 1. Normalize coordinate notation before loading the GeoJSON.
        # Supports English notation (99,659.286) and Dutch notation (99659,286).
        normalized_input_path, temp_input_path = create_normalized_geojson(input_path, feedback)

        # 2. Load the GeoJSON
        vlayer = QgsVectorLayer(normalized_input_path, "Temp_Import", "ogr")
        if not vlayer.isValid():
            if temp_input_path:
                os.remove(temp_input_path)
            feedback.reportError("Could not load the GeoJSON file!")
            return {self.OUTPUT_GPKG: output_path}

        if layer_looks_like_rd(vlayer):
            vlayer.setCrs(QgsCoordinateReferenceSystem("EPSG:28992"))
            feedback.pushInfo("Coördinaten lijken op RD New. CRS ingesteld op EPSG:28992 zonder transformatie.")

        # 3. Rename source field "fid" before GeoPackage export.
        # GeoPackage/OGR reserves fid for its internal numeric feature id.
        export_layer = vlayer
        field_names = vlayer.fields().names()
        fid_indexes = [i for i, name in enumerate(field_names) if name.lower() == "fid"]
        if fid_indexes:
            existing_names = {name.lower() for name in field_names}
            safe_fid_name = "bron_fid"
            counter = 1
            while safe_fid_name.lower() in existing_names:
                safe_fid_name = f"bron_fid_{counter}"
                counter += 1

            export_layer = QgsVectorLayer(
                f"{QgsWkbTypes.displayString(vlayer.wkbType())}?crs={vlayer.crs().authid()}",
                "Temp_Import_Safe_Fields",
                "memory"
            )
            provider = export_layer.dataProvider()

            safe_fields = []
            for index, field in enumerate(vlayer.fields()):
                new_field = QgsField(field)
                if index in fid_indexes:
                    new_field.setName(safe_fid_name)
                safe_fields.append(new_field)

            provider.addAttributes(safe_fields)
            export_layer.updateFields()

            new_features = []
            for feature in vlayer.getFeatures():
                new_feature = QgsFeature(export_layer.fields())
                new_feature.setGeometry(feature.geometry())
                new_feature.setAttributes(feature.attributes())
                new_features.append(new_feature)
            provider.addFeatures(new_features)
            feedback.pushInfo(f'Veld "fid" hernoemd naar "{safe_fid_name}" om GeoPackage-export mogelijk te maken.')

        # 4. Setup Save Options
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = "Bomen" 
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
        
        transform_context = QgsProject.instance().transformContext()
        
        # 5. Write Permanent GeoPackage
        error_code, error_msg, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
            export_layer, output_path, transform_context, options
        )
        if temp_input_path:
            os.remove(temp_input_path)

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