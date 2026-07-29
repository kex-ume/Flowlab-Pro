from openpyxl import Workbook


class ExcelExporter:

    def export(self, filename, table_widget, title):

        wb = Workbook()

        ws = wb.active
        ws.title = title

        headers = []

        for col in range(table_widget.columnCount()):
            headers.append(
                table_widget.horizontalHeaderItem(col).text()
            )

        ws.append(headers)

        for row in range(table_widget.rowCount()):

            if table_widget.isRowHidden(row):
                continue

            values = []

            for col in range(table_widget.columnCount()):

                item = table_widget.item(row, col)

                values.append("" if item is None else item.text())

            ws.append(values)

        wb.save(filename)