import pytest


def test_export_header(mod_imported, mod_exported):
    sheader = mod_imported.header
    dheader = mod_exported.header

    bones_data_error = abs(mod_imported.bones_data.size_ - mod_exported.bones_data.size_)
    assert (sheader.version in (210, 211) and not bones_data_error) or sheader.version == 156

    assert sheader.ident == dheader.ident == b"MOD\x00"
    assert sheader.version == dheader.version
    assert sheader.revision == dheader.revision
    assert sheader.num_bones == dheader.num_bones
    assert sheader.num_materials == dheader.num_materials
    assert (sheader.version in (210, 211) and sheader.reserved_01 == dheader.reserved_01 or
            sheader.version == 156 and not getattr(dheader, "reserved_01", None))
    assert sheader.num_groups == dheader.num_groups
    assert sheader.num_meshes == dheader.num_meshes
    assert ((sheader.version in (210, 211) and sheader.num_vertices == dheader.num_vertices) or
            sheader.version == 156)  # given 2nd vertex buffer unknowns

    assert sheader.offset_bones_data == dheader.offset_bones_data
    assert sheader.offset_groups == dheader.offset_groups - bones_data_error
    assert sheader.offset_materials_data == dheader.offset_materials_data - bones_data_error
    assert sheader.offset_meshes_data == dheader.offset_meshes_data - bones_data_error
    assert sheader.offset_vertex_buffer == dheader.offset_vertex_buffer - bones_data_error


def test_export_top_level(mod_imported, mod_exported):

    # assert mod_imported.bsphere.x == pytest.approx(mod_exported.bsphere.x, rel=0.5)
    assert mod_imported.bsphere.y == pytest.approx(mod_exported.bsphere.y, rel=0.001)
    # assert mod_imported.bsphere.z == pytest.approx(mod_exported.bsphere.z, rel=0.001)
    assert mod_imported.bsphere.w == pytest.approx(mod_exported.bsphere.w, rel=0.001)

    assert mod_imported.bbox_min.x == pytest.approx(mod_exported.bbox_min.x, rel=0.001)
    assert mod_imported.bbox_min.y == pytest.approx(mod_exported.bbox_min.y, rel=0.001)
    assert mod_imported.bbox_min.z == pytest.approx(mod_exported.bbox_min.z, rel=0.001)
    assert mod_imported.bbox_min.w == pytest.approx(mod_exported.bbox_min.w, rel=0.001)

    assert mod_imported.bbox_max.x == pytest.approx(mod_exported.bbox_max.x, rel=0.001)
    assert mod_imported.bbox_max.y == pytest.approx(mod_exported.bbox_max.y, rel=0.001)
    assert mod_imported.bbox_max.z == pytest.approx(mod_exported.bbox_max.z, rel=0.001)
    assert mod_imported.bbox_max.w == pytest.approx(mod_exported.bbox_max.w, rel=0.001)

    assert mod_imported.unk_01 == mod_exported.unk_01
    assert mod_imported.unk_02 == mod_exported.unk_02
    assert mod_imported.unk_03 == mod_exported.unk_03
    assert mod_imported.unk_04 == mod_exported.unk_04


def test_export_bones_data(mod_imported, mod_exported):
    # TODO: matrices
    sbd = mod_imported.bones_data
    dbd = mod_exported.bones_data
    bones_data_error = abs(mod_imported.bones_data.size_ - mod_exported.bones_data.size_)
    assert ((mod_exported.header.version in (210, 211) and not bones_data_error) or
            mod_exported.header.version == 156)

    assert mod_imported.bones_data_size_ == mod_exported.bones_data_size_ - bones_data_error

    assert (
        [b.idx_anim_map for b in sbd.bones_hierarchy] ==
        [b.idx_anim_map for b in dbd.bones_hierarchy])
    assert (
        [b.idx_parent for b in sbd.bones_hierarchy] ==
        [b.idx_parent for b in dbd.bones_hierarchy])
    assert (
        [b.idx_mirror for b in sbd.bones_hierarchy] ==
        [b.idx_mirror for b in dbd.bones_hierarchy])
    assert (
        [b.idx_mapping for b in sbd.bones_hierarchy] ==
        [b.idx_mapping for b in dbd.bones_hierarchy])
    assert (
        [b.unk_01 for b in sbd.bones_hierarchy] ==
        [b.unk_01 for b in dbd.bones_hierarchy])
    assert (
        [b.parent_distance for b in sbd.bones_hierarchy] ==
        [b.parent_distance for b in dbd.bones_hierarchy])
    assert (
        [(b.location.x, b.location.y, b.location.z) for b in sbd.bones_hierarchy] ==
        [(b.location.x, b.location.y, b.location.z) for b in dbd.bones_hierarchy])

    assert sbd.bone_map == dbd.bone_map


def test_export_groups(mod_imported, mod_exported):

    assert mod_imported.groups_size_ == mod_exported.groups_size_

    assert [g.group_index for g in mod_imported.groups] == [g.group_index for g in mod_exported.groups]
    assert [g.unk_02 for g in mod_imported.groups] == [g.unk_02 for g in mod_exported.groups]
    assert [g.unk_03 for g in mod_imported.groups] == [g.unk_03 for g in mod_exported.groups]
    assert [g.unk_04 for g in mod_imported.groups] == [g.unk_04 for g in mod_exported.groups]
    assert [g.unk_05 for g in mod_imported.groups] == [g.unk_05 for g in mod_exported.groups]
    assert [g.unk_06 for g in mod_imported.groups] == [g.unk_06 for g in mod_exported.groups]
    assert [g.unk_07 for g in mod_imported.groups] == [g.unk_07 for g in mod_exported.groups]
    assert [g.unk_08 for g in mod_imported.groups] == [g.unk_08 for g in mod_exported.groups]


def test_materials_data(mod_imported, mod_exported):

    assert mod_imported.materials_data.size_ == mod_exported.materials_data.size_
    assert ((mod_imported.header.version in (210, 211) and
            mod_imported.materials_data.material_names == mod_exported.materials_data.material_names) or
            mod_imported.header.version == 156)


def test_meshes_data_21(mod_imported, mod_exported, subtests):
    if not mod_imported.header.version == 210:
        pytest.skip()

    for i, mesh in enumerate(mod_imported.meshes_data.meshes):
        src_mesh = mesh
        dst_mesh = mod_exported.meshes_data.meshes[i]
        with subtests.test(mesh_index=i):
            assert src_mesh.idx_group == dst_mesh.idx_group
            assert src_mesh.num_vertices == dst_mesh.num_vertices
            assert src_mesh.unk_01 == dst_mesh.unk_01
            assert src_mesh.idx_material == dst_mesh.idx_material
            assert src_mesh.level_of_detail == dst_mesh.level_of_detail
            assert src_mesh.type_mesh == dst_mesh.type_mesh
            assert src_mesh.unk_class_mesh == dst_mesh.unk_class_mesh
            # assert src_mesh.vertex_stride == dst_mesh.vertex_stride
            assert src_mesh.unk_render_mode == dst_mesh.unk_render_mode
            # assert src_mesh.vertex_format == dst_mesh.vertex_format
            assert src_mesh.bone_id_start == dst_mesh.bone_id_start
            assert src_mesh.num_unique_bone_ids == dst_mesh.num_unique_bone_ids
            assert src_mesh.mesh_index == dst_mesh.mesh_index
            assert src_mesh.min_index == dst_mesh.min_index
            assert src_mesh.max_index == dst_mesh.max_index
            assert src_mesh.hash == dst_mesh.hash

    assert mod_imported.header.version == 210 and (
        mod_imported.num_weight_bounds == mod_exported.num_weight_bounds)


@pytest.mark.xfail(reason="WIP")
def test_header_xfail(pl0000_roundtrip):
    """
    Tests to fix
    """
    src_mod, dst_mod = pl0000_roundtrip
    sheader = src_mod.header
    dheader = dst_mod.header

    assert sheader.num_faces == dheader.num_faces
    assert sheader.num_edges == dheader.num_edges
    assert sheader.version not in (210, 211) or sheader.size_file == dheader.size_file
    # in 210, given we don't export some vertex formats (like the one witih blend shapes of 64 bytes)
    # the size and hence the offset of the index buffer will differ
    assert sheader.offset_index_buffer == dheader.offset_index_buffer
    assert sheader.size_vertex_buffer == dheader.size_vertex_buffer


@pytest.mark.xfail(reason="WIP")
def test_meshes_data_xfail(mod_imported, mod_exported, subtests):

    assert mod_imported.meshes_data.num_weight_bounds == mod_exported.meshes_data.num_weight_bounds
    for i, mesh in enumerate(mod_imported.meshes_data.meshes):
        src_mesh = mesh
        dst_mesh = mod_exported.meshes_data.meshes[i]
        with subtests.test(i=i):
            assert src_mesh.vertex_position == dst_mesh.vertex_position
            assert src_mesh.vertex_offset == dst_mesh.vertex_offset
            assert src_mesh.face_position == dst_mesh.face_position
            assert src_mesh.num_indices == dst_mesh.num_indices
            assert src_mesh.face_offset == dst_mesh.face_offset
