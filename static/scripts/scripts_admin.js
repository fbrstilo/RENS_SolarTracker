import { isInt, isFloat } from "./scripts_base.js";

const upload_box = document.querySelector('.upload-box');
const fileInput = document.getElementById('file-input');
const fileSelectButton = document.getElementById('file-select-button');
const fileListElement = document.getElementById('file-list');
const uploadButton = document.getElementById('upload-button');
let files = [];

upload_box.addEventListener('dragover', (e) => {
    e.preventDefault();
    upload_box.classList.add('dragover');
});

upload_box.addEventListener('dragleave', () => {
    upload_box.classList.remove('dragover');
});

upload_box.addEventListener('drop', (e) => {
    e.preventDefault();
    upload_box.classList.remove('dragover');

    for (let file of e.dataTransfer.files) {
        files.push(file);
    }

    updateFileList();
});

fileSelectButton.addEventListener('click', () => {
    fileInput.click();
});

fileInput.addEventListener('change', () => {
    for (let file of fileInput.files) {
        files.push(file);
    }
    updateFileList();
});

function updateFileList() {
    fileListElement.innerHTML = '';

    files.forEach((file, index) => {
        const li = document.createElement('li');
        const span = document.createElement('span');
        span.textContent = file.name;

        const removeButton = document.createElement('button');
        removeButton.textContent = 'X';
        removeButton.addEventListener('click', () => {
            files.splice(index, 1);
            updateFileList();
        });

        li.appendChild(span);
        li.appendChild(removeButton);
        fileListElement.appendChild(li);
    });

    if (files.length === 0) {
        uploadButton.style.display = 'none';
    } else {
        uploadButton.style.display = 'block';
    }
}

uploadButton.addEventListener('click', () => {
    if (files.length === 0) {
        alert("No files to upload.");
        return;
    }

    const formData = new FormData();
    for (let file of files) {
        formData.append('file', file);
    }

    fetch('/upload', {
        method: 'POST',
        body: formData,
    })
    .then(response => {
        // Check if the response is successful
        if (!response.ok) {
            // Handle errors based on the response status
            return response.json().then(errorData => {
                throw new Error(errorData.error || 'Unknown error');
            });
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            // Alert success message and list of uploaded files
            alert(`Success! Uploaded files:\n${data.files.join('\n')}`);
            // Clear the file list and array after upload
            files = [];
            updateFileList();
        }
    })
    .catch(error => {
        // Alert error message
        alert(`Error: ${error.message}`);
    });
});

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