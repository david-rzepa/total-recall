import QtQuick
import QtQuick.Controls as Controls
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Ui
import qs.Commons
import "RecoveryModel.js" as RecoveryModel

BarWidget {
  id: root
  moduleName: "dave.persist"
  property var state: ({windows: [], saved: []})
  property bool popupOpen: false
  readonly property bool opened: popupOpen
  property string failure: ""
  readonly property string mono: "monospace"
  readonly property var appLibrary: bar && bar.shell ? bar.shell.appLibrary : null
  function appIcon(row) {
    var wanted = (row.desktopId || row.app || "").replace(/\.desktop$/, "").toLowerCase()
    var entries = DesktopEntries.applications.values || []
    var app = entries.find(function(e) { return String(e.id).replace(/\.desktop$/, "").toLowerCase() === wanted })
    if (!app) app = entries.find(function(e) {
      var id = String(e.id).replace(/\.desktop$/, "").toLowerCase()
      return id && wanted.indexOf(id + ".") === 0
    })
    var name = app ? String(app.icon || "") : row.desktopId ? "application-x-executable" : "utilities-terminal"
    return appLibrary ? appLibrary.iconSource(name) : Quickshell.iconPath(name, true)
  }
  property string selectedKey: ""
  readonly property var selected: model.rows.find(r => r.uid === selectedKey) || null
  onModelChanged: Qt.callLater(syncSelection)
  function syncSelection() {
    var index = model.rows.findIndex(r => r.uid === selectedKey)
    if (index < 0) selectedKey = ""
    table.currentIndex = index
  }
  function selectIndex(index, scroll) {
    if (!model.rows.length) { selectedKey = ""; table.currentIndex = -1; return }
    index = Math.max(0, Math.min(model.rows.length - 1, index))
    selectedKey = model.rows[index].uid
    table.currentIndex = index
    if (scroll !== false) table.positionViewAtIndex(index, ListView.Contain)
    pendingFocus = selected && selected.address ? selected : null
    focusSelection()
  }
  function moveSelection(delta) {
    var index = model.rows.findIndex(r => r.uid === selectedKey)
    selectIndex(index < 0 ? (delta < 0 ? model.rows.length - 1 : 0) : index + delta)
  }
  property var pendingFocus: null
  property bool yieldingKeyboard: false
  function focusSelection() {
    if (!popupOpen || !pendingFocus || focusProcess.running || focusDispatch.running) return
    var row = pendingFocus
    pendingFocus = null
    failure = ""
    focusProcess.command = ["python3", "-B", script, "focus", "--address", row.address, "--key", row.key]
    yieldingKeyboard = true
    focusDispatch.start()
  }
  Timer {
    id: focusDispatch
    // Commit the layer's keyboard release before asking Hyprland to focus a client.
    interval: 25
    onTriggered: {
      if (root.popupOpen) focusProcess.running = true
      else root.yieldingKeyboard = false
    }
  }
  Process {
    id: focusProcess
    stderr: StdioCollector {
      onStreamFinished: {
        if (!text) return
        try { root.failure = JSON.parse(text).error || text } catch (e) { root.failure = text }
      }
    }
    onExited: function(code) {
      root.yieldingKeyboard = false
      if (root.popupOpen) {
        popup.focusPrimed = false
        popup.beginFocusPrime()
        Qt.callLater(function() { column.forceActiveFocus() })
      }
      Qt.callLater(root.focusSelection)
    }
  }
  property real now: Date.now() / 1000
  readonly property var model: RecoveryModel.build(state)
  readonly property bool stale: !state.updated || now - state.updated > 15
  readonly property bool hasError: stale || failure !== "" || model.error
  readonly property color statusColor: hasError ? "#ff5555" : model.dirty ? "#f1c40f" : "#ffffff"
  readonly property string statusText: hasError ? "Recovery error" : model.dirty ? "New windows to decide" : "Total Recall · all windows decided"
  readonly property string script: Qt.resolvedUrl("persist.py").toString().replace(/^file:\/\//, "")
  function close() { pendingFocus = null; focusDispatch.stop(); yieldingKeyboard = false; popupOpen = false }
  function open() { selectedKey = ""; table.currentIndex = -1; pendingFocus = null; if (appLibrary) appLibrary.refreshIcons(); popupOpen = true }
  function togglePanel() { if (popupOpen) close(); else open() }
  function skipRow(row) {
    if (!row || stale || operation.running) return
    if (!row.address) {
      if (!row.saved) return
      failure = ""
      operation.command = ["python3", "-B", script, "forget", "--id", row.id]
      operation.running = true
      return
    }
    failure = ""
    operation.command = ["python3", "-B", script, "skip", "--address", row.address, "--key", row.key]
    operation.running = true
  }
  function toggleRow(row) {
    if (!row || stale || operation.running || !(row.needsAdapter || row.saved || (row.eligible && row.address))) return
    failure = ""
    operation.command = ["python3", "-B", script].concat(RecoveryModel.primaryAction(row))
    if (row.closed) close()
    operation.running = true
  }
  IpcHandler {
    target: "dave.persist"
    function toggle(): void { root.broadcast("togglePanel") }
    function selection(): string {
      return JSON.stringify({open: root.opened, keyboardFocus: column.activeFocus,
        selected: root.selected, rows: root.model.rows.map(r => ({uid: r.uid, address: r.address}))})
    }
  }
  implicitWidth: icon.implicitWidth + Style.space(16)
  implicitHeight: barSize
  Process {
    id: poll
    command: ["python3", "-B", root.script, "status"]
    running: true
    stdout: StdioCollector {
      onStreamFinished: {
        try { root.state = JSON.parse(text) }
        catch (e) { root.failure = "Could not read recovery status." }
      }
    }
  }
  Timer {
    interval: 2000; running: true; repeat: true
    onTriggered: {
      root.now = Date.now() / 1000
      if (!poll.running) poll.running = true
    }
  }
  Process {
    id: operation
    stderr: StdioCollector {
      onStreamFinished: {
        if (!text) return
        try { root.failure = JSON.parse(text).error || text }
        catch (e) { root.failure = text }
      }
    }
    onExited: function(code) {
      if (code !== 0 && !root.failure) root.failure = "Could not update saved recovery."
      if (code !== 0) root.open()
      if (!poll.running) poll.running = true
    }
  }
  Text {
    id: icon
    anchors.centerIn: parent
    text: "󰋚"
    color: root.statusColor
    font.family: root.bar.fontFamily
    font.pixelSize: Style.font.body
  }
  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onClicked: root.togglePanel()
    onEntered: if (root.bar) root.bar.showTooltip(root, root.statusText)
    onExited: if (root.bar) root.bar.hideTooltip(root)
  }
  KeyboardPanel {
    id: popup
    anchorItem: root
    bar: root.bar
    owner: root
    open: root.popupOpen
    focusTarget: column
    // Briefly yield keyboard ownership so the compositor can activate the
    // selected client, then reacquire it for continued popup navigation.
    WlrLayershell.keyboardFocus: !root.popupOpen || root.yieldingKeyboard
      ? WlrKeyboardFocus.None
      : (popup.focusPrimed ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.Exclusive)
    contentWidth: popup.fittedContentWidth(Style.space(780))
    contentHeight: popup.fittedContentHeight(column.implicitHeight)
    Column {
      id: column
      width: parent.width
      spacing: Style.space(6)
      focus: true
      Keys.onPressed: function(event) {
        event.accepted = true
        if (event.key === Qt.Key_Escape || event.text === "q") root.close()
        else if (event.key === Qt.Key_Down || event.text === "j") root.moveSelection(1)
        else if (event.key === Qt.Key_Up || event.text === "k") root.moveSelection(-1)
        else if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab)
          root.moveSelection((event.modifiers & Qt.ShiftModifier) || event.key === Qt.Key_Backtab ? -1 : 1)
        else if (event.key === Qt.Key_Home) root.selectIndex(0)
        else if (event.key === Qt.Key_End) root.selectIndex(root.model.rows.length - 1)
        else if (event.key === Qt.Key_PageDown) root.moveSelection(8)
        else if (event.key === Qt.Key_PageUp) root.moveSelection(-8)
        else if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && root.selected && root.selected.closed) root.toggleRow(root.selected)
        else if (event.key === Qt.Key_Space || event.text === "s") root.toggleRow(root.selected)
        else if (event.text === "n" || (event.key === Qt.Key_Delete && root.selected && root.selected.closed)) root.skipRow(root.selected)
        else event.accepted = false
      }
      Row {
        width: parent.width
        height: Style.space(24)
        Text {
          anchors.verticalCenter: parent.verticalCenter
          text: "Total Recall"
          color: root.bar.foreground
          font.family: root.mono
          font.pixelSize: Style.font.subtitle
          font.bold: true
          width: parent.width - Style.space(110)
        }
        Text {
          anchors.verticalCenter: parent.verticalCenter
          text: root.model.count + " windows"
          color: Qt.alpha(root.bar.foreground, 0.6)
          font.family: root.mono
          font.pixelSize: Style.font.bodySmall
        }
      }
      Text {
        width: parent.width
        visible: root.hasError
        textFormat: Text.PlainText
        text: root.stale ? "! recovery service unavailable" : "! " + (root.failure || "Select an error row for details.")
        color: "#ff5555"
        wrapMode: Text.Wrap
        font.family: root.mono
        font.pixelSize: Style.font.bodySmall
      }
      Rectangle {
        width: parent.width
        height: Style.space(28)
        color: Qt.alpha(root.bar.foreground, 0.09)
        Row {
          anchors.fill: parent
          Text { height: parent.height; verticalAlignment: Text.AlignVCenter; width: Style.space(22); text: " " }
          Text { height: parent.height; verticalAlignment: Text.AlignVCenter; width: Style.space(84); text: "PERSIST"; font.bold: true; color: root.bar.foreground; font.family: root.mono; font.pixelSize: Style.font.bodySmall }
          Text { height: parent.height; verticalAlignment: Text.AlignVCenter; width: Style.space(100); text: "WORKSPACE"; font.bold: true; color: root.bar.foreground; font.family: root.mono; font.pixelSize: Style.font.bodySmall }
          Text { height: parent.height; verticalAlignment: Text.AlignVCenter; width: Style.space(70); text: "GROUP"; font.bold: true; color: root.bar.foreground; font.family: root.mono; font.pixelSize: Style.font.bodySmall }
          Text { height: parent.height; verticalAlignment: Text.AlignVCenter; width: Style.space(220); text: "APPLICATION"; font.bold: true; color: root.bar.foreground; font.family: root.mono; font.pixelSize: Style.font.bodySmall }
          Text { height: parent.height; verticalAlignment: Text.AlignVCenter; width: parent.width - Style.space(496); text: "WINDOW"; font.bold: true; color: root.bar.foreground; font.family: root.mono; font.pixelSize: Style.font.bodySmall }
        }
      }
      ListView {
        id: table
        width: parent.width
        height: Math.min(contentHeight, Style.space(440), Math.max(100, popup.availableCardHeight - Style.space(180)))
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: root.model.rows
        spacing: 0
        Controls.ScrollBar.vertical: Controls.ScrollBar {}
        delegate: Rectangle {
          id: entry
          required property var modelData
          required property int index
          width: table.width
          height: Style.space(28)
          color: root.selectedKey === modelData.uid ? Qt.alpha(root.bar.foreground, 0.12) : "transparent"
          MouseArea {
            anchors.fill: parent
            onClicked: { root.selectIndex(entry.index); column.forceActiveFocus() }
          }
          Row {
            anchors.fill: parent
            Text {
              height: parent.height
              verticalAlignment: Text.AlignVCenter
              width: Style.space(22)
              text: root.selectedKey === entry.modelData.uid ? ">" : " "
              color: root.bar.foreground
              font.family: root.mono
              font.pixelSize: Style.font.bodySmall
            }
            Text {
              height: parent.height
              verticalAlignment: Text.AlignVCenter
              width: Style.space(84)
              text: entry.modelData.closed ? "?" : entry.modelData.error ? "×" : entry.modelData.saved ? "✓" : entry.modelData.undecided ? "!" : "–"
              color: entry.modelData.closed || entry.modelData.error ? "#ff5555" : entry.modelData.undecided ? "#f1c40f" : entry.modelData.saved || entry.modelData.eligible ? root.bar.foreground : Qt.alpha(root.bar.foreground, 0.35)
              font.family: root.mono
              font.pixelSize: Style.font.bodySmall
              MouseArea {
                anchors.fill: parent
                cursorShape: entry.modelData.needsAdapter || entry.modelData.saved || entry.modelData.eligible ? Qt.PointingHandCursor : Qt.ArrowCursor
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                onClicked: function(mouse) {
                  root.selectIndex(entry.index)
                  if (mouse.button === Qt.RightButton) root.skipRow(entry.modelData)
                  else root.toggleRow(entry.modelData)
                  column.forceActiveFocus()
                }
              }
            }
            Text {
              height: parent.height
              verticalAlignment: Text.AlignVCenter
              width: Style.space(100)
              text: entry.modelData.workspace
              color: Qt.alpha(root.bar.foreground, 0.8)
              font.family: root.mono
              font.pixelSize: Style.font.bodySmall
            }
            Text {
              height: parent.height
              verticalAlignment: Text.AlignVCenter
              width: Style.space(70)
              text: entry.modelData.groupLabel || "–"
              color: Qt.alpha(root.bar.foreground, 0.8)
              font.family: root.mono
              font.pixelSize: Style.font.bodySmall
            }
            Row {
              height: parent.height
              width: Style.space(220)
              spacing: Style.space(6)
              Image {
                width: Style.space(16)
                height: Style.space(16)
                anchors.verticalCenter: parent.verticalCenter
                source: root.appIcon(entry.modelData)
                fillMode: Image.PreserveAspectFit
                asynchronous: true
              }
              Text {
              height: parent.height
              verticalAlignment: Text.AlignVCenter
                width: parent.width - Style.space(28)
                text: entry.modelData.label
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: root.bar.foreground
                font.family: root.mono
                font.pixelSize: Style.font.bodySmall
              }
            }
            Text {
              height: parent.height
              verticalAlignment: Text.AlignVCenter
              width: parent.width - Style.space(496)
              text: entry.modelData.title || "(closed)"
              textFormat: Text.PlainText
              elide: Text.ElideRight
              color: Qt.alpha(root.bar.foreground, 0.7)
              font.family: root.mono
              font.pixelSize: Style.font.bodySmall
            }

          }
        }
      }
      Text {
        width: parent.width
        textFormat: Text.PlainText
        text: root.selected ? root.selected.detail : root.model.rows.length ? "Select a window to inspect it." : "No windows."
        color: Qt.alpha(root.bar.foreground, 0.75)
        wrapMode: Text.Wrap
        maximumLineCount: 4
        elide: Text.ElideRight
        font.family: root.mono
        font.pixelSize: Style.font.caption
      }
      Text {
        width: parent.width
        text: root.selected && root.selected.closed ? "j/k ↑/↓ Tab select · Enter/Space restore · Delete/n delete entry · Esc close" : "j/k ↑/↓ Tab select & focus · Space " + (root.selected && root.selected.needsAdapter ? "create adapter" : root.selected && root.selected.saved ? "unpersist" : "persist") + " · n skip · Esc close"
        wrapMode: Text.Wrap
        color: root.bar.foreground
        font.family: root.mono
        font.pixelSize: Style.font.caption
      }
    }
  }
}
