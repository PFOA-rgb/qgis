# -*- coding: utf-8 -*-
import os

from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterField,
    QgsProcessingParameterVectorLayer,
    QgsProject,
    QgsProperty,
    QgsRendererCategory,
    QgsSymbol,
    QgsSymbolLayer,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import QgsColorButton
from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

VASTE_CONDITIE_KLEUREN = [
    ("Goed", "#008000"),
    ("Voldoende", "#90ee90"),
    ("Onvoldoende", "#0000ff"),
    ("Slecht", "#ffcccb"),
    ("Zeer slecht", "#8b0000"),
]

VASTE_CONCLUSIE_KLEUREN = [
    ("Tijdelijk verhoogd risico", "#ffff00"),
    ("Risicoboom", "#ff0000"),
    ("Goedgekeurd", "#008000"),
    ("Attentieboom", "#ffa500"),
    ("Afgekeurd", "#000000"),
    ("Verwijderd", "#808080"),
]

PALETTEN = [
    {
        "naam": "Natuurlijk & Organisch",
        "conditie": VASTE_CONDITIE_KLEUREN,
        "vta_condit": VASTE_CONDITIE_KLEUREN,
        "conclusie bvc": VASTE_CONCLUSIE_KLEUREN,
        "vta_conclu": VASTE_CONCLUSIE_KLEUREN,
        "projectinvloeden": [
            ("Verbeterd", "#556B2F"),
            ("Geen effect", "#8FA998"),
            ("Beperkt effect", "#E2B45C"),
            ("Sterk effect", "#C57B57"),
            ("Fataal", "#4F3130"),
            ("Verwijderd", "#7F8C8D"),
        ],
        "verplantbaarheid": [
            ("Direct verplantbaar", "#556B2F"),
            ("Verplantbaar met voorbereiding", "#E2B45C"),
            ("Niet verplantbaar", "#4F3130"),
        ],
        "_fallback": [
            "#556B2F",
            "#8FA998",
            "#E2B45C",
            "#C57B57",
            "#4F3130",
            "#7F8C8D",
            "#9B7653",
            "#B5A642",
        ],
    },
    {
        "naam": "Modern & Strak",
        "conditie": VASTE_CONDITIE_KLEUREN,
        "vta_condit": VASTE_CONDITIE_KLEUREN,
        "conclusie bvc": VASTE_CONCLUSIE_KLEUREN,
        "vta_conclu": VASTE_CONCLUSIE_KLEUREN,
        "projectinvloeden": [
            ("Verbeterd", "#27AE60"),
            ("Geen effect", "#82E0AA"),
            ("Beperkt effect", "#F1C40F"),
            ("Sterk effect", "#E67E22"),
            ("Fataal", "#C0392B"),
            ("Verwijderd", "#34495E"),
        ],
        "verplantbaarheid": [
            ("Direct verplantbaar", "#27AE60"),
            ("Verplantbaar met voorbereiding", "#F1C40F"),
            ("Niet verplantbaar", "#C0392B"),
        ],
        "_fallback": [
            "#3498DB",
            "#9B59B6",
            "#1ABC9C",
            "#F1C40F",
            "#E67E22",
            "#E74C3C",
            "#34495E",
            "#95A5A6",
        ],
    },
    {
        "naam": "Kleurblind-vriendelijk",
        "conditie": VASTE_CONDITIE_KLEUREN,
        "vta_condit": VASTE_CONDITIE_KLEUREN,
        "conclusie bvc": VASTE_CONCLUSIE_KLEUREN,
        "vta_conclu": VASTE_CONCLUSIE_KLEUREN,
        "projectinvloeden": [
            ("Verbeterd", "#004D40"),
            ("Geen effect", "#00897B"),
            ("Beperkt effect", "#D4E157"),
            ("Sterk effect", "#FFB300"),
            ("Fataal", "#D81B60"),
            ("Verwijderd", "#424242"),
        ],
        "verplantbaarheid": [
            ("Direct verplantbaar", "#004D40"),
            ("Verplantbaar met voorbereiding", "#D4E157"),
            ("Niet verplantbaar", "#D81B60"),
        ],
        "_fallback": [
            "#0072B2",
            "#E69F00",
            "#009E73",
            "#D55E00",
            "#CC79A7",
            "#F0E442",
            "#56B4E9",
            "#000000",
        ],
    },
    {
        "naam": "Pastel",
        "_fallback": [
            "#A8DADC",
            "#F4A261",
            "#E9C46A",
            "#BDE0FE",
            "#FFC8DD",
            "#CDB4DB",
            "#B7E4C7",
            "#FFDDD2",
        ],
    },
    {
        "naam": "Contrasterend",
        "_fallback": [
            "#E6194B",
            "#3CB44B",
            "#FFE119",
            "#4363D8",
            "#F58231",
            "#911EB4",
            "#46F0F0",
            "#F032E6",
            "#BCF60C",
            "#FABEBE",
        ],
    },
]


class CategorieKleurDialog(QDialog):
    def __init__(
        self, items, paletten, huidig_palet_index, veldnaam, laagnaam, parent=None
    ):
        super().__init__(parent)
        self.items = items
        self.paletten = paletten
        self.veldnaam = veldnaam
        self.setWindowTitle(f"Categorisatiekleuren - {laagnaam}")
        self.resize(720, 480)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                f"Veld: {veldnaam}. Controleer de waardes en pas kleuren aan waar nodig."
            )
        )

        palet_layout = QHBoxLayout()
        palet_layout.addWidget(QLabel("Kleurenpalet:"))
        self.palet_combo = QComboBox()
        for palet in paletten:
            self.palet_combo.addItem(palet.get("naam", "Palet"))
        self.palet_combo.setCurrentIndex(huidig_palet_index)
        palet_layout.addWidget(self.palet_combo)

        apply_button = QPushButton("Pas palet toe")
        apply_button.clicked.connect(self.apply_selected_palette)
        palet_layout.addWidget(apply_button)

        random_button = QPushButton("Willekeurige kleuren")
        random_button.clicked.connect(self.apply_distinct_colors)
        palet_layout.addWidget(random_button)
        palet_layout.addStretch()
        layout.addLayout(palet_layout)

        self.table = QTableWidget(len(items), 3)
        self.table.setHorizontalHeaderLabels(["Waarde", "Aantal", "Kleur"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        for row, item in enumerate(items):
            value_item = QTableWidgetItem(item["label"])
            value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, value_item)

            count_item = QTableWidgetItem(str(item["count"]))
            count_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            count_item.setFlags(count_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, count_item)

            color_button = QgsColorButton(self.table)
            color_button.setColor(QColor(item["color"]))
            color_button.setShowNull(False)
            color_button.setAllowOpacity(False)
            color_button.setText(item["color"])
            color_button.colorChanged.connect(
                lambda color, button=color_button: button.setText(color.name())
            )
            self.table.setCellWidget(row, 2, color_button)

        self.table.resizeColumnsToContents()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply_selected_palette(self):
        palet = self.paletten[self.palet_combo.currentIndex()]
        schema = palet.get(self.veldnaam.lower(), [])
        schema_map = {label.lower(): kleur for label, kleur in schema}
        fallback = palet.get("_fallback", [])

        fallback_index = 0
        for row, item in enumerate(self.items):
            button = self.table.cellWidget(row, 2)
            label = item["label"]
            if item["value"] is None:
                kleur = "#d3d3d3"
            elif label.lower() in schema_map:
                kleur = schema_map[label.lower()]
            elif fallback:
                kleur = fallback[fallback_index % len(fallback)]
                fallback_index += 1
            else:
                kleur = QColor.fromHsv((fallback_index * 60) % 360, 120, 230).name()
                fallback_index += 1
            button.setColor(QColor(kleur))
            button.setText(QColor(kleur).name())

    def apply_distinct_colors(self):
        color_index = 0
        total = max(1, len([item for item in self.items if item["value"] is not None]))
        for row, item in enumerate(self.items):
            button = self.table.cellWidget(row, 2)
            if item["value"] is None:
                kleur = "#d3d3d3"
            else:
                kleur = QColor.fromHsv(
                    int((color_index * 359) / total), 170, 230
                ).name()
                color_index += 1
            button.setColor(QColor(kleur))
            button.setText(QColor(kleur).name())

    def result_items(self):
        result = []
        for row, item in enumerate(self.items):
            button = self.table.cellWidget(row, 2)
            updated = dict(item)
            updated["color"] = button.color().name()
            result.append(updated)
        return result


class BoomstylerFinalAlgorithm(QgsProcessingAlgorithm):
    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return BoomstylerFinalAlgorithm()

    def name(self):
        return "boom_styler_v7_interactieve_kleuren"

    def displayName(self):
        return self.tr("Categorisatie")

    def group(self):
        return self.tr("")

    def groupId(self):
        return ""

    def flags(self):
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                "INPUT", "Kies laag", [QgsProcessing.TypeVectorAnyGeometry]
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                "CATEGORIEVELD",
                "Kies veld om op te stylen",
                parentLayerParameterName="INPUT",
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                "STIJL",
                "Kies startpalet",
                options=[palet["naam"] for palet in PALETTEN],
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                "INTERACTIEF",
                "Toon waardes met kleurkeuze voordat de stijl wordt toegepast",
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                "OPSLAAN",
                "Automatisch opslaan als GeoPackage in projectmap",
                defaultValue=True,
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        input_layer = self.parameterAsVectorLayer(parameters, "INPUT", context)
        veldnaam = self.parameterAsString(parameters, "CATEGORIEVELD", context)
        stijl_index = self.parameterAsInt(parameters, "STIJL", context)
        interactief = self.parameterAsBool(parameters, "INTERACTIEF", context)
        moet_opslaan = self.parameterAsBool(parameters, "OPSLAAN", context)

        if input_layer is None:
            raise QgsProcessingException("Geen geldige laag gekozen.")
        if not veldnaam:
            raise QgsProcessingException("Geen geldig veld gekozen.")

        schaal_expressie = "scale_linear(@map_scale, 350, 1000, 2.8, 1.5)"
        gekozen_palet = PALETTEN[stijl_index]
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
                feedback.reportError(
                    "Geen projectpad gevonden. Laag wordt als tijdelijk geladen."
                )
            else:
                clean_veld = "".join(x for x in veldnaam if x.isalnum() or x in "._- ")
                file_name = f"{input_layer.name()}_{clean_veld}.gpkg".replace(" ", "_")
                full_path = os.path.join(project_path, file_name)

                options = QgsVectorFileWriter.SaveVectorOptions()
                options.driverName = "GPKG"

                result = QgsVectorFileWriter.writeAsVectorFormatV3(
                    temp_layer, full_path, context.transformContext(), options
                )
                err = result[0]
                msg = result[1]

                if err == QgsVectorFileWriter.NoError:
                    final_layer = QgsVectorLayer(full_path, laagnaam, "ogr")
                else:
                    feedback.reportError(f"Fout bij opslaan: {msg}")

        counts = {}
        has_empty = False
        empty_count = 0
        for feat in final_layer.getFeatures():
            val = feat[veldnaam]
            if val is None or str(val).strip().lower() in ["", "null", "none"]:
                has_empty = True
                empty_count += 1
            else:
                label = str(val).strip()
                counts[label] = counts.get(label, 0) + 1

        schema_map = {label.lower(): kleur for label, kleur in schema}
        fallback_colors = gekozen_palet.get("_fallback", [])
        items = []
        used_values = set()

        for label, kleur in schema:
            match = next(
                (waarde for waarde in counts if waarde.lower() == label.lower()), None
            )
            if match:
                items.append(
                    {
                        "value": match,
                        "label": match,
                        "count": counts[match],
                        "color": kleur,
                    }
                )
                used_values.add(match)

        fallback_index = 0
        for waarde in sorted(
            [waarde for waarde in counts if waarde not in used_values], key=str.lower
        ):
            if waarde.lower() in schema_map:
                kleur = schema_map[waarde.lower()]
            elif fallback_colors:
                kleur = fallback_colors[fallback_index % len(fallback_colors)]
                fallback_index += 1
            else:
                kleur = QColor.fromHsv((fallback_index * 60) % 360, 120, 230).name()
                fallback_index += 1
            items.append(
                {
                    "value": waarde,
                    "label": waarde,
                    "count": counts[waarde],
                    "color": kleur,
                }
            )

        if has_empty:
            items.append(
                {
                    "value": None,
                    "label": "Onbekend / leeg",
                    "count": empty_count,
                    "color": "#d3d3d3",
                }
            )

        if not items:
            raise QgsProcessingException(f"Geen waardes gevonden in veld '{veldnaam}'.")

        if interactief:
            dialog = CategorieKleurDialog(
                items, PALETTEN, stijl_index, veldnaam, final_layer.name()
            )
            if dialog.exec_() != QDialog.Accepted:
                raise QgsProcessingException("Categorisatie geannuleerd.")
            items = dialog.result_items()

        def create_styled_symbol(color_hex):
            symbol = QgsSymbol.defaultSymbol(final_layer.geometryType())
            if symbol and symbol.symbolLayerCount() > 0:
                sl = symbol.symbolLayer(0)
                sl.setColor(QColor(color_hex))
                if hasattr(sl, "setStrokeColor"):
                    sl.setStrokeColor(QColor("#333333"))
                if hasattr(sl, "setStrokeWidth"):
                    sl.setStrokeWidth(0.2)
                try:
                    sl.setDataDefinedProperty(
                        QgsSymbolLayer.PropertySize,
                        QgsProperty.fromExpression(schaal_expressie),
                    )
                except Exception:
                    pass
            return symbol

        categories = []
        for item in items:
            categories.append(
                QgsRendererCategory(
                    item["value"], create_styled_symbol(item["color"]), item["label"]
                )
            )

        renderer = QgsCategorizedSymbolRenderer(veldnaam, categories)
        final_layer.setRenderer(renderer)
        final_layer.triggerRepaint()
        QgsProject.instance().addMapLayer(final_layer)

        feedback.pushInfo(f"Categorisatie toegepast op {len(categories)} waardes.")
        return {}
