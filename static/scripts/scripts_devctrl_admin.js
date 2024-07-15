import { isInt, isFloat } from "./scripts_base.js";

document.addEventListener('DOMContentLoaded', () => {
    const parametersCollapsibles = document.getElementById("parameters").querySelectorAll(".collapsible");
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

    // disable form submitting when clicking dropdown
    const parameterDropdowns = document.querySelectorAll('.main-content-dropdown')
    parameterDropdowns.forEach(dropdown => {
        dropdown.addEventListener('click',
            function(event){
                event.preventDefault();
            }
        )
    });

    // confirmation pop-up
    const paramsSubmitButtons = document.getElementById("parameters").querySelectorAll(".submit-button");
    paramsSubmitButtons.forEach(submitButton => {
        submitButton.addEventListener('click', function(event){
                const confirmed = confirm('Set parameters?');

                if(confirmed == true)   this.closest('form').submit();
                else    event.preventDefault();
            }
        )
    })

    const submitDefaultsButton = document.getElementById('submit-defaults');
    submitDefaultsButton.addEventListener('click', function(event){
        const confirmed = confirm('Reset device parameters to default values?');

        if(confirmed == true)   this.closest('form').submit();
        else    event.preventDefault();
    });

    // input sanitization
    // accept empty or valid values
    // fields left empty will revert to default values
    const sirenAndInsolationForm = document.getElementById("parameter-control-siren-and-insolation");
    sirenAndInsolationForm.addEventListener('change', function(event){
        let time = document.getElementById("siren-on-time").value;
        let insolation = document.getElementById("insolation-percentage").value;
        let submitButton = document.getElementById("submit-siren-and-insolation")
        let disabled = false;
        if((isInt(time) && parseInt(time) >= 0 && parseInt(time) <= 255) || time=="");
        else disabled = true;
        if((isInt(insolation) && parseInt(insolation) >= 0 && parseInt(insolation) <= 100) || insolation=="");
        else disabled = true;
        submitButton.disabled = disabled;
    });

    const positionForm = document.getElementById("parameter-control-position");
    positionForm.addEventListener('change', function(event){
        let lat = document.getElementById("latitude").value;
        let lon = document.getElementById("longitude").value;
        let submitButton = document.getElementById("submit-position");
        let disabled = false;
        if((isFloat(lat) && parseFloat(lat) >= -90 && parseFloat(lat) <= 90) || lat == "");
        else disabled = true;
        if((isFloat(lon) && parseFloat(lon) >= -180 && parseFloat(lon) <= 180) || lon=="");
        else disabled = true;
        submitButton.disabled = disabled
    });

    const timeOffsetForm = document.getElementById("parameter-control-time-offset");
    timeOffsetForm.addEventListener('change', function(event){
        let offset = document.getElementById("time-offset").value;
        let submitButton = document.getElementById("submit-time");
        if((isInt(offset) && Math.abs(offset) <= 65535) || offset == "")  submitButton.disabled = false;
        else    submitButton.disabled = true;
    });

    const angleLimitsForm = document.getElementById("parameter-control-angle-limits");
    angleLimitsForm.addEventListener('change', function(event){
        let east = document.getElementById("limit-east").value;
        let west = document.getElementById("limit-west").value;
        let submitButton = document.getElementById("submit-angle-limits");
        let disabled = false;
        if(isInt(east) || east=="");
        else disabled = true;
        if(isInt(west) || west=="");
        else disabled = true;
        submitButton.disabled = disabled
    });

    const heightDifferenceForm = document.getElementById("parameter-control-height");
    heightDifferenceForm.addEventListener('change', function(event){
        let first = document.getElementById("height-first").value;
        let second = document.getElementById("height-second").value;
        let submitButton = document.getElementById("submit-height");
        let disabled = false;
        if(isFloat(first) || first=="");
        else disabled = true;
        if(isFloat(second) || second=="");
        else disabled = true;
        submitButton.disabled = disabled
    });

    const lengthDistanceForm = document.getElementById("parameter-control-length-distance");
    lengthDistanceForm.addEventListener('change', function(event){
        let len = document.getElementById("panel-length").value;
        let dist = document.getElementById("axis-distance").value;
        let submitButton = document.getElementById("submit-length-and-distance");
        let disabled = false;
        if(isFloat(len) || len=="");
        else    disabled = true;
        if(isFloat(dist) || dist=="");
        else    disabled = true;

        submitButton.disabled = disabled
    });

    const homeRpdForm = document.getElementById("parameter-control-home-rpd");
    homeRpdForm.addEventListener('change', function(event){
        let home = document.getElementById("home-position").value;
        let rpd = document.getElementById("motor-rpd").value;
        let submitButton = document.getElementById("submit-home-rpd");
        let disabled = false;
        if(isFloat(home) || home=="");
        else    disabled = true;

        if(isFloat(rpd) || rpd=="");
        else    disabled = true;
        submitButton.disabled = disabled
    });
});