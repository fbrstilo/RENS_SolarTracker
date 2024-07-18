import { isInt, isFloat } from "./scripts_base.js";

document.addEventListener('DOMContentLoaded', () => {

    // Input sanitization
    // Allow empty fields or sensible values
    // Invalid values disable the 'submit' buttons
    const messageDeltaTimeForm = document.getElementById("message-delta-time");
    messageDeltaTimeForm.addEventListener('change', function(event){
        let time = document.getElementById("delta-time").value;
        let submitButton = document.getElementById("submit-delta-time");

        if(isInt(time) && parseInt(time) > 0) submitButton.disabled = false;
        else    submitButton.disabled = true;
    });

    const mqttForm = document.getElementById("mqtt");
    mqttForm.addEventListener('change', function(event){
        let app_id = document.getElementById("mqtt-app-id").value;
        let address = document.getElementById("mqtt-broker-address").value;
        let submitButton = document.getElementById("submit-mqtt");

        if(app_id != "" || address != "") submitButton.disabled = false;
        else    submitButton.disabled = true;
    });

    const chirpstackApiForm = document.getElementById("chirpstack-api");
    chirpstackApiForm.addEventListener('change', function(event){
        let key = document.getElementById("chirpstack-api-key").value;
        let address = document.getElementById("chirpstack-server-address").value;
        let submitButton = document.getElementById("submit-chirpstack-api");

        if(key != "" || address != "") submitButton.disabled = false;
        else    submitButton.disabled = true;
    });

    const passwordChangeForm = document.getElementById('change-password');
    passwordChangeForm.addEventListener('change', function(event){
        let newPass = document.getElementById('password').value;
        let newPassConfirm = document.getElementById('password-confirm').value;
        let submitButton = document.getElementById("submit-newpass");

        if(newPass != "" && newPass == newPassConfirm) submitButton.disabled = false;
        else    submitButton.disabled = true;
    });

    const defaultsForm = document.getElementById('defaults');
    defaultsForm.addEventListener('change', function(event){
        let submitButton = document.getElementById('submit-defaults');
        let disabled = false;

        let sirenOnTime = document.getElementById('siren-on-time').value;
        if(!((isInt(sirenOnTime) && 0 <= parseInt(sirenOnTime) <= 255) || sirenOnTime == "")){
            disabled = true;
        }
        let insolation = document.getElementById('insolation').value;
        if(!((isInt(insolation) && parseInt(insolation) >= 0 && parseInt(insolation) <= 100) || insolation=="")){
            disabled = true;
        }
        let latitude = document.getElementById('latitude').value;
        if(!((isFloat(latitude) && parseFloat(latitude) >= -90 && parseFloat(latitude) <= 90) || latitude == "")){
            disabled = true;
        }
        let longitude = document.getElementById('longitude').value;
        if(!((isFloat(longitude) && parseFloat(longitude) >= -180 && parseFloat(longitude) <= 180) || longitude=="")){
            disabled = true;
        }
        let timeOffset = document.getElementById('time-offset').value;
        if(!((isInt(timeOffset) && Math.abs(timeOffset) <= 65535) || timeOffset == "")){
            disabled = true;
        }
        let east = document.getElementById('limit-east').value;
        if(!(isInt(east) || east=="")){
            disabled = true;
        }
        let west = document.getElementById("limit-west").value;
        if(!(isInt(west) || west=="")){
            disabled = true;
        }
        let first = document.getElementById("height-first").value;
        if(!(isFloat(first) || first=="")){
            disabled = true;
        }
        let second = document.getElementById("height-second").value;
        if(!(isFloat(second) || second=="")){
            disabled = true;
        }
        let len = document.getElementById("panel-length").value;
        if(!(isFloat(len) || len=="")){
            disabled = true;
        }
        let dist = document.getElementById("axis-distance").value;
        if(!(isFloat(dist) || dist=="")){
            disabled = true;
        }
        let home = document.getElementById("home-position").value;
        if(!(isFloat(home) || home=="")){
            disabled = true;
        }
        let rpd = document.getElementById("motor-rpd").value;
        if(!(isFloat(rpd) || rpd=="")){
            disabled = true;
        }
        submitButton.disabled = disabled;
    });
});