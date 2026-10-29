def serialize_message(message, user):
    return {
        "id": message.pk,
        "sender": message.sender.get_username(),
        "is_mine": message.sender_id == user.pk,
        "message": message.message,
        "sent_at": message.sent_at.isoformat(),
        "is_read": message.is_read,
    }
