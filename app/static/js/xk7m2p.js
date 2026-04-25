document.addEventListener("DOMContentLoaded", function () {
    var tableBody = document.getElementById("sheet-body");
    var saveButton = document.getElementById("save-btn");
    var addRowButton = document.getElementById("add-row-btn");

    if (!tableBody || !saveButton || !addRowButton) {
        return;
    }

    var saveUrl = tableBody.dataset.saveUrl || "";
    var existingRows = [];

    try {
        existingRows = JSON.parse(tableBody.dataset.existingRows || "[]");
    } catch (error) {
        console.error("Failed to parse existing consignment rows.", error);
    }

    var statusOptions = [
        "Pickup Scheduled",
        "In Transit",
        "Out for Delivery",
        "Delivered"
    ];

    function showStatus(message, type) {
        var el = document.getElementById("status-msg");
        if (!el) {
            return;
        }
        el.innerHTML = message;
        el.className = "alert alert-" + type + " shadow-sm border-0";
        el.classList.remove("d-none");
        el.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    function escapeHtml(text) {
        return String(text == null ? "" : text)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    function buildStatusSelect(value) {
        var current = value || "";
        var opts = ["<option value=''>Select</option>"];

        statusOptions.forEach(function (status) {
            var selected = status === current ? "selected" : "";
            opts.push("<option value=\"" + escapeHtml(status) + "\" " + selected + ">" + escapeHtml(status) + "</option>");
        });

        return "<select class=\"form-select form-select-sm status\">" + opts.join("") + "</select>";
    }

    function normalizePincode(value, label, rowNumber) {
        var raw = (value || "").trim();
        if (!/^[1-9][0-9]{5}$/.test(raw)) {
            throw new Error("Row " + rowNumber + ": " + label + " must be a valid 6-digit pincode.");
        }
        return raw;
    }

    function addRow(row) {
        var source = row || {};
        var tr = document.createElement("tr");
        tr.dataset.id = source.id || "";

        tr.innerHTML =
            "<td><input class=\"form-control form-control-sm consignment_number\" maxlength=\"16\" value=\"" + escapeHtml(source.consignment_number || "") + "\" /></td>" +
            "<td>" + buildStatusSelect(source.status) + "</td>" +
            "<td><input class=\"form-control form-control-sm pickup_pincode\" maxlength=\"6\" value=\"" + escapeHtml(source.pickup_pincode || "") + "\" placeholder=\"110001\" /></td>" +
            "<td><input class=\"form-control form-control-sm drop_pincode\" maxlength=\"6\" value=\"" + escapeHtml(source.drop_pincode || "") + "\" placeholder=\"400001\" /></td>" +
            "<td class=\"text-center\"><button type=\"button\" class=\"btn btn-sm btn-outline-danger remove-row\">Delete</button></td>";

        var removeButton = tr.querySelector(".remove-row");
        if (removeButton) {
            removeButton.addEventListener("click", function () {
                tr.remove();
            });
        }

        tableBody.appendChild(tr);
    }

    function collectRows() {
        var rows = [];
        var tableRows = document.querySelectorAll("#sheet-body tr");
        var rowNumber = 0;

        tableRows.forEach(function (tr) {
            rowNumber += 1;
            var consignmentNumber = tr.querySelector(".consignment_number").value.trim();
            var status = tr.querySelector(".status").value.trim();
            var pickupPincode = tr.querySelector(".pickup_pincode").value.trim();
            var dropPincode = tr.querySelector(".drop_pincode").value.trim();

            if (!consignmentNumber && !status && !pickupPincode && !dropPincode) {
                return;
            }

            var normalizedPickupPincode = normalizePincode(pickupPincode, "Pickup pincode", rowNumber);
            var normalizedDropPincode = normalizePincode(dropPincode, "Drop pincode", rowNumber);

            rows.push({
                id: tr.dataset.id ? Number(tr.dataset.id) : null,
                consignment_number: consignmentNumber,
                status: status,
                pickup_pincode: normalizedPickupPincode,
                drop_pincode: normalizedDropPincode
            });
        });

        return rows;
    }

    async function saveSheet() {
        if (!saveUrl) {
            showStatus("Save endpoint is missing.", "danger");
            return;
        }

        var rawRows = [];
        try {
            rawRows = collectRows();
            if (!rawRows.length) {
                showStatus("Sheet is empty. Add at least one row.", "warning");
                return;
            }
        } catch (validationError) {
            showStatus(
                "<strong>Validation error.</strong> " + escapeHtml(validationError.message || "Please check the row values."),
                "danger"
            );
            return;
        }

        try {
            saveButton.disabled = true;
            var originalButtonText = saveButton.textContent;
            saveButton.textContent = "Saving...";
            showStatus('<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Saving rows to database...', "info");

            var response = await fetch(saveUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ rows: rawRows })
            });

            // Check for authentication errors (401)
            if (response.status === 401) {
                throw new Error("Your session has expired. Please refresh the page and log in again.");
            }

            var data;
            try {
                data = await response.json();
            } catch (parseError) {
                throw new Error("Invalid response from server. Please check your connection and try again.");
            }

            if (!response.ok || !data.success) {
                throw new Error(data.message || "Save failed.");
            }

            showStatus("<strong>Saved successfully.</strong> Your internal database has been updated.", "success");
            setTimeout(function () {
                window.location.reload();
            }, 1200);
        } catch (error) {
            showStatus("<strong>Save failed.</strong> " + escapeHtml(error.message || "Please check the row values and try again."), "danger");
        } finally {
            saveButton.disabled = false;
            saveButton.textContent = "Save All";
        }
    }

    addRowButton.addEventListener("click", function () {
        addRow();
    });
    saveButton.addEventListener("click", saveSheet);

    if (existingRows.length) {
        existingRows.forEach(addRow);
    } else {
        addRow();
    }
});
