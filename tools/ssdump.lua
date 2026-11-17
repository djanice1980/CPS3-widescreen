-- Dump text-layer rows (code:attr per cell, 64 columns) at the frames in DUMP_FRAMES to DUMP_OUT.
-- Runs snap.lua for inputs, pokes and snapshots.
dofile(os.getenv("SNAP_LUA"))
local frames = {}
for f in string.gmatch(os.getenv("DUMP_FRAMES") or "", "%d+") do frames[tonumber(f)] = true end
local out = io.open(os.getenv("DUMP_OUT"), "w")
local f = 0
emu.register_frame_done(function()
  f = f + 1
  if not frames[f] then return end
  local s = manager.machine.devices[":maincpu"].spaces["program"]
  for row = 0, 31 do
    local cells = {}
    for col = 0, 63 do
      local a = 0x05040000 + row * 0x100 + col * 4
      table.insert(cells, string.format("%03X:%02X", s:read_u16(a) & 0xFFF, s:read_u16(a + 2) & 0xFF))
    end
    out:write(string.format("f%d r%02d %s\n", f, row, table.concat(cells, " ")))
  end
  out:flush()
end)
