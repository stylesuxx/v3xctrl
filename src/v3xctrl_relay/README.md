# v3xctrl Relay Server

The relay server connects streamers, viewers, and spectators in real-time sessions. It forwards packets between peers using both UDP and TCP, manages session lifecycles, and handles automatic cleanup of inactive connections.

## How it works

### Session establishment

A session pairs one streamer with one viewer. Each peer registers two ports - video and control - via `PeerAnnouncement` messages. Once both peers have registered all ports, the session becomes "ready" and bidirectional packet forwarding begins.

```
Streamer                   Relay                     Viewer
   |                         |                         |
   |-- PeerAnnouncement ---->|                         |
   |   (video + control)     |                         |
   |                         |<-- PeerAnnouncement ----|
   |                         |    (video + control)    |
   |                         |                         |
   |<----- PeerInfo ---------|-------- PeerInfo ------>|
   |                         |                         |
   |=========== data flows bidirectionally ============|
```

Peers re-send `PeerAnnouncement` every second as a keepalive. The relay validates session IDs against a SQLite-backed `SessionStore` and rejects unknown sessions with an Error(403) response.

### Spectator mode

Spectators receive a one-way stream from the streamer. They join using a separate spectator ID (mapped to a session ID in the database) and only receive data - they don't send anything back to the streamer.

- Spectators are grouped by source IP (one spectator per public IP per session)
- Multiple spectators from different IPs can watch the same session
- Spectators can join before the session is ready and will start receiving data once both streamer and viewer connect

### Transport support

Peers can connect via UDP or TCP independently. The relay supports all combinations:

| Streamer | Viewer   | Spectator |
|----------|----------|-----------|
| UDP      | UDP      | UDP       |
| UDP      | TCP      | TCP       |
| TCP      | UDP      | Mixed     |
| TCP      | TCP      |           |

TCP connections are accepted by a `TCPAcceptor` running alongside the UDP server. Peers can switch transport mid-session (e.g. reconnect via TCP after starting with UDP).

### Packet forwarding

The hot path (`forward_packet`) uses a lock-protected mapping table for O(1) address lookup:

- **UDP targets**: Sent inline on the receive thread
- **TCP targets**: Returned as deferred sends, dispatched to a thread pool
- **Dead TCP targets**: Silently skipped (no UDP fallback)
- **Unknown addresses**: Routed to a control handler for heartbeat/registration processing

### Session cleanup

A background thread runs every 10 seconds and removes:

1. **Dead TCP targets** with no active mapping
2. **Expired roles** where no port has seen activity for 7.5 minutes
3. **Inactive spectators** with no heartbeat for 30 seconds (unless they have an active TCP connection)
4. **Empty sessions** where all roles have been cleaned up

A session stays alive as long as at least one peer has recent activity. This means the streamer can disconnect and reconnect without losing the session, as long as the viewer is still active (and vice versa).

## Architecture

```
RelayServer (main thread)
    |
    |-- UDP socket (recvfrom loop)
    |     |-- Control messages -> control_executor (4 threads)
    |     |-- Data packets -> forward_packet() -> tcp_executor (10 threads)
    |
    |-- TCPAcceptor (daemon thread)
    |     |-- Accepts TCP connections
    |     |-- Reads PeerAnnouncement handshake
    |     |-- Registers with PacketRelay
    |
    |-- Cleanup thread (every 10s)
    |-- Command socket (/tmp/udp_relay_command_{port}.sock)
```

### Lock ordering

The relay uses two locks with a strict acquisition order:

1. `session_lock` - protects session state (`sessions`, `spectator_by_address`)
2. `mapping_lock` - protects hot-path forwarding (`mappings`, `tcp_targets`)

**Always acquire `session_lock` before `mapping_lock`, never the reverse.**

### Key constants

| Constant              | Value   | Description                              |
|-----------------------|---------|------------------------------------------|
| `TIMEOUT`             | 450s    | Peer inactivity timeout (7.5 minutes)    |
| `SPECTATOR_TIMEOUT`   | 30s     | Spectator heartbeat timeout              |
| `CLEANUP_INTERVAL`    | 10s     | How often cleanup runs                   |
| `RECEIVE_BUFFER`      | 2048B   | UDP receive buffer size                  |

## Command interface

The relay exposes a Unix socket at `/tmp/udp_relay_command_{port}.sock` that accepts the `stats` command, returning JSON with all active sessions, their peers, transport types, and remaining timeout for each connection.
