document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById("login");
    loginForm.addEventListener('change', function(event){
        let password = document.getElementById("password").value;
        let submitButton = document.getElementById("submit-login-button");
        if(password != "") submitButton.disabled = false;
        else    submitButton.disabled = true;
    });
});