-- Launch Cider in the background on boot and always keep it on workspace 9.
o.window("^(cider)$", { workspace = "9" })

hl.on("hyprland.start", function()
  o.launch_background("cider", "9")
end)
