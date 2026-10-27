-- Launch an app in the background: its window opens on its own workspace
-- without moving the user's view or taking focus.
--
-- Both rules are required. no_initial_focus stops the window being focused when
-- it first maps; suppress_event=activatefocus stops the app taking focus
-- afterwards, which Electron/GTK/Firefox-based apps do once their window is up
-- (Hyprland honours that because misc:focus_on_activate is on). With
-- no_initial_focus alone the app still pulled the view to its workspace.
--
-- Usage: o.launch_background("cider", "9")
--   command    shell command, run through uwsm-app like every other autostart
--   workspace  workspace name to open on; pair it with an o.window(...) rule if
--              the app should also be kept there on later launches
function o.launch_background(command, workspace)
  assert(type(command) == "string" and command ~= "", "launch_background: command must be a non-empty string")
  assert(type(workspace) == "string" and workspace ~= "", "launch_background: workspace must be a non-empty string")

  hl.exec_cmd(o.launch(command), {
    workspace = workspace,
    no_initial_focus = true,
    suppress_event = "activatefocus",
  })
end
