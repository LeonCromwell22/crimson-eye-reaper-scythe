--[[
	Two-handed hold for the Crimson Eye Reaper Scythe. R6 and R15.

	On equip the left shoulder is offset so the left arm reaches across toward
	the shaft; on unequip it is restored. The offset is a JOINT OFFSET, never
	Transform, so Animate keeps owning the arm and nothing fights.

	WHERE THE JOINT IS
	  R6  : Torso.Left Shoulder          (part name has a space)
	  R15 : LeftUpperArm.LeftShoulder    (part name has none)

	WHAT YOU ACTUALLY WRITE, AND WHY IT IS NOT ALWAYS C0
	  Classic rigs use a Motor6D, whose C0 is writable. A rig with the Avatar
	  Joint Upgrade uses an AnimationConstraint instead, and its C0 is not:

	      Unable to assign property C0. Property is read only

	  On that class the joint's offset lives in its Attachment1
	  (LeftUpperArm.LeftShoulderRigAttachment), whose CFrame IS writable and which
	  Animate does not touch - so it plays the same role C0 plays on a Motor6D, and
	  the reach survives the animation. This script tries, in order: C0, then
	  Attachment1.CFrame, then Transform as a last resort, and prints which one it
	  used.

	THE ANGLES, AND THE RANGE THEY CAN REACH
	  One set per rig: pitch, yaw and roll in degrees, applied in the joint's own
	  frame. R15_ANGLES was measured on the default R15 rig by grid search - it is
	  the pose that gets the left palm closest to the shaft. Be aware of what that
	  number is: the palm still lands about 3 studs off the shaft, because the grab
	  point sits roughly 5.5 studs from the left shoulder and the arm only reaches
	  about 2.2. No joint offset can close that; reaching it needs a custom hold
	  animation that brings the weapon in toward the body. The equip print reports
	  the distance so the limit stays visible.
]]

local R6_ANGLES = { pitch = -125, yaw = -45, roll = -100 }
local R15_ANGLES = { pitch = -90, yaw = 75, roll = 0 }
local RIG_ANGLES = { R6 = R6_ANGLES, R15 = R15_ANGLES }

local RunService = game:GetService("RunService")

local tool = script.Parent
local joint, rigName, angles = nil, nil, nil
local mode = nil          -- "C0", "Attachment" or "Transform"
local original = nil      -- whatever we are offsetting held before we touched it
local frameStep = nil

local function offset()
	return CFrame.Angles(math.rad(angles.pitch), math.rad(angles.yaw),
		math.rad(angles.roll))
end

-- Any joint with a readable C0 will do; the class varies by rig generation.
local function jointNamed(parent, name)
	if not parent then return nil end
	local child = parent:FindFirstChild(name)
	if not child then return nil end
	local ok, c0 = pcall(function() return child.C0 end)
	if ok and c0 ~= nil then return child end
	return nil
end

local function findShoulder(character)
	if not character then return nil end
	local r6 = jointNamed(character:FindFirstChild("Torso"), "Left Shoulder")
	if r6 then return r6, "R6" end
	local r15 = jointNamed(character:FindFirstChild("LeftUpperArm"), "LeftShoulder")
	if r15 then return r15, "R15" end
	return nil
end

local function bindFrameStep()
	if frameStep or not joint then return end
	frameStep = RunService.RenderStepped:Connect(function()
		if joint and mode == "Transform" then
			joint.Transform = offset()
		end
	end)
end

-- How far the left hand actually got, so the limit is measurable, not guessed.
local function reportReach()
	task.wait(0.3)
	local character = tool.Parent
	local handle = tool:FindFirstChild("Handle")
	local hand = character and character:FindFirstChild("LeftHand")
	if not (handle and hand) then return end
	local rel = hand.Position - handle.CFrame.Position
	local along = rel:Dot(handle.CFrame.YVector)
	local perp = (rel - handle.CFrame.YVector * along).Magnitude
	print(("[scythe] left hand: %.2f studs from the shaft axis, %.2f along it")
		:format(perp, along))
end

local function apply()
	if not joint or not angles then return end
	if mode == nil then
		local okC0, errC0 = pcall(function() joint.C0 = original * offset() end)
		if okC0 then
			mode = "C0"
		else
			local okRef, att = pcall(function() return joint.Attachment1 end)
			if not okRef then att = nil end
			local okAtt, errAtt = false, "no writable Attachment1"
			if att then
				local readable, cf = pcall(function() return att.CFrame end)
				if readable and cf ~= nil then
					okAtt, errAtt = pcall(function()
						att.CFrame = original * offset()
					end)
				end
			end
			if okAtt then
				mode = "Attachment"
			else
				local okT, errT = pcall(function() joint.Transform = offset() end)
				if not okT then
					warn(("[scythe] cannot pose %s.%s [%s]: C0 '%s'; Attachment1 '%s'; Transform '%s'")
						:format(joint.Parent.Name, joint.Name, joint.ClassName,
							tostring(errC0), tostring(errAtt), tostring(errT)))
					joint = nil
					return
				end
				mode = "Transform"
				bindFrameStep()
			end
		end
		print(("[scythe] hold applied on %s via %s (%s.%s [%s]) by pitch %d, yaw %d, roll %d")
			:format(rigName, mode, joint.Parent.Name, joint.Name, joint.ClassName,
				angles.pitch, angles.yaw, angles.roll))
		reportReach()
		return
	end
	if mode == "C0" then
		joint.C0 = original * offset()
	elseif mode == "Attachment" then
		joint.Attachment1.CFrame = original * offset()
	else
		joint.Transform = offset()
	end
end

local function restore()
	if frameStep then
		frameStep:Disconnect()
		frameStep = nil
	end
	if joint and original then
		if mode == "C0" then
			joint.C0 = original
		elseif mode == "Attachment" and joint.Attachment1 then
			joint.Attachment1.CFrame = original
		elseif mode == "Transform" then
			joint.Transform = original
		end
	end
	joint, mode, original = nil, nil, nil
end

-- Reads whatever this rig lets us write: C0, else Attachment1.CFrame, else Transform.
local function captureOriginal(shoulder)
	local readable, c0 = pcall(function() return shoulder.C0 end)
	if readable and c0 ~= nil and pcall(function() shoulder.C0 = c0 end) then
		return c0
	end
	local okRef, att = pcall(function() return shoulder.Attachment1 end)
	if okRef and att then
		local okAtt, cf = pcall(function() return att.CFrame end)
		if okAtt and cf ~= nil and pcall(function() att.CFrame = cf end) then
			return cf
		end
	end
	local okT, transform = pcall(function() return shoulder.Transform end)
	return okT and transform or nil
end

tool.Equipped:Connect(function()
	local character = tool.Parent
	local shoulder, rig = findShoulder(character)
	if not shoulder then
		local detail = {}
		for _, name in ipairs({ "Torso", "LeftUpperArm", "Left Arm" }) do
			local part = character and character:FindFirstChild(name)
			if part then
				local kids = {}
				for _, child in ipairs(part:GetChildren()) do
					if child.Name:lower():find("shoulder") then
						table.insert(kids, child.Name .. "[" .. child.ClassName .. "]")
					end
				end
				table.insert(detail, name .. " -> " .. (#kids > 0
					and table.concat(kids, ", ") or "no shoulder-ish child"))
			end
		end
		warn("[scythe] no left shoulder joint with a C0. " .. table.concat(detail, " | "))
		return
	end
	joint, rigName, mode = shoulder, rig, nil
	angles = RIG_ANGLES[rig] or R6_ANGLES
	original = captureOriginal(shoulder)
	if not original then
		warn("[scythe] could not read a joint offset off " .. shoulder.Name)
		joint = nil
		return
	end
	apply()
end)

tool.Unequipped:Connect(function()
	if joint then
		print(("[scythe] left shoulder restored (%s via %s)")
			:format(tostring(rigName), tostring(mode)))
	end
	restore()
end)
