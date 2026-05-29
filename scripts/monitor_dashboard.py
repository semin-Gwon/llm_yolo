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
  <title>LLM MONITOR</title>
  <style>
    :root {
      --bg: #f6f8fc;
      --bg-accent: #eef4ff;
      --panel: rgba(255, 255, 255, 0.94);
      --panel-strong: #ffffff;
      --line: #e7ebf3;
      --line-strong: #d8dfec;
      --text: #18202f;
      --muted: #74809a;
      --accent: #ff7a18;
      --accent-soft: #fff2e8;
      --ok: #34b85c;
      --ok-soft: #ecfbef;
      --warn: #e5a11b;
      --warn-soft: #fff7df;
      --bad: #d84a4a;
      --bad-soft: #fff0f0;
      --shadow: 0 24px 60px rgba(24, 32, 47, 0.08);
      --mono: "JetBrains Mono", "Fira Code", monospace;
      --sans: "Pretendard", "SUIT", "Noto Sans KR", sans-serif;
      --radius: 24px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at top left, rgba(90, 145, 255, 0.14), transparent 26%),
        radial-gradient(circle at top right, rgba(255, 122, 24, 0.10), transparent 20%),
        linear-gradient(180deg, #ffffff 0%, var(--bg) 100%);
      color: var(--text);
      font-family: var(--sans);
    }
    .app-shell {
      display: grid;
      grid-template-columns: 240px minmax(0, 1fr);
      min-height: 100vh;
    }
    .sidebar {
      padding: 28px 22px 24px;
      border-right: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.78);
      backdrop-filter: blur(18px);
      display: flex;
      flex-direction: column;
      gap: 28px;
    }
    .brand {
      display: grid;
      gap: 6px;
    }
    .brand-title {
      font-size: 24px;
      font-weight: 800;
      letter-spacing: -0.05em;
    }
    .brand-sub {
      color: var(--muted);
      font-size: 14px;
      line-height: 1.5;
    }
    .nav {
      display: grid;
      gap: 8px;
    }
    .nav-item {
      appearance: none;
      width: 100%;
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 14px;
      border-radius: 16px;
      color: #33415c;
      font-size: 15px;
      font-weight: 600;
      background: transparent;
      border: 1px solid transparent;
      cursor: pointer;
      text-align: left;
      transition: 0.18s ease;
    }
    .nav-item.active {
      background: var(--accent-soft);
      color: #b95b14;
      border-color: #ffe0c7;
      box-shadow: inset 0 0 0 1px rgba(255, 122, 24, 0.08);
    }
    .nav-item:hover {
      background: rgba(255, 122, 24, 0.05);
      border-color: rgba(255, 122, 24, 0.12);
    }
    .nav-icon {
      width: 22px;
      text-align: center;
      opacity: 0.9;
    }
    .sidebar-footer {
      margin-top: auto;
      display: grid;
      gap: 14px;
    }
    .system-card {
      background: var(--panel-strong);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 16px 18px;
      box-shadow: 0 12px 28px rgba(24, 32, 47, 0.05);
    }
    .system-label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
    }
    .system-value {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 15px;
      font-weight: 700;
    }
    .shell-main {
      min-width: 0;
    }
    .content {
      max-width: 1500px;
      margin: 0 auto;
      padding: 32px 34px 40px;
    }
    .hero {
      display: flex;
      align-items: start;
      justify-content: space-between;
      gap: 24px;
      margin-bottom: 22px;
    }
    .hero-copy {
      min-width: 0;
    }
    h1 {
      margin: 0;
      font-size: 44px;
      line-height: 1;
      letter-spacing: -0.04em;
    }
    .sub {
      color: var(--muted);
      margin-top: 10px;
      font-size: 16px;
      line-height: 1.6;
    }
    .meta {
      display: grid;
      gap: 12px;
      justify-items: end;
      min-width: 360px;
    }
    .meta-actions {
      display: flex;
      align-items: center;
      gap: 14px;
      justify-content: end;
      width: 100%;
    }
    .meta-time {
      display: grid;
      gap: 8px;
      font-family: var(--mono);
      font-size: 13px;
      color: var(--muted);
      justify-items: end;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 18px;
      grid-auto-flow: row dense;
    }
    .tab-hidden {
      display: none !important;
    }
    .card {
      background: var(--panel);
      border: 1px solid rgba(231, 235, 243, 0.92);
      border-radius: var(--radius);
      padding: 22px 24px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
      min-height: 140px;
    }
    .span-3 { grid-column: span 3; }
    .span-2 { grid-column: span 2; }
    .span-4 { grid-column: span 4; }
    .span-5 { grid-column: span 5; }
    .span-6 { grid-column: span 6; }
    .span-7 { grid-column: span 7; }
    .span-8 { grid-column: span 8; }
    .span-12 { grid-column: span 12; }
    .command-card { min-height: 214px; }
    .metric-card { min-height: 210px; }
    .table-card { min-height: 268px; }
    .log-card { min-height: 230px; }
    .label {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 13px;
      font-weight: 800;
      color: var(--text);
      margin-bottom: 18px;
      letter-spacing: -0.01em;
    }
    .label-icon {
      width: 28px;
      height: 28px;
      border-radius: 10px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background: #f4f7fc;
      color: #52627d;
      font-size: 14px;
      border: 1px solid var(--line);
      flex: 0 0 auto;
    }
    .big {
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.03em;
      line-height: 1.18;
    }
    .status-row {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 7px 11px;
      font-size: 12px;
      font-weight: 700;
      border: 1px solid var(--line-strong);
      background: #fff;
      color: #41506d;
      transition: 0.18s ease;
    }
    .dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--muted);
    }
    .ok {
      background: var(--ok-soft);
      border-color: #cfeeda;
      color: var(--ok);
    }
    .warn {
      background: var(--warn-soft);
      border-color: #f5dd96;
      color: #9a6b0f;
    }
    .bad {
      background: var(--bad-soft);
      border-color: #f2c3c3;
      color: var(--bad);
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
      border-top: 1px solid rgba(231, 235, 243, 0.9);
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
      max-height: 320px;
      overflow: auto;
      padding-right: 4px;
    }
    .scroll-pane {
      max-height: 320px;
      overflow: auto;
      padding-right: 4px;
    }
    .controls {
      display: grid;
      gap: 16px;
    }
    .button-row {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }
    button {
      appearance: none;
      border: 1px solid var(--line-strong);
      background: #fff;
      color: var(--text);
      padding: 12px 16px;
      border-radius: 14px;
      font: inherit;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      box-shadow: 0 10px 20px rgba(24, 32, 47, 0.04);
      transition: 0.18s ease;
    }
    button.primary {
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
      box-shadow: 0 14px 28px rgba(255, 122, 24, 0.28);
    }
    button.active {
      background: var(--ok);
      color: #fff;
      border-color: var(--ok);
    }
    button.running {
      background: var(--ok);
      color: #fff;
      border-color: var(--ok);
      box-shadow: 0 14px 28px rgba(52, 184, 92, 0.24);
    }
    button.warn {
      background: #fff9ef;
      color: #7a4e0f;
    }
    button:hover {
      transform: translateY(-1px);
    }
    button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    input[type="text"] {
      width: 100%;
      border: 1px solid var(--line-strong);
      border-radius: 16px;
      padding: 14px 16px;
      font: inherit;
      font-size: 14px;
      background: #fff;
      color: var(--text);
      box-shadow: inset 0 1px 2px rgba(24, 32, 47, 0.03);
    }
    .inline-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }
    .hero-input {
      font-size: 17px !important;
      padding: 17px 18px !important;
    }
    .section-note {
      color: var(--muted);
      font-size: 12px;
      margin-top: 8px;
      letter-spacing: 0.02em;
    }
    .mission-copy {
      margin-top: 18px;
      min-height: 76px;
    }
    .metric-copy {
      margin-top: 10px;
      display: grid;
      gap: 8px;
    }
    .feedback {
      min-height: 20px;
    }
    .sidebar-note {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }
    @media (max-width: 1100px) {
      .app-shell {
        grid-template-columns: 1fr;
      }
      .sidebar {
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }
      .content {
        padding: 22px 18px 28px;
      }
      .hero {
        align-items: start;
        flex-direction: column;
      }
      .meta {
        justify-items: start;
        min-width: 0;
        width: 100%;
      }
      .meta-actions, .meta-time {
        justify-content: start;
        justify-items: start;
      }
      .span-2, .span-3, .span-4, .span-5, .span-6, .span-7, .span-8 { grid-column: span 12; }
    }
  </style>
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-title">LLM MONITOR</div>
        <div class="brand-sub">ROS Topic 모니터링 대시보드</div>
      </div>

      <nav class="nav">
        <button type="button" class="nav-item dashboardTabBtn active" data-tab="dashboard"><span class="nav-icon">⌂</span><span>Dashboard</span></button>
        <button type="button" class="nav-item dashboardTabBtn" data-tab="command"><span class="nav-icon">⌨</span><span>Command Console</span></button>
        <button type="button" class="nav-item dashboardTabBtn" data-tab="topics"><span class="nav-icon">☷</span><span>Topics</span></button>
        <button type="button" class="nav-item dashboardTabBtn" data-tab="logs"><span class="nav-icon">☰</span><span>Logs</span></button>
        <button type="button" class="nav-item dashboardTabBtn" data-tab="settings"><span class="nav-icon">⚙</span><span>Settings</span></button>
      </nav>

      <div class="sidebar-footer">
        <div class="system-card">
          <div class="system-label">System Status</div>
          <div class="system-value"><span class="dot" style="background: var(--ok)"></span><span>All Systems Operational</span></div>
        </div>
        <div class="sidebar-note">© 2026 LLM Monitor</div>
      </div>
    </aside>

    <main class="shell-main">
      <div class="content">
        <div class="hero">
          <div class="hero-copy">
            <h1 id="pageTitle">Dashboard</h1>
            <div id="monitorSubtitle" class="sub">ROS topic 상태 및 AI 미션 모니터링</div>
            <div id="monitorTitle" style="display:none;">LLM MONITOR</div>
          </div>
          <div class="meta">
            <div class="meta-actions">
              <button id="openRvizBtn">🖥 Open RViz</button>
              <div class="status-row">
                <div id="modeAutoPill" class="pill"><span class="dot"></span><span>AUTO</span></div>
                <div id="modeSimPill" class="pill"><span class="dot"></span><span>SIM</span></div>
                <div id="modeRealPill" class="pill"><span class="dot"></span><span>REAL</span></div>
              </div>
            </div>
            <div class="meta-time">
              <div id="serverTime">Server Time&nbsp;&nbsp;&nbsp;&nbsp; -</div>
              <div id="lastUpdate">Last Update&nbsp;&nbsp; -</div>
            </div>
          </div>
        </div>

        <div class="grid">
      <section class="card span-12 command-card dashboardCard" data-tabs="dashboard command">
        <div class="label"><span class="label-icon">⌲</span><span>Command Console</span></div>
        <div class="controls">
          <input id="userTextInput" class="hero-input" type="text" placeholder="예: chair 앞으로 가" />
          <div class="button-row">
            <button id="sendUserTextBtn" class="primary">✈ Send Command</button>
            <button id="cancelMissionBtn" class="warn">✕ Cancel Mission</button>
            <button class="quickCmd" data-command="center 로 가">center 로 가</button>
            <button class="quickCmd" data-command="chair 찾아">chair 찾아</button>
            <button class="quickCmd" data-command="chair 앞으로 가">chair 앞으로 가</button>
            <button class="quickCmd" data-command="긴급 정지">긴급 정지</button>
            <button class="quickCmd" data-command="정지 해제">정지 해제</button>
          </div>
          <div id="commandFeedback" class="mono muted feedback">-</div>
        </div>
      </section>

      <section class="card span-4 metric-card dashboardCard" data-tabs="dashboard command">
        <div class="label"><span class="label-icon">⚑</span><span>Mission Status</span></div>
        <div class="status-row">
          <div id="missionPill" class="pill warn"><span class="dot"></span><span id="missionStatus">unknown</span></div>
          <div id="executionPill" class="pill warn"><span class="dot"></span><span id="executionStatus">idle</span></div>
        </div>
        <div id="missionText" class="big mission-copy">-</div>
      </section>

      <section class="card span-4 metric-card dashboardCard" data-tabs="dashboard command">
        <div class="label"><span class="label-icon">◎</span><span>Target Distance</span></div>
        <div id="targetDistanceValue" class="big">-</div>
        <div class="metric-copy">
          <div id="targetDistanceMeta" class="sub">-</div>
        </div>
        <div id="targetDistanceHint" class="section-note">-</div>
      </section>

      <section class="card span-4 metric-card dashboardCard" data-tabs="dashboard command settings">
        <div class="label"><span class="label-icon">🛡</span><span>Safety Status</span></div>
        <div class="status-row">
          <div id="emergencyPill" class="pill ok"><span class="dot"></span><span id="emergencyStatus">clear</span></div>
        </div>
        <div id="emergencyText" class="big" style="margin-top:14px;">clear</div>
        <div class="status-row" style="margin-top:14px;">
          <div id="personPausePill" class="pill ok"><span class="dot"></span><span id="personPauseStatus">person clear</span></div>
        </div>
        <div id="personPauseText" class="sub" style="margin-top:10px;">-</div>
      </section>

      <section class="card span-4 table-card dashboardCard" data-tabs="dashboard">
        <div class="label"><span class="label-icon">⬡</span><span>Detected Objects</span></div>
        <div id="visibleObjects" class="big">-</div>
        <div class="inline-meta">
          <div id="poseCount" class="pill"><span class="dot"></span><span>poses: 0</span></div>
        </div>
      </section>

      <section class="card span-8 table-card dashboardCard" data-tabs="dashboard">
        <div class="label"><span class="label-icon">⌘</span><span>Object Poses (Live)</span></div>
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

      <section class="card span-4 log-card dashboardCard" data-tabs="dashboard logs">
        <div class="label"><span class="label-icon">🛡</span><span>Perception Debug</span></div>
        <div id="perceptionDebug" class="mono">-</div>
      </section>

      <section class="card span-4 log-card dashboardCard" data-tabs="dashboard logs">
        <div class="label"><span class="label-icon">◎</span><span>Approach Control</span></div>
        <div id="approachDebug" class="mono">-</div>
      </section>

      <section class="card span-4 log-card dashboardCard" data-tabs="dashboard logs settings">
        <div class="label"><span class="label-icon">✎</span><span>Mission Plan</span></div>
        <div id="missionPlan" class="mono">-</div>
      </section>

      <section class="card span-4 log-card dashboardCard" data-tabs="dashboard settings">
        <div class="label"><span class="label-icon">⚙</span><span>Action Health</span></div>
        <table>
          <thead>
            <tr><th>Action</th><th>Servers</th><th>Clients</th><th>Status</th></tr>
          </thead>
          <tbody id="actionHealthBody">
            <tr><td colspan="4" class="muted">no data</td></tr>
          </tbody>
        </table>
      </section>

      <section class="card span-6 log-card dashboardCard" data-tabs="topics">
        <div class="label"><span class="label-icon">☷</span><span>ROS Topic List</span></div>
        <div id="topicList" class="mono scroll-pane muted">-</div>
      </section>

      <section class="card span-6 log-card dashboardCard" data-tabs="topics">
        <div class="label"><span class="label-icon">⌘</span><span>ROS Node List</span></div>
        <div id="nodeList" class="mono scroll-pane muted">-</div>
      </section>

      <section class="card span-12 log-card dashboardCard" data-tabs="dashboard logs">
        <div class="label"><span class="label-icon">☰</span><span>Core Logs</span></div>
        <div id="coreLogs" class="history mono muted">-</div>
      </section>
        </div>
      </div>
    </main>
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

    function setActiveTab(tabName) {
      const titles = {
        dashboard: "Dashboard",
        command: "Command Console",
        topics: "Topics",
        logs: "Logs",
        settings: "Settings",
      };
      document.querySelectorAll(".dashboardTabBtn").forEach((button) => {
        button.classList.toggle("active", button.dataset.tab === tabName);
      });
      document.querySelectorAll(".dashboardCard").forEach((card) => {
        const allowedTabs = String(card.dataset.tabs || "").split(/\s+/).filter(Boolean);
        card.classList.toggle("tab-hidden", !allowedTabs.includes(tabName));
      });
      const pageTitle = document.getElementById("pageTitle");
      if (pageTitle) pageTitle.textContent = titles[tabName] || "Dashboard";
      try {
        window.localStorage.setItem("llm_monitor_tab", tabName);
      } catch (_) {}
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

        const monitor = state.monitor || {};
        const effectiveMode = monitor.selected_mode || monitor.mode || "auto";
        const titleByMode = {
          auto: "LLM MONITOR",
          sim: "SIM MONITOR",
          real: "REAL MONITOR",
        };
        const subtitleByMode = {
          auto: "ROS topic 상태를 백그라운드 구독해서 1초 주기로 갱신합니다.",
          sim: "sim 토픽과 TF 기준으로 상태를 갱신합니다.",
          real: "real 토픽과 camera_link 기준 pose를 포함해 상태를 갱신합니다.",
        };
        document.getElementById("monitorTitle").textContent = titleByMode[effectiveMode] || "LLM MONITOR";
        document.getElementById("monitorSubtitle").textContent =
          subtitleByMode[effectiveMode] || subtitleByMode.auto;

        setStatusPill(document.getElementById("modeAutoPill"), effectiveMode === "auto" ? "ok" : "warn", "AUTO");
        setStatusPill(document.getElementById("modeSimPill"), effectiveMode === "sim" ? "ok" : "warn", "SIM");
        setStatusPill(document.getElementById("modeRealPill"), effectiveMode === "real" ? "ok" : "warn", "REAL");

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
        const emergencyLabel = emergencyActive ? "EMERGENCY STOP ACTIVE" : "EMERGENCY CLEARED";
        const emergencyPillLabel = emergencyActive ? "stop active" : "stop cleared";
        setStatusPill(
          document.getElementById("emergencyPill"),
          emergencyActive ? "bad" : "ok",
          emergencyPillLabel
        );
        document.getElementById("emergencyText").textContent = emergencyLabel;

        const personPause = state.person_pause || {};
        setStatusPill(
          document.getElementById("personPausePill"),
          personPause.active ? "warn" : "ok",
          personPause.active ? "person pause active" : "person path clear"
        );
        document.getElementById("personPauseText").textContent = personPause.message || "-";

        const objects = state.visible_objects.items || [];
        document.getElementById("visibleObjects").textContent = objects.length ? objects.join(", ") : "-";

        const robotPose = state.robot_pose || {};
        const objectPoseState = state.object_poses || {};
        const lockedTarget = state.locked_target || {};
        const intent = state.intent || {};
        const poseObjects = computeObjectDistances(objectPoseState.objects || [], robotPose, objectPoseState.frame_id || "");
        document.getElementById("poseCount").textContent = `poses: ${poseObjects.length}`;
        updatePoseTable(poseObjects, lockedTarget);

        document.getElementById("perceptionDebug").textContent = state.perception_debug.last || "-";
        const approachDebug = state.approach_debug || {};
        document.getElementById("approachDebug").textContent = approachDebug.pretty || approachDebug.last || "-";
        document.getElementById("missionPlan").textContent = state.mission_plan.pretty || state.mission_plan.last || "-";
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
        document.getElementById("targetDistanceHint").textContent =
          robotPose.available
            ? `robot pose source: ${robotPose.frame_id || "-"}`
            : (state.object_poses.frame_id === "camera_link"
                ? "camera_link 기준 상대 pose만 수신 중"
                : "robot pose unavailable");
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

        const topicItems = ((state.topic_list || {}).items || []);
        const nodeItems = ((state.node_list || {}).items || []);
        document.getElementById("topicList").innerHTML = topicItems.length
          ? topicItems.map((line) => escapeHtml(line)).join("<br>")
          : "-";
        document.getElementById("nodeList").innerHTML = nodeItems.length
          ? nodeItems.map((line) => escapeHtml(line)).join("<br>")
          : "-";

        const rviz = state.rviz || {};
        const rvizButton = document.getElementById("openRvizBtn");
        if (rvizButton) {
          rvizButton.classList.toggle("running", Boolean(rviz.running));
          rvizButton.textContent = rviz.running ? "🖥 RViz Running" : "🖥 Open RViz";
          rvizButton.disabled = Boolean(rviz.running);
        }

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

    document.getElementById("openRvizBtn").addEventListener("click", async () => {
      const button = document.getElementById("openRvizBtn");
      try {
        button.disabled = true;
        button.textContent = "🖥 Starting RViz";
        await postJson("/api/open_rviz", {});
        refresh();
      } catch (err) {
        button.classList.remove("running");
        button.disabled = false;
        button.textContent = "RViz Failed";
        window.setTimeout(() => {
          button.textContent = "🖥 Open RViz";
        }, 3000);
      }
    });

    document.getElementById("modeAutoPill").addEventListener("click", async () => {
      await postJson("/api/mode", { mode: "auto" });
      refresh();
    });
    document.getElementById("modeSimPill").addEventListener("click", async () => {
      await postJson("/api/mode", { mode: "sim" });
      refresh();
    });
    document.getElementById("modeRealPill").addEventListener("click", async () => {
      await postJson("/api/mode", { mode: "real" });
      refresh();
    });

    document.querySelectorAll(".dashboardTabBtn").forEach((button) => {
      button.addEventListener("click", () => {
        setActiveTab(button.dataset.tab || "dashboard");
      });
    });

    const savedTab = (() => {
      try {
        return window.localStorage.getItem("llm_monitor_tab") || "dashboard";
      } catch (_) {
        return "dashboard";
      }
    })();
    setActiveTab(savedTab);

    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>
"""


class SharedState:
    def __init__(self, initial_mode: str = 'auto'):
        self._lock = threading.Lock()
        mode = initial_mode if initial_mode in {'auto', 'sim', 'real'} else 'auto'
        self._perception_hold_sec = 3.0
        self._state: dict[str, Any] = {
            'monitor': {
                'mode': mode,
                'selected_mode': mode,
            },
            'server_time': '',
            'last_update': '',
            'mission_state': {'last': '', 'history': []},
            'perception_debug': {'last': ''},
            'approach_debug': {'last': '', 'pretty': ''},
            'object_poses': {'frame_id': '', 'objects': [], 'raw': '', 'last_nonempty_time': 0.0},
            'visible_objects': {'raw': '', 'items': [], 'last_nonempty_time': 0.0},
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
            'topic_list': {
                'items': [],
            },
            'node_list': {
                'items': [],
            },
            'rviz': {
                'running': False,
                'pid': None,
                'message': 'not started',
            },
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

    def update_approach_debug(self, text: str):
        pretty = text
        try:
            payload = json.loads(text) if text else {}
            display = {
                'source': payload.get('control_source', '-'),
                'distance_m': round(float(payload['distance_m']), 3) if 'distance_m' in payload else None,
                'error_m': round(float(payload['distance_error_m']), 3) if 'distance_error_m' in payload else None,
                'stop_at_m': round(float(payload['approach_distance_m']), 3) if 'approach_distance_m' in payload else None,
                'target_x_m': round(float(payload['target_x_m']), 3) if 'target_x_m' in payload else None,
                'target_y_m': round(float(payload['target_y_m']), 3) if 'target_y_m' in payload else None,
                'heading_rad': round(float(payload['heading_rad']), 3) if 'heading_rad' in payload else None,
                'cmd_linear': round(float(payload['commanded_linear_mps']), 3) if 'commanded_linear_mps' in payload else None,
                'cmd_yaw': round(float(payload['commanded_yaw_radps']), 3) if 'commanded_yaw_radps' in payload else None,
                'odom_ok': bool(payload.get('odom_available', False)),
                'odom_target': bool(payload.get('odom_target_active', False)),
                'outcome': payload.get('outcome', ''),
            }
            pretty = '\n'.join(f'{key}: {value}' for key, value in display.items() if value not in (None, ''))
        except Exception:
            pass
        with self._lock:
            self._state['approach_debug'] = {'last': text, 'pretty': pretty}
            self._touch()

    def update_visible_objects(self, text: str):
        items: list[str] = []
        try:
            payload = json.loads(text) if text else {}
        except Exception:
            payload = None

        if isinstance(payload, dict):
            raw_objects = payload.get('objects', [])
            if isinstance(raw_objects, list):
                for item in raw_objects:
                    if isinstance(item, dict):
                        label = str(item.get('class_name', '')).strip()
                        if label:
                            items.append(label)
                    else:
                        label = str(item).strip()
                        if label:
                            items.append(label)
        elif isinstance(payload, list):
            items = [str(item).strip() for item in payload if str(item).strip()]

        if not items:
            normalized = text.replace('\n', ',')
            items = [item.strip() for item in normalized.split(',') if item.strip()]

        with self._lock:
            previous = self._state.get('visible_objects', {})
            last_nonempty_time = float(previous.get('last_nonempty_time', 0.0) or 0.0)
            now = time.time()
            if items:
                last_nonempty_time = now
            elif previous.get('items') and (now - last_nonempty_time) <= self._perception_hold_sec:
                items = list(previous.get('items', []))

            self._state['visible_objects'] = {
                'raw': text,
                'items': items,
                'last_nonempty_time': last_nonempty_time,
            }
            self._recompute_person_pause_locked()
            self._touch()

    def update_emergency_stop(self, active: bool):
        with self._lock:
            self._state['emergency_stop'] = {
                'active': bool(active),
                'last': 'engaged' if active else 'clear',
            }
            self._touch()

    def update_emergency_clear(self, active: bool):
        if not active:
            return
        self.update_emergency_stop(False)

    def update_object_poses(self, text: str):
        payload: dict[str, Any]
        try:
            payload = json.loads(text) if text else {}
        except Exception:
            payload = {'raw': text, 'objects': []}
        raw_objects = payload.get('objects', [])
        objects = raw_objects if isinstance(raw_objects, list) else []
        frame_id = str(payload.get('frame_id', ''))
        with self._lock:
            previous = self._state.get('object_poses', {})
            last_nonempty_time = float(previous.get('last_nonempty_time', 0.0) or 0.0)
            now = time.time()
            if objects:
                last_nonempty_time = now
            elif previous.get('objects') and (now - last_nonempty_time) <= self._perception_hold_sec:
                objects = list(previous.get('objects', []))
                if not frame_id:
                    frame_id = str(previous.get('frame_id', ''))

            self._state['object_poses'] = {
                'frame_id': frame_id,
                'objects': objects,
                'raw': text,
                'last_nonempty_time': last_nonempty_time,
            }
            self._apply_real_pose_fallback_locked(frame_id)
            self._try_lock_target_locked()
            self._update_locked_target_distance_locked()
            self._touch()

    def update_monitor_mode(self, mode: str):
        normalized = str(mode).strip().lower()
        if normalized not in {'auto', 'sim', 'real'}:
            return
        with self._lock:
            self._state['monitor']['selected_mode'] = normalized
            self._apply_real_pose_fallback_locked(
                str(self._state.get('object_poses', {}).get('frame_id', ''))
            )
            self._try_lock_target_locked()
            self._update_locked_target_distance_locked()
            self._touch()

    def _effective_mode_locked(self) -> str:
        return str(self._state.get('monitor', {}).get('selected_mode', 'auto')).strip().lower() or 'auto'

    def _apply_real_pose_fallback_locked(self, object_frame: str):
        effective_mode = self._effective_mode_locked()
        robot_pose = self._state.get('robot_pose', {})
        if effective_mode not in {'auto', 'real'}:
            return
        if robot_pose.get('available'):
            return
        if object_frame != 'camera_link':
            return
        self._state['robot_pose'] = {
            'available': True,
            'frame_id': 'camera_link',
            'x': 0.0,
            'y': 0.0,
            'z': 0.0,
        }

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

    def update_topic_list(self, items: list[str]):
        with self._lock:
            self._state['topic_list'] = {'items': list(items)}
            self._touch()

    def update_node_list(self, items: list[str]):
        with self._lock:
            self._state['node_list'] = {'items': list(items)}
            self._touch()

    def update_rviz(self, running: bool, pid: int | None = None, message: str = ''):
        with self._lock:
            self._state['rviz'] = {
                'running': bool(running),
                'pid': int(pid) if pid is not None else None,
                'message': message or ('running' if running else 'not running'),
            }
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
            if not available:
                self._apply_real_pose_fallback_locked(
                    str(self._state.get('object_poses', {}).get('frame_id', ''))
                )
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


class RosGraphInspector:
    def __init__(self, shared: SharedState):
        self.shared = shared
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=1.0)

    def _run(self):
        while not self.stop_event.is_set():
            self.shared.update_topic_list(self._collect_list('ros2 topic list'))
            self.shared.update_node_list(self._collect_list('ros2 node list'))
            self.stop_event.wait(3.0)

    def _collect_list(self, command: str) -> list[str]:
        try:
            result = subprocess.run(
                ['/bin/bash', '-lc', command],
                capture_output=True,
                text=True,
                timeout=4.0,
                env=os.environ.copy(),
            )
        except Exception as exc:
            return [f'error: {exc}']

        output = (result.stdout or '').strip()
        if result.returncode != 0:
            stderr = (result.stderr or '').strip()
            return [line for line in [output, stderr] if line] or ['unavailable']
        return [line for line in output.splitlines() if line.strip()]


class MonitorNode(Node):
    def __init__(self, shared: SharedState, monitor_mode: str = 'auto'):
        super().__init__('monitor_dashboard_node')
        self.shared = shared
        self.monitor_mode = monitor_mode if monitor_mode in {'auto', 'sim', 'real'} else 'auto'
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.user_text_pub = self.create_publisher(String, '/user_text', 10)
        self.intent_pub = self.create_publisher(Intent, '/intent', 10)
        self.create_subscription(String, '/mission_state', self.on_mission_state, 10)
        self.create_subscription(String, '/perception_debug', self.on_perception_debug, 10)
        self.create_subscription(String, '/approach_object/debug', self.on_approach_debug, 10)
        self.create_subscription(String, '/perception/visible_objects', self.on_visible_objects, 10)
        self.create_subscription(String, '/perception/object_poses', self.on_object_poses, 10)
        self.create_subscription(String, '/mission_plan', self.on_mission_plan, 10)
        self.create_subscription(Bool, '/emergency_stop', self.on_emergency_stop, 10)
        self.create_subscription(Bool, '/emergency_clear', self.on_emergency_clear, 10)
        self.create_subscription(Intent, '/intent', self.on_intent, 10)
        self.create_subscription(Log, '/rosout', self.on_rosout, 100)
        self.create_subscription(Twist, '/cmd_vel', self.on_cmd_vel, 20)
        self.create_subscription(Odometry, '/odom', self.on_odom, 20)
        self.create_timer(0.5, self.update_robot_pose_from_tf)
        self.rviz_process: subprocess.Popen | None = None
        self.create_timer(1.0, self.update_rviz_status)

    def on_mission_state(self, msg: String):
        self.shared.update_mission_state(msg.data)

    def on_perception_debug(self, msg: String):
        self.shared.update_perception_debug(msg.data)

    def on_approach_debug(self, msg: String):
        self.shared.update_approach_debug(msg.data)

    def on_visible_objects(self, msg: String):
        self.shared.update_visible_objects(msg.data)

    def on_object_poses(self, msg: String):
        self.shared.update_object_poses(msg.data)

    def on_mission_plan(self, msg: String):
        self.shared.update_mission_plan(msg.data)

    def on_emergency_stop(self, msg: Bool):
        self.shared.update_emergency_stop(bool(msg.data))

    def on_emergency_clear(self, msg: Bool):
        self.shared.update_emergency_clear(bool(msg.data))

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

    def launch_rviz(self):
        self.update_rviz_status()
        if self.rviz_process is not None and self.rviz_process.poll() is None:
            self.shared.update_rviz(True, self.rviz_process.pid, 'already running')
            return
        env = os.environ.copy()
        env.setdefault('DISPLAY', os.environ.get('DISPLAY', ':0'))
        config_path = '/home/jnu/llm_yolo/rviz/real_perception.rviz'
        self.rviz_process = subprocess.Popen(
            ['rviz2', '-d', config_path],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.shared.update_rviz(True, self.rviz_process.pid, 'running')

    def update_rviz_status(self):
        if self.rviz_process is None:
            self.shared.update_rviz(False, None, 'not started')
            return
        returncode = self.rviz_process.poll()
        if returncode is None:
            self.shared.update_rviz(True, self.rviz_process.pid, 'running')
            return
        self.shared.update_rviz(False, None, f'exited: {returncode}')
        self.rviz_process = None

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
        frame_candidates: list[tuple[str, str]] = []
        if self.monitor_mode in {'auto', 'sim'}:
            frame_candidates.extend([
                ('map', 'base_link'),
                ('odom', 'base_link'),
            ])
        if self.monitor_mode in {'auto', 'real'}:
            frame_candidates.extend([
                ('odom', 'base_link'),
                ('odom', 'camera_link'),
            ])

        for target_frame, source_frame in frame_candidates:
            try:
                transform = self.tf_buffer.lookup_transform(target_frame, source_frame, Time())
                translation = transform.transform.translation
                self.shared.update_robot_pose(True, target_frame, translation.x, translation.y, translation.z)
                return
            except TransformException:
                continue
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

            if parsed.path == '/api/open_rviz':
                try:
                    node.launch_rviz()
                except Exception as exc:
                    return self._send_json(500, {'ok': False, 'message': f'failed to launch rviz: {exc}'})
                return self._send_json(200, {'ok': True, 'message': 'launched rviz2'})

            if parsed.path == '/api/mode':
                mode = str(payload.get('mode', '')).strip().lower()
                if mode not in {'auto', 'sim', 'real'}:
                    return self._send_json(400, {'ok': False, 'message': f'invalid mode: {mode}'})
                shared.update_monitor_mode(mode)
                return self._send_json(200, {'ok': True, 'message': f'monitor mode set: {mode}'})

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
    parser.add_argument('--mode', choices=['auto', 'sim', 'real'], default='auto')
    args = parser.parse_args()

    shared = SharedState(initial_mode=args.mode)

    rclpy.init()
    node = MonitorNode(shared, monitor_mode=args.mode)
    action_inspector = ActionInspector(shared)
    ros_graph_inspector = RosGraphInspector(shared)
    ros_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    ros_thread.start()
    action_inspector.start()
    ros_graph_inspector.start()

    server = ThreadingHTTPServer((args.host, args.port), make_handler(shared, node))
    print(f'llm_yolo dashboard listening on http://{args.host}:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        action_inspector.stop()
        ros_graph_inspector.stop()
        node.destroy_node()
        rclpy.shutdown()
        ros_thread.join(timeout=1.0)


if __name__ == '__main__':
    main()
