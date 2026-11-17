-- MAME autoboot script: save a snapshot at chosen frames, optionally hold inputs, then exit.
-- Environment: SNAP_FRAMES="600,1200,..." (frames at which to snapshot), SNAP_EXIT=<frame>,
-- SNAP_INPUTS="frame|port|field|value;..." (press/release fields at frames, value 1/0).
local frames = {}
for f in string.gmatch(os.getenv("SNAP_FRAMES") or "", "%d+") do frames[tonumber(f)] = true end
local exit_at = tonumber(os.getenv("SNAP_EXIT") or "0")
local inputs = {}
for item in string.gmatch(os.getenv("SNAP_INPUTS") or "", "[^;]+") do
  local f, port, field, value = string.match(item, "^(%d+)|([^|]+)|([^|]+)|(%d)$")
  if f then table.insert(inputs, {frame = tonumber(f), port = port, field = field, value = tonumber(value)}) end
end

-- SNAP_POKE="addr=value,..." (hex): bytes written to the main CPU's space every frame
local pokes = {}
for a, v in string.gmatch(os.getenv("SNAP_POKE") or "", "(%x+)=(%x+)") do
  table.insert(pokes, {addr = tonumber(a, 16), value = tonumber(v, 16)})
end

local frame = 0
emu.register_frame_done(function()
  frame = frame + 1
  if #pokes > 0 then
    local space = manager.machine.devices[":maincpu"].spaces["program"]
    for _, p in ipairs(pokes) do space:write_u8(p.addr, p.value) end
  end
  for _, i in ipairs(inputs) do
    if i.frame == frame then
      local p = manager.machine.ioport.ports[i.port]
      local fld = p and p.fields[i.field]
      if fld then fld:set_value(i.value) else print("no input " .. i.port .. " / " .. i.field) end
    end
  end
  if frames[frame] then manager.machine.video:snapshot() end
  if exit_at > 0 and frame >= exit_at then manager.machine:exit() end
end)
