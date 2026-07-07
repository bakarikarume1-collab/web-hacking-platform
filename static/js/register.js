document.addEventListener("DOMContentLoaded", function () {
    // 1. TOGGLE PASSWORD VISIBILITY
    const togglePassword = document.getElementById("togglePassword");
    const toggleConfirmPassword = document.getElementById("toggleConfirmPassword");
    
    if (togglePassword) {
        togglePassword.addEventListener("click", function () {
            const pass = document.getElementById("password");
            pass.type = pass.type === "password" ? "text" : "password";
        });
    }

    if (toggleConfirmPassword) {
        toggleConfirmPassword.addEventListener("click", function () {
            const pass = document.getElementById("confirmPassword");
            pass.type = pass.type === "password" ? "text" : "password";
        });
    }

    // 2. FORM SUBMISSION NA VALIDATION
    const registerForm = document.getElementById("registerForm");
    if (registerForm) {
        registerForm.addEventListener("submit", function (e) {
            e.preventDefault(); // Zuia form isijitume kawaida

            const password = document.getElementById("password").value;
            const confirm = document.getElementById("confirmPassword").value;
            const errorBox = document.getElementById("errorBox");

            // Reset error box
            errorBox.style.display = "none";
            errorBox.innerText = "";

            // Validation: Password match
            if (password !== confirm) {
                errorBox.style.display = "block";
                errorBox.innerText = "Passwords do not match!";
                return;
            }

            // Tuma data kwa backend
            const formData = new FormData(this);

            fetch('/register', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Imefaulu: Nenda kwenye ukurasa wa login
                    window.location.href = '/login';
                } else {
                    // Imetokea kosa (mfano: password haina herufi kubwa)
                    errorBox.style.display = "block";
                    errorBox.innerText = data.message;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                errorBox.style.display = "block";
                errorBox.innerText = "An unexpected error occurred. Please try again.";
            });
        });
    }
});
