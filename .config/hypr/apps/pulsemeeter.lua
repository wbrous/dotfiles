-- Launch Pulsemeeter on boot and always keep it on workspace 10 (shown as "0" in the bar).
o.window("^(org.pulsemeeter.pulsemeeter)$", { workspace = "10" })

hl.on("hyprland.start", function()
  hl.exec_cmd(o.launch("pulsemeeter"))
end)
