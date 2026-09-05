import QtQuick
import qs.Commons
import qs.Ui

BarIndicator {
  id: root

  // If the built-in notifications plugin has been cloned (e.g.
  // wils.notifications), the original "omarchy.notifications" is disabled
  // and firstPartyServiceFor would return null, silently breaking this
  // indicator (renders inactive, click does nothing). resolveEnabledId maps
  // the built-in id to whichever enabled plugin actually implements it.
  readonly property string notificationServiceId:
    bar?.shell?.pluginRegistry?.resolveEnabledId("omarchy.notifications") ?? "omarchy.notifications"
  readonly property var notificationService: bar?.shell?.firstPartyServiceFor(notificationServiceId)
  readonly property bool dnd: notificationService ? notificationService.doNotDisturb : false

  active: dnd
  activeText: "󰂛"
  inactiveText: "󰂛"
  activeTooltipText: "Allow Notifications"
  inactiveTooltipText: "Silence Notifications"

  onPressed: function() {
    if (root.notificationService) {
      root.notificationService.setDoNotDisturb(!root.notificationService.doNotDisturb)
    }
  }
}
