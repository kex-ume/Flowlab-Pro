/* Equipment Logs — serialise the replica sheet's table inputs into rows_json. */
(function () {
    function gridRows(grid) {
        return Array.from(grid.querySelectorAll('tr')).filter(function (tr) {
            return tr.querySelector('input.cell');
        });
    }

    function serialize(grid, rowsInput) {
        var rows = gridRows(grid).map(function (tr) {
            return Array.from(tr.querySelectorAll('input.cell')).map(function (input) { return input.value; });
        });
        rowsInput.value = JSON.stringify(rows);
    }

    window.EquipmentLogs = {
        serialize: function (gridId, formId) {
            var grid = document.getElementById(gridId);
            var form = document.getElementById(formId);
            if (!grid || !form) { return; }
            serialize(grid, form.querySelector('input[name=rows_json]'));
        },
        bindSerializer: function (gridId, formId) {
            var grid = document.getElementById(gridId);
            var form = document.getElementById(formId);
            if (!grid || !form) { return; }
            var rowsInput = form.querySelector('input[name=rows_json]');
            var handler = function () { serialize(grid, rowsInput); };
            form.addEventListener('submit', handler);
            handler();
        },
        addRow: function (gridId) {
            var grid = document.getElementById(gridId);
            var tbody = grid.querySelector('tbody');
            var columnCount = grid.querySelectorAll('thead th, tbody tr:first-child td').length;
            var tr = document.createElement('tr');
            for (var index = 0; index < columnCount - 1; index += 1) {
                var td = document.createElement('td');
                td.innerHTML = '<input class="qinput cell" type="text">';
                tr.appendChild(td);
            }
            var remove = document.createElement('td');
            remove.innerHTML = '<button type="button" class="el-row-del" title="Remove row">&times;</button>';
            tr.appendChild(remove);
            tbody.appendChild(tr);
        },
        removeRow: function (button) {
            var tr = button.closest('tr');
            if (tr) { tr.remove(); }
        }
    };
})();
