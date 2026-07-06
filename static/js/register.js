
// TOGGLE PASSWORD
document.getElementById("togglePassword").addEventListener("click", function () {
    const pass = document.getElementById("password");

    pass.type = pass.type === "password" ? "text" : "password";
});

// TOGGLE CONFIRM PASSWORD
document.getElementById("toggleConfirmPassword").addEventListener("click", function () {
    const pass = document.getElementById("confirmPassword");

    pass.type = pass.type === "password" ? "text" : "password";
});


// FORM VALIDATION
document.getElementById("registerForm").addEventListener("submit", function (e) {
    e.preventDefault();

    const password = document.getElementById("password").value;
    const confirm = document.getElementById("confirmPassword").value;
    const errorBox = document.getElementById("errorBox");

    errorBox.style.display = "none";

    if (password !== confirm) {
        errorBox.style.display = "block";
        errorBox.innerText = "Passwords do not match!";
        return;
    }

    // kama sawa (hapa unaweza connect backend)
    this.submit();
});
