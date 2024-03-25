CREATE TABLE IF NOT EXISTS scheduled_messages(
    user_id BITINT NOT NULL,
    channel_id BIGINT NOT NULL,
    send_at TIMESTAMP NOT NULL,
    msg TEXT,

    PRIMARY KEY(user_id, channel_id, send_at)
);
