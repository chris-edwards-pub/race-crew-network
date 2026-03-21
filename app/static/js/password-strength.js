/**
 * Password strength meter — attaches to #password input and renders
 * a colored bar + label inside #password-strength-meter.
 */
(function () {
    var input = document.getElementById("password");
    var meter = document.getElementById("password-strength-meter");
    if (!input || !meter) return;

    input.addEventListener("input", function () {
        var pw = input.value;
        if (!pw) {
            meter.innerHTML = "";
            return;
        }

        var checks = 0;
        if (pw.length >= 8) checks++;
        if (/[A-Z]/.test(pw)) checks++;
        if (/[a-z]/.test(pw)) checks++;
        if (/[0-9]/.test(pw)) checks++;

        var label, color;
        if (checks <= 1) {
            label = "Weak";
            color = "#dc3545";
        } else if (checks <= 2) {
            label = "Fair";
            color = "#fd7e14";
        } else if (checks === 3) {
            label = "Good";
            color = "#ffc107";
        } else {
            label = "Strong";
            color = "#198754";
        }

        var pct = (checks / 4) * 100;
        meter.innerHTML =
            '<div class="password-strength-bar">' +
            '<div class="password-strength-fill" style="width:' + pct + "%;background-color:" + color + ';"></div>' +
            "</div>" +
            '<small class="password-strength-label" style="color:' + color + ';">' + label + "</small>";
    });
})();
