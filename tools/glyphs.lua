-- Draw a grid of Japanese menu glyphs (codes 0x1200 + 4n, 2x2 tiles each) into SS RAM every frame from
-- GLYPH_FROM on, 16 glyphs a row, over the page on screen. Runs snap.lua for inputs and snapshots.
-- GLYPH_BASE: first glyph number (default 0). Rows of the grid start at tile row 1.
dofile(os.getenv("SNAP_LUA"))
local from = tonumber(os.getenv("GLYPH_FROM") or "0")
local base = tonumber(os.getenv("GLYPH_BASE") or "0")
local frame = 0
emu.register_frame_done(function()
  frame = frame + 1
  if frame < from then return end
  local space = manager.machine.devices[":maincpu"].spaces["program"]
  for a = 0x05040000, 0x05043FFC, 4 do space:write_u16(a, 0x1200); space:write_u16(a + 2, 2) end
  for i = 0, 127 do
    local g = base + i
    local d = 0x1200 + 4 * g
    local gx, gy = 1 + (i % 16) * 3, 1 + math.floor(i / 16) * 3
    for r = 0, 1 do
      for c = 0, 1 do
        local code = d + r * 2 + c
        local a = 0x05040000 + ((gx + c) << 2) + ((gy + r) << 8)
        space:write_u16(a, code & 0xFFFF)
        space:write_u16(a + 2, 2 | ((code & 0x100) >> 8))
      end
    end
  end
end)
