WebSocket server for real-time notifications, live updates, user presence tracking, and bi-directional communication using Python, Flask-SocketIO, and Redis.

Quick start
- docker compose up --build
- Open example/client.html in a browser and connect with a user_id.
- Use HTTP endpoints: GET /api/presence/online, GET /api/presence/room/<room>, POST /api/notify.

Auth
- Pass user_id via Socket.IO auth payload, query string (?user_id=...), or Authorization: Bearer <user_id> header.

Events
- connect/disconnect: handled by server.
- join_room {room}: join a room; presence reflected in Redis and broadcasted.
- leave_room {room}: leave a room; presence updated and broadcasted.
- notify_user {to_user_id, event?, payload?}: send direct message to a user.
- notify_room {room, event?, payload?}: send message to a room.
- broadcast_update {any payload}: broadcast to all clients as update event.
- typing {room, typing?: boolean}: ephemeral typing indicator to a room.
- whoami: server replies with whoami:result containing user_id and sid.
- heartbeat: server replies with heartbeat:ack.

Presence storage (Redis)
- presence:online_users -> set of online user IDs.
- presence:user:{user_id}:sids -> set of active Socket.IO sids for the user.
- presence:sid:{sid}:user -> string mapping sid -> user_id.
- presence:sid:{sid}:rooms -> set of rooms joined by this sid.
- presence:room:{room}:users -> set of user IDs present in room.

Scaling
- Flask-SocketIO is configured with Redis message queue for horizontal scaling.
- Run multiple app instances behind a load balancer; they will share rooms and events via Redis.

