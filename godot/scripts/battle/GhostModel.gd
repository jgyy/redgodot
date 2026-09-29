class_name GhostModel
extends Node3D
## The unidentifiable GHOST of Pokémon Tower (upstream src/scripts/mid.js
## ghostPic): a pale sheet with a round head, flared wavy hem, stubby arms,
## dark eye holes and a gaping mouth -- built as a small 3D mesh set.

func _init() -> void:
	var body := StandardMaterial3D.new()
	body.albedo_color = Color("#e8e2f6")
	body.rim_enabled = true
	body.rim = 0.6
	var hole := StandardMaterial3D.new()
	hole.albedo_color = Color("#1c1428")
	hole.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_add(_sphere(0.5), body, Vector3(0, 1.05, 0), Vector3(1, 1, 0.95))
	# the sheet: a flared open cone with a wavy hem
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var seg := 28
	var rows := 6
	var pts: Array = []
	for r in rows + 1:
		var row: Array = []
		var y := 1.0 - r * 0.16
		for i in seg + 1:
			var a := TAU * i / seg
			var rad := 0.5 + r * 0.045
			var yy := y - (0.05 * sin(a * 6.0) if r == rows else 0.0)
			row.append(Vector3(cos(a) * rad, yy, sin(a) * rad))
		pts.append(row)
	for r in rows:
		for i in seg:
			for v in [pts[r][i], pts[r + 1][i], pts[r + 1][i + 1], pts[r][i], pts[r + 1][i + 1], pts[r][i + 1]]:
				st.add_vertex(v)
	st.generate_normals()
	var sheet := MeshInstance3D.new()
	sheet.mesh = st.commit()
	var sm: StandardMaterial3D = body.duplicate()
	sm.cull_mode = BaseMaterial3D.CULL_DISABLED
	sheet.material_override = sm
	add_child(sheet)
	for sx in [-1.0, 1.0]:
		_add(_sphere(0.14), body, Vector3(sx * 0.58, 0.72, 0.05), Vector3(1.3, 0.7, 0.8))
		_add(_sphere(0.1), hole, Vector3(sx * 0.2, 1.12, 0.44), Vector3(0.7, 1.2, 0.4))
	_add(_sphere(0.12), hole, Vector3(0, 0.86, 0.46), Vector3(1.2, 0.9, 0.4))

func _sphere(r: float) -> SphereMesh:
	var m := SphereMesh.new()
	m.radius = r
	m.height = r * 2.0
	return m

func _add(mesh: Mesh, mat: Material, pos: Vector3, scl: Vector3) -> void:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = mat
	mi.position = pos
	mi.scale = scl
	add_child(mi)
