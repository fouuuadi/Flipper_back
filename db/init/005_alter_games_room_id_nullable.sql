-- Solo sessions are not tied to a room (room_id stays NULL).
ALTER TABLE games ALTER COLUMN room_id DROP NOT NULL;
