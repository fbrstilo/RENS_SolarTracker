export function isFloat(val) {
    let floatRegex = /^-?\d+(?:[.]\d*?)?$/;
    if (!floatRegex.test(val))
        return false;

    val = parseFloat(val);
    if (isNaN(val))
        return false;
    return true;
}

export function isInt(val) {
    let intRegex = /^-?\d+$/;
    if (!intRegex.test(val))
        return false;

    let intVal = parseInt(val, 10);
    return parseFloat(val) == intVal && !isNaN(intVal);
}

document.addEventListener('DOMContentLoaded', () => {
    //sidebar stays expanded if device or log is selected
    if(window.location.pathname.startsWith('/device')){
        let devicesButton = document.getElementById('collapsible-devices');
        devicesButton.classList.add('active');
        devicesButton.nextElementSibling.style.display = 'block';
    }
    else if(window.location.pathname.startsWith('/logs')){
        let logsButton = document.getElementById('logs');
        logsButton.classList.add('active');
    }
    else if(window.location.pathname.startsWith('/admin')){
        let adminButton = document.getElementById('admin');
        adminButton.classList.add('active');
    }
    else if(window.location.pathname.startsWith('/alarms-errors')){
        let errorsButton = document.getElementById('collapsible-alarms');
        errorsButton.classList.add('active');
        errorsButton.nextElementSibling.style.display = 'block';
    }
    else{
        let homeButton = document.getElementById('home')
        homeButton.classList.add('active');
    }
    
    let params = new URLSearchParams(window.location.search)
    let selectedButtonID = params.get('id');
    if(selectedButtonID != null){
        let selectedButton = document.getElementById(selectedButtonID)
        if(selectedButton != null) selectedButton.classList.add('active')
    }

    const sidebarCollapsibles = document.querySelector(".sidebar").querySelectorAll('.collapsible');
    sidebarCollapsibles.forEach(collapsible => {
        collapsible.addEventListener('click', function() {
            this.classList.toggle('active');
            const content = this.nextElementSibling;
            if (content.style.display === "block") {
                content.style.display = "none";
            } else {
                content.style.display = "block";
            }
        });
    });

    const logoutButton = document.getElementById('logout-button');
    if(logoutButton != null){
        logoutButton.addEventListener('click', function(){
            document.cookie = 'admin_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;';
            // Redirect to the homepage
            window.location.href = '/';
        });
    };
});