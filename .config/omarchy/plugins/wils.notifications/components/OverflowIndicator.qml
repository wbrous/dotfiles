// One-line pseudo-toast above the deck when the backlog queue holds
// notifications that are not on screen ("+N more notifications"). Purely
// presentational: the count is pushed in by the service.
import QtQuick
import qs.Commons
import qs.Ui

BorderSurface {
  id: root

  /// Notifications waiting off screen. Precondition: >= 0.
  property int count: 0

  implicitWidth: Style.space(380)
  implicitHeight: label.implicitHeight + borderTop + borderBottom + Style.space(14)
  radius: Style.cornerRadius
  color: Color.notifications.background
  borderSpec: Border.surfaceSpec("notifications", "border", Color.notifications.border, Math.max(1, Style.space(2)))
  clip: true

  Text {
    id: label
    textFormat: Text.PlainText
    anchors.centerIn: parent
    text: "+" + root.count + " more notification" + (root.count === 1 ? "" : "s")
    font.family: Style.font.family
    font.pixelSize: Style.font.title
    color: Qt.darker(Color.notifications.text, 1.15)
  }
}
