---
name: websocket
description: WebSocket testing for cross-site handshake abuse, missing per-message authorization, and object references inside frames
---

# WebSocket

A WebSocket is an authenticated channel that often skips the checks the HTTP API enforces. Test the handshake and then the messages. The browser sends cookies on the upgrade; the server must decide who is allowed to open the socket and who is allowed to act on each frame.

## Handshake

- Capture the upgrade with the proxy. Note `Origin`, `Cookie` or `Authorization`, subprotocols, and the path (`/ws`, `/socket.io`, `/graphql`, `/cable`).
- Replay the upgrade without credentials. A `101` that then accepts a privileged action is a missing authentication check.
- Replay the upgrade with another test account's session and the first account's object ids in later frames.
- Cross-site handshake: a page on an origin you control should not be able to open the socket using the victim browser's cookies. If `Origin` is not checked, confirm with two test accounts that a foreign origin can send a state-changing frame. Do not involve a real user.

Socket.IO and similar libraries wrap the frames. Test the message names the client actually emits, not only a raw WebSocket.

## Messages

- Repeat a frame that reads or changes an object (`id`, `room`, `channel`, `userId`, `tenant`) with another test account's id
- Repeat an admin or staff event name as an unprivileged test account
- Send the same frame twice, and send it as two concurrent connections, when the action spends a balance, redeems a token, or changes a role
- If the HTTP API rejected an action and the socket accepts the same action, that mismatch is the finding

## Proof

Show the unauthorized effect: the other account's data in a frame, or a state change that account did not make, with both sessions identified. A socket that stays open with no privileged effect is an observation.

## Ruled out

The upgrade rejects a missing or foreign `Origin` and a missing session, and each state-changing frame checks the same authorization as the HTTP route. Name the check you saw fail closed.
