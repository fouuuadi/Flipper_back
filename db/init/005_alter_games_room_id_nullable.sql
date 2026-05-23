-- Solo sessions are not tied to a room (room_id stays NULL).
ALTER TABLE games MODIFY COLUMN room_id int NULL;
