dofile(os.getenv("SNAP_LUA"))
local frame = 0
emu.register_frame_done(function()
  frame = frame + 1
  if frame < 5000 then return end
  local s = manager.machine.devices[":maincpu"].spaces["program"]
  for a = 0x05040000, 0x05041FFC, 4 do s:write_u32(a, 0x00200000) end
end)
