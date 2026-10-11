def test_parent_manages_profiles(parent_client):
    created = parent_client.post(
        "/api/profiles", json={"display_name": "  Ali ", "grade": 2, "avatar_key": "lion"}
    )
    assert created.status_code == 201
    ali = created.json()
    assert ali["display_name"] == "Ali" and ali["grade"] == 2

    updated = parent_client.patch(f"/api/profiles/{ali['id']}", json={"grade": 3}).json()
    assert updated["grade"] == 3 and updated["display_name"] == "Ali"

    assert parent_client.delete(f"/api/profiles/{ali['id']}").status_code == 204
    assert parent_client.get("/api/profiles").json() == []


def test_picker_list_is_public_and_minimal(db_client, parent_client, child):
    listed = db_client.get("/api/profiles").json()
    assert listed == [child]
    assert set(child) == {"id", "display_name", "grade", "avatar_key"}


def test_validation(parent_client):
    for bad in [
        {"display_name": "", "grade": 2},
        {"display_name": "A" * 31, "grade": 2},
        {"display_name": "Ali", "grade": 6},
        {"display_name": "Ali", "grade": 2, "avatar_key": "Bad Key"},
    ]:
        assert parent_client.post("/api/profiles", json=bad).status_code == 422


def test_children_cannot_manage_profiles(student_client, child):
    assert student_client.post("/api/profiles", json={"display_name": "X", "grade": 1}).status_code == 403
    assert student_client.patch(f"/api/profiles/{child['id']}", json={"grade": 5}).status_code == 403
    assert student_client.delete(f"/api/profiles/{child['id']}").status_code == 403


def test_signed_out_cannot_manage_profiles(db_client, parent_client):
    assert db_client.post("/api/profiles", json={"display_name": "X", "grade": 1}).status_code == 401


def test_child_sees_only_own_profile(parent_client, student_client, child):
    sibling = parent_client.post("/api/profiles", json={"display_name": "Sami", "grade": 1}).json()
    assert student_client.get(f"/api/profiles/{child['id']}").status_code == 200
    assert student_client.get(f"/api/profiles/{sibling['id']}").status_code == 403


def test_archiving_signs_child_out(parent_client, student_client, child):
    parent_client.delete(f"/api/profiles/{child['id']}")
    assert student_client.get("/api/auth/status").json()["actor"] is None
