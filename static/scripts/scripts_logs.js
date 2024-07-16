function highlightWordsAndTimestamps() {
    const pElement = document.getElementById('text');
    let htmlContent = pElement.innerHTML;

    // Highlight timestamps of format YYYY-MM-DD hh:mm:ss
    const timestampRegex = /\b\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)?\b/g;
    htmlContent = htmlContent.replace(timestampRegex, match => {
        return `<span class="highlight-green">${match}</span>`;
    });

    // Highlight words ending with ':'
    const wordsWithColonRegex = /[A-Za-z]+: /gi;
    htmlContent = htmlContent.replace(wordsWithColonRegex, match => {
        return `<span class="highlight-yellow">${match}</span>`;
    });

    pElement.innerHTML = htmlContent;
}

highlightWordsAndTimestamps();
