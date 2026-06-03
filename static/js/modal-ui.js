/**
 * Shared modal shell helpers and detail-view markup utilities.
 */
(function (global) {
    function escapeHtml(str) {
        if (str == null || str === '') return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function formatDisplayDate(value) {
        if (!value) return 'N/A';
        const s = String(value);
        return s.length >= 10 ? s.slice(0, 10) : s;
    }

    function formatStatusLabel(status) {
        if (!status) return 'Active';
        const s = String(status);
        return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
    }

    function memberInitials(name) {
        if (!name) return '?';
        const parts = String(name).trim().split(/\s+/).filter(Boolean);
        if (parts.length >= 2) {
            return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
        }
        return parts[0] ? parts[0].slice(0, 2).toUpperCase() : '?';
    }

    function detailField(label, valueHtml) {
        return '<div class="detail-field-label">' + escapeHtml(label) + '</div>' +
            '<div class="detail-field-value">' + valueHtml + '</div>';
    }

    global.escapeHtml = escapeHtml;
    global.formatDisplayDate = formatDisplayDate;
    global.formatStatusLabel = formatStatusLabel;
    global.memberInitials = memberInitials;
    global.detailField = detailField;
    global.pdField = detailField;

    global.AppModal = {
        escapeHtml: escapeHtml,
        formatDisplayDate: formatDisplayDate,
        formatStatusLabel: formatStatusLabel,
        memberInitials: memberInitials,
        detailField: detailField
    };
})(typeof window !== 'undefined' ? window : this);
