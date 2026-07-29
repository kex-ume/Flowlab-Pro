from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
)
from reportlab.lib.styles import getSampleStyleSheet


class PDFExporter:

    def export(self, filename, table_widget, title):

        styles = getSampleStyleSheet()

        doc = SimpleDocTemplate(
            filename,
            pagesize=landscape(A4),
        )

        data = []

        headers = []

        for col in range(table_widget.columnCount()):
            headers.append(
                table_widget.horizontalHeaderItem(col).text()
            )

        data.append(headers)

        for row in range(table_widget.rowCount()):

            if table_widget.isRowHidden(row):
                continue

            values = []

            for col in range(table_widget.columnCount()):

                item = table_widget.item(row, col)

                values.append("" if item is None else item.text())

            data.append(values)

        table = Table(data)

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ]))

        doc.build([
            Paragraph(f"<b>{title} Report</b>", styles["Title"]),
            table,
        ])