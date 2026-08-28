-- Extra autostart processes.

hl.on("hyprland.start", function()
  hl.exec_cmd("busctl --user set-property org.a11y.Bus /org/a11y/bus org.a11y.Status IsEnabled b true")
end)
