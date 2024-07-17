import { isInt, isFloat } from "./scripts_base.js";


function showPopup_old(){
    document.getElementById('overlay').style.display = 'block';
    document.getElementById('popup').style.display = 'block';
    
    // Initialize countdown
    let remainingTime = document.getElementById('countdown').textContent;
    
    // Update countdown every second
    let countdownTimer = setInterval(() => {
        remainingTime--;
        document.getElementById('timer').textContent = remainingTime;
    
        if (remainingTime <= 0) {
            closePopup(countdownTimer);
        }
    }, 1000);
}
function closePopup_old(countdownTimer) {
    document.getElementById('overlay').style.display = 'none';
    document.getElementById('popup').style.display = 'none';

    // Clear the countdown timer
    clearInterval(countdownTimer);
    countdownTimer = null;
}

document.addEventListener('DOMContentLoaded', () => {
    const parametersCollapsibles = document.querySelectorAll(".collapsible");
    parametersCollapsibles.forEach(collapsible => {
        collapsible.addEventListener('click', function() {
            this.classList.toggle('active');
            const content = this.nextElementSibling;
            if (content.style.display === "flex") {
                content.style.display = "none";
            } else {
                content.style.display = "flex";
            }
        });
    });

    const manualToggleSwitch = document.getElementById('manual-toggle-switch');
    const manualToggleLabel = document.getElementById('manual-toggle-label');
    const elevationTextBox = document.getElementById('elevation-text-box');

    manualToggleSwitch.addEventListener('change', function() {
        if (manualToggleSwitch.checked) {
            manualToggleLabel.textContent = 'Manual';
            elevationTextBox.style.display = 'inline-block'; // Show text box
        } else {
            manualToggleLabel.textContent = 'Auto';
            elevationTextBox.style.display = 'none'; // Hide text box
        }
    });

    const logToggleSwitch = document.getElementById('log-toggle-switch');
    const logToggleLabel = document.getElementById('log-toggle-label');

    logToggleSwitch.addEventListener('change', function() {
        if (logToggleSwitch.checked) {
            logToggleLabel.textContent = 'All';
        } else {
            logToggleLabel.textContent = 'Last';
        }
    });

    // confirmation pop-ups
    const elevationControlForm = document.getElementById("elevation-control");
    elevationControlForm.addEventListener('submit', function(event) {
        const confirmed = confirm('Submit data?');

        if(confirmed == true){
            this.submit();
        }
        else{
            event.preventDefault();
        }
    });
    

    const logRequestForm = document.getElementById("log-request");
    logRequestForm.addEventListener('submit', function(event) {
        const confirmed = confirm('Request the log(s)?');

        if(confirmed == true){
            this.submit();
        }
        else{
            event.preventDefault();
        }
    });

    const resetForm = document.getElementById("reset");
    resetForm.addEventListener('submit', function(event) {
        const confirmed = confirm('Reset the device?');

        if(confirmed == true){
            this.submit();
        }
        else{
            event.preventDefault();
        }
    });

    // input sanitization
    // accept empty or valid values
    // fields left empty will revert to default values
    elevationControlForm.addEventListener('change', function(event){
        let submitButton = document.getElementById("submit-elevation")
        if(manualToggleSwitch.checked){
            let num = elevationTextBox.value;
            if(isFloat(num))    submitButton.disabled = false;
            else    submitButton.disabled = true
        }
        else    submitButton.disabled = false;
    });
    
    //let wait_time = document.getElementById("timer").textContent;
    //if(wait_time > 0){
    //    showPopup();
    //}

    const popup = document.getElementById('popup');
    const overlay = document.getElementById('overlay')
    const timerDisplay = document.getElementById('timer');
    const countdownTime = document.getElementById('wait-time').value; // Timer duration in seconds
    const timerKey = 'popupTimer';
    overlay.style.height = document.getElementById('main-content').scrollHeight + 'px'; // Cover the entire main content, even when scrolling
    
    // Function to show the popup
    const showPopup = () => {
        overlay.style.display = 'block';
        popup.style.display = 'block';
    };
    
    // Function to hide the popup
    const hidePopup = () => {
        overlay.style.display = 'none';
        popup.style.display = 'none';
    };

    // Function to update the timer display
    const updateTimer = (seconds) => {
        timerDisplay.textContent = seconds;
    };

    // Initialize the timer
    let timerEndTime = localStorage.getItem(timerKey);
    if (!timerEndTime) {
        timerEndTime = Date.now() + countdownTime * 1000;
        localStorage.setItem(timerKey, timerEndTime);
    }

    // Update the popup every second
    const updatePopup = () => {
        const now = Date.now();
        const timeLeft = Math.max(0, Math.round((timerEndTime - now) / 1000));
        updateTimer(timeLeft);

        if (timeLeft > 0) {
            showPopup();
            setTimeout(updatePopup, 1000);
        } else {
            hidePopup();
            localStorage.removeItem(timerKey);
        }
    };

    // Start the popup update
    updatePopup();
});