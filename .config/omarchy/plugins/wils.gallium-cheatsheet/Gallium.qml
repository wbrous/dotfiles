// Shows a draggable Gallium keymap cheat sheet while the Gallium keyboard
// layout is the active xkb group, and hides it the moment the layout
// switches away (e.g. back to QWERTY via grp:alts_toggle).
//
// Detection mirrors the bar's KeyboardLayout widget: poll `hyprctl -j
// devices` for each typed keyboard's active_keymap description, and refresh
// on Hyprland's "activelayout"/"configreloaded" events rather than polling
// on a timer. The xkb variant this pairs with (see ~/.config/hypr/input.lua)
// reports itself as "English (US, Gallium)" — see us(gallium) in
// /usr/share/X11/xkb/symbols/us.

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import Quickshell.Wayland
import qs.Commons
import qs.Ui

Item {
  id: root

  readonly property var untypedKeyboards: /^(hl-virtual-keyboard|power-button|sleep-button|lid-switch|video-bus)/
  property bool galliumActive: false

  function refresh() {
    if (queryProc.running) return
    queryProc.running = true
  }

  Component.onCompleted: refresh()

  Connections {
    target: Hyprland
    function onRawEvent(event) {
      if (!event || !event.name) return
      const name = String(event.name)
      if (name.indexOf("activelayout") !== -1 || name === "configreloaded") root.refresh()
    }
  }

  Process {
    id: queryProc
    command: ["hyprctl", "-j", "devices"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        let listed
        try {
          listed = JSON.parse(text || "{}").keyboards
        } catch (e) {
          return
        }
        if (!Array.isArray(listed)) return

        root.galliumActive = listed.some(function(kb) {
          if (root.untypedKeyboards.test(String(kb.name || ""))) return false
          return String(kb.active_keymap || "").indexOf("Gallium") !== -1
        })
      }
    }
  }

  // Drag position persists across shell reloads/restarts so the card stays
  // where it was left.
  PersistentProperties {
    id: pos
    reloadableId: "gallium-cheatsheet-position"
    property real x: 120
    property real y: 120
  }

  PanelWindow {
    id: panel
    visible: root.galliumActive
    color: "transparent"
    WlrLayershell.namespace: "gallium-cheatsheet"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    exclusionMode: ExclusionMode.Ignore
    anchors { left: true; top: true }
    margins.left: pos.x
    margins.top: pos.y
    implicitWidth: card.width
    implicitHeight: card.height

    readonly property real screenW: panel.screen ? panel.screen.width : 0
    readonly property real screenH: panel.screen ? panel.screen.height : 0

    function clamp() {
      if (screenW <= 0 || screenH <= 0) return
      pos.x = Math.min(Math.max(pos.x, 0), Math.max(0, screenW - card.width))
      pos.y = Math.min(Math.max(pos.y, 0), Math.max(0, screenH - card.height))
    }

    onVisibleChanged: if (visible) clamp()

    BorderSurface {
      id: card
      width: Math.max(header.implicitWidth, image.width) + card.borderLeft + card.borderRight + 2 * Style.space(14)
      height: card.borderTop + card.borderBottom + header.implicitHeight + Style.space(10) + image.height + 2 * Style.space(14)
      color: Util.alpha(Color.background, 0.97)
      borderSpec: Border.surfaceSpec("popups", "border", Color.popups.border, Math.max(1, Style.space(2)))
      radius: Style.cornerRadius

      MouseArea {
        id: dragArea
        anchors.fill: parent
        cursorShape: Qt.SizeAllCursor
        property real pressX: 0
        property real pressY: 0
        onPressed: function(mouse) {
          pressX = mouse.x
          pressY = mouse.y
        }
        onPositionChanged: function(mouse) {
          if (!pressed) return
          pos.x += mouse.x - pressX
          pos.y += mouse.y - pressY
          panel.clamp()
        }
      }

      Column {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.margins: card.borderTop + Style.space(14)
        spacing: Style.space(10)

        Text {
          id: header
          text: "Gallium layout active"
          font.family: Style.font.family
          font.bold: true
          font.pixelSize: Style.font.body
          color: Color.popups.text
        }

        Image {
          id: image
          source: "assets/keymap.svg"
          sourceSize.width: 599 * 1.5
          sourceSize.height: 165 * 1.5
          width: sourceSize.width
          height: sourceSize.height
          fillMode: Image.PreserveAspectFit
          smooth: true
        }
      }
    }
  }
}
