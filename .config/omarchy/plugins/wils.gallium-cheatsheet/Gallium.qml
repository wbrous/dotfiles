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
//
// The surface itself is a stationary, full-screen, click-through-except-
// over-the-card layer (same pattern as the notifications/OSD/menu overlays
// in this shell — see `mask: Region { item: card }`). Only `card` moves,
// via plain Item x/y, using MouseArea's built-in `drag.target` — Qt's own
// well-tested pointer-tracking, not hand-rolled delta math, which kept
// drifting/overshooting under fast mouse movement.
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

    // Full-screen, fixed surface — the surface itself never moves, only
    // `card` does (via x/y), so nothing round-trips through the compositor
    // mid-drag.
    anchors { top: true; bottom: true; left: true; right: true }

    // Click-through everywhere except over the card.
    mask: Region { item: card }

    readonly property real screenW: panel.screen ? panel.screen.width : 0
    readonly property real screenH: panel.screen ? panel.screen.height : 0

    function clampedX(x) { return Math.min(Math.max(x, 0), Math.max(0, screenW - card.width)) }
    function clampedY(y) { return Math.min(Math.max(y, 0), Math.max(0, screenH - card.height)) }

    onVisibleChanged: {
      if (!visible) return
      card.x = clampedX(pos.x)
      card.y = clampedY(pos.y)
    }

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
        drag.target: card
        drag.axis: Drag.XAndYAxis
        drag.minimumX: 0
        drag.maximumX: Math.max(0, panel.screenW - card.width)
        drag.minimumY: 0
        drag.maximumY: Math.max(0, panel.screenH - card.height)
        onReleased: {
          pos.x = card.x
          pos.y = card.y
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
