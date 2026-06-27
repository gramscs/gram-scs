(function () {
  'use strict';

  var DEFAULTS = {
    apiBase: '',
    lookupPath: '/api/track/{number}',
    podPath: '/api/track/{number}/pod',
    homeHref: '/',
    requestHeaders: { Accept: 'application/json' }
  };

  function initTrackWidget(root, options) {
    var config = Object.assign({}, DEFAULTS, window.TRACK_WIDGET_CONFIG || {}, options || {});
    config.apiBase = root.dataset.apiBase || config.apiBase;
    config.podPath = root.dataset.podRouteTemplate || config.podPath;

    var form = root.querySelector('[data-track-form]');
    var input = root.querySelector('[name="consignment_number"]');
    var alertBox = root.querySelector('[data-track-alert]');
    var result = root.querySelector('[data-track-result]');
    var home = root.querySelector('[data-track-home-link]');
    if (home && config.homeHref) home.href = config.homeHref;

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var number = (input.value || '').trim().toUpperCase();
      input.value = number;
      if (!/^[A-Z0-9]{1,16}$/.test(number)) {
        return showError(alertBox, 'Invalid consignment number format.');
      }
      setLoading(form, true);
      hideError(alertBox);
      fetchJson(buildUrl(config, config.lookupPath, number), config.requestHeaders)
        .then(function (payload) {
          var consignment = normalizeConsignment(payload);
          if (!consignment || !consignment.consignment_number) throw new Error('Consignment not found. Please check the number and try again.');
          result.innerHTML = renderConsignment(consignment, config);
          result.hidden = false;
          bindPodDownload(result, consignment, config, alertBox);
        })
        .catch(function (error) {
          result.hidden = true;
          result.innerHTML = '';
          showError(alertBox, error.message || 'Unable to load tracking data. Please try again later.');
        })
        .finally(function () { setLoading(form, false); });
    });
  }

  function fetchJson(url, headers) {
    return fetch(url, { headers: headers, credentials: 'same-origin' }).then(function (res) {
      return res.json().catch(function () { return null; }).then(function (body) {
        if (!res.ok) throw new Error((body && (body.message || body.error)) || 'Unable to load tracking data. Please try again later.');
        return body;
      });
    });
  }

  function normalizeConsignment(payload) {
    var data = payload && payload.success && payload.data ? payload.data : payload;
    if (!data) return null;
    return {
      consignment_number: data.consignment_number || data.consignmentNumber || data.awb || data.tracking_number || data.trackingNumber,
      status: data.status || 'Unknown',
      pickup_pincode: data.pickup_pincode || data.pickupPincode || data.origin_pincode,
      pickup_address: data.pickup_address || data.pickupAddress || data.origin_address,
      pickup_tag: data.pickup_tag || data.pickupTag || data.origin || 'Origin',
      pickup_date: data.pickup_date || data.pickupDate || data.shipped_at,
      drop_pincode: data.drop_pincode || data.dropPincode || data.destination_pincode,
      drop_address: data.drop_address || data.dropAddress || data.destination_address,
      drop_tag: data.drop_tag || data.dropTag || data.destination || 'Destination',
      drop_date: data.drop_date || data.dropDate || data.delivered_at,
      eta: data.eta || data.expected_delivery || data.expectedDelivery,
      pod_image: data.pod_image || data.podImage || data.pod_url || data.podUrl || data.has_pod || data.hasPod
    };
  }

  function deriveStatus(status) {
    var key = String(status || 'Unknown').toLowerCase();
    if (key.indexOf('deliver') !== -1) return { className: 'ok', steps: 4 };
    if (key.indexOf('out for') !== -1) return { className: 'warn', steps: 3 };
    if (key.indexOf('transit') !== -1) return { className: 'warn', steps: 2 };
    if (key.indexOf('pickup') !== -1 || key.indexOf('scheduled') !== -1) return { className: 'warn', steps: 1 };
    if (key.indexOf('delay') !== -1 || key.indexOf('hold') !== -1 || key.indexOf('issue') !== -1) return { className: 'bad', steps: 1 };
    return { className: 'warn', steps: 1 };
  }

  function renderConsignment(c, config) {
    var s = deriveStatus(c.status);
    var labels = ['Shipment Picked Up', 'In Transit', 'Out for Delivery', 'Delivered'];
    var steps = labels.map(function (label, i) {
      var n = i + 1, complete = s.steps >= n, current = s.steps === n;
      return '<div class="tracking-step ' + (complete ? 'is-complete ' : '') + (current ? 'is-current' : '') + '"><span class="tracking-dot">' + ((s.steps > n || (s.steps === 4 && n === 4)) ? '✓' : n) + '</span><span class="tracking-step-label">' + escapeHtml(label) + '</span>' + (current ? '<span class="tracking-step-note">Current status</span>' : '') + '</div>';
    }).join('');
    var pod = !!c.pod_image;
    return '<article class="shipment-panel"><div class="shipment-summary"><div><span class="shipment-label">Consignment No.</span><h2 class="shipment-number">' + escapeHtml(c.consignment_number) + '</h2></div><div class="shipment-status-block"><span class="shipment-status ' + s.className + '">' + escapeHtml(c.status || 'Unknown') + '</span>' + (c.eta ? '<span class="shipment-eta">Expected by ' + escapeHtml(c.eta) + '</span>' : '') + '</div></div><div class="journey-card"><div class="journey-heading"><div><span class="shipment-label">Package Journey</span><h3>Current delivery progress</h3></div><span class="journey-progress">Step ' + s.steps + ' of 4</span></div><div class="tracking-rail" style="--completed-steps: ' + s.steps + ';">' + steps + '</div></div><div class="shipment-details-grid"><section class="route-card pickup-card"><span class="route-icon">▣</span><div><span class="shipment-label">Pickup location</span><h3>' + escapeHtml(c.pickup_tag || 'Origin') + '</h3><p>' + escapeHtml(c.pickup_address || c.pickup_pincode || 'Not available') + '</p>' + (c.pickup_pincode && c.pickup_address ? '<small>PIN ' + escapeHtml(c.pickup_pincode) + '</small>' : '') + (c.pickup_date ? '<small>Pickup date: ' + escapeHtml(c.pickup_date) + '</small>' : '') + '</div></section><section class="route-card drop-card"><span class="route-icon">⌖</span><div><span class="shipment-label">Delivery location</span><h3>' + escapeHtml(c.drop_tag || 'Destination') + '</h3><p>' + escapeHtml(c.drop_address || c.drop_pincode || 'Not available') + '</p>' + (c.drop_pincode && c.drop_address ? '<small>PIN ' + escapeHtml(c.drop_pincode) + '</small>' : '') + (c.drop_date ? '<small>Drop date: ' + escapeHtml(c.drop_date) + '</small>' : '') + '</div></section></div><div class="shipment-footer-row"><div class="shipment-info-chip"><span>Last known update</span><strong>' + escapeHtml(c.drop_date || c.pickup_date || c.eta || 'Not available') + '</strong></div><div class="shipment-info-chip"><span>Proof of Delivery</span><strong>' + (pod ? 'Available' : 'Pending') + '</strong></div><button class="btn pod-btn ' + (pod ? '' : 'pod-btn-disabled') + '" type="button" data-pod-download ' + (pod ? '' : 'disabled') + '>' + (pod ? 'Download POD' : 'No POD available') + '</button></div></article>';
  }

  function bindPodDownload(result, c, config, alertBox) {
    var btn = result.querySelector('[data-pod-download]');
    if (!btn || !c.pod_image) return;
    btn.addEventListener('click', function () {
      var original = btn.textContent;
      btn.disabled = true; btn.textContent = 'Downloading...'; hideError(alertBox);
      fetch(buildUrl(config, config.podPath, c.consignment_number), { credentials: 'same-origin' }).then(function (res) {
        if (!res.ok) throw new Error('Failed to download POD');
        return res.blob().then(function (blob) { downloadBlob(blob, filenameFromHeaders(res) || c.consignment_number + '_pod'); });
      }).catch(function (error) { showError(alertBox, error.message); }).finally(function () { btn.disabled = false; btn.textContent = original; });
    });
  }

  function buildUrl(config, path, number) { return (config.apiBase || '') + path.replace('{number}', encodeURIComponent(number)); }
  function showError(el, msg) { el.textContent = msg; el.hidden = false; }
  function hideError(el) { el.textContent = ''; el.hidden = true; }
  function setLoading(form, loading) { Array.prototype.forEach.call(form.querySelectorAll('button,input'), function (el) { el.disabled = loading; }); }
  function escapeHtml(v) { return String(v == null ? '' : v).replace(/[&<>"']/g, function (ch) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]; }); }
  function filenameFromHeaders(res) { var cd = res.headers.get('content-disposition') || ''; var m = cd.match(/filename\*=UTF-8''([^;]+)/) || cd.match(/filename="?([^";]+)"?/); return m ? decodeURIComponent(m[1]) : null; }
  function downloadBlob(blob, filename) { var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = filename; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(a.href); }

  document.addEventListener('DOMContentLoaded', function () {
    Array.prototype.forEach.call(document.querySelectorAll('[data-track-widget]'), function (root) { initTrackWidget(root); });
  });
  window.initTrackWidget = initTrackWidget;
}());
