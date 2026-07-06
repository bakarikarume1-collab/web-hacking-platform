document.getElementById("registerForm").addEventListener("submit", function (e) {
    e.preventDefault();

    const password = document.getElementById("password").value;
    const confirm = document.getElementById("confirmPassword").value;
    const errorBox = document.getElementById("errorBox"); // Hii ni ile div yako

    // Reset error box
    errorBox.style.display = "none";
    errorBox.innerText = "";

    if (password !== confirm) {
        errorBox.style.display = "block";
        errorBox.innerText = "Passwords do not match!";
        return;
    }

    const formData = new FormData(this);

    fetch('/register', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            window.location.href = '/login';
        } else {
            // Hapa ndipo ujumbe unapelekwa kwenye box
            errorBox.style.display = "block";
            errorBox.innerText = data.message; 
        }
    })
    .catch(error => {
        errorBox.style.display = "block";
        errorBox.innerText = "An error occurred. Please try again.";
    });
});
