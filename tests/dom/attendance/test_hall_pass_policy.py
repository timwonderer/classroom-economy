from app.extensions import db
from app.feats.attendance import save_hall_pass_setup_config
from app.models import HallPassSettings
from tests.helpers.classroom_initializer import initialize


def test_hall_pass_policy_submission_is_append_only(client):
    classroom = initialize("chemistry_p1", client.application)
    payload = [{"pass_name": "Break", "max_queue": 2, "consume_pass": False}]
    first = save_hall_pass_setup_config(
        user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        hall_pass_enabled=True, pass_type_payload=payload, max_queue_limit=10,
        correlation_id="corr_test_hall_pass_append", idempotency_key="test:hall-pass:append:1",
    )
    second = save_hall_pass_setup_config(
        user_id=classroom.teacher_user.id, class_id=classroom.class_id,
        hall_pass_enabled=True, pass_type_payload=payload, max_queue_limit=4,
        correlation_id="corr_test_hall_pass_append_2", idempotency_key="test:hall-pass:append:2",
    )
    assert first.policy_uuid != second.policy_uuid
    assert HallPassSettings.query.filter_by(class_id=classroom.class_id).count() >= 3
    assert second.effective_queue_limit == 2
