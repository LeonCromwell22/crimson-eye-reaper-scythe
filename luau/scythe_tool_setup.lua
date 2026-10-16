--[[
	Crimson Eye Reaper Scythe - Roblox Studio setup.

	WHAT THIS DOES
	  Turns the imported model into a working Tool in StarterPack: Handle, welds,
	  one SurfaceAppearance carrying the five maps, Neon eyes, a red PointLight
	  inside the head eye and a Trail along the blade's cutting edge.

	HOW TO RUN
	  Paste into the Studio command bar, or drop it in a Script in
	  ServerScriptService and press Play. Safe to re-run: it rebuilds the Tool.

	BEFORE RUNNING
	  Rename the imported Model to MODEL_NAME (it is looked up by name). The five
	  asset ids are already filled in below.

	THE MODEL IS COPIED, NOT MOVED
	  The parts are cloned into the Tool and the source Model is left exactly as
	  it is, so you can compare and delete it once you are happy.

	THREE THINGS THIS SCRIPT LEARNED THE HARD WAY, ALL VERIFIED IN STUDIO 4.5
	  1. Never assign tool.Handle. The property is engine-managed: reading or
	     writing it throws "Handle is not a valid member of Tool" until a child
	     is *named* "Handle", after which the engine wires it up itself. Naming
	     and parenting is the whole job.
	  2. The parts must be direct children of the Tool, not inside a nested
	     Model, or there is no Handle for the engine to resolve.
	  3. An FBX imported at the default Stud scale comes in 3.57x too small.
	     AUTO_SCALE below measures that and fixes it.
]]

local StarterPack = game:GetService("StarterPack")

local MODEL_NAME = "crimson_eye_reaper_scythe"

-- Uploaded asset ids: the files in Documents\ScytheTextures_1024, all 1024x1024.
local UPLOAD = {
	Scythe_ColorMap = 135922769550902,
	Scythe_NormalMap = 127172587170280,
	Scythe_RoughnessMap = 96826213749466,
	Scythe_MetalnessMap = 129780027463352,
	Scythe_EmissiveMask = 74269402365427,
}

local TOOL_NAME = "CrimsonEyeReaperScythe"
local BODY = "Scythe_Body"
local EYES = { "Scythe_EyeHead", "Scythe_EyePommel" }
local PUPILS = { "Scythe_PupilHead", "Scythe_PupilPommel" }
local WELDED = { "Scythe_EyeHead", "Scythe_EyePommel",
                 "Scythe_PupilHead", "Scythe_PupilPommel" }
local EYE_RED = Color3.fromRGB(255, 42, 32)
local PUPIL_DARK = Color3.fromRGB(12, 10, 10)

-- The weapon is 1.8008 m tall and the hand grips it 1.1 m up the shaft, so its
-- measured height in studs says how the importer treated it: 6.43 studs when
-- Studio was told Scale Unit = Meter, 1.80 when it was left on Stud.
local MODEL_HEIGHT_M = 1.8008
local GRIP_Z_M = 1.1
local BLADE_EDGE_BASE_M = Vector3.new(-0.1033, 1.580, 0)
local BLADE_EDGE_TIP_M = Vector3.new(-0.8817, 1.791, 0)
local AUTO_SCALE = true
local STUD = 25 / 7

local importFactor   -- studs per authored unit; set once the Handle is measured

-- Blender (X, Y, Z) -> this mesh's local (X, Y, Z) relative to the grip:
-- Blender's +Z becomes Roblox's +Y, and Blender's -Y becomes +Z.
local function fromGrip(v)
	return Vector3.new(v.X * importFactor,
		(v.Y - GRIP_Z_M) * importFactor,
		v.Z * importFactor)
end

local function findMesh(parent, name)
	local found = parent:FindFirstChild(name, true)
	if not found or not found:IsA("BasePart") then
		warn(("[scythe] no BasePart named %s under %s"):format(name, parent.Name))
		return nil
	end
	return found
end

local function asset(id)
	if id and id ~= 0 then
		return "rbxassetid://" .. tostring(id)
	end
	return ""
end

-- ---------------------------------------------------------------------------
local model = workspace:FindFirstChild(MODEL_NAME)
if not model then
	warn(("[scythe] no Model named %s in Workspace"):format(MODEL_NAME))
	return
end

local sourceBody = findMesh(model, BODY)
if not sourceBody then return end
for _, name in ipairs(WELDED) do
	if not findMesh(model, name) then return end
end

local existing = StarterPack:FindFirstChild(TOOL_NAME)
if existing then
	existing:Destroy()
	print(("[scythe] removed the previous %s"):format(TOOL_NAME))
end

local tool = Instance.new("Tool")
tool.Name = TOOL_NAME
tool.RequiresHandle = true
tool.CanBeDropped = false
tool.ToolTip = "Crimson Eye Reaper Scythe"
-- Identity grip: measured in a live session to hold the shaft vertical with the
-- crescent sweeping to the character's left, which is the brief's hold. A
-- non-zero rotation here swings the blade behind the character - the solver
-- that "corrected" the hand's frame got it wrong, and the measurement said so.
tool.Grip = CFrame.new(0, 0, 0)
-- The Tool must be in the DataModel before a child named "Handle" can resolve.
tool.Parent = StarterPack

-- Clone the parts in as DIRECT children, keeping each world CFrame so the
-- assembly is unchanged and the welds can preserve the current offsets.
local clones = {}
for _, name in ipairs({ BODY, table.unpack(WELDED) }) do
	local clone = findMesh(model, name):Clone()
	clone.Anchored = false
	clone.CanCollide = false
	clone.Massless = true
	clone.CanTouch = false
	clone.CanQuery = false
	clone.Parent = tool
	clones[name] = clone
end

-- Naming the part "Handle" is what wires Tool.Handle; see the header.
local handle = clones[BODY]
handle.Name = "Handle"

-- Measure the import scale, and correct it on the clones if Studio was left on
-- Stud. Scaling about the Handle's pivot keeps the grip point in the hand.
importFactor = handle.Size.Y / MODEL_HEIGHT_M
if AUTO_SCALE and importFactor < 2 then
	local pivot = handle.Position
	for _, part in ipairs(tool:GetChildren()) do
		if part:IsA("BasePart") then
			local offset = part.Position - pivot
			local rotation = part.CFrame - part.Position
			part.Size = part.Size * STUD
			part.CFrame = CFrame.new(pivot + offset * STUD) * rotation
		end
	end
	importFactor = handle.Size.Y / MODEL_HEIGHT_M
	print(("[scythe] import was %.3fx too small; scaled to %.2f studs tall")
		:format(STUD, handle.Size.Y))
end
print(("[scythe] Handle %.2f studs tall (%.2f m), import factor %.4f")
	:format(handle.Size.Y, handle.Size.Y / STUD, importFactor))

local resolvedOk, resolved = pcall(function() return tool.Handle end)
print(("[scythe] Tool.Handle resolved by name: %s")
	:format(tostring(resolvedOk and resolved == handle)))

-- ---------------------------------------------------------------- welds -----
for _, name in ipairs(WELDED) do
	local part = clones[name]
	local weld = Instance.new("WeldConstraint")
	weld.Name = "Weld_" .. name
	weld.Part0 = handle
	weld.Part1 = part
	weld.Parent = handle
end
print(("[scythe] welded %d part(s) to the Handle"):format(#WELDED))

-- ----------------------------------------------------------------- eyes -----
-- Neon red, as asked. The pupils stay SmoothPlastic and near-black: they are the
-- slit in the eye, and a Neon pupil would just glow like the eye around it.
for _, name in ipairs(EYES) do
	local eye = clones[name]
	eye.Material = Enum.Material.Neon
	eye.Color = EYE_RED
end
for _, name in ipairs(PUPILS) do
	local pupil = clones[name]
	pupil.Material = Enum.Material.SmoothPlastic
	pupil.Color = PUPIL_DARK
end

local eyeHead = clones[EYES[1]]
local light = Instance.new("PointLight")
light.Name = "EyeGlow"
light.Color = EYE_RED
light.Brightness = 2.5
light.Range = 9
light.Shadows = true
light.Parent = eyeHead
print(("[scythe] PointLight inside %s"):format(eyeHead.Name))

-- ----------------------------------------------------------- appearance -----
local appearance = handle:FindFirstChildOfClass("SurfaceAppearance")
if not appearance then
	appearance = Instance.new("SurfaceAppearance")
	appearance.Parent = handle
end
appearance.ColorMap = asset(UPLOAD.Scythe_ColorMap)
appearance.NormalMap = asset(UPLOAD.Scythe_NormalMap)
appearance.RoughnessMap = asset(UPLOAD.Scythe_RoughnessMap)
appearance.MetalnessMap = asset(UPLOAD.Scythe_MetalnessMap)
-- The veins: a grayscale mask, white where the glow is. Guarded because
-- Content.fromUri("") throws before the id is uploaded. EmissiveTint is applied
-- to whatever the mask lights, and Roblox validates EmissiveStrength into 0-40
-- if this is ever published as a Marketplace accessory.
if UPLOAD.Scythe_EmissiveMask ~= 0 then
	appearance.EmissiveMaskContent = Content.fromUri(asset(UPLOAD.Scythe_EmissiveMask))
end
appearance.EmissiveTint = Color3.fromRGB(190, 20, 32)
appearance.EmissiveStrength = 4
appearance.AlphaMode = Enum.AlphaMode.Overlay
-- White, so the ColorMap is what you see rather than being tinted by the part.
handle.Color = Color3.fromRGB(255, 255, 255)
print("[scythe] SurfaceAppearance wired with the five maps")

-- ----------------------------------------------------------------- trail ----
-- Along the blade's CUTTING edge: two attachments on the Handle at the edge's
-- base and its tip, in the mesh's own local frame.
local function edgeAttachment(name, metres)
	local att = Instance.new("Attachment")
	att.Name = name
	att.Position = fromGrip(metres)
	att.Parent = handle
	return att
end
local baseAtt = edgeAttachment("BladeEdgeBase", BLADE_EDGE_BASE_M)
local tipAtt = edgeAttachment("BladeEdgeTip", BLADE_EDGE_TIP_M)

local trail = Instance.new("Trail")
trail.Name = "CrimsonEdge"
trail.Attachment0 = baseAtt
trail.Attachment1 = tipAtt
trail.Lifetime = 0.3
trail.MinLength = 0.1
trail.WidthScale = NumberSequence.new({
	NumberSequenceKeypoint.new(0, 1),
	NumberSequenceKeypoint.new(1, 0.2),
})
trail.Transparency = NumberSequence.new({
	NumberSequenceKeypoint.new(0, 0.2),
	NumberSequenceKeypoint.new(1, 1),
})
trail.Color = ColorSequence.new({
	ColorSequenceKeypoint.new(0, Color3.fromRGB(230, 36, 44)),
	ColorSequenceKeypoint.new(1, Color3.fromRGB(70, 0, 0)),
})
trail.LightEmission = 0.7
trail.LightInfluence = 0.2
trail.FaceCamera = true
trail.Enabled = true
trail.Parent = handle
print(("[scythe] Trail along the blade edge, %.2f studs long")
	:format((baseAtt.Position - tipAtt.Position).Magnitude))

-- ----------------------------------------------------------------- report ---
local weldCount, anchoredCount, collidingCount = 0, 0, 0
for _, child in ipairs(tool:GetChildren()) do
	if child:IsA("BasePart") and child ~= handle then
		if child.Anchored then anchoredCount = anchoredCount + 1 end
		if child.CanCollide then collidingCount = collidingCount + 1 end
	end
end
for _, child in ipairs(handle:GetChildren()) do
	if child:IsA("WeldConstraint") then weldCount = weldCount + 1 end
end
print(("[scythe] %d weld(s); %d anchored; %d colliding; Handle anchored=%s collide=%s massless=%s")
	:format(weldCount, anchoredCount, collidingCount, tostring(handle.Anchored),
		tostring(handle.CanCollide), tostring(handle.Massless)))
print(("[scythe] %s is in %s; the source model in Workspace is untouched")
	:format(TOOL_NAME, StarterPack:GetFullName()))
