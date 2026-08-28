-- Launch Cider on boot and always keep it on workspace 9.
o.window("^(cider)$", { workspace = "9" })

hl.on("hyprland.start", function()
  hl.exec_cmd(o.launch("cider"))
end)
