document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById("login");
    loginForm.addEventListener('change', function(event){
        let password = document.getElementById("password").value;
        let submitButton = document.getElementById("submit-login-button");
        if(password != "") submitButton.disabled = false;
        else    submitButton.disabled = true;
    });

    loginForm.addEventListener('submit', function(event) {
        event.preventDefault(); // Prevent form submission to handle the password hashing first
        let passwordField = document.getElementById("password");
        let pass_hash = document.getElementById('pass-hash');
    
        window.crypto.subtle.digest("SHA-256", new TextEncoder().encode(passwordField.value)).then(function(hash) {
            // Convert the ArrayBuffer to a hex string
            let hashArray = Array.from(new Uint8Array(hash));
            let hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
            
            pass_hash.value = hashHex;
    
            // Now submit the form programmatically
            loginForm.submit();
        }).catch(function(error) {
            console.error('Hashing failed:', error);
        });
    });
});