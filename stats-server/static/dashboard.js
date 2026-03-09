(function () {
  "use strict";

  const Role = Object.freeze({
    STREAMER: "STREAMER",
    VIEWER: "VIEWER",
    SPECTATOR: "SPECTATOR",
  });

  const ROLE_BADGE_CLASSES = Object.freeze({
    [Role.STREAMER]: "badge-streamer",
    [Role.VIEWER]: "badge-viewer",
    [Role.SPECTATOR]: "badge-spectator",
  });

  const ROLE_SORT_ORDER = Object.freeze({
    [Role.STREAMER]: 0,
    [Role.VIEWER]: 1,
    [Role.SPECTATOR]: 2,
  });

  const PORT_TYPE_SORT_ORDER = Object.freeze({
    "CONTROL": 0,
    "VIDEO": 1,
  });

  let timerId = null;

  const autoRefreshCheckbox = document.getElementById("auto-refresh");
  const intervalSelect = document.getElementById("refresh-interval");
  const refreshNowButton = document.getElementById("refresh-now");
  const lastUpdatedElement = document.getElementById("last-updated");
  const pulseElement = document.getElementById("pulse");
  const summaryBody = document.getElementById("summary-body");
  const sessionsBody = document.getElementById("sessions-body");

  function getIntervalMilliseconds() {
    return parseInt(intervalSelect.value, 10) * 1000;
  }

  function formatRelativeTime(unixTimestamp) {
    const difference = Math.floor(Date.now() / 1000 - unixTimestamp);
    if (difference < 60) {
      return difference + "s ago";
    }
    if (difference < 3600) {
      return Math.floor(difference / 60) + "m ago";
    }
    if (difference < 86400) {
      return Math.floor(difference / 3600) + "h ago";
    }
    return Math.floor(difference / 86400) + "d ago";
  }

  function formatTimeout(seconds) {
    var minutes = Math.floor(seconds / 60);
    var remaining = seconds % 60;
    return String(minutes).padStart(2, "0") + ":" + String(remaining).padStart(2, "0");
  }

  function timeoutClass(seconds) {
    if (seconds > 300) {
      return "timeout-high";
    }
    if (seconds > 100) {
      return "timeout-mid";
    }
    return "timeout-low";
  }

  function roleBadgeClass(role) {
    return ROLE_BADGE_CLASSES[role] || ROLE_BADGE_CLASSES[Role.SPECTATOR];
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function formatAddress(address) {
    const lastColon = address.lastIndexOf(":");
    if (lastColon === -1) {
      return escapeHtml(address);
    }
    const ip = address.substring(0, lastColon);
    const port = address.substring(lastColon);
    return '<a href="https://ipinfo.io/' + encodeURIComponent(ip) + '" target="_blank" rel="noopener">' +
      escapeHtml(ip) + "</a>" + escapeHtml(port);
  }

  function renderSummary(relays) {
    const ports = Object.keys(relays).sort();
    for (const port of ports) {
      const row = document.getElementById("summary-" + port);
      if (!row) {
        continue;
      }

      const data = relays[port];
      const cells = row.querySelectorAll("td");

      if (data.status === "error") {
        cells[1].innerHTML = '<span class="badge bg-danger">offline</span>';
        cells[2].textContent = escapeHtml(data.error || "Connection failed");
      } else {
        const sessionCount = Object.keys(data.sessions || {}).length;
        cells[1].innerHTML = '<span class="badge bg-success">online</span>';
        cells[2].textContent = sessionCount + " session" + (sessionCount !== 1 ? "s" : "");
      }
    }
  }

  function groupEntries(entries) {
    var result = [];
    var index = 0;
    while (index < entries.length) {
      var groupKey = entries[index].role + ":" + (entries[index].spectator_index !== undefined ? entries[index].spectator_index : "");
      var size = 1;
      while (index + size < entries.length) {
        var nextKey = entries[index + size].role + ":" + (entries[index + size].spectator_index !== undefined ? entries[index + size].spectator_index : "");
        if (nextKey !== groupKey) {
          break;
        }
        size++;
      }
      for (var i = 0; i < size; i++) {
        result.push({isFirst: i === 0, size: size});
      }
      index += size;
    }
    return result;
  }

  function renderSessions(relays) {
    const ports = Object.keys(relays).sort();
    let html = "";

    for (const port of ports) {
      const data = relays[port];

      if (data.status === "error") {
        continue;
      }

      const sessions = data.sessions || {};
      const sessionIds = Object.keys(sessions);

      for (const sessionId of sessionIds) {
        const session = sessions[sessionId];
        const entries = (session.mappings || []).concat(session.spectators || []);

        if (entries.length === 0) {
          html +=
            "<tr>" +
            "<td><code>" + escapeHtml(port) + "</code></td>" +
            "<td><code>" + escapeHtml(sessionId) + "</code></td>" +
            "<td>" + escapeHtml(formatRelativeTime(session.created_at)) + "</td>" +
            '<td colspan="5" class="text-muted">No active mappings</td>' +
            "</tr>";
          continue;
        }

        entries.sort(function (a, b) {
          const orderA = ROLE_SORT_ORDER[a.role] !== undefined ? ROLE_SORT_ORDER[a.role] : 99;
          const orderB = ROLE_SORT_ORDER[b.role] !== undefined ? ROLE_SORT_ORDER[b.role] : 99;
          if (orderA !== orderB) {
            return orderA - orderB;
          }
          const indexA = a.spectator_index !== undefined ? a.spectator_index : -1;
          const indexB = b.spectator_index !== undefined ? b.spectator_index : -1;
          if (indexA !== indexB) {
            return indexA - indexB;
          }
          const ptA = PORT_TYPE_SORT_ORDER[a.port_type] !== undefined ? PORT_TYPE_SORT_ORDER[a.port_type] : 99;
          const ptB = PORT_TYPE_SORT_ORDER[b.port_type] !== undefined ? PORT_TYPE_SORT_ORDER[b.port_type] : 99;
          return ptA - ptB;
        });

        var groups = groupEntries(entries);

        for (let index = 0; index < entries.length; index++) {
          const entry = entries[index];
          const group = groups[index];
          html += "<tr>";

          if (index === 0) {
            html +=
              '<td rowspan="' + entries.length + '"><code>' + escapeHtml(port) + "</code></td>" +
              '<td rowspan="' + entries.length + '"><code>' +
              escapeHtml(sessionId) +
              "</code></td>";
          }

          if (index === 0) {
            html +=
              '<td rowspan="' + entries.length + '">' +
              escapeHtml(formatRelativeTime(session.created_at)) +
              "</td>";
          }

          html +=
            '<td><span class="badge ' + roleBadgeClass(entry.role) + '">' +
            escapeHtml(entry.role) +
            "</span></td>" +
            "<td>" + escapeHtml(entry.port_type) + "</td>" +
            "<td><code>" + formatAddress(entry.address) + "</code></td>" +
            "<td>" + escapeHtml((entry.transport || "udp").toUpperCase()) + "</td>" +
            '<td class="' + timeoutClass(entry.timeout_in_sec) + '">' +
            formatTimeout(entry.timeout_in_sec) + "</td>";

          html += "</tr>";
        }
      }
    }

    if (!html) {
      html = '<tr><td colspan="8" class="text-center text-muted">No active sessions</td></tr>';
    }

    sessionsBody.innerHTML = html;
  }

  function fetchStats() {
    fetch("/api/stats")
      .then(function (response) {
        if (response.status === 401 || response.redirected) {
          window.location.href = "/login";
          return null;
        }
        return response.json();
      })
      .then(function (data) {
        if (!data) {
          return;
        }

        const relays = data.relays || {};
        renderSummary(relays);
        renderSessions(relays);

        lastUpdatedElement.textContent = "Updated " + new Date().toLocaleTimeString();
      })
      .catch(function (error) {
        lastUpdatedElement.textContent = "Update failed: " + error.message;
      });
  }

  function startAutoRefresh() {
    stopAutoRefresh();
    if (autoRefreshCheckbox.checked) {
      timerId = setInterval(fetchStats, getIntervalMilliseconds());
      pulseElement.style.display = "";
    }
  }

  function stopAutoRefresh() {
    if (timerId !== null) {
      clearInterval(timerId);
      timerId = null;
    }
    pulseElement.style.display = "none";
  }

  autoRefreshCheckbox.addEventListener("change", function () {
    if (this.checked) {
      startAutoRefresh();
    } else {
      stopAutoRefresh();
    }
  });

  intervalSelect.addEventListener("change", function () {
    if (autoRefreshCheckbox.checked) {
      startAutoRefresh();
    }
  });

  refreshNowButton.addEventListener("click", fetchStats);

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) {
      stopAutoRefresh();
    } else if (autoRefreshCheckbox.checked) {
      fetchStats();
      startAutoRefresh();
    }
  });

  fetchStats();
  startAutoRefresh();
})();
