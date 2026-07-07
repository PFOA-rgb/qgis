# -*- coding: utf-8 -*-
import os
from qgis.core import (
    QgsProject,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterField,
    QgsProcessingParameterEnum,
    QgsProcessingParameterBoolean,
    QgsVectorLayer,
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsSymbol,
    QgsSymbolLayer,
    QgsProperty,
    QgsWkbTypes,
    QgsVectorFileWriter
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import QCoreApplication

class BoomstylerFinalAlgorithm(QgsProcessingAlgorithm):

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return BoomstylerFinalAlgorithm()

    def name(self):
        return "boom_styler_v6_custom_kleuren"

    def displayName(self):
        return self.tr("Categorisatie")

    def group(self):
        return self.tr("")

    def groupId(self):
        return ""

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer("INPUT", "Kies laag", [QgsProcessing.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterField("CATEGORIEVELD", "Kies veld om op te stylen", parentLayerParameterName="INPUT"))
        
        self.addParameter(
            QgsProcessingParameterEnum(
                "STIJL",
                "Kies kleurstijl (Conditie & Conclusie hebben vaste kleuren)",
                options=["Natuurlijk & Organisch", "Modern & Strak", "Kleurblind-vriendelijk"],
                defaultValue=0
            )
        )
        
        self.addParameter(
            QgsProcessingParameterBoolean(
                "OPSLAAN",
                "Automatisch opslaan als GeoPackage in projectmap",
                defaultValue=True
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        input_layer = self.parameterAsVectorLayer(parameters, "INPUT", context)
        veldnaam = self.parameterAsString(parameters, "CATEGORIEVELD", context)
        stijl_index = self.parameterAsInt(parameters, "STIJL", context)
        moet_opslaan = self.parameterAsBool(parameters, "OPSLAAN", context)

        if input_layer is None:
            raise QgsProcessingException("Geen geldige laag gekozen.")

        schaal_expressie = "scale_linear(@map_scale, 350, 1000, 2.8, 1.5)"
        
        # De vaste kleuren voor Conditie
        vaste_conditie_kleuren = [
            ("Goed", "#008000"),
            ("Voldoende", "#90ee90"),
            ("Onvoldoende", "#0000ff"),
            ("Slecht", "#ffcccb"),
            ("Zeer slecht", "#8b0000")
        ]

        # De vaste kleuren voor Conclusie BVC / VTA_CONCLU
        vaste_conclusie_kleuren = [
            ("Tijdelijk verhoogd risico", "#ffff00"),
            ("Risicoboom", "#ff0000"),
            ("Goedgekeurd", "#008000"),
            ("Attentieboom", "#ffa500"),
            ("Afgekeurd", "#000000"),
            ("Verwijderd", "#808080")
        ]
        
        paletten = [
            {
             "conditie": vaste_conditie_kleuren,
             "vta_condit": vaste_conditie_kleuren,
             "conclusie bvc": vaste_conclusie_kleuren,
             "vta_conclu": vaste_conclusie_kleuren,
             "projectinvloeden": [("Verbeterd","#556B2F"), ("Geen effect","#8FA998"), ("Beperkt effect","#E2B45C"), ("Sterk effect","#C57B57"), ("Fataal","#4F3130"), ("Verwijderd","#7F8C8D")],
             "verplantbaarheid": [("Direct verplantbaar","#556B2F"), ("Verplantbaar met voorbereiding","#E2B45C"), ("Niet verplantbaar","#4F3130")]},
            
            {
             "conditie": vaste_conditie_kleuren,
             "vta_condit": vaste_conditie_kleuren,
             "conclusie bvc": vaste_conclusie_kleuren,
             "vta_conclu": vaste_conclusie_kleuren,
             "projectinvloeden": [("Verbeterd","#27AE60"), ("Geen effect","#82E0AA"), ("Beperkt effect","#F1C40F"), ("Sterk effect","#E67E22"), ("Fataal","#C0392B"), ("Verwijderd","#34495E")],
             "verplantbaarheid": [("Direct verplantbaar","#27AE60"), ("Verplantbaar met voorbereiding","#F1C40F"), ("Niet verplantbaar","#C0392B")]},
            
            {
             "conditie": vaste_conditie_kleuren,
             "vta_condit": vaste_conditie_kleuren,
             "conclusie bvc": vaste_conclusie_kleuren,
             "vta_conclu": vaste_conclusie_kleuren,
             "projectinvloeden": [("Verbeterd","#004D40"), ("Geen effect","#00897B"), ("Beperkt effect","#D4E157"), ("Sterk effect","#FFB300"), ("Fataal","#D81B60"), ("Verwijderd","#424242")],
             "verplantbaarheid": [("Direct verplantbaar","#004D40"), ("Verplantbaar met voorbereiding","#D4E157"), ("Niet verplantbaar","#D81B60")]}
        ]

        gekozen_palet = paletten[stijl_index]
        schema = gekozen_palet.get(veldnaam.lower(), [])

        laagnaam = f"{input_layer.name()} ({veldnaam})"
        crs = input_layer.crs().authid()
        geom_type = QgsWkbTypes.displayString(input_layer.wkbType())
        
        temp_layer = QgsVectorLayer(f"{geom_type}?crs={crs}", laagnaam, "memory")
        provider = temp_layer.dataProvider()
        provider.addAttributes(input_layer.fields())
        temp_layer.updateFields()
        provider.addFeatures(input_layer.getFeatures())

        final_layer = temp_layer
        if moet_opslaan:
            project_path = QgsProject.instance().absolutePath()
            if not project_path:
                feedback.reportError("Geen projectpad gevonden. Laag wordt als tijdelijk geladen.")
            else:
                clean_veld = "".join(x for x in veldnaam if x.isalnum() or x in "._- ")
                file_name = f"{input_layer.name()}_{clean_veld}.gpkg".replace(" ", "_")
                full_path = os.path.join(project_path, file_name)
                
                options = QgsVectorFileWriter.SaveVectorOptions()
                options.driverName = "GPKG"
                
                result = QgsVectorFileWriter.writeAsVectorFormatV3(temp_layer, full_path, context.transformContext(), options)
                err = result[0]
                msg = result[1]
                
                if err == QgsVectorFileWriter.NoError:
                    final_layer = QgsVectorLayer(full_path, laagnaam, "ogr")
                else:
                    feedback.reportError(f"Fout bij opslaan: {msg}")

        # --- STYLING (API Safe) ---
        data_waardes = set()
        heeft_leeg = False
        for feat in final_layer.getFeatures():
            val = feat[veldnaam]
            if val is None or str(val).strip().lower() in ["", "null", "none"]:
                heeft_leeg = True
            else:
                data_waardes.add(str(val).strip())

        def create_styled_symbol(color_hex):
            symbol = QgsSymbol.defaultSymbol(final_layer.geometryType())
            if symbol.symbolLayerCount() > 0:
                sl = symbol.symbolLayer(0)
                sl.setColor(QColor(color_hex))
                sl.setStrokeColor(QColor("#333333"))
                sl.setStrokeWidth(0.2)
                sl.setDataDefinedProperty(QgsSymbolLayer.PropertySize, QgsProperty.fromExpression(schaal_expressie))
            return symbol

        categories = []
        verwerkte = []
        for label, kleur in schema:
            match = next((x for x in data_waardes if x.lower() == label.lower()), None)
            if match:
                categories.append(QgsRendererCategory(match, create_styled_symbol(kleur), label))
                verwerkte.append(match)

        overige = sorted(list(data_waardes - set(verwerkte)))
        for i, waarde in enumerate(overige):
            rand_kleur = QColor.fromHsv((i * 60) % 360, 100, 240).name()
            categories.append(QgsRendererCategory(waarde, create_styled_symbol(rand_kleur), waarde))

        if heeft_leeg:
            categories.append(QgsRendererCategory(None, create_styled_symbol("#d3d3d3"), "Onbekend / leeg"))

        renderer = QgsCategorizedSymbolRenderer(veldnaam, categories)
        final_layer.setRenderer(renderer)
        QgsProject.instance().addMapLayer(final_layer)
        
        return {}