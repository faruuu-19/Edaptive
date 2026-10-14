# Consent — Track C boundary, parent dashboard integration

Owner: Ibrahim / Track C. Local implementation added at Amna's request; storage and policy need Track C review before merging. This module uses the existing `ParentActor` identity and core household/profile access checks. No feature-module imports are needed.

The dashboard stores real parental permission choices for camera and microphone, per child. Missing consent is false. `GET /api/consent/{student_id}` reads the latest decisions. `PUT /api/consent/{student_id}/{camera|microphone}` accepts only a strict boolean `granted`. Only a parent of an active child in this household can read or save permissions. Updates lock the profile, append one decision when the requested state changes, and keep prior decisions. The monotonic decision ID orders changes even when timestamps match. Policy version `no-input-v1` describes this stage: no sensor capture or media-input implementation.

Migration 0005 creates the `consent` decision-history table described in DATA-MODEL. `decided_by=parent` refers to the existing PIN-unlocked guardian role; the actor contract has no separate parent account ID. It is an operational table and does not publish unregistered consent events. Consent event contracts and enforcement by future attention/input modules remain team integration work.

`input_available` is always false. Saving application consent does not request browser device access, start a camera or microphone, or store audio/video. Browser permission and the relevant module's checks are still required when input is implemented. Revoking is a real saved consent decision, with no active stream to stop in this stage.
