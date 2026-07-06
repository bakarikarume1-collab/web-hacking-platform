document.getElementById("registerForm").addEventListener("submit", function (e) {
    e.preventDefault(); // Zuia form isijitume kawaida

    const password = document.getElementById("password").value;
    const confirm = document.getElementById("confirmPassword").value;
    
    // Validation ya msingi
    if (password !== confirm) {
        alert("Passwords do not match!");
        return;
    }

    // Tuma data kwenda kwenye server
    const formData = new FormData(this);

    fetch('/register', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json()) // Tunatarajia jibu la JSON
    .then(data => {
        if (data.status === 'success') {
            alert("Registration successful!");
            window.location.href = '/login'; // Hapa ndipo inakupeleka kwenye login
        } else {
            alert(data.message); // Hapa ndipo itaonyesha "Password must contain..."
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert("An error occurred. Please try again.");
    });
});
