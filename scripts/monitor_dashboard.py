#!/usr/bin/env python3
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
from typing import Any
from urllib.parse import urlparse

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rcl_interfaces.msg import Log
from rclpy.time import Time
from std_msgs.msg import Bool, String
from tf2_ros import Buffer, TransformException, TransformListener

from llm_yolo_interfaces.msg import Intent


HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SIM MONITOR</title>
  <style>
    :root {
      --bg: #f3f0e8;
      --panel: #fffaf0;
      --line: #d8cfbf;
      --text: #1f1d1a;
      --muted: #6f6a61;
      --accent: #b6542d;
      --ok: #2f7d4d;
      --warn: #9b6a12;
      --bad: #a3332f;
      --shadow: rgba(31, 29, 26, 0.08);
      --mono: "JetBrains Mono", "Fira Code", monospace;
      --sans: "Pretendard", "Noto Sans KR", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(182,84,45,0.10), transparent 28%),
        radial-gradient(circle at bottom right, rgba(47,125,77,0.08), transparent 24%),
        var(--bg);
      color: var(--text);
      font-family: var(--sans);
    }
    .wrap {
      max-width: 1400px;
      margin: 0 auto;
      padding: 24px;
    }
    .topbar {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 16px;
      margin-bottom: 18px;
    }
    h1 {
      margin: 0;
      font-size: 30px;
      line-height: 1.05;
      letter-spacing: -0.04em;
    }
    .sub {
      color: var(--muted);
      margin-top: 6px;
      font-size: 14px;
    }
    .meta {
      display: grid;
      gap: 6px;
      justify-items: end;
      font-family: var(--mono);
      font-size: 12px;
      color: var(--muted);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 16px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px 16px 14px;
      box-shadow: 0 10px 28px var(--shadow);
      min-height: 130px;
    }
    .hero-card {
      min-height: 190px;
    }
    .compact-card {
      min-height: 110px;
    }
    .table-card {
      min-height: 220px;
    }
    .span-3 { grid-column: span 3; }
    .span-2 { grid-column: span 2; }
    .span-4 { grid-column: span 4; }
    .span-5 { grid-column: span 5; }
    .span-6 { grid-column: span 6; }
    .span-7 { grid-column: span 7; }
    .span-8 { grid-column: span 8; }
    .span-12 { grid-column: span 12; }
    .label {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 10px;
    }
    .big {
      font-size: 26px;
      font-weight: 700;
      letter-spacing: -0.03em;
      line-height: 1.15;
    }
    .status-row {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 2px;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 700;
      border: 1px solid var(--line);
      background: #fff;
    }
    .dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--muted);
    }
    .ok .dot { background: var(--ok); }
    .warn .dot { background: var(--warn); }
    .bad .dot { background: var(--bad); }
    .mono {
      font-family: var(--mono);
      font-size: 13px;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .list {
      display: grid;
      gap: 10px;
    }
    .row {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      border-top: 1px solid rgba(216, 207, 191, 0.6);
      padding-top: 10px;
    }
    .row:first-child {
      border-top: 0;
      padding-top: 0;
    }
    .key {
      color: var(--muted);
      min-width: 110px;
      font-size: 13px;
    }
    .value {
      flex: 1;
      text-align: right;
      font-family: var(--mono);
      font-size: 13px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      text-align: left;
      padding: 8px 10px;
      border-top: 1px solid rgba(216, 207, 191, 0.7);
      font-family: var(--mono);
      vertical-align: top;
    }
    th {
      color: var(--muted);
      font-weight: 600;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      border-top: 0;
      padding-top: 0;
    }
    .muted {
      color: var(--muted);
    }
    .history {
      max-height: 280px;
      overflow: auto;
      padding-right: 4px;
    }
    .controls {
      display: grid;
      gap: 14px;
    }
    .button-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 10px;
    }
    button {
      appearance: none;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      padding: 10px 14px;
      border-radius: 12px;
      font: inherit;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
    }
    button.primary {
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }
    button.warn {
      background: #fff7e8;
      color: #7a4e0f;
    }
    button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    input[type="text"] {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px 14px;
      font: inherit;
      font-size: 14px;
      background: #fff;
      color: var(--text);
    }
    .inline-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }
    .hero-input {
      font-size: 16px !important;
      padding: 14px 16px !important;
    }
    .section-note {
      color: var(--muted);
      font-size: 12px;
      margin-top: 6px;
      letter-spacing: 0.02em;
    }
    @media (max-width: 1100px) {
      .span-2, .span-3, .span-4, .span-5, .span-6, .span-7, .span-8 { grid-column: span 12; }
      .topbar { align-items: start; flex-direction: column; }
      .meta { justify-items: start; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div>
        <h1>SIM MONITOR</h1>
        <div class="sub">ROS topic 상태를 백그라운드 구독해서 1초 주기로 갱신합니다.</div>
      </div>
      <div class="meta">
        <div id="serverTime">server_time: -</div>
        <div id="lastUpdate">last_update: -</div>
      </div>
    </div>
    <div class="grid">
      <section class="card span-7 hero-card">
        <div class="label">Command Console</div>
        <div class="controls">
          <input id="userTextInput" class="hero-input" type="text" placeholder="예: chair 앞으로 가" />
          <div class="button-row">
            <button id="sendUserTextBtn" class="primary">Send Command</button>
            <button id="cancelMissionBtn" class="warn">Cancel Mission</button>
            <button class="quickCmd" data-command="center 로 가">center 로 가</button>
            <button class="quickCmd" data-command="chair 찾아">chair 찾아</button>
            <button class="quickCmd" data-command="chair 앞으로 가">chair 앞으로 가</button>
            <button class="quickCmd" data-command="긴급 정지">긴급 정지</button>
            <button class="quickCmd" data-command="정지 해제">정지 해제</button>
          </div>
          <div id="commandFeedback" class="mono muted">-</div>
        </div>
      </section>

      <section class="card span-3 compact-card">
        <div class="label">Mission</div>
        <div class="status-row">
          <div id="missionPill" class="pill warn"><span class="dot"></span><span id="missionStatus">unknown</span></div>
          <div id="executionPill" class="pill warn"><span class="dot"></span><span id="executionStatus">idle</span></div>
        </div>
        <div id="missionText" class="big" style="margin-top:14px;">-</div>
      </section>

      <section class="card span-2 compact-card">
        <div class="label">Safety</div>
        <div class="status-row">
          <div id="emergencyPill" class="pill ok"><span class="dot"></span><span id="emergencyStatus">clear</span></div>
        </div>
        <div id="emergencyText" class="big" style="margin-top:14px;">clear</div>
        <div class="status-row" style="margin-top:14px;">
          <div id="personPausePill" class="pill ok"><span class="dot"></span><span id="personPauseStatus">person clear</span></div>
        </div>
        <div id="personPauseText" class="sub" style="margin-top:10px;">-</div>
      </section>

      <section class="card span-4 compact-card">
        <div class="label">Target Distance</div>
        <div id="targetDistanceValue" class="big">-</div>
        <div id="targetDistanceMeta" class="sub" style="margin-top:10px;">-</div>
      </section>

      <section class="card span-4 compact-card">
        <div class="label">Objects</div>
        <div id="visibleObjects" class="big">-</div>
        <div class="inline-meta">
          <div id="poseCount" class="pill"><span class="dot"></span><span>poses: 0</span></div>
        </div>
      </section>

      <section class="card span-4 compact-card">
        <div class="label">Intent</div>
        <div id="intentText" class="big">-</div>
        <div id="intentMeta" class="sub" style="margin-top:10px;">-</div>
      </section>

      <section class="card span-12 compact-card">
        <div class="label">Recent Mission State</div>
        <div id="missionHistory" class="history mono muted">-</div>
      </section>

      <section class="card span-8 table-card">
        <div class="label">Object Poses</div>
        <div class="section-note">현재 perception이 보고 있는 live object 목록</div>
        <table>
          <thead>
            <tr><th>Target</th><th>Class</th><th>Conf</th><th>X</th><th>Y</th><th>Z</th><th>Dist</th></tr>
          </thead>
          <tbody id="poseTableBody">
            <tr><td colspan="7" class="muted">no data</td></tr>
          </tbody>
        </table>
      </section>

      <section class="card span-4 table-card">
        <div class="label">Action Health</div>
        <table>
          <thead>
            <tr><th>Action</th><th>Servers</th><th>Clients</th><th>Status</th></tr>
          </thead>
          <tbody id="actionHealthBody">
            <tr><td colspan="4" class="muted">no data</td></tr>
          </tbody>
        </table>
      </section>

      <section class="card span-6">
        <div class="label">Perception Debug</div>
        <div id="perceptionDebug" class="mono">-</div>
      </section>

      <section class="card span-6">
        <div class="label">Mission Plan</div>
        <div id="missionPlan" class="mono">-</div>
      </section>

      <section class="card span-12">
        <div class="label">Core Logs</div>
        <div id="coreLogs" class="history mono muted">-</div>
      </section>
    </div>
  </div>

  <script>
    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }

    function setStatusPill(element, status, text) {
      element.classList.remove("ok", "warn", "bad");
      element.classList.add(status);
      element.querySelector("span:last-child").textContent = text;
    }

    function missionStatusFromText(text) {
      const value = (text || "").toLowerCase();
      if (!value) return ["warn", "unknown"];
      if (value.includes("completed") || value.includes("success") || value.includes("arrived")) return ["ok", "success"];
      if (value.includes("failed") || value.includes("aborted") || value.includes("rejected") || value.includes("unavailable")) return ["bad", "failed"];
      return ["warn", "running"];
    }

    function computeObjectDistances(objects, robotPose, frameId) {
      const robotFrame = robotPose.frame_id || "";
      if (!robotFrame || !frameId || robotFrame !== frameId) {
        return objects.map((obj) => ({ ...obj, distance_m: null }));
      }
      const rx = Number(robotPose.x || 0);
      const ry = Number(robotPose.y || 0);
      const rz = Number(robotPose.z || 0);
      return objects.map((obj) => {
        const dx = Number(obj.x_m || 0) - rx;
        const dy = Number(obj.y_m || 0) - ry;
        const dz = Number(obj.z_m || 0) - rz;
        return { ...obj, distance_m: Math.sqrt(dx * dx + dy * dy + dz * dz) };
      });
    }

    function isLockedTargetRow(obj, lockedTarget) {
      if (!lockedTarget || !lockedTarget.active) return false;
      if ((obj.class_name || "") !== (lockedTarget.class_name || "")) return false;
      const eps = 1e-6;
      return (
        Math.abs(Number(obj.x_m || 0) - Number(lockedTarget.x || 0)) < eps &&
        Math.abs(Number(obj.y_m || 0) - Number(lockedTarget.y || 0)) < eps &&
        Math.abs(Number(obj.z_m || 0) - Number(lockedTarget.z || 0)) < eps
      );
    }

    function updatePoseTable(objects, lockedTarget) {
      const body = document.getElementById("poseTableBody");
      if (!objects || objects.length === 0) {
        body.innerHTML = '<tr><td colspan="7" class="muted">no data</td></tr>';
        return;
      }
      body.innerHTML = objects.map((obj) => {
        const isTarget = isLockedTargetRow(obj, lockedTarget);
        return `<tr>
          <td>${isTarget ? "target" : "-"}</td>
          <td>${escapeHtml(obj.class_name || "-")}</td>
          <td>${Number(obj.confidence || 0).toFixed(2)}</td>
          <td>${Number(obj.x_m || 0).toFixed(2)}</td>
          <td>${Number(obj.y_m || 0).toFixed(2)}</td>
          <td>${Number(obj.z_m || 0).toFixed(2)}</td>
          <td>${obj.distance_m == null ? "-" : `${Number(obj.distance_m).toFixed(2)} m`}</td>
        </tr>`;
      }).join("");
    }

    async function postJson(url, payload) {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {}),
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `${response.status}`);
      }
      return response.json();
    }

    async function refresh() {
      try {
        const response = await fetch("/api/state", { cache: "no-store" });
        const state = await response.json();

        const missionText = state.mission_state.last || "-";
        const [missionClass, missionLabel] = missionStatusFromText(missionText);
        setStatusPill(document.getElementById("missionPill"), missionClass, missionLabel);
        document.getElementById("missionText").textContent = missionText;
        const execution = state.execution || {};
        setStatusPill(
          document.getElementById("executionPill"),
          execution.busy ? "warn" : "ok",
          execution.busy ? "busy" : "idle"
        );

        const emergencyActive = Boolean(state.emergency_stop.active);
        setStatusPill(
          document.getElementById("emergencyPill"),
          emergencyActive ? "bad" : "ok",
          emergencyActive ? "engaged" : "clear"
        );
        document.getElementById("emergencyText").textContent = emergencyActive ? "engaged" : "clear";

        const personPause = state.person_pause || {};
        setStatusPill(
          document.getElementById("personPausePill"),
          personPause.active ? "warn" : "ok",
          personPause.active ? "person pause" : "person clear"
        );
        document.getElementById("personPauseText").textContent = personPause.message || "-";

        const objects = state.visible_objects.items || [];
        document.getElementById("visibleObjects").textContent = objects.length ? objects.join(", ") : "-";

        const robotPose = state.robot_pose || {};
        const objectPoseState = state.object_poses || {};
        const lockedTarget = state.locked_target || {};
        const poseObjects = computeObjectDistances(objectPoseState.objects || [], robotPose, objectPoseState.frame_id || "");
        document.getElementById("poseCount").textContent = `poses: ${poseObjects.length}`;
        updatePoseTable(poseObjects, lockedTarget);

        const intent = state.intent || {};
        document.getElementById("intentText").textContent = intent.intent || "-";
        document.getElementById("intentMeta").textContent =
          intent.intent ? `${intent.target_type || "-"}:${intent.target_value || "-"} / speed=${intent.speed_hint || "-"}` : "-";

        document.getElementById("perceptionDebug").textContent = state.perception_debug.last || "-";
        document.getElementById("missionPlan").textContent = state.mission_plan.pretty || state.mission_plan.last || "-";
        document.getElementById("missionHistory").innerHTML =
          (state.mission_state.history || []).map((line) => escapeHtml(line)).join("<br>") || "-";
        document.getElementById("coreLogs").innerHTML =
          (state.core_logs || []).map((line) => escapeHtml(line)).join("<br>") || "-";
        if (lockedTarget.active) {
          if (lockedTarget.distance_m == null) {
            document.getElementById("targetDistanceValue").textContent = "-";
            document.getElementById("targetDistanceMeta").textContent = lockedTarget.message || "distance unavailable";
          } else {
            document.getElementById("targetDistanceValue").textContent = `${Number(lockedTarget.distance_m).toFixed(2)} m`;
            document.getElementById("targetDistanceMeta").textContent =
              `locked ${lockedTarget.class_name || intent.target_value || "-"} / robot_frame=${robotPose.frame_id || "-"} / target_frame=${lockedTarget.frame_id || "-"}`;
          }
        } else if (!intent.intent || intent.intent !== "approach_object") {
          document.getElementById("targetDistanceValue").textContent = "-";
          document.getElementById("targetDistanceMeta").textContent = "approach target not active";
        } else if (!lockedTarget.active) {
          document.getElementById("targetDistanceValue").textContent = "-";
          document.getElementById("targetDistanceMeta").textContent = lockedTarget.message || "target lock unavailable";
        }
        const actions = state.actions || {};
        const actionRows = Object.entries(actions);
        document.getElementById("actionHealthBody").innerHTML = actionRows.length
          ? actionRows.map(([name, info]) => `
              <tr>
                <td>${escapeHtml(name)}</td>
                <td>${Number(info.servers || 0)}</td>
                <td>${Number(info.clients || 0)}</td>
                <td>${escapeHtml(info.status || "-")}</td>
              </tr>
            `).join("")
          : '<tr><td colspan="4" class="muted">no data</td></tr>';

        document.getElementById("serverTime").textContent = `server_time: ${state.server_time}`;
        document.getElementById("lastUpdate").textContent = `last_update: ${state.last_update || "-"}`;
      } catch (err) {
        document.getElementById("perceptionDebug").textContent = `dashboard fetch failed: ${err}`;
      }
    }

    document.getElementById("sendUserTextBtn").addEventListener("click", async () => {
      const input = document.getElementById("userTextInput");
      const text = input.value.trim();
      if (!text) return;
      try {
        const result = await postJson("/api/command", { text });
        document.getElementById("commandFeedback").textContent = result.message || `published: ${text}`;
        input.value = "";
        refresh();
      } catch (err) {
        document.getElementById("commandFeedback").textContent = `send failed: ${err}`;
      }
    });

    document.getElementById("userTextInput").addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        document.getElementById("sendUserTextBtn").click();
      }
    });

    document.querySelectorAll(".quickCmd").forEach((button) => {
      button.addEventListener("click", async () => {
        const text = button.dataset.command;
        try {
          const result = await postJson("/api/command", { text });
          document.getElementById("commandFeedback").textContent = result.message || `published: ${text}`;
          refresh();
        } catch (err) {
          document.getElementById("commandFeedback").textContent = `send failed: ${err}`;
        }
      });
    });

    document.getElementById("cancelMissionBtn").addEventListener("click", async () => {
      try {
        const result = await postJson("/api/cancel", {});
        document.getElementById("commandFeedback").textContent = result.message || "cancel requested";
        refresh();
      } catch (err) {
        document.getElementById("commandFeedback").textContent = `cancel failed: ${err}`;
      }
    });

    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>
"""


class SharedState:
    def __init__(self):
        self._lock = threading.Lock()
        self._state: dict[str, Any] = {
            'server_time': '',
            'last_update': '',
            'mission_state': {'last': '', 'history': []},
            'perception_debug': {'last': ''},
            'object_poses': {'frame_id': '', 'objects': []},
            'visible_objects': {'raw': '', 'items': []},
            'emergency_stop': {'active': False, 'last': ''},
            'mission_plan': {'last': '', 'pretty': ''},
            'intent': {
                'intent': '',
                'target_type': '',
                'target_value': '',
                'speed_hint': '',
                'confidence': 0.0,
            },
            'person_pause': {
                'active': False,
                'message': '',
            },
            'execution': {
                'busy': False,
                'message': 'idle',
            },
            'core_logs': [],
            'actions': {},
            'cmd_vel': {
                'linear_x': 0.0,
                'angular_z': 0.0,
            },
            'odom': {
                'linear_x': 0.0,
                'angular_z': 0.0,
            },
            'robot_pose': {
                'available': False,
                'frame_id': '',
                'x': 0.0,
                'y': 0.0,
                'z': 0.0,
            },
            'locked_target': {
                'active': False,
                'class_name': '',
                'frame_id': '',
                'x': 0.0,
                'y': 0.0,
                'z': 0.0,
                'confidence': 0.0,
                'distance_m': None,
                'message': 'no locked target',
            },
        }

    def _touch(self):
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        self._state['server_time'] = now
        self._state['last_update'] = now

    def update_mission_state(self, text: str):
        with self._lock:
            history = self._state['mission_state']['history']
            history.append(text)
            self._state['mission_state']['history'] = history[-12:]
            self._state['mission_state']['last'] = text
            lower_text = str(text).lower()
            if 'approach requested' in lower_text:
                target_class = self._extract_target_class_from_mission_text_locked(text)
                if target_class:
                    locked = self._state.get('locked_target', {})
                    if locked.get('class_name') != target_class:
                        self._clear_locked_target_locked(f'awaiting target lock: {target_class}')
                else:
                    self._clear_locked_target_locked('awaiting target lock')
                self._try_lock_target_locked()
            self._recompute_execution_locked(text)
            self._recompute_person_pause_locked()
            if any(token in lower_text for token in ('completed', 'failed', 'aborted', 'canceled', 'rejected')):
                self._update_locked_target_distance_locked()
            self._touch()

    def update_perception_debug(self, text: str):
        with self._lock:
            self._state['perception_debug']['last'] = text
            self._touch()

    def update_visible_objects(self, text: str):
        items = [item.strip() for item in text.split(',') if item.strip()]
        with self._lock:
            self._state['visible_objects'] = {'raw': text, 'items': items}
            self._recompute_person_pause_locked()
            self._touch()

    def update_emergency_stop(self, active: bool):
        with self._lock:
            self._state['emergency_stop'] = {
                'active': bool(active),
                'last': 'engaged' if active else 'clear',
            }
            self._touch()

    def update_object_poses(self, text: str):
        payload: dict[str, Any]
        try:
            payload = json.loads(text) if text else {}
        except Exception:
            payload = {'raw': text, 'objects': []}
        with self._lock:
            self._state['object_poses'] = {
                'frame_id': str(payload.get('frame_id', '')),
                'objects': payload.get('objects', []),
            }
            self._try_lock_target_locked()
            self._update_locked_target_distance_locked()
            self._touch()

    def update_mission_plan(self, text: str):
        pretty = text
        try:
            payload = json.loads(text) if text else {}
            pretty = json.dumps(payload, ensure_ascii=False, indent=2)
        except Exception:
            pass
        with self._lock:
            self._state['mission_plan'] = {'last': text, 'pretty': pretty}
            self._touch()

    def update_intent(self, msg: Intent):
        with self._lock:
            previous_intent = str(self._state.get('intent', {}).get('intent', ''))
            previous_target_value = str(self._state.get('intent', {}).get('target_value', ''))
            next_intent = str(msg.intent)
            next_target_value = str(msg.target_value)
            self._state['intent'] = {
                'intent': next_intent,
                'target_type': str(msg.target_type),
                'target_value': next_target_value,
                'speed_hint': str(msg.speed_hint),
                'confidence': float(msg.confidence),
            }
            if next_intent == 'cancel':
                self._clear_locked_target_locked('mission canceled')
            elif next_intent == 'approach_object' and (
                previous_intent != 'approach_object' or previous_target_value != next_target_value
            ):
                self._clear_locked_target_locked('target changed')
            self._try_lock_target_locked()
            self._update_locked_target_distance_locked()
            self._recompute_person_pause_locked()
            self._touch()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            if not self._state['server_time']:
                self._state['server_time'] = time.strftime('%Y-%m-%d %H:%M:%S')
            return json.loads(json.dumps(self._state, ensure_ascii=False))

    def append_core_log(self, line: str):
        with self._lock:
            logs = self._state['core_logs']
            logs.append(line)
            self._state['core_logs'] = logs[-40:]
            self._touch()

    def update_actions(self, actions: dict[str, Any]):
        with self._lock:
            self._state['actions'] = actions
            self._touch()

    def update_cmd_vel(self, linear_x: float, angular_z: float):
        with self._lock:
            self._state['cmd_vel'] = {
                'linear_x': float(linear_x),
                'angular_z': float(angular_z),
            }
            self._touch()

    def update_odom(self, linear_x: float, angular_z: float):
        with self._lock:
            self._state['odom'] = {
                'linear_x': float(linear_x),
                'angular_z': float(angular_z),
            }
            self._touch()

    def update_robot_pose(self, available: bool, frame_id: str, x: float, y: float, z: float):
        with self._lock:
            self._state['robot_pose'] = {
                'available': bool(available),
                'frame_id': str(frame_id),
                'x': float(x),
                'y': float(y),
                'z': float(z),
            }
            self._try_lock_target_locked()
            self._update_locked_target_distance_locked()
            self._touch()

    def _clear_locked_target_locked(self, message: str):
        self._state['locked_target'] = {
            'active': False,
            'class_name': '',
            'frame_id': '',
            'x': 0.0,
            'y': 0.0,
            'z': 0.0,
            'confidence': 0.0,
            'distance_m': None,
            'message': message,
        }

    def _try_lock_target_locked(self):
        locked = self._state.get('locked_target', {})
        if locked.get('active'):
            return

        target_class = self._get_current_approach_target_locked()
        object_poses = self._state.get('object_poses', {})
        robot_pose = self._state.get('robot_pose', {})
        object_frame = str(object_poses.get('frame_id', ''))
        robot_frame = str(robot_pose.get('frame_id', ''))
        if not target_class or not robot_pose.get('available') or not object_frame or object_frame != robot_frame:
            return

        rx = float(robot_pose.get('x', 0.0))
        ry = float(robot_pose.get('y', 0.0))
        rz = float(robot_pose.get('z', 0.0))
        candidates = []
        for obj in object_poses.get('objects', []):
            if str(obj.get('class_name', '')) != target_class:
                continue
            dx = float(obj.get('x_m', 0.0)) - rx
            dy = float(obj.get('y_m', 0.0)) - ry
            dz = float(obj.get('z_m', 0.0)) - rz
            distance_m = (dx * dx + dy * dy + dz * dz) ** 0.5
            candidates.append((distance_m, obj))

        if not candidates:
            return

        distance_m, obj = min(candidates, key=lambda item: item[0])
        self._state['locked_target'] = {
            'active': True,
            'class_name': target_class,
            'frame_id': object_frame,
            'x': float(obj.get('x_m', 0.0)),
            'y': float(obj.get('y_m', 0.0)),
            'z': float(obj.get('z_m', 0.0)),
            'confidence': float(obj.get('confidence', 0.0)),
            'distance_m': float(distance_m),
            'message': f'locked {target_class} target',
        }

    def _update_locked_target_distance_locked(self):
        locked = self._state.get('locked_target', {})
        if not locked.get('active'):
            return

        robot_pose = self._state.get('robot_pose', {})
        if not robot_pose.get('available'):
            locked['distance_m'] = None
            locked['message'] = 'robot pose unavailable'
            return

        robot_frame = str(robot_pose.get('frame_id', ''))
        target_frame = str(locked.get('frame_id', ''))
        if not robot_frame or robot_frame != target_frame:
            locked['distance_m'] = None
            locked['message'] = f'frame mismatch: robot={robot_frame or "-"} target={target_frame or "-"}'
            return

        dx = float(locked.get('x', 0.0)) - float(robot_pose.get('x', 0.0))
        dy = float(locked.get('y', 0.0)) - float(robot_pose.get('y', 0.0))
        dz = float(locked.get('z', 0.0)) - float(robot_pose.get('z', 0.0))
        locked['distance_m'] = (dx * dx + dy * dy + dz * dz) ** 0.5
        locked['message'] = f'locked {locked.get("class_name", "")} target'

    def _extract_target_class_from_mission_text_locked(self, text: str) -> str:
        value = str(text).strip()
        lower_value = value.lower()
        prefix = 'approach requested:'
        idx = lower_value.find(prefix)
        if idx < 0:
            return ''
        remainder = value[idx + len(prefix):].strip()
        if not remainder:
            return ''
        if '(' in remainder:
            remainder = remainder.split('(', 1)[0].strip()
        if ':' in remainder:
            remainder = remainder.split(':', 1)[0].strip()
        return remainder

    def _get_current_approach_target_locked(self) -> str:
        mission_text = str(self._state.get('mission_state', {}).get('last', ''))
        target_from_mission = self._extract_target_class_from_mission_text_locked(mission_text)
        if target_from_mission:
            return target_from_mission

        intent = self._state.get('intent', {})
        if str(intent.get('intent', '')) != 'approach_object':
            return ''
        if str(intent.get('target_type', '')) != 'object_class':
            return ''
        return str(intent.get('target_value', ''))

    def _recompute_person_pause_locked(self):
        visible = self._state.get('visible_objects', {}).get('items', [])
        intent = str(self._state.get('intent', {}).get('intent', ''))
        target_type = str(self._state.get('intent', {}).get('target_type', ''))
        target_value = str(self._state.get('intent', {}).get('target_value', ''))
        mission_text = str(self._state.get('mission_state', {}).get('last', ''))

        moving_or_approaching = any(token in mission_text for token in ('navigate requested', 'approach requested'))
        person_visible = 'person' in visible
        person_target = intent == 'approach_object' and target_type == 'object_class' and target_value == 'person'
        active = bool(person_visible and moving_or_approaching and not person_target)
        message = 'person visible during active navigation/approach' if active else 'no person pause condition'
        self._state['person_pause'] = {
            'active': active,
            'message': message,
        }

    def _recompute_execution_locked(self, mission_text: str):
        text = str(mission_text).lower()
        busy = self._state.get('execution', {}).get('busy', False)
        if any(token in text for token in ('requested', 'started')):
            busy = True
        if any(token in text for token in (
            'completed',
            'failed',
            'aborted',
            'canceled',
            'rejected',
            'mission canceled',
            'return_home',
        )):
            busy = False
        self._state['execution'] = {
            'busy': busy,
            'message': 'busy' if busy else 'idle',
        }
class ActionInspector:
    def __init__(self, shared: SharedState):
        self.shared = shared
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.action_names = [
            '/approach_object',
            '/llm_navigate_to_pose',
            '/navigate_to_pose',
            '/scan_scene',
        ]

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=1.0)

    def _run(self):
        while not self.stop_event.is_set():
            snapshot: dict[str, Any] = {}
            for action_name in self.action_names:
                snapshot[action_name] = self._inspect_action(action_name)
            self.shared.update_actions(snapshot)
            self.stop_event.wait(2.0)

    def _inspect_action(self, action_name: str) -> dict[str, Any]:
        try:
            result = subprocess.run(
                ['/bin/bash', '-lc', f'ros2 action info {action_name}'],
                capture_output=True,
                text=True,
                timeout=3.0,
                env=os.environ.copy(),
            )
        except Exception as exc:
            return {'servers': 0, 'clients': 0, 'status': f'error: {exc}'}

        output = (result.stdout or '') + '\n' + (result.stderr or '')
        servers = 0
        clients = 0
        lines = [line.rstrip() for line in output.splitlines() if line.strip()]
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('Action servers:'):
                try:
                    servers = int(stripped.split(':', 1)[1].strip())
                except Exception:
                    servers = 0
            elif stripped.startswith('Action clients:'):
                try:
                    clients = int(stripped.split(':', 1)[1].strip())
                except Exception:
                    clients = 0

        if result.returncode != 0:
            status = 'unavailable'
        elif servers == 0:
            status = 'no server'
        elif servers == 1:
            status = 'ok'
        else:
            status = 'duplicate servers'
        return {'servers': servers, 'clients': clients, 'status': status}


class MonitorNode(Node):
    def __init__(self, shared: SharedState):
        super().__init__('monitor_dashboard_node')
        self.shared = shared
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.user_text_pub = self.create_publisher(String, '/user_text', 10)
        self.intent_pub = self.create_publisher(Intent, '/intent', 10)
        self.create_subscription(String, '/mission_state', self.on_mission_state, 10)
        self.create_subscription(String, '/perception_debug', self.on_perception_debug, 10)
        self.create_subscription(String, '/perception/visible_objects', self.on_visible_objects, 10)
        self.create_subscription(String, '/perception/object_poses', self.on_object_poses, 10)
        self.create_subscription(String, '/mission_plan', self.on_mission_plan, 10)
        self.create_subscription(Bool, '/emergency_stop', self.on_emergency_stop, 10)
        self.create_subscription(Intent, '/intent', self.on_intent, 10)
        self.create_subscription(Log, '/rosout', self.on_rosout, 100)
        self.create_subscription(Twist, '/cmd_vel', self.on_cmd_vel, 20)
        self.create_subscription(Odometry, '/odom', self.on_odom, 20)
        self.create_timer(0.5, self.update_robot_pose_from_tf)

    def on_mission_state(self, msg: String):
        self.shared.update_mission_state(msg.data)

    def on_perception_debug(self, msg: String):
        self.shared.update_perception_debug(msg.data)

    def on_visible_objects(self, msg: String):
        self.shared.update_visible_objects(msg.data)

    def on_object_poses(self, msg: String):
        self.shared.update_object_poses(msg.data)

    def on_mission_plan(self, msg: String):
        self.shared.update_mission_plan(msg.data)

    def on_emergency_stop(self, msg: Bool):
        self.shared.update_emergency_stop(bool(msg.data))

    def on_intent(self, msg: Intent):
        self.shared.update_intent(msg)

    def publish_user_text(self, text: str):
        msg = String()
        msg.data = text
        self.user_text_pub.publish(msg)

    def publish_cancel_intent(self):
        msg = Intent()
        msg.intent = 'cancel'
        msg.target_type = ''
        msg.target_value = ''
        msg.confidence = 1.0
        msg.max_duration_sec = 0
        msg.speed_hint = 'normal'
        msg.object_selector = ''
        msg.approach_distance_m = 0.0
        self.intent_pub.publish(msg)

    def on_rosout(self, msg: Log):
        if msg.name not in {'llm_command_router_node', 'mission_manager_node', 'navigate_to_pose_server', 'approach_object_server'}:
            return
        level_map = {
            Log.DEBUG: 'DEBUG',
            Log.INFO: 'INFO',
            Log.WARN: 'WARN',
            Log.ERROR: 'ERROR',
            Log.FATAL: 'FATAL',
        }
        level = level_map.get(msg.level, str(msg.level))
        line = f'[{msg.name}] [{level}] {msg.msg}'
        self.shared.append_core_log(line)

    def on_cmd_vel(self, msg: Twist):
        self.shared.update_cmd_vel(msg.linear.x, msg.angular.z)

    def on_odom(self, msg: Odometry):
        self.shared.update_odom(msg.twist.twist.linear.x, msg.twist.twist.angular.z)

    def update_robot_pose_from_tf(self):
        try:
            transform = self.tf_buffer.lookup_transform('map', 'base_link', Time())
            translation = transform.transform.translation
            self.shared.update_robot_pose(True, 'map', translation.x, translation.y, translation.z)
        except TransformException:
            self.shared.update_robot_pose(False, '', 0.0, 0.0, 0.0)


def make_handler(shared: SharedState, node: MonitorNode):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == '/':
                body = HTML.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == '/api/state':
                payload = json.dumps(shared.snapshot(), ensure_ascii=False).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            self.send_error(404)

        def do_POST(self):
            parsed = urlparse(self.path)
            length = int(self.headers.get('Content-Length', '0') or 0)
            raw = self.rfile.read(length) if length > 0 else b'{}'
            try:
                payload = json.loads(raw.decode('utf-8') or '{}')
            except Exception:
                payload = {}

            if parsed.path == '/api/command':
                text = str(payload.get('text', '')).strip()
                if not text:
                    return self._send_json(400, {'ok': False, 'message': 'empty command'})
                node.publish_user_text(text)
                return self._send_json(200, {'ok': True, 'message': f'published user_text: {text}'})

            if parsed.path == '/api/cancel':
                node.publish_cancel_intent()
                return self._send_json(200, {'ok': True, 'message': 'published cancel intent'})

            self.send_error(404)

        def log_message(self, fmt: str, *args: Any):
            return

        def _send_json(self, status: int, payload: dict[str, Any]):
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main():
    import argparse

    parser = argparse.ArgumentParser(description='llm_yolo web monitor dashboard')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()

    shared = SharedState()

    rclpy.init()
    node = MonitorNode(shared)
    action_inspector = ActionInspector(shared)
    ros_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    ros_thread.start()
    action_inspector.start()

    server = ThreadingHTTPServer((args.host, args.port), make_handler(shared, node))
    print(f'llm_yolo dashboard listening on http://{args.host}:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        action_inspector.stop()
        node.destroy_node()
        rclpy.shutdown()
        ros_thread.join(timeout=1.0)


if __name__ == '__main__':
    main()
