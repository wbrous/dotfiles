// One-line pseudo-toast shown at the open end of the popup stack when the
// backlog queue holds more notifications than fit on screen ("+N more
// notifications"). Purely presentational — the count is pushed in from the
// container, same pattern as NotificationCard.
import QtQuick
import qs.Commons
import qs.Ui

BorderSurface {
  id: root

  property int count: 0
  property int cornerRadius: 0
  property string fontFamily: ""

  readonly property var indicatorBorderSpec: Border.surfaceSpec("notifications", "border", Color.notifications.border, Math.max(1, Style.space(2)))

  implicitWidth: Style.space(380)
  implicitHeight: label.implicitHeight + borderTop + borderBottom + Style.space(14)
  radius: cornerRadius
  color: Color.notifications.background
  borderSpec: indicatorBorderSpec
  clip: true

  Text {
    id: label
    anchors.centerIn: parent
    text: "+" + root.count + " more notification" + (root.count === 1 ? "" : "s")
    font.family: root.fontFamily
    font.pixelSize: Style.font.title
    color: Qt.darker(Color.notifications.text, 1.15)
  }
}
