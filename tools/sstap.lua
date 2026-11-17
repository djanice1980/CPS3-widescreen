-- Record who writes the text layer (SS RAM page 05040000-05041FFF) between TAP_FROM and TAP_TO frames:
-- for each (PC, PR) pair the frames, rows and columns it wrote. Written to TAP_OUT at TAP_TO.
-- Runs snap.lua for inputs, pokes and snapshots.
dofile(os.getenv("SNAP_LUA"))
local from = tonumber(os.getenv("TAP_FROM") or "0")
local to = tonumber(os.getenv("TAP_TO") or "0")
local out = os.getenv("TAP_OUT")
local cpu = manager.machine.devices[":maincpu"]
local space = cpu.spaces["program"]
local seen = {}
local f = 0
local tap
local function on_write(offset, data, mask)
  local pc, pr = cpu.state["PC"].value, cpu.state["PR"].value
  local key = string.format("%08X %08X", pc, pr)
  local o = offset - 0x05040000
  local row, col = o >> 8, (o & 0xFF) >> 2
  local s = seen[key]
  if not s then
    s = {n = 0, r0 = row, r1 = row, c0 = col, c1 = col, f0 = f, f1 = f}
    seen[key] = s
  end
  s.n = s.n + 1
  if row < s.r0 then s.r0 = row end
  if row > s.r1 then s.r1 = row end
  if col < s.c0 then s.c0 = col end
  if col > s.c1 then s.c1 = col end
  s.f1 = f
  return data
end
emu.register_frame_done(function()
  f = f + 1
  if f == from then tap = space:install_write_tap(0x05040000, 0x05041FFF, "sstap", on_write) end
  if f == to then
    if tap then tap:remove() end
    local h = io.open(out, "w")
    for k, s in pairs(seen) do
      h:write(string.format("%s n=%d rows=%d-%d cols=%d-%d frames=%d-%d\n", k, s.n, s.r0, s.r1, s.c0, s.c1, s.f0, s.f1))
    end
    h:close()
  end
end)
