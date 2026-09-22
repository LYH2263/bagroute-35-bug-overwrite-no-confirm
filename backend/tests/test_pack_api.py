from app.models.models import DeliveryRoute, SubscriberStop


def _make_route(db, max_weight=4.0, max_volume=10.0) -> DeliveryRoute:
    route = DeliveryRoute(name="测试线", max_weight_kg=max_weight, max_volume_l=max_volume)
    db.add(route)
    db.flush()
    db.add_all(
        [
            SubscriberStop(route_id=route.id, seq=1, name="站点1", weight_kg=2.0, volume_l=3.0),
            SubscriberStop(route_id=route.id, seq=2, name="站点2", weight_kg=2.5, volume_l=3.0),
            SubscriberStop(route_id=route.id, seq=3, name="站点3", weight_kg=1.0, volume_l=1.0),
            SubscriberStop(route_id=route.id, seq=4, name="超大件", weight_kg=9.0, volume_l=1.0),
        ]
    )
    db.commit()
    return route


def _bag_names(bags):
    return [[i["stop_name"] for i in b["items"]] for b in bags]


def test_first_pack_without_flag_succeeds(client, db_session):
    route = _make_route(db_session)
    res = client.post("/api/pack", json={"route_id": route.id})
    assert res.status_code == 200
    assert _bag_names(res.json()) == [["站点1"], ["站点2", "站点3"]]
    rejects = client.get("/api/rejects").json()
    assert [r["stop_name"] for r in rejects] == ["超大件"]


def test_repack_without_confirm_fails_and_keeps_old_results(client, db_session):
    route = _make_route(db_session)
    assert client.post("/api/pack", json={"route_id": route.id}).status_code == 200
    old_bags = client.get("/api/bags").json()
    old_rejects = client.get("/api/rejects").json()
    old_weights = client.get("/api/weights").json()
    assert len(old_bags) == 2 and len(old_rejects) == 1

    res = client.post("/api/pack", json={"route_id": route.id})
    assert res.status_code == 409
    assert "确认覆盖" in res.json()["detail"]

    # 旧袋明细、拒收、袋重保持不变
    assert client.get("/api/bags").json() == old_bags
    assert client.get("/api/rejects").json() == old_rejects
    assert client.get("/api/weights").json() == old_weights


def test_repack_with_confirm_applies_new_weight_limit(client, db_session):
    route = _make_route(db_session)
    assert client.post("/api/pack", json={"route_id": route.id}).status_code == 200
    assert len(client.get("/api/bags").json()) == 2

    # 新限额：单袋限重 4.0 → 3.0，原两袋装不下
    route.max_weight_kg = 3.0
    db_session.commit()

    res = client.post("/api/pack", json={"route_id": route.id, "confirm_overwrite": True})
    assert res.status_code == 200
    bags = res.json()
    assert _bag_names(bags) == [["站点1"], ["站点2"], ["站点3"]]
    assert [b["weight_kg"] for b in bags] == [2.0, 2.5, 1.0]
    # 旧袋已被替换而非累加：库中该路线只有新算的 3 袋
    assert len(client.get("/api/bags").json()) == 3
    weights = client.get("/api/weights").json()
    assert len(weights) == 3
    assert all(w["route_id"] == route.id for w in weights)


def test_repack_with_confirm_picks_up_new_stop(client, db_session):
    route = _make_route(db_session)
    assert client.post("/api/pack", json={"route_id": route.id}).status_code == 200

    db_session.add(SubscriberStop(route_id=route.id, seq=5, name="新站点", weight_kg=1.0, volume_l=1.0))
    db_session.commit()

    res = client.post("/api/pack", json={"route_id": route.id, "confirm_overwrite": True})
    assert res.status_code == 200
    assert _bag_names(res.json()) == [["站点1"], ["站点2", "站点3"], ["新站点"]]
