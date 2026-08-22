from __future__ import annotations

from html import escape

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView

from app.database.database import get_connection


class _DashboardBridge(QObject):
    action_requested = Signal(str)

    @Slot(str)
    def open(self, action: str):
        self.action_requested.emit(action)


class DashboardPage(QWebEngineView):
    action_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LiveDashboard")
        self._bridge = _DashboardBridge(self)
        self._bridge.action_requested.connect(self.action_requested.emit)
        self._channel = QWebChannel(self.page())
        self._channel.registerObject("flowlabBridge", self._bridge)
        self.page().setWebChannel(self._channel)
        self.refresh()

    def refresh(self):
        connection = get_connection()
        try:
            due_setting = connection.execute("""SELECT setting_value FROM system_settings
                WHERE setting_key='equipment_due_soon_days'""").fetchone()
            try:
                due_days = max(0, int(due_setting[0])) if due_setting else 30
            except (TypeError, ValueError):
                due_days = 30
            counts = {
                "Equipment": connection.execute("SELECT COUNT(*) FROM laboratory_equipment WHERE is_active=1").fetchone()[0],
                "Calibration Programme": connection.execute("SELECT COUNT(*) FROM laboratory_equipment WHERE is_active=1 AND include_in_calibration_programme=1").fetchone()[0],
                "Open Jobs": connection.execute("SELECT COUNT(*) FROM calibration_jobs WHERE is_deleted=0 AND status NOT IN ('Completed','Closed')").fetchone()[0],
                "Controlled Documents": connection.execute("SELECT COUNT(*) FROM controlled_documents WHERE is_deleted=0").fetchone()[0],
            }
            overdue = connection.execute("""SELECT COUNT(*) FROM laboratory_equipment
                WHERE is_active=1 AND next_calibration_date IS NOT NULL
                AND next_calibration_date < date('now','localtime')""").fetchone()[0]
            due_soon = connection.execute("""SELECT COUNT(*) FROM laboratory_equipment
                WHERE is_active=1 AND next_calibration_date >= date('now','localtime')
                AND next_calibration_date <= date('now','localtime',?)""",
                (f"+{due_days} days",)).fetchone()[0]
            jobs = connection.execute("""SELECT j.job_number,COALESCE(c.customer_name,''),
                j.mut_description,j.status,j.required_date FROM calibration_jobs j
                LEFT JOIN customers c ON c.id=j.customer_id WHERE j.is_deleted=0
                ORDER BY j.id DESC LIMIT 8""").fetchall()
        finally:
            connection.close()
        cards = "".join(
            f'<button class="card" data-route="{route}"><span>{escape(label)}</span><strong>{value}</strong></button>'
            for (label, value), route in zip(counts.items(), ("laboratory", "laboratory", "projects", "standards"))
        )
        rows = "".join(
            "<tr>" + "".join(f"<td>{escape(str(value or ''))}</td>" for value in row) + "</tr>"
            for row in jobs
        )
        if not rows:
            rows = '<tr><td colspan="5"><div class="empty">No jobs match the selected filters.</div></td></tr>'
        html = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
        <style>:root{{--bg:#f2f6f9;--ink:#0e2131;--muted:#5b7185;--border:#dce5ec;--teal:#0e7c86;--red:#c6413e;--amber:#c2872f}}*{{box-sizing:border-box}}body{{margin:0;padding:clamp(14px,3vw,28px);background:var(--bg);color:var(--ink);font:14px Arial,sans-serif}}.cards{{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:14px}}.card{{display:flex;justify-content:space-between;align-items:center;min-height:88px;padding:18px;background:#fff;border:1px solid var(--border);border-radius:12px;color:var(--ink);cursor:pointer}}.card span{{color:var(--muted)}}.card strong{{font-size:28px}}.alerts{{display:flex;gap:12px;margin:18px 0}}.alert{{flex:1;padding:15px;border-radius:10px;background:#fff;border:1px solid var(--border)}}.alert strong{{display:block;font-size:22px;color:var(--red)}}.alert.due strong{{color:var(--amber)}}.panel{{background:#fff;border:1px solid var(--border);border-radius:12px;padding:18px;overflow:auto}}table{{width:100%;min-width:640px;border-collapse:collapse}}th,td{{padding:11px;text-align:left;border-bottom:1px solid var(--border)}}th{{font-size:11px;color:var(--muted)}}.empty{{padding:28px;text-align:center;color:var(--muted)}}@media(max-width:850px){{.cards{{grid-template-columns:repeat(2,1fr)}}}}@media(max-width:520px){{.cards{{grid-template-columns:1fr}}.alerts{{flex-direction:column}}}}@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto!important;transition:none!important}}}}</style></head><body>
        <section class="cards">{cards}</section><section class="alerts"><div class="alert"><span>Expired Equipment</span><strong>{overdue}</strong></div><div class="alert due"><span>Due Within {due_days} Days</span><strong>{due_soon}</strong></div></section>
        <section class="panel"><table><thead><tr><th>Job</th><th>Customer</th><th>MUT</th><th>Status</th><th>Required Date</th></tr></thead><tbody>{rows}</tbody></table></section>
        <script src="qrc:///qtwebchannel/qwebchannel.js"></script><script>new QWebChannel(qt.webChannelTransport,channel=>{{document.querySelectorAll('[data-route]').forEach(button=>button.addEventListener('click',()=>channel.objects.flowlabBridge.open(button.dataset.route)))}});</script></body></html>"""
        self.setHtml(html)
