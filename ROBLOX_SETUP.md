# Crimson Eye Reaper Scythe — Roblox Studio setup

Six steps, no guesswork. Every number here was measured by the build, not
estimated: `out/s16_export_response.json` carries the same figures.

## 1. Import

1. **File → Import 3D** (Ctrl+M), pick `out/crimson_eye_reaper_scythe.fbx`.
2. Set **Scale Unit = Meter**. The file carries metres, and Roblox's ratio is
   25:7 studs per metre (1 stud ≈ 28 cm), so the scythe lands at
   **1.8008 m = 6.43 studs** tall. Leave the scale factor at 1.0.
   If you accidentally import it as *Stud* it arrives 3.57× too small.
3. Check against a default Part (4 × 1.2 × 2 studs): the scythe should be a
   little over 1.5 Part-lengths tall.
4. Rename the imported Model to **`crimson_eye_reaper_scythe`** — the setup
   script looks it up by that name.

The import brings in six objects:

| Object | What it is |
|---|---|
| `Scythe_Root` | empty, the model root |
| `Scythe_Body` | **the whole weapon: 1 mesh, 1 material, 1 atlas** |
| `Scythe_EyeHead` | the crown eye, its own mesh so it can be Neon |
| `Scythe_EyePommel` | the pommel eye, likewise |
| `Scythe_PupilHead` | the crown eye's slit pupil |
| `Scythe_PupilPommel` | the pommel eye's slit pupil |

## 2. Upload the five maps

Upload the PNGs in `Documents\ScytheTextures_1024` as **Decals**, then paste each
numeric id into `UPLOAD` at the top of `luau/scythe_tool_setup.lua`:

| File | Role |
|---|---|
| `Scythe_ColorMap.png` | colour, sRGB, ambient occlusion already folded in |
| `Scythe_NormalMap.png` | tangent-space normal, green up |
| `Scythe_RoughnessMap.png` | roughness |
| `Scythe_MetalnessMap.png` | metalness |
| `Scythe_EmissiveMask.png` | grayscale — white where the veins glow |

Two further maps sit in the same folder and are **not** uploaded:
`Scythe_AO.png` and `Scythe_Curvature.png`. Roblox's `SurfaceAppearance` has no
ambient-occlusion slot, so AO is multiplied into the ColorMap; the two maps are
kept for Blender and for any future use.

## 3. Build the Tool

Run `luau/scythe_tool_setup.lua` from the **command bar** after importing — it
was executed and verified against Studio 4.5 while this asset was made, and it is
safe to re-run (it destroys and rebuilds the Tool). It:

- **copies** the five parts into a Tool named `CrimsonEyeReaperScythe` and puts
  it in **StarterPack**, leaving your source Model in Workspace untouched so you
  can compare, then delete it;
- names the body `Handle`, which is what makes it the Handle
  (**Tool → Handle → MeshPart**, `RequiresHandle = true`). Do **not** assign
  `tool.Handle` in your own code: the property is engine-managed and both reading
  and writing it throws *"Handle is not a valid member of Tool"* until a child is
  named `Handle`, after which the engine wires it up itself. Verified by probe;
- sets the Handle to `Anchored = false`, `CanCollide = false`, `Massless = true`,
  welds the other four parts to it with `WeldConstraint`s, and clears collisions
  and anchoring on all of them;
- sets **`Grip` to the identity CFrame**. Measured in a live session, that holds
  the shaft vertical with the crescent sweeping to the character's **left** —
  blade up, in the right hand. The mesh's origin *is* the grip point (1.1 m up
  the shaft), so no `GripPos` offset is needed. Two warnings from that
  measurement: `handle.CFrame = hand.CFrame * Grip` is **not** the real relation
  (it is 0.125 studs out, because the handle lands on the hand's grip
  attachment), and any rotation you add swings the blade behind the character
  rather than in front.
- **fixes the import scale.** The FBX carries metres; an import at the default
  *Stud* unit arrives 3.571× too small (1.80 studs instead of 6.43). The script
  measures `Handle.Size.Y` against the model's real height, scales every part
  about the grip pivot and scales the Trail's attachments to match. To avoid this
  entirely, re-import with **Scale Unit = Meter**.

## R6 grip and the two-handed left arm

The Tool in StarterPack is set up for **R6**. If your place is set to R15 the
values below will place it differently — Studio's Game Settings → **Avatar** →
Avatar Type is where that is chosen, and this particular place currently spawns
an R15 rig in Play, so check that before judging the pose.

### The grip, as set on the Tool

| Property | Value |
|---|---|
| `GripPos` | `Vector3.new(-0.40, -0.50, 0.23)` |
| `GripRight` | `Vector3.new(-1, 0, 0)` |
| `GripUp` | `Vector3.new(0, 1, 0)` |
| `GripForward` | `Vector3.new(0, 0, 1)` |

That is `CFrame.new(-0.40, -0.50, 0.23) * CFrame.Angles(0, math.pi, 0)`: a 180°
turn of the hand frame, which is what flips the shaft from pointing *down* to
pointing *up*, plus a small offset that lifts the weapon half a stud and nudges
it toward the body's centre.

Measured, with the right arm in the toolnone pose (shoulder pitched so the arm
points forward):

- shaft axis **vertical** (dot with world up = 1.000), blade at the top;
- blade sweeps **to the character's right** and the flat faces forward, so it
  curves away from the face;
- **0 of 20 sampled weapon points** (shaft, crown ring, blade edge, pommel) fall
  inside the head or torso boxes;
- the **pommel clears the ground**: y 37.07 against the feet at 37.00. With
  `GripPos` Y at 0 it sat 0.43 studs *below* the feet, because a 6.43-stud scythe
  gripped 3.93 studs above the pommel is taller than the gap under an R6 hand;
- the hand grips the shaft 0.40 studs off the shaft's axis, which is inside the
  1-stud width of an R6 hand — so it still reads as held.

Two things worth knowing if you tune it: `GripPos` components are applied with
Y **inverted** (the engine builds the weld as `C1 = Grip`, so the handle lands at
`arm * C0 * Grip:Inverse()`), and the real relation is *not*
`handle.CFrame = rightArm.CFrame * Grip` — that is 0.125 studs out because the
handle sits on the arm's grip attachment.

### `TwoHandedHold` (LocalScript inside the Tool)

While equipped it writes the Left Shoulder Motor6D's `C0` inside the Torso, and
restores the original on unequip. It writes **C0 and never Transform**, because
the Animate script rewrites Transform every frame for the tool pose — C0 is the
joint offset the animation leaves alone. The three angles are at the top:

```lua
local PITCH = -125      -- swings the arm up toward the shaft
local YAW = -45         -- swings it across the body
local ROLL = -100       -- rotates it about the joint
local OFFSET = Vector3.new(0, 0, 0)
```

**What it honestly achieves.** An R6 arm is one rigid 2-stud part — 1.58 studs
from the shoulder joint to the centre of the hand — and with the shaft running
through the right hand, the left shoulder sits about 2.6 studs from it. So the
left hand **cannot touch the shaft**: the best measured result is **1.12 studs
from the shaft's axis, 0.12 studs above the right-hand grip**, which leaves
about **half a stud of daylight** between a 1-stud hand and a 0.2-stud shaft. It
reads as reaching across to hold it, but it is not touching.

If you want a real contact, the lever is the *right* arm, not the left: with the
right arm angled 20° inward in your own tool pose, the same search reaches 1.15
studs from a starting point 0.7 studs closer, and the gap closes to about 0.55
studs — while a torso twist cannot help at all, because it turns the shoulder and
the weapon together.

## 4. Neon eyes and the glow

- Both eyes: `Material = Neon`, colour `255, 42, 32`.
- Both pupils: `SmoothPlastic`, near-black `12, 10, 10`.
- The eyes deliberately carry **no** `SurfaceAppearance`: a Neon part ignores it,
  and the brief asks for the gems to read as lit from inside.
- The veins glow through the body's `SurfaceAppearance` instead:

```lua
appearance.EmissiveMaskContent = Content.fromUri("rbxassetid://<mask id>")
appearance.EmissiveTint   = Color3.fromRGB(190, 20, 32)
appearance.EmissiveStrength = 4      -- start here and tune
appearance.AlphaMode      = Enum.AlphaMode.Overlay
```

Set the Handle's `Color` to white (`255, 255, 255`) so the ColorMap is what you
see; any other colour tints the painted maps. If the item is ever published as a
Marketplace accessory, Roblox validates `EmissiveStrength` into **0–40**.

## 5. Light and trail

The script adds both, and both are ordinary instances you can retune:

- **PointLight** — parented inside `Scythe_EyeHead`: crimson, `Brightness 2.5`,
  `Range 9`, `Shadows = true`.
- **Trail** — parented to the Handle as `CrimsonWake`, between two attachments
  the script creates: `BladeBase` and `BladeTip`, converted from the metre
  coordinates the mesh was authored in. Crimson to near-black, `Lifetime 0.28`,
  `LightEmission 0.65`. It is enabled on `Tool.Equipped` and disabled on
  `Unequipped`, so it does not smear while the tool is in the backpack.

## 6. Collision

Set in **edit mode** — these cannot be changed at runtime, so no script touches
them:

- `Scythe_Body`: **`CollisionFidelity = Hull`**. A `Box` would swallow the whole
  crescent; `Hull` follows the silhouette without the cost of `PreciseConvexDecomposition`.
- The two eyes and two pupils: `CanCollide = false`, `Massless = true` — they
  are decoration sitting in a recess.

## Verifying it landed correctly

- Height: **1.8008 m → 6.43 studs**. A 1 m reference cube exported with these
  same settings re-imports at exactly 1.0 (measured in `s1_scale_spike`), which
  is what makes the stud figure trustworthy rather than assumed.
- Facing: exported `-Z forward, Y up`, so Blender's front becomes Roblox's front
  — the flat of the blade should face the camera in Studio's default view.
- Pivot: select `Scythe_Body` in Studio and the move gizmo should sit on the
  shaft where the hand grips it, **1.1 m** up from the pommel.
