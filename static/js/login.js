document.getElementById("togglePassword").addEventListener("click", function () {
    const input = document.getElementById("password");

    if (input.type === "password") {
        input.type = "text";
        this.textContent = "🙈";
    } else {
        input.type = "password";
        this.textContent = "👁️";
    }
});
