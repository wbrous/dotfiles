-- gallium.nvim
--
-- Restores hjkl-style navigation on the physical key block when the system
-- keyboard layout is Gallium.
--
-- Gallium relocates the letters typed by the physical h/j/k/l keys:
--   physical h-key -> types "y"
--   physical j-key -> types "h"
--   physical k-key -> types "a"
--   physical l-key -> types "e"
--
-- Vim's built-in motions are bound by character, not by physical key, so
-- without remapping, pressing the physical hjkl block runs the default
-- p/h/a/e commands (paste / help / insert-after-cursor / end-of-word)
-- instead of moving the cursor. This plugin swaps each pair bidirectionally:
-- navigation lands back on the physical hjkl block, and the displaced
-- commands become reachable wherever their own letters now live on the
-- layout.

local M = {}

M.default_pairs = {
  { "h", "y" },
  { "j", "h" },
  { "k", "a" },
  { "l", "e" },
}

local defaults = {
  enabled = true,
  modes = { "n", "x", "o" },
  pairs = M.default_pairs,
  uppercase = true,
  window_nav = true,
  disable_filetypes = { "TelescopePrompt" },
}

local state = { opts = nil, applied = false }

local function set_pair(modes, a, b)
  vim.keymap.set(modes, a, b, { noremap = true, silent = true })
  vim.keymap.set(modes, b, a, { noremap = true, silent = true })
end

local function apply(opts)
  for _, pair in ipairs(opts.pairs) do
    local a, b = pair[1], pair[2]
    set_pair(opts.modes, a, b)
    if opts.uppercase then
      set_pair(opts.modes, a:upper(), b:upper())
    end
  end

  if opts.window_nav then
    for _, pair in ipairs(opts.pairs) do
      local a, b = pair[1], pair[2]
      vim.keymap.set("n", "<C-w>" .. a, "<C-w>" .. b, { noremap = true })
      vim.keymap.set("n", "<C-w>" .. b, "<C-w>" .. a, { noremap = true })
    end
  end

  if #opts.disable_filetypes > 0 then
    vim.api.nvim_create_autocmd("FileType", {
      pattern = opts.disable_filetypes,
      group = vim.api.nvim_create_augroup("GalliumDisable", { clear = true }),
      callback = function(ev)
        -- Buffer-local self-mapping short-circuits our global noremap and
        -- restores each key's true default behaviour for this buffer.
        for _, pair in ipairs(opts.pairs) do
          for _, ch in ipairs({ pair[1], pair[2] }) do
            vim.keymap.set(opts.modes, ch, ch, { buffer = ev.buf, noremap = true })
            if opts.uppercase then
              vim.keymap.set(opts.modes, ch:upper(), ch:upper(), { buffer = ev.buf, noremap = true })
            end
          end
        end
      end,
    })
  end
end

local function unapply(opts)
  for _, pair in ipairs(opts.pairs) do
    for _, ch in ipairs({ pair[1], pair[2] }) do
      pcall(vim.keymap.del, opts.modes, ch)
      if opts.uppercase then
        pcall(vim.keymap.del, opts.modes, ch:upper())
      end
    end
  end
  if opts.window_nav then
    for _, pair in ipairs(opts.pairs) do
      for _, ch in ipairs({ pair[1], pair[2] }) do
        pcall(vim.keymap.del, "n", "<C-w>" .. ch)
      end
    end
  end
end

local descriptions = {
  h = "cursor left",
  j = "cursor down",
  k = "cursor up",
  l = "cursor right",
  y = "yank",
  a = "insert after cursor",
  e = "end of word",
}

function M.help()
  local opts = state.opts or defaults
  local lines = { "Gallium navigation remap", "" }
  for _, pair in ipairs(opts.pairs) do
    local a, b = pair[1], pair[2]
    table.insert(lines, string.format("%s  ->  %-22s  (was: %s)", a, descriptions[b] or b, descriptions[a] or a))
    table.insert(lines, string.format("%s  ->  %-22s  (was: %s)", b, descriptions[a] or a, descriptions[b] or b))
    if opts.uppercase then
      table.insert(
        lines,
        string.format("%s  ->  %-22s  (was: %s)", a:upper(), descriptions[b] or b:upper(), (descriptions[a] or a) .. " (uppercase)")
      )
      table.insert(
        lines,
        string.format("%s  ->  %-22s  (was: %s)", b:upper(), descriptions[a] or a:upper(), (descriptions[b] or b) .. " (uppercase)")
      )
    end
  end
  if opts.window_nav then
    table.insert(lines, "")
    table.insert(lines, "Window nav (<C-w>...): same pairs swapped, e.g. <C-w>p -> <C-w>h")
  end
  table.insert(lines, "")
  table.insert(lines, string.format("Remap currently: %s", state.applied and "ENABLED" or "DISABLED"))
  table.insert(lines, ":GalliumToggle to flip")

  local buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
  local width = 0
  for _, l in ipairs(lines) do
    width = math.max(width, #l)
  end
  vim.api.nvim_open_win(buf, true, {
    relative = "editor",
    width = width + 2,
    height = #lines,
    row = math.floor((vim.o.lines - #lines) / 2),
    col = math.floor((vim.o.columns - width) / 2),
    style = "minimal",
    border = "rounded",
    title = " gallium ",
  })
  vim.keymap.set("n", "q", "<cmd>close<cr>", { buffer = buf, silent = true })
  vim.keymap.set("n", "<esc>", "<cmd>close<cr>", { buffer = buf, silent = true })
end

--- @param opts table|nil see `defaults` above

function M.setup(opts)
  state.opts = vim.tbl_deep_extend("force", {}, defaults, opts or {})
  if state.opts.enabled then
    apply(state.opts)
    state.applied = true
  end

  vim.api.nvim_create_user_command("GalliumToggle", function()
    M.toggle()
  end, { desc = "Toggle Gallium hjkl navigation remap" })

  vim.api.nvim_create_user_command("GalliumHelp", function()
    M.help()
  end, { desc = "Show Gallium remap cheat sheet" })
end

function M.toggle()
  if not state.opts then
    return
  end
  if state.applied then
    unapply(state.opts)
    state.applied = false
    vim.notify("gallium: navigation remap disabled", vim.log.levels.INFO)
  else
    apply(state.opts)
    state.applied = true
    vim.notify("gallium: navigation remap enabled", vim.log.levels.INFO)
  end
end

return M
