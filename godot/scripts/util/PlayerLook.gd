class_name PlayerLook
extends RefCounted
## The player's appearance, chosen in the new-game character creator (CharacterCreator.gd) and saved with the game.
## Geometry choices (hair, hat, eyes, outfit) pick prebuilt model parts, colour choices recolour their atlases at
## runtime (PlayerModel.gd).  Stored in GameState.look as a plain Dictionary so it round-trips through the save JSON.

const HAIRS := ["short", "spiky", "long", "pony", "bun", "bald"]
const HAIR_NAMES := ["SHORT", "SPIKY", "LONG", "PONYTAIL", "BUN", "BALD"]
const HATS := ["none", "cap", "beanie"]
const HAT_NAMES := ["NONE", "CAP", "BEANIE"]
const EYES := ["round", "lash"]
const EYE_NAMES := ["ROUND", "LASHES"]
const OUTFITS := ["tee_jeans", "jacket_jeans", "tee_shorts", "dress", "tee_skirt", "coat_pants", "long_pants"]
const OUTFIT_NAMES := ["TEE+JEANS", "JACKET", "TEE+SHORTS", "DRESS", "TEE+SKIRT", "COAT", "LONG SLEEVE"]
const GENDERS := ["boy", "girl"]
const GENDER_NAMES := ["BOY", "GIRL"]

const SKIN := ["#fbe0c4", "#f0b88a", "#e2a172", "#c98a5c", "#a56a42", "#7c4c30", "#5c3624"]
const HAIR_COL := ["#3a2a26", "#6a4430", "#9a6a3a", "#d8a850", "#f4dc98", "#c8603a", "#e8e8f0", "#6a6a78", "#2c3c8c", "#d85a9a", "#48a060"]
const HAT_COL := ["#d8383a", "#3a68d8", "#3aa860", "#f0c030", "#8a4ad8", "#2a2a34", "#f4f4f4", "#e87a30", "#e85aa0"]
const SHIRT_COL := ["#d64a3a", "#4a78c8", "#48a868", "#e8c040", "#9a58c8", "#2e2e38", "#f0f0f0", "#e87a30", "#e060a0", "#40b0c0"]
const PANTS_COL := ["#34508a", "#2a2a34", "#6a4a30", "#5a6a3a", "#8a8a98", "#c8b890", "#a03a4a", "#2a6a8a"]
const SHOES_COL := ["#4a3a3a", "#d8383a", "#2a2a34", "#f4f4f4", "#3a68d8", "#e8c040", "#48a868"]
const BAG_COL := ["#e0b048", "#c83a3a", "#3a68d8", "#48a868", "#8a58c8", "#2a2a34", "#f0f0f0"]
const EYE_COL := ["#2a2018", "#3a5a9a", "#3a8a5a", "#7a4a2a", "#7a3a8a", "#8a8a98"]
const COAT_COL := ["#f4f4f8", "#c8603a", "#2e2e38", "#4a78c8", "#a03a4a", "#6a5a40"]

var gender := "boy"
var hair := "short"
var hat := "cap"
var eyes := "round"
var outfit := "jacket_jeans"
var colors := {"skin": "#f0b88a", "hair": "#3a2a26", "hat": "#d8383a", "shirt": "#d64a3a", "pants": "#34508a",
		"shoes": "#4a3a3a", "bag": "#e0b048", "coat": "#f4f4f8", "iris": "#2a2018"}

static func default_boy() -> PlayerLook:
	return PlayerLook.new()

static func default_girl() -> PlayerLook:
	var l := PlayerLook.new()
	l.gender = "girl"
	l.hair = "pony"
	l.hat = "none"
	l.eyes = "lash"
	l.outfit = "dress"
	l.colors["hair"] = "#6a4430"
	l.colors["shirt"] = "#e060a0"
	l.colors["pants"] = "#8a8a98"
	l.colors["shoes"] = "#d8383a"
	l.colors["bag"] = "#e0b048"
	l.colors["iris"] = "#3a5a9a"
	return l

static func random(rng: RandomNumberGenerator = null) -> PlayerLook:
	var r := rng if rng else RandomNumberGenerator.new()
	if rng == null:
		r.randomize()
	var l := PlayerLook.new()
	l.gender = GENDERS[r.randi() % 2]
	l.hair = HAIRS[r.randi() % HAIRS.size()]
	l.hat = HATS[r.randi() % HATS.size()]
	l.eyes = EYES[r.randi() % 2]
	l.outfit = OUTFITS[r.randi() % OUTFITS.size()]
	l.colors = {"skin": SKIN[r.randi() % SKIN.size()], "hair": HAIR_COL[r.randi() % HAIR_COL.size()],
		"hat": HAT_COL[r.randi() % HAT_COL.size()], "shirt": SHIRT_COL[r.randi() % SHIRT_COL.size()],
		"pants": PANTS_COL[r.randi() % PANTS_COL.size()], "shoes": SHOES_COL[r.randi() % SHOES_COL.size()],
		"bag": BAG_COL[r.randi() % BAG_COL.size()], "coat": COAT_COL[r.randi() % COAT_COL.size()],
		"iris": EYE_COL[r.randi() % EYE_COL.size()]}
	return l

## Switching gender swaps the default silhouette like upstream's customiser (girl: long hair + dress, boy: cap + jacket)
## but keeps anything the player already customised away from the other gender's default.
func set_gender(g: String) -> void:
	if g == gender:
		return
	gender = g
	if g == "girl":
		if hair in ["short", "spiky", "bald"]:
			hair = "pony"
		if outfit in ["jacket_jeans", "tee_jeans"]:
			outfit = "dress"
		eyes = "lash"
	else:
		if hair in ["long", "pony", "bun"]:
			hair = "short"
		if outfit in ["dress", "tee_skirt"]:
			outfit = "jacket_jeans"
		eyes = "round"

func head_key() -> String:
	return "head_%s_%s_%s" % [hair, hat, eyes]

func body_key() -> String:
	return "body_%s" % outfit

func to_dict() -> Dictionary:
	return {"gender": gender, "hair": hair, "hat": hat, "eyes": eyes, "outfit": outfit, "colors": colors.duplicate()}

static func from_dict(d: Variant) -> PlayerLook:
	var l := PlayerLook.new()
	if not (d is Dictionary):
		return l
	var dd: Dictionary = d
	l.gender = str(dd.get("gender", l.gender)) if GENDERS.has(str(dd.get("gender", ""))) else l.gender
	l.hair = str(dd.get("hair", l.hair)) if HAIRS.has(str(dd.get("hair", ""))) else l.hair
	l.hat = str(dd.get("hat", l.hat)) if HATS.has(str(dd.get("hat", ""))) else l.hat
	l.eyes = str(dd.get("eyes", l.eyes)) if EYES.has(str(dd.get("eyes", ""))) else l.eyes
	l.outfit = str(dd.get("outfit", l.outfit)) if OUTFITS.has(str(dd.get("outfit", ""))) else l.outfit
	var c: Variant = dd.get("colors", {})
	if c is Dictionary:
		for k in l.colors.keys():
			if (c as Dictionary).has(k) and str((c as Dictionary)[k]).begins_with("#"):
				l.colors[k] = str((c as Dictionary)[k])
	return l

func duplicate_look() -> PlayerLook:
	return PlayerLook.from_dict(to_dict())
