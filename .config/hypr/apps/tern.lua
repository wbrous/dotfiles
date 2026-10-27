-- Tern is the default terminal (see ~/.config/xdg-terminals.list).

-- Omarchy's terminal tag covers a fixed list of classes. Without this, Tern
-- windows miss the terminal clipboard shortcuts (Ctrl+Shift+C/V) and the
-- terminal transparency rule, both of which key off the tag.
o.window("so\\.stencil\\.tern", { tag = "+terminal" })

-- Omarchy's own terminal launcher passes `--dir` through xdg-terminal-exec,
-- which Tern's desktop entry does not accept, and omarchy-cmd-terminal-cwd
-- cannot see inside Tern windows. tern-launch-cwd handles both.
o.rebind("SUPER + RETURN", "Terminal", "tern-launch-cwd")

-- Agent launchers on SUPER + SHIFT + A. These keys collide with Omarchy
-- defaults (ChatGPT, Grok, Agent picker), so unbind those first.
hl.unbind("SUPER + SHIFT + A")        -- was "ChatGPT"
hl.unbind("SUPER + SHIFT + ALT + A")  -- was "Grok"
hl.unbind("SUPER + SHIFT + CTRL + A") -- was "Agent" (omarchy-agent --pick)

o.bind("SUPER + SHIFT + A", "omp", "omp-launch")
o.bind("SUPER + SHIFT + CTRL + A", "omp (cwd)", "omp-launch-cwd")
o.bind("SUPER + SHIFT + ALT + A", "Claude", { webapp = "https://claude.ai" })
o.bind("SUPER + SHIFT + CTRL + ALT + A", "ChatGPT", { webapp = "https://chatgpt.com" })
