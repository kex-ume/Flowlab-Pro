"""The FlowLab Pro dashboard, rendered from the approved interface reference.

The supplied HTML is retained verbatim in ``app/ui/resources`` so the visual
baseline stays traceable.  This wrapper removes the duplicate HTML shell,
lets the native PySide shell own navigation, and turns every dashboard summary
into an in-application route.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView


class _DashboardBridge(QObject):
    """A deliberately narrow bridge from the approved HTML to PySide pages."""

    action_requested = Signal(str)

    @Slot(str)
    def open(self, action: str):
        self.action_requested.emit(action)


class DashboardPage(QWebEngineView):
    """Reference-accurate, interactive laboratory dashboard.

    The document's dashboard is the visual source of truth.  A small, runtime
    injected behaviour layer maps each information surface to the relevant
    native module without altering the approved markup or styling.
    """

    action_requested = Signal(str)

    _REFERENCE_FILE = (
        Path(__file__).resolve().parents[2]
        / "resources"
        / "dashboard_reference.html"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ReferenceDashboard")

        self._bridge = _DashboardBridge(self)
        self._bridge.action_requested.connect(self.action_requested.emit)
        self._channel = QWebChannel(self.page())
        self._channel.registerObject("flowlabBridge", self._bridge)
        self.page().setWebChannel(self._channel)
        self.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
            True,
        )
        self.loadFinished.connect(self._configure_reference_view)

        if not self._REFERENCE_FILE.exists():
            raise FileNotFoundError(
                "The approved FlowLab dashboard reference is missing: "
                f"{self._REFERENCE_FILE}"
            )
        self.load(QUrl.fromLocalFile(str(self._REFERENCE_FILE)))

    def refresh(self):
        """Reload the reference view when a manual dashboard refresh is needed."""
        self.reload()

    def _configure_reference_view(self, loaded: bool):
        if not loaded:
            return
        self.page().runJavaScript(self._interaction_script())

    @staticmethod
    def _interaction_script() -> str:
        """Hide the HTML shell and turn dashboard information into routes."""
        return """
            (() => {
                if (document.documentElement.dataset.flowlabNativeShell) return;
                document.documentElement.dataset.flowlabNativeShell = 'loading';

                const activate = () => {
                    if (!window.flowlabBridge || document.documentElement.dataset.flowlabNativeShell === 'ready') return;
                    const shellStyle = document.createElement('style');
                    shellStyle.textContent = `
                    .sidebar, .topbar { display: none !important; }
                    html, body, .layout, .main { height: auto !important; min-height: 100% !important; }
                    .layout, .main { display: block !important; }
                    .content { overflow: visible !important; padding: 26px 28px 40px !important; }
                    .flowlab-action { cursor: pointer !important; }
                    .flowlab-action:focus-visible { outline: 2px solid var(--teal) !important; outline-offset: 3px; }
                    `;
                    document.head.appendChild(shellStyle);

                    const route = (target) => window.flowlabBridge.open(target);
                    const wire = (elements, target) => {
                    [...elements].forEach((element) => {
                        if (element.dataset.flowlabAction) return;
                        element.dataset.flowlabAction = target;
                        element.classList.add('flowlab-action');
                        element.setAttribute('role', 'link');
                        element.tabIndex = 0;
                        element.addEventListener('click', (event) => {
                            event.preventDefault();
                            event.stopPropagation();
                            route(target);
                        });
                        element.addEventListener('keydown', (event) => {
                            if (event.key === 'Enter' || event.key === ' ') {
                                event.preventDefault();
                                route(target);
                            }
                        });
                    });
                    };

                    const metrics = document.querySelectorAll('#dashboard-page .gauge-card');
                    metrics.forEach((card, index) => wire([card], index === 3 ? 'laboratory' : 'projects'));
                    wire(document.querySelectorAll('#dashboard-page .readiness-item'), 'laboratory');
                    wire(document.querySelectorAll('#dashboard-page .status-bar'), 'laboratory');
                    wire(document.querySelectorAll('#dashboard-page .data tbody tr'), 'projects');
                    wire(document.querySelectorAll('#dashboard-page .notif-item'), 'reminders');
                    document.querySelectorAll('#dashboard-page .panel-link').forEach((link) => {
                        const label = link.textContent.toLowerCase();
                        wire([link], label.includes('equipment') ? 'laboratory' : label.includes('jobs') ? 'projects' : 'reminders');
                    });

                    const quickActions = ['projects', 'laboratory', 'reports', 'tools', 'standards'];
                    document.querySelectorAll('#dashboard-page .qa-card').forEach((card, index) => {
                    wire([card], quickActions[index] || 'dashboard');
                    });
                    wire(document.querySelectorAll('#dashboard-page .meta-pill'), 'reminders');
                    wire(document.querySelectorAll('#dashboard-page .foot-note'), 'settings');
                    document.documentElement.dataset.flowlabNativeShell = 'ready';
                };

                const connectBridge = () => {
                    new QWebChannel(qt.webChannelTransport, (channel) => {
                        window.flowlabBridge = channel.objects.flowlabBridge;
                        activate();
                    });
                };
                if (window.QWebChannel) {
                    connectBridge();
                } else {
                    const bridgeScript = document.createElement('script');
                    bridgeScript.src = 'qrc:///qtwebchannel/qwebchannel.js';
                    bridgeScript.onload = connectBridge;
                    document.head.appendChild(bridgeScript);
                }
            })();
        """
