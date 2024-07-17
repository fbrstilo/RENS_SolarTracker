document.addEventListener('DOMContentLoaded', () => {
    const pElement = document.getElementById('text');
    let htmlContent = pElement.innerHTML;

    // Highlight timestamps of format YYYY-MM-DD hh:mm:ss.ms (milliseconds optional)
    const timestampRegex = /\b\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)?\b/g;
    htmlContent = htmlContent.replace(timestampRegex, match => {
        return `<span class="highlight-green">${match}</span>`;
    });

    // Highlight words ending with ':' and surrounded by spaces
    const wordsWithColonRegex = / [^\d\s]+: /gi;
    htmlContent = htmlContent.replace(wordsWithColonRegex, match => {
        return `<span class="highlight-yellow">${match}</span>`;
    });

    // Highlight ALL CAPS words
    const allCapsWordsRegex = / [A-Z]+ /g;
    htmlContent = htmlContent.replace(allCapsWordsRegex, match => {
        return `<span class="highlight-blue">${match}</span>`;
    });

    pElement.innerHTML = htmlContent;

    const deleteLogForm = document.getElementById("delete-log-form");
    deleteLogForm.addEventListener('submit', function(event) {
        const confirmed = confirm('Delete log?');

        if(confirmed == true){
            this.submit();
        }
        else{
            event.preventDefault();
        }
    });
});
