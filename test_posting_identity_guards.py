from pathlib import Path


ROOT = Path(__file__).resolve().parent


def test_pipeline_requires_identity_at_batch_start_and_immediately_before_post():
    source = (ROOT / "src" / "coupang_uploader.py").read_text(encoding="utf-8")
    flow = source[
        source.index("    def process_and_upload(") :
    ]

    assert "if not helper.verify_account(ig_username):" in flow
    post_index = flow.index("success = helper.create_thread_direct(")
    nearest_guard = flow.rfind("if not helper.verify_account(ig_username):", 0, post_index)
    assert nearest_guard >= 0
    assert post_index - nearest_guard < 900


def test_legacy_queue_rechecks_identity_after_reservation_before_post():
    source = (ROOT / "src" / "main_window.py").read_text(encoding="utf-8")
    flow = source[
        source.index("    def _run_upload_queue(") :
        source.index("    def stop_upload(")
    ]

    assert '"expected_username": str(ig_username or "").strip()' in source
    assert "if not expected_username:" in flow
    assert "helper.verify_account(expected_username)" in flow
    generation = flow.index("post_data = pipeline_ref.process_link(")
    first_guard = flow.index("if not ensure_threads_ready():")
    assert first_guard < generation
    post_index = flow.index("success = helper.create_thread_direct(")
    second_guard = flow.rfind("if not ensure_threads_ready():", 0, post_index)
    reservation = flow.index("reserve_work(")
    assert reservation < second_guard < post_index
    assert "stop_before_external_post(" in flow[second_guard:post_index]
    recovery = source[
        source.index("    def _recover_unattempted_legacy_post(") :
        source.index("    def _run_upload_queue(")
    ]
    assert '"reservation_release_pending"' in recovery
    assert "release_reserved_work(reservation_id)" in recovery
    assert "self.link_queue.put(item)" in recovery
    assert "getattr(helper, \"external_post_attempted\", True)" in flow
    assert "threads_identity_unverified" in flow
    assert "if not success and not external_post_attempted:" in flow
    assert "stop_before_external_post(" in flow
    assert '"pre_post_validation_failed"' in flow
    attempted_failure = flow.index(
        '"Threads 게시 결과를 확인하지 못했습니다. 중복 게시를 막기 위해 "'
    )
    assert flow.index('"posting_unknown"', second_guard) < attempted_failure
    assert "break" in flow[attempted_failure : attempted_failure + 900]
